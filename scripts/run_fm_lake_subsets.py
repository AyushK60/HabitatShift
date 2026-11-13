"""Lake result by lake and without Imja Tsho (exploratory, run after the pooled four-lake evaluation).

Same patches, labels and scores as scripts/run_fm_lake_evaluation.py; only the grouping differs. Groups: each lake alone,
the three pilot lakes (2018 against 2024), the lakes without Imja Tsho, and Imja Tsho alone. Paired differences from MNDWI
z use the same spatial block bootstrap. Output: data/experiments/v3_fm/lakes/subsets.json

    python scripts/run_fm_lake_subsets.py
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
import run_fm_lake_evaluation as LK  # noqa: E402

LAKES = ["lake_tsho_rolpa", "lake_imja_tsho", "lake_thulagi", "lake_himag_gl087092e27798n"]
METHODS = ["raw6:z", "prithvi:z", "ssl4eo_rgb:z", "ndvi:z", "indices5:z", "mndwi:z"]
GROUPS = {
    "pilot_three_lakes": ["lake_tsho_rolpa", "lake_imja_tsho", "lake_thulagi"],
    "without_imja": ["lake_tsho_rolpa", "lake_thulagi", "lake_himag_gl087092e27798n"],
    "imja_only": ["lake_imja_tsho"],
    "added_lake_only": ["lake_himag_gl087092e27798n"],
    "tsho_rolpa_only": ["lake_tsho_rolpa"],
    "thulagi_only": ["lake_thulagi"],
}


def main() -> None:
    embedders = {"prithvi": PrithviEmbedder(), "ssl4eo_rgb": SSL4EOResNetEmbedder()}
    data = {}
    for n, study_id in enumerate(LAKES):
        d = LK.lake_inputs(study_id, embedders)
        finite = np.logical_and.reduce([np.isfinite(s) for s in d["scores"].values()])
        eligible = d["near"] & d["ok"] & d["reference_ok"] & finite
        positive, negative = eligible & (d["delta"] >= LK.POSITIVE), eligible & (d["delta"] < LK.NEGATIVE)
        use = positive | negative
        rows, cols = np.indices(use.shape)
        data[study_id] = {"y": positive[use].astype(int), "blocks": E.block_ids(rows, cols, LK.BLOCK)[use] + n * 10_000_000,
                          "s": {m: d["scores"][m][use] for m in METHODS}}
    out = {"design": "same labels and scores as the pooled lake evaluation; grouping only", "groups": {}}
    for name, members in GROUPS.items():
        y = np.concatenate([data[k]["y"] for k in members])
        blocks = np.concatenate([data[k]["blocks"] for k in members])
        sc = {m: np.concatenate([data[k]["s"][m] for k in members]) for m in METHODS}
        entry = {"lakes": members, "positives": int(y.sum()), "negatives": int((1 - y).sum()),
                 "blocks_with_positives": int(np.unique(blocks[y == 1]).size)}
        if y.sum() >= 3 and (1 - y).sum() >= 3:
            entry["metrics"] = {m: E.metrics(y, s) for m, s in sc.items()}
            boot = E.block_bootstrap(y, sc, blocks, reference="mndwi:z", n_boot=500)
            entry["ap_ci95"] = {m: boot[m]["average_precision"]["ci95"] for m in METHODS}
            entry["diff_vs_mndwi_ap_ci95"] = {m: boot[m]["average_precision"]["diff_vs_reference_ci95"] for m in METHODS}
        out["groups"][name] = entry
        print(name, entry["positives"], {m: round(v["average_precision"], 2) for m, v in entry.get("metrics", {}).items()}, flush=True)
    path = config.DATA_DIR / "experiments" / "v3_fm" / "lakes" / "subsets.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
