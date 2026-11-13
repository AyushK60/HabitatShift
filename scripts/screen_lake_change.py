"""Label-only screen: which Nepal lakes changed water state between two periods, judged from Sentinel-1 alone.

No optical scene and no foundation-model score is read here. For each lake in studies/lakes.yaml the Sentinel-1
scenes within +/-20 days of each window give a water frequency map; the patch counts use the same rule as
scripts/run_fm_lake_evaluation.py (16 x 16 pixel patches, within 6 patches of the lake seed, positive = water
frequency changed by at least 0.25, clean = under 0.05). Unlike the evaluation, per-lake usable radar orbits are not
known for most lakes, so a scene is kept when the lake looks dark in it (contrast <= -4 dB); the evaluation must
recompute the reference properly for any lake it selects.

    python scripts/screen_lake_change.py [--earlier 2018-10-01 2018-11-30] [--later 2024-10-01 2024-11-30] [lake ids]
Resumable: one JSON per lake in data/experiments/v3_fm/lake_screen/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy import ndimage

os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.foundation import compare as C  # noqa: E402
from backend.app.radar import lakes as L  # noqa: E402
from backend.app.radar.planetary import S1_COLLECTION, PlanetaryClient  # noqa: E402

MARGIN_DAYS, DOMAIN_PATCHES, POSITIVE, NEGATIVE = 20, 6, 0.25, 0.05


def patch_mean(a: np.ndarray) -> np.ndarray:
    valid = np.isfinite(a)
    return C.patch_mean(np.where(valid, a, 0.0)[None].astype("float32"), valid)[0][..., 0]


def period_frequency(client, lake, prep, window) -> tuple[np.ndarray, dict]:
    start = dt.date.fromisoformat(window[0]) - dt.timedelta(days=MARGIN_DAYS)
    end = dt.date.fromisoformat(window[1]) + dt.timedelta(days=MARGIN_DAYS)
    items = client.search(S1_COLLECTION, lake.bbox, start, end)
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda it: L.scene_water_mask(client, it, prep), items))
    masks, valids, areas = [], [], []
    for mask, record in results:
        if mask is None or record["contrast_db"] > L.DARK_CONTRAST_DB:
            continue
        masks.append(mask)
        valids.append(record["_valid"])
        areas.append(record["area_km2"])
    if not masks:
        return np.full(prep["seed"].shape, np.nan, dtype="float32"), {"found": len(items), "used": 0, "area_km2": None}
    wet, seen = np.sum(masks, axis=0).astype("float32"), np.sum(valids, axis=0).astype("float32")
    freq = np.where(seen > 0, wet / np.maximum(seen, 1), np.nan).astype("float32")
    return freq, {"found": len(items), "used": len(masks), "area_km2": round(float(np.median(areas)), 3)}


def screen(client, lake, earlier, later) -> dict:
    prep = L.prepare_lake(client, lake)
    f0, s0 = period_frequency(client, lake, prep, earlier)
    f1, s1 = period_frequency(client, lake, prep, later)
    out = {"lake": lake.id, "earlier": s0, "later": s1}
    if s0["used"] == 0 or s1["used"] == 0:
        out["status"] = "no usable radar scenes in one period"
        return out
    delta = np.abs(patch_mean(f1) - patch_mean(f0))
    both = patch_mean(np.where(np.isfinite(f0) & np.isfinite(f1), 1.0, np.nan))
    near = ndimage.binary_dilation(patch_mean(prep["seed"].astype("float32")) > 0, iterations=DOMAIN_PATCHES)
    eligible = near & np.isfinite(delta) & (both > 0.9)
    out.update(status="ok", domain_patches=int(eligible.sum()), positives=int((eligible & (delta >= POSITIVE)).sum()),
               negatives=int((eligible & (delta < NEGATIVE)).sum()),
               area_change_km2=round(s1["area_km2"] - s0["area_km2"], 3))
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("lakes", nargs="*")
    p.add_argument("--earlier", nargs=2, default=["2018-10-01", "2018-11-30"])
    p.add_argument("--later", nargs=2, default=["2024-10-01", "2024-11-30"])
    p.add_argument("--folder", default="lake_screen", help="output folder name under data/experiments/v3_fm/")
    args = p.parse_args()
    all_lakes = L.load_lakes()
    ids = args.lakes or list(all_lakes)
    folder = config.DATA_DIR / "experiments" / "v3_fm" / args.folder
    folder.mkdir(parents=True, exist_ok=True)
    client = PlanetaryClient()
    for lake_id in ids:
        target = folder / f"{lake_id}.json"
        if target.exists():
            print(lake_id, "cached", flush=True)
            continue
        try:
            result = screen(client, all_lakes[lake_id], args.earlier, args.later)
        except Exception as exc:  # keep going; the failure is recorded, not hidden
            result = {"lake": lake_id, "status": f"error: {type(exc).__name__}: {exc}"}
        result["windows"] = {"earlier": args.earlier, "later": args.later}
        target.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k not in ("windows",)}), flush=True)


if __name__ == "__main__":
    main()
