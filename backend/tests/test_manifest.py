"""Provenance manifest completeness and output records."""

from __future__ import annotations

import json

import pytest

from backend.app.provenance import manifest as manifest_mod


def _complete_manifest() -> dict:
    return {
        "manifest_version": "1.0",
        "generated_utc": "2026-11-04T10:00:00+00:00",
        "study": {
            "study_id": "coringa_coastal",
            "title": "Coringa",
            "study_type": "coastal_ecotone",
            "question": "Q?",
        },
        "aoi": {
            "geojson": {"type": "Feature"},
            "bounds_4326": [82.24, 16.71, 82.28, 16.74],
            "crs": "EPSG:4326",
            "analysis_crs": "EPSG:32644",
            "area_km2": 17.5,
            "grid": {
                "resolution_m": 10.0,
                "transform": [10.0, 0.0, 500000.0, 0.0, -10.0, 1850000.0],
                "width": 429,
                "height": 390,
            },
        },
        "catalog": {
            "endpoint": "https://earth-search.aws.element84.com/v1",
            "collection": "sentinel-2-l2a",
            "provider": "Element 84",
            "license": "Copernicus",
        },
        "periods": [
            {
                "period_id": pid,
                "scene": {"item_id": f"ITEM_{pid}"},
                "acquisition_date": "2020-03-26",
                "valid_fraction": 0.99,
                "mask_policy": {"rejected_scl_classes": ["9"]},
                "outputs": {},
            }
            for pid in ("earlier", "later")
        ],
        "processing": {
            "pipeline_version": "0.1.0-m0",
            "profile": "coastal_ndvi_m0",
            "operations": ["read", "mask", "ndvi"],
            "parameters": {"scale": 0.0001},
        },
        "outputs": {"ndvi": {"path": "data/processed/x.tif", "sha256": "abc"}},
        "software": {"python": "3.11.9"},
        "attribution": {
            "text": "Contains modified Copernicus Sentinel data",
            "license": "Copernicus",
            "access_date_utc": "2026-11-04T10:00:00+00:00",
        },
        "validity": {
            "comparable_valid_fraction": 0.98,
            "suitable_for_comparison": True,
        },
    }


def test_complete_manifest_validates():
    manifest_mod.validate_manifest(_complete_manifest())


@pytest.mark.parametrize(
    "missing",
    [
        "study",
        "aoi",
        "catalog",
        "periods",
        "processing",
        "outputs",
        "software",
        "attribution",
        "validity",
    ],
)
def test_each_missing_section_is_rejected(missing):
    payload = _complete_manifest()
    del payload[missing]
    with pytest.raises(Exception):
        manifest_mod.validate_manifest(payload)


def test_builder_raises_when_incomplete():
    builder = manifest_mod.ManifestBuilder()
    builder.set("study", {"study_id": "x"})
    with pytest.raises(manifest_mod.ManifestError):
        builder.validate()


def test_builder_writes_valid_file(tmp_path):
    builder = manifest_mod.ManifestBuilder()
    builder.update(_complete_manifest())
    # generated_utc from the builder wins; keep the rest
    target = tmp_path / "m.json"
    builder.write(target)
    saved = json.loads(target.read_text("utf-8"))
    manifest_mod.validate_manifest(saved)


def test_single_period_is_rejected():
    payload = _complete_manifest()
    payload["periods"] = payload["periods"][:1]
    with pytest.raises(Exception):
        manifest_mod.validate_manifest(payload)


def test_bad_period_id_is_rejected():
    payload = _complete_manifest()
    payload["periods"][0]["period_id"] = "middle"
    with pytest.raises(Exception):
        manifest_mod.validate_manifest(payload)


def test_valid_fraction_range_enforced():
    payload = _complete_manifest()
    payload["validity"]["comparable_valid_fraction"] = 1.5
    with pytest.raises(Exception):
        manifest_mod.validate_manifest(payload)


def test_describe_output_records_checksum(tmp_path):
    target = tmp_path / "artifact.png"
    target.write_bytes(b"payload")
    record = manifest_mod.describe_output(target, "preview")
    assert record["bytes"] == 7
    assert len(record["sha256"]) == 64
    assert record["kind"] == "preview"


def test_sha256_is_stable(tmp_path):
    target = tmp_path / "a.bin"
    target.write_bytes(b"same")
    assert manifest_mod.sha256_file(target) == manifest_mod.sha256_file(target)
