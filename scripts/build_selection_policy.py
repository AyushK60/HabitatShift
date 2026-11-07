#!/usr/bin/env python3
"""Build the findings selection-policy disclosure artifact for the frontend.

M4-R3 requirement (brief §5): the product must state honestly that the
recorded findings are a curated top-five-per-index-direction selection, and
show how many qualifying components were not recorded.  Those counts are
produced by the independent audit (scripts/audit_findings_m4r2.py) and are
NOT part of the findings containers, so this script derives the disclosure
from the audit artifact programmatically — no hand-copied numbers.

Output: frontend/public/studies/selection_policy.json
        (schema habitatshift-selection-policy/1)

Usage:
    python scripts/build_selection_policy.py \
        [--audit docs/evidence/m4-r2/findings_audit_results.json] \
        [--out frontend/public/studies/selection_policy.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA = "habitatshift-selection-policy/1"


def git_commit() -> str | None:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.strip()
            or None
        )
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit",
        default=str(REPO_ROOT / "docs/evidence/m4-r2/findings_audit_results.json"),
    )
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "frontend/public/studies/selection_policy.json"),
    )
    args = parser.parse_args()

    audit_path = Path(args.audit)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("failed"):
        raise SystemExit(
            f"refusing to build from a failing audit: {audit.get('failed')} failed checks"
        )

    experiments = []
    totals = {
        "findings_recorded": 0,
        "components_at_or_above_mmu_total": 0,
        "components_at_or_above_mmu_unrecorded_top5_cap": 0,
    }
    for result in audit["results"]:
        by_index = {}
        exp_keys = (
            "recorded_findings",
            "components_at_or_above_mmu_total",
            "components_at_or_above_mmu_unrecorded_top5_cap",
        )
        exp_totals = dict.fromkeys(exp_keys, 0)
        for index, entry in sorted(result["per_index"].items()):
            row = {
                "recorded_findings": entry["recorded_findings"],
                "components_at_or_above_mmu_total": entry[
                    "components_at_or_above_mmu_total"
                ],
                "components_at_or_above_mmu_unrecorded_top5_cap": entry[
                    "components_at_or_above_mmu_unrecorded_top5_cap"
                ],
            }
            by_index[index] = row
            for key in row:
                exp_totals[key] += row[key]
        experiments.append(
            {
                "experiment_id": result["experiment_id"],
                "findings_recorded": result["findings_recorded"],
                "components_at_or_above_mmu_total": exp_totals[
                    "components_at_or_above_mmu_total"
                ],
                "components_at_or_above_mmu_unrecorded_top5_cap": exp_totals[
                    "components_at_or_above_mmu_unrecorded_top5_cap"
                ],
                "by_index": by_index,
            }
        )
        totals["findings_recorded"] += result["findings_recorded"]
        totals["components_at_or_above_mmu_total"] += exp_totals[
            "components_at_or_above_mmu_total"
        ]
        totals["components_at_or_above_mmu_unrecorded_top5_cap"] += exp_totals[
            "components_at_or_above_mmu_unrecorded_top5_cap"
        ]

    payload = {
        "schema": SCHEMA,
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "policy": {
            "rule": "top 5 components per index x direction, sorted by (-area_ha, x, y)",
            "minimum_mapping_unit_px": 25,
            "recorded_findings_are": "a curated selection of candidate spectral signals, not a complete inventory of qualifying regions",
            "unrecorded_components_are": "components at or above the minimum mapping unit that the selection rule did not record; they have no evidence records and are not findings by the recorded rule",
        },
        "source": {
            "generator": "scripts/build_selection_policy.py",
            "audit_artifact": str(audit_path.relative_to(REPO_ROOT)).replace(
                "\\", "/"
            ),
            "audit_checks_passed": audit.get("passed"),
            "audit_checks_failed": audit.get("failed"),
            "git_commit": git_commit(),
        },
        "experiments": experiments,
        "totals": {"experiments": len(experiments), **totals},
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    print(
        f"totals: recorded={totals['findings_recorded']} "
        f"unrecorded={totals['components_at_or_above_mmu_unrecorded_top5_cap']} "
        f"across {len(experiments)} experiments"
    )


if __name__ == "__main__":
    main()
