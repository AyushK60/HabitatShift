"""Two extra checks on the forest evaluation, run after review (exploratory).

1. Paired difference in average precision between Prithvi z and six-raw-band z, per area (block bootstrap, same blocks).
2. Between-year z on Hansen clean patches (nothing lost): median z and the share above z = 3, per method and area.
   If the noise model were right for between-year change, clean patches would sit near z = 1 and few would pass z > 3.

    python scripts/run_fm_extra_checks.py
Output: data/experiments/v3_fm/extra_checks.json. Uses the dataset code of scripts/run_fm_probe.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from backend.app import config  # noqa: E402
from backend.app.foundation import evaluate as E  # noqa: E402
from backend.app.foundation.prithvi import PrithviEmbedder  # noqa: E402
from backend.app.foundation.resnet import SSL4EOResNetEmbedder  # noqa: E402
import run_fm_probe as P  # noqa: E402


def main() -> None:
    embedders = {"prithvi": PrithviEmbedder(), "ssl4eo_rgb": SSL4EOResNetEmbedder()}
    out = {"paired_prithvi_minus_raw6_ap_ci95": {}, "clean_patch_z": {}}
    for study_id, tile in P.FOREST.items():
        d = P.forest_dataset(study_id, tile, embedders)
        y, blocks, main = d["y"], d["blocks"], d["main"]
        boot = E.block_bootstrap(y, {m: main[m] for m in ("prithvi", "raw6", "ssl4eo_rgb")}, blocks, reference="raw6", n_boot=500)
        out["paired_prithvi_minus_raw6_ap_ci95"][study_id] = {
            "prithvi": boot["prithvi"]["average_precision"]["diff_vs_reference_ci95"],
            "ssl4eo_rgb": boot["ssl4eo_rgb"]["average_precision"]["diff_vs_reference_ci95"]}
        clean = y == 0
        out["clean_patch_z"][study_id] = {
            m: {"median_z": float(np.median(main[m][clean])), "share_above_3": float((main[m][clean] > 3).mean()),
                "clean_patches": int(clean.sum())} for m in main}
        print(study_id, out["paired_prithvi_minus_raw6_ap_ci95"][study_id], flush=True)
    path = config.DATA_DIR / "experiments" / "v3_fm" / "extra_checks.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
