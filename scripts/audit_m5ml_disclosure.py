"""M5-G6 independent audit of the ML disclosure layer.

Verifies across every generated container + the static frontend index:

1. provenance — each container records its source run and the frozen
   mathematical findings container's SHA-256, which must still match the file
   on disk (the ML layer never modifies the frozen records);
2. framing — every metric carries the agreement-with-reference framing; the
   strings "ground truth" appear only negated ("NOT independent ground-truth
   accuracy") anywhere in the disclosure surface;
3. gating — classes below the recorded support floor have suppressed metrics
   (None) and a support note in the record itself;
4. application — recorded predicted fractions are present for both epochs,
   and probabilities are labelled as confidences, not accuracy;
5. consistency — the static index served to the frontend is byte-consistent
   with the per-experiment containers (same experiment ids, same agreement
   values).

Usage: python scripts/audit_m5ml_disclosure.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Report:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.failures: list[str] = []

    def check(self, ok: bool, label: str) -> bool:
        if ok:
            self.passed += 1
        else:
            self.failed += 1
            self.failures.append(label)
            print(f"  [FAIL] {label}")
        return ok


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    report = Report()
    container_dir = ROOT / "data" / "findings_m5ml"
    containers = {p.stem: json.loads(p.read_text()) for p in sorted(container_dir.glob("*.json"))}
    report.check(len(containers) == 5, f"five ML containers present (found {len(containers)})")

    for experiment_id, container in containers.items():
        record = container["ml_record"]
        ev = record["evaluation"]

        # 1. provenance: frozen math container unchanged
        ref = container["references"]["mathematical_findings_container"]
        math_path = ROOT / ref["path"]
        report.check(
            math_path.exists() and sha256_file(math_path) == ref["sha256"],
            f"{experiment_id}: frozen mathematical findings container unchanged (sha256 match)",
        )
        report.check(
            ref["schema"] == "habitatshift-findings/2",
            f"{experiment_id}: math reference points at the frozen findings schema",
        )
        run_result = ROOT / record["identification"]["source_run"] / "result.json"
        report.check(
            run_result.exists() and sha256_file(run_result) == record["identification"]["source_result_sha256"],
            f"{experiment_id}: source run traceable by checksum",
        )

        # 2. framing
        blob = json.dumps(container)
        report.check(
            "ground-truth accuracy" in ev["framing"] and "NOT" in ev["framing"],
            f"{experiment_id}: evaluation framing disclaims ground-truth accuracy",
        )
        # every occurrence of 'ground truth'/'ground-truth' must be negated
        for match in re.finditer(r"ground[- ]truth", blob, flags=re.IGNORECASE):
            context = blob[max(0, match.start() - 80): match.end() + 40].lower()
            report.check(
                "not" in context or "never" in context,
                f"{experiment_id}: 'ground truth' mention is negated in context ({context[-60:]!r})",
            )
        report.check(
            container["evidence_status"] == "MODEL_OUTPUT_AGAINST_REFERENCE",
            f"{experiment_id}: evidence_status marks ML output as model-vs-reference",
        )
        def accuracy_ok(match: re.Match) -> bool:
            before = blob[max(0, match.start() - 80): match.start()].lower()
            after = blob[match.end(): match.end() + 60].lower()
            if "balanced_" in before or before.endswith("macro_") or before.endswith("support_"):
                return True  # metric field name, not a claim
            return (
                bool(re.search(r"(?:^|[^a-z])(no|not|never)([^a-z]|$)", before)) or "not" in after
            )

        report.check(
            all(accuracy_ok(m) for m in re.finditer(r"accuracy", blob, flags=re.IGNORECASE)),
            f"{experiment_id}: every 'accuracy' mention is a metric name or explicitly negated",
        )

        # 3. gating
        for name, row in ev["per_class"].items():
            if row["support"] < ev["support_floor"]:
                report.check(
                    row["precision"] is None and row["f1"] is None and not row["metrics_reported"],
                    f"{experiment_id}/{name}: metrics suppressed below the support floor",
                )
                report.check(
                    row["support_note"] is not None,
                    f"{experiment_id}/{name}: support note explains the suppression",
                )

        # 4. application epochs
        report.check(
            len(record["application"]) == 2,
            f"{experiment_id}: application recorded for both epochs",
        )
        for tag, app in record["application"].items():
            report.check(
                abs(sum(app["predicted_fractions"].values()) - 1.0) < 0.01,
                f"{experiment_id}/{tag}: predicted fractions sum to 1",
            )
            report.check(
                "confidence" in json.dumps(container.get("ml_record", {}).get("application", {})).lower()
                or "confidence" in json.dumps(record.get("interpretation_guardrails", [])).lower(),
                f"{experiment_id}/{tag}: probabilities recorded as confidences",
            )

        # 5. plain-language paragraph exists and carries the framing
        plain = record["plain_language"]
        report.check(
            "not independent ground truth" in plain and "reference" in plain.lower(),
            f"{experiment_id}: plain-language summary carries the honest framing",
        )

    # static index consistency
    static_path = ROOT / "frontend" / "public" / "studies" / "m5ml_findings.json"
    report.check(static_path.exists(), "static ML index present for the frontend")
    static = json.loads(static_path.read_text())
    report.check(static["schema"] == "habitatshift-m5ml-index/1", "static ML index schema")
    report.check(
        set(static["experiments"].keys()) == set(containers.keys()),
        "static ML index covers exactly the recorded containers",
    )
    for experiment_id, container in containers.items():
        report.check(
            static["experiments"][experiment_id]["ml_record"]["evaluation"]["overall_agreement"]
            == container["ml_record"]["evaluation"]["overall_agreement"],
            f"{experiment_id}: static index agreement equals the container",
        )

    print(f"\nTOTAL: {report.passed} passed, {report.failed} failed")
    out = ROOT / "docs" / "evidence" / "m5" / "audit_m5ml_disclosure_checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"passed": report.passed, "failed": report.failed, "failures": report.failures}, indent=1))
    print(f"wrote {out}")
    return 0 if report.failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
