"""Noise-aware change test: is a pixel's change larger than scene-to-scene noise?

The recorded change maps use a fixed |delta| >= 0.15 rule. That number is a convention. Each
period, however, is built from several scenes, which gives a direct, per-pixel estimate of how
much an index fluctuates between acquisitions of (nearly) the same date. This script asks, for
every pixel:  |delta| > k * SE ?   with  SE = sqrt(s_e^2/n_e + s_l^2/n_l)  (standard error of the
difference of the two period means), s = per-pixel standard deviation across that period's scenes,
floored at SIGMA_FLOOR so near-identical scenes cannot make any tiny difference look significant.

Read-only over the frozen outputs: the recorded delta rasters and the cached per-scene
observations (corrected radiometry entries only; the engine's own index functions).
Result: data/experiments/m6_noise/<experiment>/result.json

What it does NOT do: it does not prove a change is real or caused by anything. Scene-to-scene
spread only measures acquisition noise; it ignores seasonal, tidal and phenological differences
between the two periods, and with 3 scenes the standard deviations are themselves uncertain.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.indices.spectral import compute_index  # noqa: E402

CACHE = ROOT / "data" / "cache" / "observations"
OUT = ROOT / "data" / "experiments" / "m6_noise"
SIGMA_FLOOR = 0.02
KS = (2.0, 3.0)
EXPERIMENTS = {
    "coringa_m1": "m1_coringa_coastal.json",
    "chilika_m4_dry": "m4_chilika_m4_dry.json",
    "chilika_m4_postmonsoon": "m4_chilika_m4_postmonsoon.json",
    "western_ghats_m4": "m4_western_ghats_m4.json",
    "himalaya_purepu_2025_m4": "m4_himalaya_purepu_2025_m4.json",
    "himalaya_langtang_2026_m4": "m4_himalaya_langtang_2026_m4.json",
    "kathmandu_m4": "m4_kathmandu_m4.json",
}


def scene_bands(metas: dict, item_id: str, signature: str):
    entries = metas.get((item_id, signature), [])
    if not entries:
        return None
    corrected = [p for p, m in entries if "radiometry_evidence" in m]
    paths = corrected or [p for p, _ in entries]
    bands: dict[str, np.ndarray] = {}
    valid = None
    for path in paths:
        z = np.load(path.with_suffix(".npz"))
        v = z["valid"].astype(bool)
        valid = v if valid is None else (valid | v)
        for key in z.files:
            if key.startswith("reflectance_"):
                bands.setdefault(key.replace("reflectance_", ""), z[key].astype("float32"))
    return bands, valid


def period_stack(index: str, period: dict, metas: dict, signature: str) -> np.ndarray:
    layers = []
    for item_id in period["item_ids"]:
        got = scene_bands(metas, item_id, signature)
        if got is None:
            continue
        bands, valid = got
        try:
            arr = compute_index(index, bands)
        except Exception:  # band set lacks what this index needs
            continue
        layers.append(np.where(valid, arr, np.nan))
    return np.stack(layers) if layers else np.empty((0,))


def mean_var(stack: np.ndarray):
    n = np.isfinite(stack).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean = np.nanmean(stack, axis=0)
            var = np.nanvar(stack, axis=0, ddof=1)
    return n, mean, var


def main() -> int:
    metas: dict = {}
    for p in CACHE.glob("*.json"):
        m = json.loads(p.read_text(encoding="utf-8"))
        metas.setdefault((m["item_id"], m["grid_signature"]), []).append((p, m))

    for exp, manifest_name in EXPERIMENTS.items():
        manifest = json.loads((ROOT / "data" / "manifests" / manifest_name).read_text(encoding="utf-8"))
        signature = manifest["grid"]["signature"]
        earlier, later = manifest["periods"][0], manifest["periods"][1]
        per_index = {}
        for index, block in manifest["change"].items():
            with rasterio.open(ROOT / block["delta_tif"]) as src:
                delta = src.read(1).astype("float32")
            valid_common = np.isfinite(delta)
            thr = float(block["primary_threshold"])
            fixed_dec = valid_common & (delta <= -thr)
            fixed_inc = valid_common & (delta >= thr)
            recorded = block["primary"]
            cross_ok = (
                int(fixed_dec.sum()) == recorded["decrease_pixels"]
                and int(fixed_inc.sum()) == recorded["increase_pixels"]
            )

            st_e = period_stack(index, earlier, metas, signature)
            st_l = period_stack(index, later, metas, signature)
            if st_e.size == 0 or st_l.size == 0 or st_e.shape[0] < 2 or st_l.shape[0] < 2:
                per_index[index] = {"status": "not_computable", "reason": "fewer than 2 scenes in a period"}
                continue
            n_e, _, var_e = mean_var(st_e)
            n_l, _, var_l = mean_var(st_l)
            testable = valid_common & (n_e >= 2) & (n_l >= 2) & np.isfinite(var_e) & np.isfinite(var_l)
            sigma_e = np.maximum(np.sqrt(np.where(testable, var_e, 0.0)), SIGMA_FLOOR)
            sigma_l = np.maximum(np.sqrt(np.where(testable, var_l, 0.0)), SIGMA_FLOOR)
            se = np.sqrt(sigma_e**2 / np.maximum(n_e, 1) + sigma_l**2 / np.maximum(n_l, 1))
            n_testable = int(testable.sum())
            row = {
                "status": "ok",
                "primary_threshold": thr,
                "scenes_earlier": int(st_e.shape[0]),
                "scenes_later": int(st_l.shape[0]),
                "common_valid_pixels": int(valid_common.sum()),
                "testable_pixels": n_testable,
                "testable_fraction": round(n_testable / max(int(valid_common.sum()), 1), 4),
                "fixed_threshold_cross_check_matches_manifest": bool(cross_ok),
                "median_standard_error": round(float(np.median(se[testable])), 4),
                "fixed_rule": {
                    "decrease_pixels": int(fixed_dec.sum()),
                    "increase_pixels": int(fixed_inc.sum()),
                },
                "by_k": {},
            }
            fixed_any = fixed_dec | fixed_inc
            for k in KS:
                sig = testable & (np.abs(delta) > k * se)
                fixed_t = fixed_any & testable
                both = fixed_t & sig
                row["by_k"][str(k)] = {
                    "noise_significant_pixels": int(sig.sum()),
                    "noise_significant_percent_of_testable": round(100 * sig.sum() / max(n_testable, 1), 3),
                    "fixed_rule_pixels_testable": int(fixed_t.sum()),
                    "fixed_rule_pixels_also_noise_significant": int(both.sum()),
                    "fixed_rule_share_noise_supported": (
                        round(float(both.sum() / fixed_t.sum()), 4) if fixed_t.sum() else None
                    ),
                    "noise_significant_but_below_fixed_threshold": int((sig & ~fixed_any).sum()),
                }
            per_index[index] = row

        result = {
            "schema": "habitatshift-m6-noise-aware-threshold/1",
            "experiment": exp,
            "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "method": "pixel is noise-supported when |delta| > k*SE; SE = sqrt(s_e^2/n_e + s_l^2/n_l), s floored at "
            f"{SIGMA_FLOOR}; s = per-pixel std across the period's scenes (ddof=1)",
            "sigma_floor": SIGMA_FLOOR,
            "k_values": list(KS),
            "framing": "Scene-to-scene spread measures acquisition noise only. It cannot see seasonal, tidal or "
            "phenological differences between the periods and is itself uncertain with 2-3 scenes per period. "
            "A noise-supported pixel is not proof of real change; an unsupported one is not proof of none.",
            "per_index": per_index,
        }
        out = OUT / exp
        out.mkdir(parents=True, exist_ok=True)
        (out / "result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        for index, r in per_index.items():
            if r["status"] != "ok":
                print(exp, index, r["reason"])
                continue
            b = r["by_k"]["3.0"]
            fixed_n = r["fixed_rule"]["decrease_pixels"] + r["fixed_rule"]["increase_pixels"]
            print(
                f"{exp:28s} {index:6s} testable {r['testable_fraction']:.2f} medSE {r['median_standard_error']:.3f} "
                f"fixed {fixed_n:6d} supported(k3) {b['fixed_rule_share_noise_supported']} "
                f"xcheck {r['fixed_threshold_cross_check_matches_manifest']}"
            )
    # Aggregate for the website (same numbers, one file).
    STUDY_OF = {
        "coringa_m1": "coringa_coastal", "chilika_m4_dry": "chilika_wetland",
        "chilika_m4_postmonsoon": "chilika_wetland", "western_ghats_m4": "western_ghats_forest",
        "himalaya_purepu_2025_m4": "himalaya_purepu_2025", "himalaya_langtang_2026_m4": "himalaya_langtang_2026",
        "kathmandu_m4": "kathmandu_urban",
    }
    docs = []
    for exp in EXPERIMENTS:
        doc = json.loads((OUT / exp / "result.json").read_text(encoding="utf-8"))
        doc["study_id"] = STUDY_OF[exp]
        docs.append(doc)
    pub = ROOT / "frontend" / "public" / "studies" / "m6_noise.json"
    pub.write_text(json.dumps({"schema": "habitatshift-m6-noise-bundle/1", "experiments": docs}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
