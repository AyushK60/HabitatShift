#!/usr/bin/env python3
"""M4-R3 G5 — study-interpretation and top-five-disclosure verification.

Programmatically verifies, from the recorded artifacts only (no UI code):

1. Disclosure math (brief §5): the recorded findings count in each findings
   container equals the audited recorded count; recorded + unrecorded equals
   the audited components-at-or-above-MMU total; the generated
   selection_policy.json agrees with the audit artifact per experiment.
2. Per-study interpretation themes (brief §6): each experiment's container
   text (limitations, overview, per-finding interpretations) carries its
   documented guardrail themes.
3. Forbidden claims: no container text presents candidate signals as
   verified deforestation, verified new construction/buildings, or a
   verified collapse footprint.
4. PARTIAL propagation: himalaya_purepu_2025_m4 is `partial` at container
   and in every per-finding evidence record.

Writes docs/evidence/m4-r3/study_interpretation_checks.json and exits
non-zero if any check fails.

Usage: python scripts/audit_m4r3_disclosure.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FINDINGS_DIR = REPO_ROOT / "data" / "findings"
POLICY_PATH = REPO_ROOT / "frontend" / "public" / "studies" / "selection_policy.json"
AUDIT_PATH = REPO_ROOT / "docs" / "evidence" / "m4-r2" / "findings_audit_results.json"
OUT_PATH = REPO_ROOT / "docs" / "evidence" / "m4-r3" / "study_interpretation_checks.json"

# (experiment_id, [required regex themes], experiment-level status)
THEMES = {
    "coringa_m1": (
        ["tidal", "turbidity", "ecological-causation|species", "composite"],
        "processed",
    ),
    "chilika_m4_dry": (
        ["water level", "seasonal|seasonality", "turbidity"],
        "processed",
    ),
    "chilika_m4_postmonsoon": (
        ["water level", "seasonal|seasonality", "turbidity"],
        "processed",
    ),
    "western_ghats_m4": (
        ["shadow", "candidate spectral signals|index differences"],
        "processed",
    ),
    "himalaya_purepu_2025_m4": (
        ["monsoon", "shadow", "volume|dam-failure"],
        "partial",
    ),
    "himalaya_langtang_2026_m4": (
        ["snow", "cloud", "optical only|optical"],
        "processed",
    ),
    "kathmandu_m4": (
        ["bare soil", "construction", "building"],
        "processed",
    ),
}

# Candidate signals must never be presented as verified outcomes.
FORBIDDEN = [
    (r"verif\w+ deforestation", "verified-deforestation claim"),
    (r"confirm\w* deforestation", "confirmed-deforestation claim"),
    (
        r"verif\w+ (new )?(construction|building)",
        "verified-construction claim",
    ),
    (
        r"confirm\w* (new )?(construction|building)",
        "confirmed-construction claim",
    ),
    (r"verif\w+ collapse", "verified-collapse claim"),
    (r"confirm\w* collapse", "confirmed-collapse claim"),
    (
        r"collapse footprint (is )?(confirmed|verified|established)",
        "verified collapse footprint",
    ),
]


def assertion_sentences(text: str) -> list[str]:
    """Sentences that assert rather than negate: a sentence containing a
    forbidden phrase only counts as a violation when the sentence itself
    carries no negation (guardrails like 'not verified deforestation' are
    the honest wording, not a claim)."""
    violations = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        if re.search(
            r"\b(not|never|no|rather|cannot|isn't|aren't)\b", sentence, re.I
        ):
            continue
        violations.append(sentence.strip())
    return violations


def container_text(payload: dict) -> str:
    parts: list[str] = [json.dumps(payload.get("limitations", []))]
    overview = payload.get("overview") or {}
    parts.append(json.dumps(overview))
    for finding in payload.get("findings", []):
        interp = finding.get("interpretation") or {}
        parts.append(json.dumps(interp, ensure_ascii=False))
    return " ".join(parts).lower()


def main() -> int:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    audit_by_exp = {r["experiment_id"]: r for r in audit["results"]}
    policy_by_exp = {e["experiment_id"]: e for e in policy["experiments"]}

    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            print(f"FAIL {name}: {detail}")

    for path in sorted(FINDINGS_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        exp = payload["experiment_id"]
        recorded = len(payload.get("findings", []))

        # 1. disclosure math
        a_row, p_row = audit_by_exp.get(exp), policy_by_exp.get(exp)
        check(
            f"{exp}: recorded count matches audit",
            a_row is not None and a_row["findings_recorded"] == recorded,
            f"container {recorded} vs audit {a_row and a_row['findings_recorded']}",
        )
        check(
            f"{exp}: policy recorded count matches container",
            p_row is not None and p_row["findings_recorded"] == recorded,
            f"container {recorded} vs policy {p_row and p_row['findings_recorded']}",
        )
        if a_row is not None and p_row is not None:
            total = sum(
                entry["components_at_or_above_mmu_total"]
                for entry in a_row["per_index"].values()
            )
            unrec = sum(
                entry["components_at_or_above_mmu_unrecorded_top5_cap"]
                for entry in a_row["per_index"].values()
            )
            check(
                f"{exp}: recorded + unrecorded = components >= MMU",
                recorded + unrec == total,
                f"{recorded}+{unrec} != {total}",
            )
            check(
                f"{exp}: policy unrecorded matches audit",
                p_row["components_at_or_above_mmu_unrecorded_top5_cap"] == unrec,
                f"policy {p_row['components_at_or_above_mmu_unrecorded_top5_cap']} vs audit {unrec}",
            )

        # 2. per-study themes
        themes, expected_status = THEMES[exp]
        text = container_text(payload)
        for theme in themes:
            check(
                f"{exp}: theme '{theme}' present",
                re.search(theme, text) is not None,
                exp,
            )

        # 3. evidence status
        check(
            f"{exp}: container evidence_status is {expected_status}",
            payload.get("evidence_status") == expected_status,
            str(payload.get("evidence_status")),
        )
        if expected_status == "partial":
            mismatches = [
                f["evidence"]["identification"]["evidence_id"]
                for f in payload.get("findings", [])
                if f["evidence"]["identification"]["evidence_status"] != "partial"
            ]
            check(
                f"{exp}: PARTIAL propagates into every evidence record",
                not mismatches,
                ", ".join(mismatches[:3]),
            )

        # 4. forbidden claims (only assertive sentences count)
        assertions = " ".join(assertion_sentences(text))
        for pattern, label in FORBIDDEN:
            check(
                f"{exp}: no {label}",
                re.search(pattern, assertions) is None,
                exp,
            )

    passed = sum(1 for c in checks if c["passed"])
    failed = len(checks) - passed
    result = {
        "schema": "habitatshift-m4r3-disclosure-audit/1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "sources": {
            "findings": "data/findings/*.json",
            "selection_policy": "frontend/public/studies/selection_policy.json",
            "audit": "docs/evidence/m4-r2/findings_audit_results.json",
        },
        "checks_total": len(checks),
        "checks_passed": passed,
        "checks_failed": failed,
        "checks": checks,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"disclosure audit: {passed}/{len(checks)} checks passed, {failed} failed")
    print(f"wrote {OUT_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
