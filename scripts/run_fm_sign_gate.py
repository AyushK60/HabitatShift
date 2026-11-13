"""Does direction alone explain the gap between signed NDVI and the unsigned embedding scores? (exploratory)

The unsigned embedding distance z cannot say whether a change is a loss. Here each unsigned z is multiplied by 1 where the
NDVI fell between the periods and by 0 otherwise (a hard sign gate), so every method gets the same direction information
and nothing is trained. If gated Prithvi z matches signed NDVI, direction accounts for the gap; if not, the embedding adds
or loses something beyond direction. Same patches, labels and block bootstrap as the main forest evaluation.

    python scripts/run_fm_sign_gate.py
Output: data/experiments/v3_fm/sign_gate.json
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
    out = {}
    for study_id, tile in P.FOREST.items():
        d = P.forest_dataset(study_id, tile, embedders)
        y, blocks, ref = d["y"], d["blocks"], d["ref"]
        gate = (ref > 0).astype(float)
        scores = {"signed_ndvi": ref}
        for m in ("prithvi", "ssl4eo_rgb", "raw6", "indices5"):
            scores[f"{m}_gated"] = d["main"][m] * gate
            scores[f"{m}_unsigned"] = d["main"][m]
        boot = E.block_bootstrap(y, scores, blocks, reference="signed_ndvi", n_boot=500)
        out[study_id] = {
            "metrics": {k: E.metrics(y, s) for k, s in scores.items()},
            "diff_vs_signed_ndvi_ap_ci95": {k: boot[k]["average_precision"]["diff_vs_reference_ci95"] for k in scores}}
        print(study_id, {k: round(v["average_precision"], 2) for k, v in out[study_id]["metrics"].items() if "unsigned" not in k}, flush=True)
    path = config.DATA_DIR / "experiments" / "v3_fm" / "sign_gate.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
