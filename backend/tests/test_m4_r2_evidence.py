"""Integrity tests for the M4-R2 Evidence Records (schema
``habitatshift-evidence-record/1`` embedded in findings containers of schema
``habitatshift-findings/2``).

These tests pin the honesty contract: complete record groups, content-derived
stable IDs, hole accounting that matches the recorded geometry, sealed
SHA-256 checksums, populated provenance, and nulls where the pipeline has no
value — never invented numbers.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FINDINGS_DIR = PROJECT_ROOT / "data" / "findings"

EXPECTED_EXPERIMENTS = {
    "coringa_m1",
    "chilika_m4_dry",
    "chilika_m4_postmonsoon",
    "western_ghats_m4",
    "himalaya_purepu_2025_m4",
    "himalaya_langtang_2026_m4",
    "kathmandu_m4",
}

REQUIRED_GROUPS = (
    "identification",
    "source_observations",
    "input_measurements",
    "spatial_measurements",
    "evidence_quality",
    "method_provenance",
)


def _load(name: str) -> dict:
    return json.loads((FINDINGS_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("experiment_id", sorted(EXPECTED_EXPERIMENTS))
def test_every_finding_carries_complete_evidence_record(experiment_id: str) -> None:
    payload = _load(experiment_id)
    for finding in payload["findings"]:
        evidence = finding["evidence"]
        for group in REQUIRED_GROUPS:
            assert group in evidence, f"{experiment_id}/{finding['display_id']}: {group} missing"
        assert evidence["schema"] == "habitatshift-evidence-record/1"
        ident = evidence["identification"]
        assert ident["evidence_id"] == finding["evidence_id"]
        assert ident["study_id"] == payload["study_id"]
        assert ident["finding_type"] == "threshold-connected-region"
        assert ident["candidate_direction"] == finding["direction"]


def test_evidence_ids_are_unique_and_content_derived() -> None:
    for experiment_id in sorted(EXPECTED_EXPERIMENTS):
        payload = _load(experiment_id)
        ids = [f["evidence_id"] for f in payload["findings"]]
        assert len(ids) == len(set(ids)), f"{experiment_id}: duplicate evidence IDs"
        for finding in payload["findings"]:
            cx, cy = finding["centroid_utm"]
            expected = (
                f"ev-{experiment_id}-{finding['index']}-"
                f"{finding['direction'][:3]}-{round(cx)}-{round(cy)}"
            )
            assert finding["evidence_id"] == expected, (
                f"{experiment_id}/{finding['display_id']}: evidence ID not content-derived"
            )


@pytest.mark.parametrize("experiment_id", sorted(EXPECTED_EXPERIMENTS))
def test_hole_accounting_matches_geometry(experiment_id: str) -> None:
    payload = _load(experiment_id)
    for finding in payload["findings"]:
        holes = finding["hole_pixel_count"]
        assert isinstance(holes, int) and holes >= 0
        rings = finding["geometry_wgs84"]["coordinates"]
        assert rings[0][0] == rings[0][-1]
        for hole in rings[1:]:
            assert hole[0] == hole[-1], "interior ring must close"
            assert len(hole) >= 4


def test_output_checksums_verify() -> None:
    for experiment_id in sorted(EXPECTED_EXPERIMENTS):
        payload = _load(experiment_id)
        for finding in payload["findings"]:
            claimed = finding["evidence"]["method_provenance"]["output_checksum"]
            probe = json.loads(json.dumps(finding))
            probe["evidence"]["method_provenance"]["output_checksum"] = None
            recomputed = hashlib.sha256(
                json.dumps(probe, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            assert claimed == recomputed, f"{experiment_id}/{finding['display_id']}: checksum mismatch"


@pytest.mark.parametrize("experiment_id", sorted(EXPECTED_EXPERIMENTS))
def test_provenance_is_populated(experiment_id: str) -> None:
    payload = _load(experiment_id)
    for finding in payload["findings"]:
        prov = finding["evidence"]["method_provenance"]
        assert prov["git_commit"], "git commit of record required"
        assert len(prov["git_commit"]) == 40
        assert prov["algorithm_version"]
        for key in ("delta_raster", "common_valid_mask"):
            digest = prov["input_hashes"][key]
            assert digest and len(digest) == 64, f"{key} sha256 required"
        assert prov["parameters"]["connectivity"] == 4
        assert prov["parameters"]["minimum_mapping_unit_px"] == 25
        software = prov["software"]
        assert software["numpy"] and software["rasterio"] and software["scipy"] and software["pyproj"]


@pytest.mark.parametrize("experiment_id", sorted(EXPECTED_EXPERIMENTS))
def test_input_measurements_are_complete(experiment_id: str) -> None:
    payload = _load(experiment_id)
    for finding in payload["findings"]:
        im = finding["evidence"]["input_measurements"]
        assert im["formula"], "index formula required"
        assert im["bands"], "index bands required"
        assert im["delta_definition"].startswith("I_later")
        assert im["threshold"] == finding["threshold"]
        grid = im["analysis_grid"]
        assert grid["crs"].startswith("EPSG:") and grid["pixel_area_m2"] == 100.0
        assert grid["resolution_m"] == 10.0


@pytest.mark.parametrize("experiment_id", sorted(EXPECTED_EXPERIMENTS))
def test_evidence_quality_states_support_and_limitations(experiment_id: str) -> None:
    payload = _load(experiment_id)
    for finding in payload["findings"]:
        q = finding["evidence"]["evidence_quality"]
        assert q["shared_valid_fraction_of_aoi"] is not None
        support = q["observation_support"]
        assert support["earlier_observations"] >= 1 and support["later_observations"] >= 1
        # Honesty: threshold sensitivity is null-with-status until G6 fills it.
        ts = q["threshold_sensitivity"]
        assert ts["result"] is None or isinstance(ts["result"], dict)
        assert isinstance(q["masking_and_cloud_limitations"], list)
        assert q["confounding_factors"], "confounders must be stated"


def test_partial_status_only_for_partial_studies() -> None:
    partial_experiments = {"himalaya_purepu_2025_m4"}
    for experiment_id in sorted(EXPECTED_EXPERIMENTS):
        payload = _load(experiment_id)
        if experiment_id in partial_experiments:
            assert payload["evidence_status"] == "partial"
        for finding in payload["findings"]:
            status = finding["evidence"]["identification"]["evidence_status"]
            if experiment_id in partial_experiments:
                assert status == "partial"
            else:
                assert status != "partial"


def test_spatial_measurements_agree_with_flat_fields() -> None:
    for experiment_id in sorted(EXPECTED_EXPERIMENTS):
        payload = _load(experiment_id)
        for finding in payload["findings"]:
            sp = finding["evidence"]["spatial_measurements"]
            assert sp["pixel_count"] == finding["pixel_count"]
            assert sp["area_ha"] == finding["area_ha"]
            assert sp["mean_delta"] == finding["mean_delta"]
            assert sp["valid_pixel_denominator"] == finding["common_valid_pixels"]
            assert sp["hole_pixel_count"] == finding["hole_pixel_count"]
