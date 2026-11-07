"""M3-G0 tests: georeference, pixel sampling, ROI and product-serving routes.

These endpoints are additive read paths over the frozen M1 artefacts.  The
tests assert that every returned number traces to the exported GeoTIFFs and
the stored M1 summary, and that the labelling rule of
`docs/architecture/M3_ARCHITECTURE_DECISION.md` (D5) is enforced.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.app import app

client = TestClient(app, raise_server_exceptions=False)
STUDY = "coringa_coastal"

# Grid centre of the frozen M1 study (EPSG:32644 632700–636990 / 1847890–1851790).
AOI_LON_LAT = (82.2649, 16.7275)
OUTSIDE_LON_LAT = (80.0, 16.728)


def _m1_summary() -> dict:
    root = Path(__file__).resolve().parents[2]
    return json.loads(
        (root / "data" / "processed" / "m1" / STUDY / "summary.json").read_text("utf-8")
    )


def test_georef_corners_match_grid_bounds() -> None:
    response = client.get(f"/api/m1/study/{STUDY}/georef")
    assert response.status_code == 200
    payload = response.json()
    grid = _m1_summary()["grid"]
    assert payload["grid"]["signature"] == grid["signature"]
    assert payload["bounds_utm"] == grid["bounds"]
    corners = payload["corners_wgs84"]
    assert len(corners) == 4
    lons = [c[0] for c in corners]
    lats = [c[1] for c in corners]
    # The AOI declared in studies/registry.yaml (82.245–82.285, 16.71–16.745).
    assert min(lons) == pytest.approx(82.245, abs=2e-3)
    assert max(lons) == pytest.approx(82.285, abs=2e-3)
    assert min(lats) == pytest.approx(16.710, abs=2e-3)
    assert max(lats) == pytest.approx(16.745, abs=2e-3)
    centre = payload["centre_wgs84"]
    assert min(lons) < centre[0] < max(lons)
    assert min(lats) < centre[1] < max(lats)


def test_pixel_returns_measured_values_inside_grid() -> None:
    response = client.get(
        f"/api/m1/study/{STUDY}/pixel",
        params={"lon": AOI_LON_LAT[0], "lat": AOI_LON_LAT[1]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["inside_grid"] is True
    assert payload["inside_aoi"] is True
    assert payload["source"] == "full-resolution server-side GeoTIFF sample"
    summary = _m1_summary()
    periods = payload["periods"]
    assert len(periods) == len(summary["periods"])
    for period, stored in zip(periods, summary["periods"]):
        assert period["period_id"] == stored["period_id"]
        assert period["observation_count"] == stored["observation_count_stats"]["max"]
        # Reflectance must lie in the physical 0–1 surface-reflectance range.
        for band, value in period["reflectance"].items():
            assert value is None or 0.0 <= value <= 1.0, band
        for key, value in period["indices"].items():
            assert value is None or -1.0 <= value <= 1.0, key
    # NDVI from bands must equal the stored NDVI raster value (float32 read).
    earlier = periods[0]
    nir = earlier["reflectance"]["nir_B08"]
    red = earlier["reflectance"]["red_B04"]
    ndvi_from_bands = (nir - red) / (nir + red)
    assert ndvi_from_bands == pytest.approx(earlier["indices"]["ndvi"], abs=1e-4)


def test_pixel_outside_grid_reports_honestly() -> None:
    response = client.get(
        f"/api/m1/study/{STUDY}/pixel",
        params={"lon": OUTSIDE_LON_LAT[0], "lat": OUTSIDE_LON_LAT[1]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "outside_grid"
    assert payload["inside_grid"] is False
    assert "periods" not in payload


def test_roi_labels_full_resolution_source_and_matches_summary_thresholds() -> None:
    summary = _m1_summary()
    response = client.get(
        f"/api/m1/study/{STUDY}/roi",
        params={"west": 82.26, "south": 16.72, "east": 82.27, "north": 16.73},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "full-resolution server-side GeoTIFF window"
    assert payload["resolution_m"] == summary["grid"]["resolution_m"]
    # Area conservation on the common-valid footprint must hold per index.
    for key, block in payload["indices"].items():
        if "delta_stats" not in block:
            continue
        assert (
            block["decrease_pixels"] + block["increase_pixels"]
            <= block["common_valid_pixels"]
        )
        stored_threshold = summary["change"][key]["primary_threshold"]
        assert block["primary_threshold"] == stored_threshold


def test_roi_rejects_inverted_window() -> None:
    response = client.get(
        f"/api/m1/study/{STUDY}/roi",
        params={"west": 82.27, "south": 16.73, "east": 82.26, "north": 16.72},
    )
    assert response.status_code == 400


def test_registry_served_as_yaml() -> None:
    response = client.get("/api/studies/registry")
    assert response.status_code == 200
    assert "text/yaml" in response.headers["content-type"]
    body = response.text
    # Status vocabulary from the registry itself, no invented statuses.
    assert "status: processed" in body
    assert "status: feasibility" in body
