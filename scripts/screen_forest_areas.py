"""Label-only screen for the pre-registered forest areas (studies/forest_expansion_prereg.yaml).

Counts eligible, positive and clean-negative 16 x 16 patches from Hansen alone, with the rules of
scripts/run_fm_evaluation.py. No scenes and no model scores are used. Scene validity is not applied here,
so these counts are upper bounds for the final evaluation.

    python scripts/screen_forest_areas.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.app import config  # noqa: E402
from backend.app.radar.planetary import make_grid  # noqa: E402
from run_fm_evaluation import hansen_layer, patch_fraction  # noqa: E402

PREREG = Path(__file__).resolve().parents[1] / "studies" / "forest_expansion_prereg.yaml"
OUT = Path(__file__).resolve().parents[1] / "studies" / "forest_expansion_screen.json"


def main() -> None:
    spec = yaml.safe_load(PREREG.read_text(encoding="utf-8"))
    results = []
    for area in spec["areas"]:
        g = make_grid(tuple(area["bbox"]))
        grid = {"crs": g.crs, "transform": list(g.transform)[:6], "width": g.width, "height": g.height}
        folder = config.DATA_DIR / "fm" / area["id"]
        folder.mkdir(parents=True, exist_ok=True)
        lossyear = hansen_layer("lossyear", area["hansen_tile"], grid, folder / "hansen_lossyear.npy")
        cover = hansen_layer("treecover2000", area["hansen_tile"], grid, folder / "hansen_treecover2000.npy")
        forest = cover >= 30
        forest_frac = patch_fraction(forest)
        pos = patch_fraction(forest & (lossyear >= 22) & (lossyear <= 24))
        neg = patch_fraction(forest & (lossyear >= 21) & (lossyear <= 24))
        eligible = forest_frac >= 0.5
        positive = int((eligible & (pos >= 0.10)).sum())
        negative = int((eligible & (neg < 0.02)).sum())
        passes = positive >= spec["min_positive_patches"] and negative >= spec["min_clean_negative_patches"]
        row = {"id": area["id"], "eligible": int(eligible.sum()), "positives": positive,
               "clean_negatives": negative, "passes_label_screen": passes}
        results.append(row)
        print(row, flush=True)
    OUT.write_text(json.dumps({"rule": {k: spec[k] for k in ("min_positive_patches", "min_clean_negative_patches")},
                               "areas": results}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
