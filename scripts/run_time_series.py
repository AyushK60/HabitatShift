"""Multi-date index time series for one study area (free Sentinel-2 L2A via the public STAC).

For every calendar month in the window, search the catalogue, measure the in-AOI valid fraction
of the few best candidates, keep the best usable scene, read it onto the study's own analysis grid
with the audited engine reader, and record the mean of each index over that scene's valid pixels.
Months with no usable scene (typically monsoon cloud) are recorded as gaps, never filled.

On top of the monthly series a simple, transparent model is fitted to the first index:

    y(t) = a + b * t + c * sin(2 pi t) + d * cos(2 pi t)        (t in years)

so the annual cycle is separated from a linear drift. The trend b gets a residual-bootstrap 95 %
interval. This answers a question the two-date comparison cannot: is the 2020 -> 2025 difference
larger than the normal seasonal swing and the scatter between months?

Limits stated in the output: irregular sampling (cloud gaps cluster in the monsoon), residuals are
not independent, a linear trend is a convenience not a physical claim, and the mean over an AOI
hides all spatial detail.

Usage: python scripts/run_time_series.py --experiment kathmandu_m4 [--start 2020-01 --end 2026-10]
Result: data/experiments/m6_timeseries/<experiment>/result.json  (+ frontend bundle)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.indices.spectral import compute_index  # noqa: E402
from backend.app.pipeline import engine as engine_mod  # noqa: E402
from backend.app.pipeline.config import load_study_config  # noqa: E402
from backend.app.catalog.stac_client import SearchRequest  # noqa: E402
from backend.app.preprocess.scoring import score_candidates  # noqa: E402
from backend.app import config  # noqa: E402

LOGGER = logging.getLogger("run_time_series")
STUDY_OF = {
    "coringa_m1": "coringa_coastal", "chilika_m4_dry": "chilika_wetland",
    "chilika_m4_postmonsoon": "chilika_wetland", "western_ghats_m4": "western_ghats_forest",
    "himalaya_purepu_2025_m4": "himalaya_purepu_2025", "himalaya_langtang_2026_m4": "himalaya_langtang_2026",
    "kathmandu_m4": "kathmandu_urban",
}


MANIFEST_OF = {
    "kathmandu_m4": "m4_kathmandu_m4.json",
    "western_ghats_m4": "m4_western_ghats_m4.json",
    "coringa_m1": "m1_coringa_coastal.json",
    "chilika_m4_dry": "m4_chilika_m4_dry.json",
    "chilika_m4_postmonsoon": "m4_chilika_m4_postmonsoon.json",
    "himalaya_purepu_2025_m4": "m4_himalaya_purepu_2025_m4.json",
    "himalaya_langtang_2026_m4": "m4_himalaya_langtang_2026_m4.json",
}


def comparison_anchors(experiment: str) -> list[str]:
    """Anchor dates of the recorded two-date comparison, so the chart can mark them."""
    manifest = json.loads((ROOT / "data" / "manifests" / MANIFEST_OF[experiment]).read_text(encoding="utf-8"))
    return [p["anchor_date"] for p in manifest["periods"]]


def months(start: str, end: str):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        first = dt.date(y, m, 1)
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        yield first, dt.date(ny, nm, 1) - dt.timedelta(days=1)
        y, m = ny, nm


def harmonic_fit(t_years: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> dict:
    X = np.column_stack([np.ones_like(t_years), t_years, np.sin(2 * np.pi * t_years), np.cos(2 * np.pi * t_years)])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ coef
    resid = y - fitted
    dof = max(len(y) - X.shape[1], 1)
    resid_sd = float(np.sqrt((resid**2).sum() / dof))
    boots = []
    for _ in range(2000):
        yb = fitted + rng.choice(resid, size=len(resid), replace=True)
        cb, *_ = np.linalg.lstsq(X, yb, rcond=None)
        boots.append(cb[1])
    amp = float(np.hypot(coef[2], coef[3]))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return {
        "trend_per_year": round(float(coef[1]), 5),
        "trend_ci95": [round(float(np.percentile(boots, 2.5)), 5), round(float(np.percentile(boots, 97.5)), 5)],
        "seasonal_amplitude": round(amp, 4),
        "residual_sd": round(resid_sd, 4),
        "r_squared": round(1 - float((resid**2).sum()) / ss_tot, 3) if ss_tot else None,
        "n_months": int(len(y)),
        "fitted": [round(float(v), 4) for v in fitted],
        "residuals": [round(float(v), 4) for v in resid],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", default="kathmandu_m4")
    ap.add_argument("--start", default="2020-01")
    ap.add_argument("--end", default="2026-10")
    ap.add_argument("--per-month-budget", type=int, default=4)
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    cfg = load_study_config(ROOT / "studies" / "experiments" / f"{args.experiment}.yaml")
    eng = engine_mod.M1Engine(cfg)
    index_keys = list(cfg.indices)
    points, gaps = [], []
    for first, last in months(args.start, args.end):
        label = first.strftime("%Y-%m")
        request = SearchRequest(
            aoi=eng.aoi,
            start=dt.datetime.combine(first, dt.time.min, tzinfo=dt.timezone.utc),
            end=dt.datetime.combine(last, dt.time.max, tzinfo=dt.timezone.utc),
            max_cloud_cover=cfg.max_cloud_cover,
            limit=100,
            label=f"series:{label}",
        )
        try:
            result = eng.client.search(request)
            scores = score_candidates(
                result.items, eng.aoi, min_valid_fraction=cfg.min_scene_valid_fraction,
                max_measured=args.per_month_budget, cache_dir=config.SCL_MEASUREMENT_CACHE_DIR,
            )
        except Exception as exc:
            gaps.append({"month": label, "reason": f"search failed: {type(exc).__name__}"})
            print(label, "search failed", exc)
            continue
        usable = [s for s in scores if s.usable]
        if not usable:
            gaps.append({"month": label, "reason": "no scene with enough valid in-AOI pixels"})
            print(label, "gap")
            continue
        best = max(usable, key=lambda s: (s.aoi_valid_fraction or 0.0, s.item_id))
        cand = next(c for c in result.items if c.item_id == best.item_id)
        try:
            obs = engine_mod.read_observation(
                cand, eng.window, eng.aoi_mask, eng.band_keys, period_id="series", cache=eng.observation_cache
            )
        except Exception as exc:
            gaps.append({"month": label, "reason": f"read failed: {type(exc).__name__}"})
            print(label, "read failed", exc)
            continue
        valid = obs.valid & eng.aoi_mask
        means = {}
        for key in index_keys:
            arr = compute_index(key, obs.reflectance)
            ok = valid & np.isfinite(arr)
            if ok.any():
                means[key] = round(float(arr[ok].mean()), 4)
        points.append({
            "month": label, "date": cand.date_str, "item_id": cand.item_id,
            "valid_fraction": round(float(best.aoi_valid_fraction or 0), 3),
            "valid_pixels": int(valid.sum()), "mean": means,
        })
        print(label, cand.date_str, means)

    primary = index_keys[0] if "ndvi" not in index_keys else "ndvi"
    fit = None
    if len([p for p in points if primary in p["mean"]]) >= 12:
        pts = [p for p in points if primary in p["mean"]]
        t = np.array([(dt.date.fromisoformat(p["date"]) - dt.date(2020, 1, 1)).days / 365.25 for p in pts])
        y = np.array([p["mean"][primary] for p in pts])
        fit = harmonic_fit(t, y, np.random.default_rng(20260101))
        fit["index"] = primary
        fit["dates"] = [p["date"] for p in pts]

    result = {
        "schema": "habitatshift-m6-timeseries/1",
        "experiment": args.experiment,
        "study_id": STUDY_OF[args.experiment],
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "window": {"start": args.start, "end": args.end},
        "selection": "best usable scene per calendar month (highest in-AOI valid fraction among the "
        f"{args.per_month_budget} best pre-ranked candidates); gaps are recorded, never filled",
        "indices": index_keys,
        "comparison_anchors": comparison_anchors(args.experiment),
        "points": points,
        "gaps": gaps,
        "model": fit,
        "limits": [
            "Cloud gaps cluster in the monsoon, so the monsoon months are sparsely observed.",
            "Residuals are not independent and sampling is irregular; the trend interval is indicative.",
            "A linear trend is a descriptive convenience, not a physical claim.",
            "An AOI mean hides all spatial structure; use the change maps for where.",
        ],
    }
    out = ROOT / "data" / "experiments" / "m6_timeseries" / args.experiment
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    pub = ROOT / "frontend" / "public" / "studies" / "m6_timeseries"
    pub.mkdir(parents=True, exist_ok=True)
    (pub / f"{args.experiment}.json").write_text(json.dumps(result), encoding="utf-8")
    print("DONE", len(points), "months,", len(gaps), "gaps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
