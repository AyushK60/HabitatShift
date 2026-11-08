"""M5-G6: build the additive ML findings containers from the M5-ML runs.

Creates ``data/findings_m5ml/<experiment_id>.json`` (schema
``habitatshift-m5ml-findings/1``) — sibling containers that reference, and
never modify, the frozen ``habitatshift-findings/2`` records.  Every field is
generated from the recorded experiment results (never hand-copied), every
number carries its agreement-with-reference framing, and the container records
the source run directory + result checksum for traceability.

Usage: python scripts/build_m5ml_findings.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCHEMA = "habitatshift-m5ml-findings/1"

#: experiment_id -> the m5_ml run-study key and its frozen m4 counterpart
STUDIES = {
    "kathmandu_m4": "kathmandu_m5_ml",
    "western_ghats_m4": "western_ghats_m5_ml",
    "chilika_m4_dry": "chilika_dry_m5_ml",
    "chilika_m4_postmonsoon": "chilika_postmonsoon_m5_ml",
    "coringa_m1": "coringa_m5_ml",
}


def latest_run(study: str) -> Path:
    runs = sorted((ROOT / "data" / "experiments" / "m5_ml" / study).iterdir())
    return runs[-1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plain_language(result: dict) -> str:
    ev = result["evaluation_test"]
    app = result["application"]
    tags = sorted(app)
    if len(tags) == 2:
        first, second = app[tags[0]], app[tags[1]]
        order = ev["class_order"]
        shifts = []
        for name in order:
            row = ev["per_class"][name]
            if row["support"] < ev["support_floor"]:
                continue
            delta = second["predicted_fractions"][name] - first["predicted_fractions"][name]
            if abs(delta) >= 0.01:
                shifts.append(f"{name} {'+' if delta > 0 else '−'}{abs(delta) * 100:.1f} pp")
        shift_text = "; ".join(shifts) if shifts else "no class shifted by more than 1 percentage point"
        return (
            f"A Random Forest trained on 2021 reference labels (ESA WorldCover) reproduces "
            f"that reference on held-out test blocks at {ev['overall_agreement']:.0%} overall "
            f"agreement. Applied to the two measured composites, the predicted class mix "
            f"shifts: {shift_text}. These are model predictions against reference-product "
            f"labels — not independent ground truth and not verified change."
        )
    return "Reference-agreement experiment; see the technical panel for the recorded metrics."


def build(experiment_id: str, study: str) -> dict:
    run = latest_run(study)
    result = json.loads((run / "result.json").read_text())
    manifest = json.loads((run / "manifest.json").read_text())
    ev = result["evaluation_test"]
    findings_container = json.loads((ROOT / "data" / "findings" / f"{experiment_id}.json").read_text())

    ml_record = {
        "schema": "habitatshift-m5ml-record/1",
        "identification": {
            "experiment_id": experiment_id,
            "ml_study": study,
            "source_run": str(run.relative_to(ROOT)),
            "source_result_sha256": sha256_file(run / "result.json"),
            "status": result["status"],
            "evidence_status": "MODEL_OUTPUT_AGAINST_REFERENCE",
        },
        "reference": result["reference"],
        "model": result["model"],
        "features": {
            "list": result["features"],
            "resolution_note": result["feature_resolution_note"],
            "importance": result["feature_importance"],
        },
        "split_design": result["split_design"],
        "evaluation": {
            "class_order": ev["class_order"],
            "overall_agreement": ev["overall_agreement"],
            "macro_f1_all_classes": ev["macro_f1_all_classes"],
            "macro_f1_supported_classes": ev["macro_f1_supported_classes"],
            "balanced_accuracy": ev["balanced_accuracy"],
            "per_class": ev["per_class"],
            "support_floor": ev["support_floor"],
            "confusion_matrix": ev["confusion_matrix_rows_true_cols_pred"],
            "framing": ev["framing"],
        },
        "geographic_stability": result.get("geographic_stability", {"available": False}),
        "application": result["application"],
        "math_baseline_comparison": result["math_baseline_comparison"],
        "plain_language": plain_language(result),
        "interpretation_guardrails": result["interpretation_guardrails"],
    }

    return {
        "schema": SCHEMA,
        "experiment_id": experiment_id,
        "generated_utc": result["generated_utc"],
        "references": {
            "mathematical_findings_container": {
                "schema": findings_container["schema"],
                "path": f"data/findings/{experiment_id}.json",
                "sha256": sha256_file(ROOT / "data" / "findings" / f"{experiment_id}.json"),
                "note": "frozen mathematical evidence records; this container adds ML context and never modifies them",
            },
            "run_manifest": {
                "path": f"data/experiments/m5_ml/{study}/{run.name}/manifest.json",
                "git_commit": manifest.get("git_commit"),
            },
        },
        "label_gate": "docs/M5_ML_LABEL_FEASIBILITY.md",
        "evidence_status": "MODEL_OUTPUT_AGAINST_REFERENCE",
        "ml_record": ml_record,
        "limitations": [
            "Reference labels are ESA WorldCover v200, itself a classification product; all metrics measure agreement with it, not ground truth.",
            "Applying the 2021-trained classifier to 2020/2025 composites assumes class-spectral stability across epochs.",
            "Rare classes below the 50-px test-support floor are not reported rather than estimated.",
            "Class-prediction probabilities are confidences, never accuracy.",
        ],
    }


def main() -> int:
    out_dir = ROOT / "data" / "findings_m5ml"
    out_dir.mkdir(exist_ok=True)
    index: dict[str, dict] = {}
    for experiment_id, study in STUDIES.items():
        container = build(experiment_id, study)
        path = out_dir / f"{experiment_id}.json"
        path.write_text(json.dumps(container, indent=2) + "\n", encoding="utf-8")
        index[experiment_id] = container
        print(f"{experiment_id}: {path.name} (agreement {container['ml_record']['evaluation']['overall_agreement']:.3f})")
    # combined static index served to the frontend (same pattern as
    # selection_policy.json): works identically live and in showcase mode
    static_path = ROOT / "frontend" / "public" / "studies" / "m5ml_findings.json"
    static_path.write_text(
        json.dumps({
            "schema": "habitatshift-m5ml-index/1",
            "generated_utc": max(c["generated_utc"] for c in index.values()),
            "experiments": index,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {static_path.relative_to(ROOT)} ({len(index)} experiments)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
