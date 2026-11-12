"""JRC Global Surface Water vs ESA WorldCover: water-label cross-check (post-M5 addition).

Why: the M5 label-feasibility record said no working JRC GSW endpoint could be
established. The public GCS tiles (`global-surface-water/downloads2021/...`) are
reachable now, so this script quantifies how two *reference products* agree on
water inside three AOIs. It is deliberately **reference-vs-reference** and does
not retrain, replace or alter any sealed M5 result.

Inputs: the training-epoch composite grid of each study (grid only) and two
live COG reads (WorldCover v200 2021; GSW occurrence v1.4, 1984-2021).
Output: data/experiments/m5_gsw/<study>/result.json (sealed with sha256s).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
import rasterio.warp
from rasterio import Env
from rasterio.crs import CRS
from rasterio.io import MemoryFile
from rasterio.transform import Affine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_m5_ml as ml  # reuse the audited WorldCover reader  # noqa: E402

GSW_URL = "https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_{ew}_{ns}v1_4_2021.tif"
GDAL_ENV = {"GDAL_HTTP_TIMEOUT": "60", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "VSI_CACHE": "TRUE"}
STUDIES = {
    "chilika_dry": "chilika_dry_m5_ml",
    "chilika_postmonsoon": "chilika_postmonsoon_m5_ml",
    "coringa": "coringa_m5_ml",
}
WC_WATER = (80, 90)
OCC_THRESHOLDS = (10, 25, 50, 75)  # percent of valid observations that were water


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def grid_of(tif: Path) -> dict:
    with rasterio.open(tif) as src:
        return {"crs": src.crs.to_string(), "transform": list(src.transform)[:6],
                "width": src.width, "height": src.height}


def gsw_tile_url(w: float, n: float) -> str:
    lon0 = int(np.floor(w / 10.0)) * 10
    lat1 = (int(np.floor(n / 10.0)) + 1) * 10  # tiles are named by their north edge
    ew = f"{abs(lon0)}{'E' if lon0 >= 0 else 'W'}"
    ns = f"{abs(lat1)}{'N' if lat1 >= 0 else 'S'}"
    return GSW_URL.format(ew=ew, ns=ns)


def read_gsw_on_grid(bounds: tuple, grid: dict) -> tuple[np.ndarray, str]:
    w, s, e, n = bounds
    url = gsw_tile_url(w, n)
    with Env(**GDAL_ENV):
        with rasterio.open(url) as src:
            win = rasterio.windows.from_bounds(w, s, e, n, transform=src.transform).round_offsets().round_lengths()
            raw = src.read(1, window=win)
            tf = src.window_transform(win)
            nodata = src.nodata
    dst = np.full((grid["height"], grid["width"]), 255, dtype=np.uint8)
    with MemoryFile() as mem, mem.open(driver="GTiff", width=raw.shape[1], height=raw.shape[0], count=1,
                                       dtype="uint8", crs="EPSG:4326", transform=tf) as tmp:
        tmp.write(raw, 1)
        rasterio.warp.reproject(rasterio.band(tmp, 1), dst, dst_transform=Affine(*grid["transform"]),
                                dst_crs=CRS.from_string(grid["crs"]), resampling=rasterio.warp.Resampling.nearest)
    return dst, url


def kappa(tp: int, fp: int, fn: int, tn: int) -> float | None:
    n = tp + fp + fn + tn
    po = (tp + tn) / n
    pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
    return None if pe == 1 else float((po - pe) / (1 - pe))


def run(name: str, spec_key: str) -> dict:
    spec = ml.EXPERIMENTS[spec_key]
    grid = grid_of(PROJECT_ROOT / spec["training"])
    bounds, _ = ml.reproject_grid_to_4326(grid)
    wc, wc_url, _ = ml.read_labels_on_grid(bounds, grid)
    gsw, gsw_url = read_gsw_on_grid(bounds, grid)
    # GSW 255 = no data (never observed); 0 = observed, never water
    valid = (gsw != 255) & (wc != 0)
    wc_water = np.isin(wc, WC_WATER)
    rows = []
    for t in OCC_THRESHOLDS:
        g = gsw >= t
        a, b = wc_water[valid], g[valid]
        tp, fp = int((a & b).sum()), int((a & ~b).sum())
        fn, tn = int((~a & b).sum()), int((~a & ~b).sum())
        rows.append({
            "gsw_occurrence_threshold_percent": t,
            "worldcover_water_and_gsw_water": tp, "worldcover_water_only": fp,
            "gsw_water_only": fn, "neither": tn,
            "overall_agreement": float((tp + tn) / (tp + fp + fn + tn)),
            "cohen_kappa": kappa(tp, fp, fn, tn),
            "water_overlap_iou": float(tp / (tp + fp + fn)) if (tp + fp + fn) else None,
        })
    result = {
        "schema": "habitatshift-m5-gsw-crosscheck/1",
        "study": name,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "framing": "reference-product vs reference-product consistency; neither is ground truth. "
                   "GSW occurrence summarises 1984-2021 whereas WorldCover is a 2021 snapshot, so "
                   "differences are expected in seasonally varying water.",
        "grid": grid,
        "valid_pixels": int(valid.sum()),
        "worldcover_water_fraction": float(wc_water[valid].mean()),
        "interpretation_note": "Cohen's kappa is unstable when one class dominates (e.g. Chilika is almost all "
                               "water, so kappa is ~0 whenever the 'neither' cell is empty); read agreement and "
                               "water IoU together with the per-cell counts.",
        "gsw_no_data_pixels": int((gsw == 255).sum()),
        "sources": {
            "worldcover": {"url": wc_url, "version": "v200 (2021)", "licence": "CC-BY 4.0 (c) ESA WorldCover project 2022"},
            "jrc_gsw": {"url": gsw_url, "version": "occurrence v1.4 (1984-2021)",
                        "licence": "CC-BY 4.0; Pekel et al. 2016, Nature 540, 418-422"},
        },
        "worldcover_water_classes": list(WC_WATER),
        "results_by_gsw_threshold": rows,
        "label_array_sha256": {"worldcover": sha256_bytes(wc.tobytes()), "gsw": sha256_bytes(gsw.tobytes())},
    }
    out = PROJECT_ROOT / "data" / "experiments" / "m5_gsw" / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    best = max(rows, key=lambda r: r["cohen_kappa"] or -1)
    print(f"[{name}] valid={result['valid_pixels']}  best kappa={best['cohen_kappa']:.3f} at occ>={best['gsw_occurrence_threshold_percent']}%")
    return result


def main() -> int:
    for name, key in STUDIES.items():
        run(name, key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
