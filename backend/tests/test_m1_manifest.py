"""M1 manifest schema, hashes and output-record tests."""

from __future__ import annotations

import hashlib
import json

import pytest

from backend.app.pipeline.provenance import (
    M1ManifestBuilder,
    M1ManifestError,
    hash_outputs,
    output_record,
    validate_m1_manifest,
)


def _valid_manifest() -> dict:
    return {
        "manifest_version": "m1-1.0",
        "generated_utc": "2026-11-06T00:00:00+00:00",
        "experiment_id": "test_m1",
        "study": {
            "study_id": "demo",
            "title": "Demo",
            "study_type": "coastal_ecotone",
            "question": "Does the manifest validate?",
        },
        "aoi": {
            "geojson": {"type": "Polygon", "coordinates": []},
            "bounds_4326": [82.0, 16.0, 82.1, 16.1],
            "analysis_crs": "EPSG:32644",
            "area_km2": 1.0,
        },
        "grid": {
            "crs": "EPSG:32644",
            "resolution_m": 10.0,
            "width": 10,
            "height": 10,
            "transform": [10.0, 0.0, 100.0, 0.0, -10.0, 200.0],
            "signature": "abcdef0123456789",
        },
        "catalog": {
            "endpoint": "https://example.invalid/v1",
            "collection": "sentinel-2-l2a",
            "provider": "test",
            "license": "test",
        },
        "periods": [
            {
                "period_id": "earlier",
                "anchor_date": "2020-03-26",
                "observation_dates": ["2020-03-26"],
                "item_ids": ["S2A_TEST"],
                "composite_method": "median",
                "observation_count": 1,
                "valid_fraction": 1.0,
                "indices": {"ndvi": {}},
            },
            {
                "period_id": "later",
                "anchor_date": "2025-03-25",
                "observation_dates": ["2025-03-25"],
                "item_ids": ["S2B_TEST"],
                "composite_method": "median",
                "observation_count": 1,
                "valid_fraction": 1.0,
                "indices": {"ndvi": {}},
            },
        ],
        "indices": {"ndvi": {}},
        "change": {"ndvi": {}},
        "processing": {
            "pipeline_version": "0.2.0-m1",
            "profile": "spectral_change_m1",
            "operations": ["read", "composite"],
            "parameters": {"thresholds": [0.15]},
        },
        "outputs": {"x": {"path": "x", "sha256": "0" * 64}},
        "software": {"python": "3"},
        "attribution": {
            "text": "Copernicus",
            "license": "free",
            "access_date_utc": "2026-11-06T00:00:00+00:00",
        },
        "verification": {"all_passed": True},
        "limitations": [],
    }


def test_minimal_manifest_validates():
    validate_m1_manifest(_valid_manifest())


@pytest.mark.parametrize(
    "missing",
    [
        "manifest_version",
        "experiment_id",
        "study",
        "grid",
        "periods",
        "indices",
        "change",
        "processing",
        "outputs",
        "verification",
        "limitations",
    ],
)
def test_missing_required_section_rejected(missing):
    payload = _valid_manifest()
    del payload[missing]
    with pytest.raises(Exception):
        validate_m1_manifest(payload)


def test_period_requires_scene_ids_and_dates():
    payload = _valid_manifest()
    del payload["periods"][0]["item_ids"]
    with pytest.raises(Exception):
        validate_m1_manifest(payload)


def test_builder_refuses_incomplete_manifest(tmp_path):
    builder = M1ManifestBuilder()
    builder.set("experiment_id", "incomplete")
    with pytest.raises(M1ManifestError):
        builder.write(tmp_path / "manifest.json")
    assert not (tmp_path / "manifest.json").exists()


def test_builder_writes_valid_manifest(tmp_path):
    builder = M1ManifestBuilder()
    builder.update(_valid_manifest())
    path = builder.write(tmp_path / "manifest.json")
    assert json.loads(path.read_text("utf-8"))["manifest_version"] == "m1-1.0"


def test_output_record_hash_matches_independent_sha256(tmp_path):
    path = tmp_path / "layer.tif"
    payload = b"synthetic raster bytes"
    path.write_bytes(payload)
    record = output_record(path, "raster")
    assert record["sha256"] == hashlib.sha256(payload).hexdigest()
    assert record["bytes"] == len(payload)
    assert record["kind"] == "raster"
    assert record["path"].endswith("layer.tif")

    mapping = hash_outputs({"layer": record})
    assert mapping == {record["path"]: record["sha256"]}


def test_hash_changes_when_bytes_change(tmp_path):
    path = tmp_path / "layer.bin"
    path.write_bytes(b"a")
    first = output_record(path, "summary")["sha256"]
    path.write_bytes(b"b")
    second = output_record(path, "summary")["sha256"]
    assert first != second
