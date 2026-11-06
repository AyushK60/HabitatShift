"""M1 API route tests against a synthetic on-disk study bundle."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.api import app as api_mod


@pytest.fixture
def client(tmp_path, monkeypatch):
    processed = tmp_path / "processed" / "m1"
    previews = tmp_path / "previews" / "m1"
    manifests = tmp_path / "manifests"
    study = processed / "demo"
    study_previews = previews / "demo"
    study.mkdir(parents=True)
    study_previews.mkdir(parents=True)
    manifests.mkdir(parents=True)

    raster = study / "delta_ndvi.tif"
    raster.write_bytes(b"II*\x00synthetic")
    png = study_previews / "delta_ndvi.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")
    legend = study_previews / "ndvi_legend.json"
    legend.write_text(json.dumps({"index": "ndvi", "breaks": []}), encoding="utf-8")

    summary = {
        "schema": "habitatshift-m1-summary/1",
        "experiment_id": "demo_m1",
        "study": {"study_id": "demo", "title": "Demo study"},
        "grid": {
            "crs": "EPSG:32644",
            "resolution_m": 10.0,
            "width": 2,
            "height": 2,
            "signature": "abcdef0123456789",
        },
        "periods": [
            {
                "period_id": "earlier",
                "observation_dates": ["2020-03-26"],
                "observation_count": 1,
                "indices": {"ndvi": {"stats": {"mean": 0.5}}},
                "previews": {"ndvi": str(study_previews / "earlier_ndvi.png")},
            },
            {
                "period_id": "later",
                "observation_dates": ["2025-03-25"],
                "observation_count": 1,
                "indices": {"ndvi": {"stats": {"mean": 0.4}}},
                "previews": {"ndvi": str(study_previews / "later_ndvi.png")},
            },
        ],
        "indices": {"ndvi": {"formula": "(NIR - Red) / (NIR + Red)"}},
        "change": {
            "ndvi": {
                "common_valid_fraction_of_aoi": 0.9,
                "primary_threshold": 0.15,
                "primary": {"decrease_area_ha": 1.0, "increase_area_ha": 2.0},
            }
        },
        "area_cross_check": {"aoi_raster_km2": 0.0004},
        "verification": {"all_passed": True, "check_count": 3},
        "limitations": ["synthetic study"],
        "generated_utc": "2026-11-06T00:00:00+00:00",
        "outputs": {
            "delta_ndvi_tif": {
                "kind": "raster",
                "path": str(raster),
                "bytes": raster.stat().st_size,
                "sha256": "0" * 64,
            },
            "delta_ndvi_png": {
                "kind": "preview",
                "path": str(png),
                "bytes": png.stat().st_size,
                "sha256": "1" * 64,
            },
        },
    }
    (study / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (study / "status.json").write_text(
        json.dumps({"status": "complete", "stages": []}), encoding="utf-8"
    )
    manifest = {
        "manifest_version": "m1-1.0",
        "experiment_id": "demo_m1",
        "periods": [],
    }
    (manifests / "m1_demo.json").write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(api_mod, "M1_ROOT", processed)
    monkeypatch.setattr(api_mod, "M1_PREVIEW_ROOT", previews)
    monkeypatch.setattr(api_mod.config, "MANIFEST_DIR", manifests)
    return TestClient(api_mod.app), study, study_previews, summary


def test_health_lists_m1_studies(client):
    http, *_ = client
    payload = http.get("/api/health").json()
    assert payload["m1_studies"] == ["demo"]
    assert payload["m1_pipeline_version"]


def test_studies_endpoint(client):
    http, *_ = client
    payload = http.get("/api/m1/studies").json()
    assert payload["studies"][0]["study_id"] == "demo"
    assert payload["studies"][0]["verification_passed"] is True
    assert payload["studies"][0]["status"] == "complete"


def test_study_summary_and_status(client):
    http, _, _, summary = client
    assert http.get("/api/m1/study/demo").json()["experiment_id"] == "demo_m1"
    status = http.get("/api/m1/study/demo/status").json()
    assert status["status"] == "complete"


def test_layers_resolve_scopes_and_urls(client):
    http, *_ = client
    payload = http.get("/api/m1/study/demo/layers").json()
    names = {layer["name"]: layer for layer in payload["layers"]}
    assert names["delta_ndvi_tif"]["scope"] == "processed"
    assert names["delta_ndvi_png"]["scope"] == "previews"
    assert names["delta_ndvi_png"]["url"] == "/files/m1/demo/previews/delta_ndvi.png"
    assert names["delta_ndvi_png"]["content_type"] == "image/png"
    assert payload["grid"]["signature"] == "abcdef0123456789"


def test_indices_and_change_endpoints(client):
    http, *_ = client
    indices = http.get("/api/m1/study/demo/indices").json()
    assert indices["periods"]["earlier"]["observation_dates"] == ["2020-03-26"]
    assert indices["indices"]["ndvi"]["formula"].startswith("(NIR")
    change = http.get("/api/m1/study/demo/change").json()
    assert change["change"]["ndvi"]["primary_threshold"] == 0.15
    assert change["limitations"] == ["synthetic study"]


def test_provenance_and_manifest_alias(client):
    http, *_ = client
    assert http.get("/api/m1/study/demo/provenance").json()["manifest_version"] == "m1-1.0"
    assert http.get("/api/m1/study/demo/manifest").json()["experiment_id"] == "demo_m1"


def test_file_serving_and_traversal_guard(client):
    http, *_ = client
    response = http.get("/files/m1/demo/previews/delta_ndvi.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    assert http.get("/files/m1/demo/previews/x..y.png").status_code == 400
    assert http.get("/files/m1/demo/bad-scope/x.png").status_code == 404
    assert http.get("/files/m1/nope/previews/x.png").status_code == 404


def test_unknown_study_returns_404(client):
    http, *_ = client
    assert http.get("/api/m1/study/unknown").status_code == 404


def test_missing_summary_returns_503(client, monkeypatch):
    http, study, *_ = client
    (study / "summary.json").unlink()
    assert http.get("/api/m1/study/demo").status_code == 503


def test_m0_summary_route_reports_missing_artifact(client, monkeypatch, tmp_path):
    http, *_ = client
    monkeypatch.setattr(api_mod, "SUMMARY_PATH", tmp_path / "absent.json")
    response = http.get("/api/study")
    assert response.status_code == 503
    assert "not found" in response.json()["detail"]
