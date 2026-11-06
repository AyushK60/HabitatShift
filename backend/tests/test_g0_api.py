"""API contract tests for the presentation-only M2-G0 routes."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.app.api import app as api_mod


def _client(tmp_path, monkeypatch):
    root = tmp_path / "g0"
    study = root / "demo"
    study.mkdir(parents=True)
    (study / "common_valid.png").write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")
    payload = {
        "presentation_version": "g0-1.0",
        "study_id": "demo",
        "coverage": {"common_valid_pixels": 12, "uniform_common": True},
    }
    (study / "quality.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(api_mod, "G0_PREVIEW_ROOT", root)
    return TestClient(api_mod.app), study


def test_presentation_endpoint_serves_quality_json(tmp_path, monkeypatch):
    http, _ = _client(tmp_path, monkeypatch)
    response = http.get("/api/m1/study/demo/presentation")
    assert response.status_code == 200
    assert response.json()["coverage"]["uniform_common"] is True


def test_presentation_endpoint_missing_assets_is_404(tmp_path, monkeypatch):
    http, _ = _client(tmp_path, monkeypatch)
    assert http.get("/api/m1/study/absent/presentation").status_code == 404


def test_g0_file_serving_and_traversal_guard(tmp_path, monkeypatch):
    http, _ = _client(tmp_path, monkeypatch)
    response = http.get("/files/g0/demo/common_valid.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    assert http.get("/files/g0/demo/x..y.png").status_code == 400
    assert http.get("/files/g0/absent/common_valid.png").status_code == 404
