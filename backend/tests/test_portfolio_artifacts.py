"""Consistency checks on the post-M5 recorded artifacts (offline, no rasters needed).

* JRC GSW cross-check: contingency cells add up, metrics are in range, sources recorded.
* Complete-component inventory: totals equal the audited selection policy.
* Resolution sensitivity: schema, and that the 10 m side equals the recorded manifest.
* Figures builder: runs from recorded artifacts only.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GSW = ROOT / "data" / "experiments" / "m5_gsw"
INV = ROOT / "data" / "experiments" / "m5_inventory"
RES = ROOT / "data" / "experiments" / "m5_resolution"


@pytest.mark.parametrize("study", ["chilika_dry", "chilika_postmonsoon", "coringa"])
def test_gsw_crosscheck_is_internally_consistent(study):
    data = json.loads((GSW / study / "result.json").read_text(encoding="utf-8"))
    assert data["schema"] == "habitatshift-m5-gsw-crosscheck/1"
    assert "neither is ground truth" in data["framing"]
    assert data["sources"]["jrc_gsw"]["licence"].startswith("CC-BY 4.0")
    assert data["sources"]["worldcover"]["licence"].startswith("CC-BY 4.0")
    for row in data["results_by_gsw_threshold"]:
        cells = (
            row["worldcover_water_and_gsw_water"], row["worldcover_water_only"],
            row["gsw_water_only"], row["neither"],
        )
        assert sum(cells) == data["valid_pixels"]
        assert 0.0 <= row["overall_agreement"] <= 1.0
        assert row["water_overlap_iou"] is None or 0.0 <= row["water_overlap_iou"] <= 1.0
    thresholds = [r["gsw_occurrence_threshold_percent"] for r in data["results_by_gsw_threshold"]]
    assert thresholds == sorted(thresholds)


def test_component_inventory_matches_audited_selection_policy():
    policy = json.loads((ROOT / "frontend/public/studies/selection_policy.json").read_text(encoding="utf-8"))
    expected = {e["experiment_id"]: e["components_at_or_above_mmu_total"] for e in policy["experiments"]}
    assert expected, "selection policy lists no experiments"
    for experiment, total in expected.items():
        summary = json.loads((INV / experiment / "summary.json").read_text(encoding="utf-8"))
        assert summary["matches_selection_policy"] is True
        assert summary["components_at_or_above_mmu_total"] == total
        per_index = sum(
            d["components_at_or_above_mmu"] for idx in summary["by_index"].values() for d in idx.values()
        )
        assert per_index == total
        rows = (INV / experiment / "components.csv").read_text(encoding="utf-8").strip().splitlines()
        assert len(rows) - 1 == total  # header + one row per component


def test_resolution_sensitivity_records_the_unchanged_10m_run():
    result = json.loads((RES / "kathmandu_m4" / "result.json").read_text(encoding="utf-8"))
    assert result["resolution_m"] == 20.0 and result["recorded_resolution_m"] == 10.0
    manifest = json.loads((ROOT / "data" / "manifests" / "m4_kathmandu_m4.json").read_text(encoding="utf-8"))
    for index, row in result["per_index"].items():
        block = manifest["change"][index]
        assert row["common_valid_pixels_10m"] == block["common_valid_pixels"]
        primary = next(r for r in block["thresholds"] if abs(r["threshold"] - block["primary_threshold"]) < 1e-9)
        pct = 100 * primary["decrease_pixels"] / block["common_valid_pixels"]
        assert abs(row["decrease_percent_10m"] - pct) < 1e-9
        assert row["common_valid_pixels_20m"] < row["common_valid_pixels_10m"]


def test_figures_build_from_recorded_artifacts(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_portfolio_figures", ROOT / "scripts" / "build_portfolio_figures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "OUT", tmp_path)
    assert module.main() == 0
    names = sorted(p.name for p in tmp_path.glob("*.svg"))
    assert names == [
        "fig1_rf_agreement.svg",
        "fig2_two_methods_direction.svg",
        "fig3_water_reference_crosscheck.svg",
    ]
    for path in tmp_path.glob("*.svg"):
        text = path.read_text(encoding="utf-8")
        assert text.startswith("<svg") and "aria-label" in text


def test_inventory_bundle_matches_recorded_summaries():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    bundle = json.loads((root / "frontend/public/studies/m5_inventory.json").read_text(encoding="utf-8"))
    assert len(bundle["experiments"]) == 7
    for item in bundle["experiments"]:
        summary = json.loads(
            (root / "data/experiments/m5_inventory" / item["experiment"] / "summary.json").read_text(encoding="utf-8")
        )
        assert item["total"] == summary["components_at_or_above_mmu_total"]
        assert item["matches_selection_policy"] is True
        assert (root / "frontend/public" / item["csv"]).exists()


def test_scene_timeseries_covers_every_recorded_scene():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    doc = json.loads((root / "frontend/public/studies/m5_timeseries.json").read_text(encoding="utf-8"))
    assert len(doc["studies"]) == 7
    for study in doc["studies"]:
        assert study["scenes_found"] == study["scenes_expected"], study["key"]
        for scene in study["scenes"]:
            assert scene["valid_pixels"] > 0
            assert -1.0 <= scene["mean"]["ndvi"] <= 1.0


def test_noise_aware_threshold_reproduces_recorded_fixed_rule():
    root = Path(__file__).resolve().parents[2]
    bundle = json.loads((root / "frontend/public/studies/m6_noise.json").read_text(encoding="utf-8"))
    assert len(bundle["experiments"]) == 7
    tested = 0
    for exp in bundle["experiments"]:
        for index, row in exp["per_index"].items():
            if row["status"] != "ok":
                continue
            tested += 1
            # the fixed rule recomputed from the delta raster must equal the sealed manifest counts
            assert row["fixed_threshold_cross_check_matches_manifest"] is True, (exp["experiment"], index)
            for k in row["by_k"].values():
                share = k["fixed_rule_share_noise_supported"]
                assert share is None or 0.0 <= share <= 1.0
    assert tested >= 15


def test_hansen_validation_is_consistent():
    root = Path(__file__).resolve().parents[2]
    doc = json.loads((root / "frontend/public/studies/m6_validation.json").read_text(encoding="utf-8"))
    r = doc["result"]
    assert r["reference"]["licence"] == "CC-BY 4.0"
    c = r["main"]["fixed_rule_ndvi_decrease"]
    assert c["tp"] + c["fn"] == r["reference_loss_pixels_in_domain"]
    assert c["tp"] + c["fp"] == r["predicted_decrease_pixels_in_domain"]
    assert c["tp"] + c["fp"] + c["fn"] + c["tn"] == r["domain_pixels"]


@pytest.mark.parametrize("experiment", ["kathmandu_m4", "western_ghats_m4"])
def test_monthly_timeseries_is_well_formed(experiment):
    root = Path(__file__).resolve().parents[2]
    doc = json.loads((root / f"frontend/public/studies/m6_timeseries/{experiment}.json").read_text(encoding="utf-8"))
    pts = doc["points"]
    months = [p["month"] for p in pts]
    assert months == sorted(set(months)), "one scene per month, in order"
    assert len(pts) >= 12 and doc["model"]["n_months"] == len(pts)
    assert all(-1.0 <= p["mean"]["ndvi"] <= 1.0 for p in pts)
    low, high = doc["model"]["trend_ci95"]
    assert low <= doc["model"]["trend_per_year"] <= high
    assert len(doc["comparison_anchors"]) == 2
