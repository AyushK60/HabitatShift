"""Independent validation of the Western Ghats NDVI-decrease map against Hansen forest loss.

Reference: Hansen/UMD/Google/USGS/NASA Global Forest Change v1.12 (2000-2024), CC-BY 4.0,
Hansen et al. 2013, Science 342:850. Bands used: `lossyear` (year of stand-replacement
disturbance, 1 = 2001 ... 24 = 2024) and `treecover2000` (percent canopy in 2000).

Only the AOI window is read (HTTP range requests through GDAL /vsicurl); the window is
warped onto the study's own 10 m grid with nearest-neighbour resampling (categorical data is
never interpolated) and stored with a SHA-256 so the validation can be re-run offline.

Design choices, fixed before looking at results:
  * Evaluation domain: pixels in the common-valid footprint with treecover2000 >= 30 %
    (the standard forest definition for this product). Forest loss is not defined elsewhere.
  * Reference positive: lossyear in 21..24 (2021-2024), i.e. loss recorded between the two
    mid-February acquisitions. 2020 is excluded because part of it precedes the first scene
    and 2025 is not yet in the product (sensitivity: 2020 added).
  * Predictions compared: (a) the recorded fixed NDVI decrease rule (delta <= -0.15) and
    (b) the same pixels that also pass the noise test at 3 x SE (scripts/run_noise_aware_threshold.py).
  * Metrics: confusion matrix, precision, recall, F1, plus the reference base rate so a
    reader can see how much better than chance the map is (lift = precision / base rate).
    Also repeated after dilating the reference by one 30 m pixel (tolerance for the 10 m vs 30 m
    grid mismatch and registration error).

Result: data/experiments/m6_validation/western_ghats_m4/result.json
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = "https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12"
TILE = "20N_070E"  # covers 10N-20N, 70E-80E (the AOI is at 15.1N, 74.35E)
EXPERIMENT = "western_ghats_m4"
OUT = ROOT / "data" / "experiments" / "m6_validation" / EXPERIMENT
REF_DIR = ROOT / "data" / "external" / "hansen_gfc_2024"
DELTA = ROOT / "data" / "processed" / "m4" / EXPERIMENT / "delta_ndvi.tif"
MANIFEST = ROOT / "data" / "manifests" / "m4_western_ghats_m4.json"


def warp_band(layer: str, grid: dict) -> np.ndarray:
    url = f"/vsicurl/{BASE}/Hansen_GFC-2024-v1.12_{layer}_{TILE}.tif"
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="3"):
        with rasterio.open(url) as src:
            with WarpedVRT(
                src,
                crs=CRS.from_string(grid["crs"]),
                transform=rasterio.Affine(*grid["transform"][:6]),
                width=grid["width"],
                height=grid["height"],
                resampling=Resampling.nearest,
            ) as vrt:
                return vrt.read(1)


def get_reference(grid: dict) -> tuple[np.ndarray, np.ndarray, dict]:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    path = REF_DIR / f"{EXPERIMENT}_window.npz"
    if not path.exists():
        loss = warp_band("lossyear", grid)
        cover = warp_band("treecover2000", grid)
        np.savez_compressed(path, lossyear=loss, treecover2000=cover)
    z = np.load(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return z["lossyear"], z["treecover2000"], {"file": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha}


def confusion(pred: np.ndarray, ref: np.ndarray, domain: np.ndarray) -> dict:
    tp = int((pred & ref & domain).sum())
    fp = int((pred & ~ref & domain).sum())
    fn = int((~pred & ref & domain).sum())
    tn = int((~pred & ~ref & domain).sum())
    n = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    base = (tp + fn) / n if n else None
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn, "pixels_evaluated": n,
        "precision": None if precision is None else round(precision, 4),
        "recall": None if recall is None else round(recall, 4),
        "f1": None if f1 is None else round(f1, 4),
        "reference_base_rate": None if base is None else round(base, 5),
        "lift_over_chance": None if (precision is None or not base) else round(precision / base, 2),
    }


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    grid = manifest["grid"]
    loss, cover, ref_meta = get_reference(grid)

    with rasterio.open(DELTA) as src:
        delta = src.read(1).astype("float32")
    valid = np.isfinite(delta)
    forest = cover >= 30
    domain = valid & forest

    ref_main = (loss >= 21) & (loss <= 24)
    ref_with_2020 = (loss >= 20) & (loss <= 24)
    pred_fixed = valid & (delta <= -0.15)

    # noise-supported subset (recomputed with the same code path as the noise script)
    noise = json.loads((ROOT / "data/experiments/m6_noise/western_ghats_m4/result.json").read_text(encoding="utf-8"))
    noise_ok = noise["per_index"]["ndvi"]["status"] == "ok"
    pred_noise = None
    if noise_ok:
        sys.path.insert(0, str(ROOT / "scripts"))
        import run_noise_aware_threshold as nat  # reuse the exact stack builders

        metas: dict = {}
        for p in nat.CACHE.glob("*.json"):
            m = json.loads(p.read_text(encoding="utf-8"))
            metas.setdefault((m["item_id"], m["grid_signature"]), []).append((p, m))
        st_e = nat.period_stack("ndvi", manifest["periods"][0], metas, grid["signature"])
        st_l = nat.period_stack("ndvi", manifest["periods"][1], metas, grid["signature"])
        n_e, _, var_e = nat.mean_var(st_e)
        n_l, _, var_l = nat.mean_var(st_l)
        ok = valid & (n_e >= 2) & (n_l >= 2) & np.isfinite(var_e) & np.isfinite(var_l)
        s_e = np.maximum(np.sqrt(np.where(ok, var_e, 0)), nat.SIGMA_FLOOR)
        s_l = np.maximum(np.sqrt(np.where(ok, var_l, 0)), nat.SIGMA_FLOOR)
        se = np.sqrt(s_e**2 / np.maximum(n_e, 1) + s_l**2 / np.maximum(n_l, 1))
        pred_noise = pred_fixed & ok & (np.abs(delta) > 3.0 * se)

    # tolerance: allow a one-30m-pixel (3 px) neighbourhood around reference loss
    ref_dilated = ndimage.binary_dilation(ref_main, structure=np.ones((3, 3), bool), iterations=3)

    def block(ref: np.ndarray) -> dict:
        out = {"fixed_rule_ndvi_decrease": confusion(pred_fixed, ref, domain)}
        if pred_noise is not None:
            out["fixed_rule_and_noise_supported_3x"] = confusion(pred_noise, ref, domain)
        return out

    result = {
        "schema": "habitatshift-m6-validation/1",
        "experiment": EXPERIMENT,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "reference": {
            "name": "Hansen Global Forest Change v1.12 (2000-2024)",
            "citation": "Hansen, M. C. et al. (2013) High-resolution global maps of 21st-century forest cover change. Science 342, 850-853.",
            "licence": "CC-BY 4.0",
            "source": BASE,
            "tile": TILE,
            "native_resolution_m": 30,
            "window_cache": ref_meta,
            "retrieved_utc": dt.datetime.now(dt.timezone.utc).date().isoformat(),
        },
        "design": {
            "domain": "common-valid pixels with treecover2000 >= 30 %",
            "reference_positive": "lossyear 21..24 (2021-2024)",
            "prediction": "recorded NDVI decrease rule delta <= -0.15; and the subset passing the 3 x SE noise test",
            "grid_note": "Hansen 30 m warped to the 10 m study grid by nearest neighbour",
        },
        "domain_pixels": int(domain.sum()),
        "forest_fraction_of_valid": round(float(domain.sum() / max(valid.sum(), 1)), 4),
        "reference_loss_pixels_in_domain": int((ref_main & domain).sum()),
        "reference_loss_cells_30m_approx": round(float((ref_main & domain).sum() / 9), 1),
        "predicted_decrease_pixels_in_domain": int((pred_fixed & domain).sum()),
        "predicted_decrease_pixels_outside_forest_domain": int((pred_fixed & valid & ~forest).sum()),
        "main": block(ref_main),
        "sensitivity_including_2020": block(ref_with_2020),
        "sensitivity_one_pixel_tolerance": {
            "note": "reference dilated by 3 px (one 30 m cell) to absorb grid mismatch and registration error; recall is then not penalised for near misses, precision is evaluated against the dilated reference",
            **block(ref_dilated),
        },
        "interpretation_guardrails": [
            "Hansen loss is annual stand-replacement disturbance; NDVI decrease also responds to leaf shedding, selective logging and moisture, so low precision is expected and not an error of either dataset.",
            "Hansen is itself a model product with its own error; this is agreement with an independent product, not accuracy against ground truth.",
            "One 24 km2 area with few loss pixels: treat the numbers as indicative, not as a general accuracy claim.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    pub = ROOT / "frontend" / "public" / "studies" / "m6_validation.json"
    pub.write_text(json.dumps({"schema": "habitatshift-m6-validation-bundle/1", "study_id": "western_ghats_forest", "result": result}, indent=1), encoding="utf-8")
    (OUT / "result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    for name in ("main", "sensitivity_including_2020", "sensitivity_one_pixel_tolerance"):
        for key, c in result[name].items():
            if isinstance(c, dict) and "precision" in c:
                print(f"{name:34s} {key:36s} P={c['precision']} R={c['recall']} F1={c['f1']} lift={c['lift_over_chance']} tp={c['tp']} fp={c['fp']} fn={c['fn']}")
    print("domain", result["domain_pixels"], "ref loss", result["reference_loss_pixels_in_domain"], "pred", result["predicted_decrease_pixels_in_domain"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
