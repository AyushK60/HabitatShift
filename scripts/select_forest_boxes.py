"""Label-only box selection from Amendment 1 of studies/forest_expansion_prereg.yaml.

For each region, slide a 760 x 800 pixel box (10 m) over a 0.4 degree window and keep the box with the most
positive patches (Hansen loss 2022-2024 >= 10% of a 16 x 16 patch) among boxes with >= 300 clean negatives.
No scenes and no model scores are used.

    python scripts/select_forest_boxes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import yaml
from rasterio.transform import Affine
from rasterio.warp import transform_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.app import config  # noqa: E402
from backend.app.radar.planetary import make_grid  # noqa: E402
from run_fm_evaluation import hansen_layer, patch_fraction  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "studies" / "forest_expansion_prereg.yaml"
OUT = ROOT / "studies" / "forest_expansion_selected.json"
PATCH = 16


def main() -> None:
    spec = yaml.safe_load(PREREG.read_text(encoding="utf-8"))
    am = spec["amendment_1"]
    bw, bh = am["box_pixels"]
    step = am["step_pixels"]
    half = am["window_degrees"] / 2
    results = []
    for area in spec["areas"]:
        lat, lon = area["centre"]
        g = make_grid((lon - half, lat - half, lon + half, lat + half))
        grid = {"crs": g.crs, "transform": list(g.transform)[:6], "width": g.width, "height": g.height}
        cache = config.DATA_DIR / "fm" / f"_search_{area['id']}"
        cache.mkdir(parents=True, exist_ok=True)
        loss = hansen_layer("lossyear", area["hansen_tile"], grid, cache / "lossyear.npy")
        cover = hansen_layer("treecover2000", area["hansen_tile"], grid, cache / "treecover2000.npy")
        forest = cover >= 30
        eligible = patch_fraction(forest) >= 0.5
        pos = eligible & (patch_fraction(forest & (loss >= 22) & (loss <= 24)) >= 0.10)
        neg = eligible & (patch_fraction(forest & (loss >= 21) & (loss <= 24)) < 0.02)
        pw, ph = bw // PATCH, bh // PATCH
        best = None
        for r in range(0, pos.shape[0] - ph + 1, step // PATCH):
            for c in range(0, pos.shape[1] - pw + 1, step // PATCH):
                p = int(pos[r:r + ph, c:c + pw].sum())
                n = int(neg[r:r + ph, c:c + pw].sum())
                if n >= spec["min_clean_negative_patches"] and (best is None or p > best[0]):
                    best = (p, n, r, c)
        row = {"id": area["id"], "region": area["type"]}
        if best is None:
            row.update(selected=False, reason="no candidate has enough clean negatives")
        else:
            p, n, r, c = best
            t = Affine(*grid["transform"][:6])
            x0, y0 = t * (c * PATCH, r * PATCH)
            x1, y1 = t * ((c + pw) * PATCH, (r + ph) * PATCH)
            west, south, east, north = transform_bounds(grid["crs"], "EPSG:4326", x0, y1, x1, y0)
            row.update(selected=True, bbox=[round(west, 3), round(south, 3), round(east, 3), round(north, 3)],
                       hansen_tile=area["hansen_tile"], positives=p, clean_negatives=n,
                       passes_label_screen=bool(p >= spec["min_positive_patches"]))
        results.append(row)
        print(row, flush=True)
    OUT.write_text(json.dumps({"amendment": 1, "areas": results}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
