"""The numbers in the technical report must match the recorded outputs they were taken from."""
from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "paper" / "report" / "paper.md"
STUDIES = ROOT / "frontend" / "public" / "studies"
EXP = ROOT / "data" / "experiments"
V3 = ROOT / "frontend" / "public" / "research" / "v3.json"
EVIDENCE = ROOT / "docs" / "evidence"

pytestmark = pytest.mark.skipif(not REPORT.exists(), reason="report source missing")


def fmt(x: float, places: int) -> str:
    q = Decimal(1).scaleb(-places)
    return str(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def row(text: str, label: str) -> str:
    return next(line for line in text.splitlines() if line.startswith("| " + label))


def test_random_forest_table_matches_findings():
    path = STUDIES / "m5ml_findings.json"
    if not path.exists():
        pytest.skip("findings bundle missing")
    text, data = REPORT.read_text(encoding="utf-8"), json.loads(path.read_text(encoding="utf-8"))["experiments"]
    names = {"Chilika (dry)": "chilika_m4_dry", "Chilika (post-monsoon)": "chilika_m4_postmonsoon",
             "Western Ghats": "western_ghats_m4", "Coringa": "coringa_m1", "Kathmandu": "kathmandu_m4"}
    section = text[text.index("Table: Random Forest agreement"):]
    for label, key in names.items():
        record = data[key]["ml_record"]
        ev = record["evaluation"]
        folds = [f["overall_agreement"] for f in record["geographic_stability"]["folds"] if f.get("available")]
        cells = [c.strip() for c in row(section, label).strip("|").split("|")]
        assert cells[1] == fmt(ev["overall_agreement"], 3), (label, cells)
        assert cells[2] == fmt(ev["macro_f1_supported_classes"], 3), (label, cells)
        assert cells[3] == f"{fmt(min(folds), 3)} to {fmt(max(folds), 3)}", (label, cells)


def test_noise_table_matches_recorded_results():
    text = REPORT.read_text(encoding="utf-8")
    rows = {"Western Ghats NDVI": ("western_ghats_m4", "ndvi"), "Chilika (dry) NDVI": ("chilika_m4_dry", "ndvi"),
            "Chilika (dry) NDWI": ("chilika_m4_dry", "ndwi"), "Kathmandu NDBI": ("kathmandu_m4", "ndbi"),
            "Chilika (post-monsoon) NDWI": ("chilika_m4_postmonsoon", "ndwi"), "Coringa MNDWI": ("coringa_m1", "mndwi")}
    section = text[text.index("Table: Share of fixed-rule"):]
    for label, (study, index) in rows.items():
        path = EXP / "m6_noise" / study / "result.json"
        if not path.exists():
            pytest.skip("noise results missing")
        v = json.loads(path.read_text())["per_index"][index]["by_k"]["3.0"]
        cells = [c.strip() for c in row(section, label).strip("|").split("|")]
        assert cells[1] == f"{v['fixed_rule_pixels_testable']:,}", (label, cells)
        assert cells[2] == f"{fmt(100 * v['fixed_rule_share_noise_supported'], 1)}%", (label, cells)


def test_hansen_validation_and_time_series_numbers():
    text = REPORT.read_text(encoding="utf-8")
    vpath = EXP / "m6_validation" / "western_ghats_m4" / "result.json"
    if not vpath.exists():
        pytest.skip("validation results missing")
    m = json.loads(vpath.read_text())["main"]["fixed_rule_ndvi_decrease"]
    assert f"{round(100 * m['recall'])}% of Hansen forest loss" in text
    assert f"{m['tp']} of {m['tp'] + m['fn']} pixels" in text
    assert f"precision {fmt(m['precision'], 3)}, {m['tp']} of {m['tp'] + m['fp']} flagged" in text
    for study, label in (("kathmandu_m4", "Kathmandu"), ("western_ghats_m4", "Western Ghats")):
        model = json.loads((EXP / "m6_timeseries" / study / "result.json").read_text())["model"]
        lo, hi = model["trend_ci95"]
        assert fmt(model["trend_per_year"], 4).replace("-", "$-") in text or fmt(model["trend_per_year"], 4) in text
        assert fmt(lo, 4) in text and fmt(hi, 4) in text, label


def test_water_crosscheck_numbers():
    text = REPORT.read_text(encoding="utf-8")
    data = {s: json.loads((EXP / "m5_gsw" / s / "result.json").read_text()) for s in ("chilika_dry", "coringa")}
    chilika = [r["water_overlap_iou"] for r in data["chilika_dry"]["results_by_gsw_threshold"]]
    coringa = [r["water_overlap_iou"] for r in data["coringa"]["results_by_gsw_threshold"]]
    assert f"{fmt(min(chilika[:3]), 2)} to {fmt(max(chilika[:3]), 2)} for Chilika" in text
    assert f"drops to {fmt(chilika[3], 2)}" in text or f"dropping to {fmt(chilika[3], 2)}" in text
    assert f"{fmt(min(coringa), 2)} to {fmt(max(coringa), 2)}" in text
    assert f"{fmt(100 * data['chilika_dry']['worldcover_water_fraction'], 1)}% of the area water" in text


def test_audit_counts_match_evidence_files():
    text = REPORT.read_text(encoding="utf-8")
    files = {"Independent scientific audit": EVIDENCE / "m5" / "audit_m5_science_checks.json",
             "Machine-learning reproducibility audit": EVIDENCE / "m5" / "audit_m5_ml_checks.json"}
    for label, path in files.items():
        if not path.exists():
            pytest.skip("audit evidence missing")
        d = json.loads(path.read_text())
        assert d["failed"] == 0
        assert f"{d['passed']:,} of {d['passed']:,}" in row(text, label), label
    disclosure = json.loads((EVIDENCE / "m5" / "audit_m5ml_disclosure_checks.json").read_text())
    assert disclosure["failed"] == 0 and f"{disclosure['passed']} of {disclosure['passed']}" in text


def test_unet_and_coverage_numbers_match_v3_bundle():
    if not V3.exists():
        pytest.skip("results bundle missing")
    text, data = REPORT.read_text(encoding="utf-8"), json.loads(V3.read_text())
    sets = data["unet"]["sets"]
    held, unseen = sets["time_holdout_2022_same_lakes"], sets["test_lakes"]
    assert f"| {held['n_pairs']} | {fmt(held['unet_mean'], 2)}" in text and f"| {fmt(held['otsu'], 2)} |" in text
    assert f"| {unseen['n_pairs']} | {fmt(unseen['unet_mean'], 2)}" in text and f"| {fmt(unseen['otsu'], 2)} |" in text
    for c in data["unet"]["cv"]["coverage"].values():
        line = f"| {round(c['target'] * 100)}% | {round(c['achieved'] * 100)}% | {c['lakes_below_target']} of 30 |"
        assert line in text, line


def test_version3_claims_match_forest_results():
    if not V3.exists():
        pytest.skip("results bundle missing")
    data = json.loads(V3.read_text())["forest"]
    assert len(data) == 5 and "five forest areas" in REPORT.read_text(encoding="utf-8")
    for area in data.values():
        rows = {r["id"]: r for r in area["rows"]}
        best_fm = max(rows["prithvi"]["ap"], rows["ssl4eo_rgb"]["ap"])
        assert rows["ndvi_decrease"]["ap"] >= best_fm, area["title"]
