"""AOI validation and analysis-grid derivation."""

from __future__ import annotations

import math

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine
from shapely.geometry import Polygon, box

from backend.app.preprocess import aoi as aoi_mod
from backend.app.preprocess import grid as grid_mod


def test_valid_bounds_produce_polygon(aoi):
    assert aoi.polygon.is_valid
    assert aoi.polygon.area > 0
    assert aoi.area_km2() == pytest.approx(17.5, abs=2.0)
    assert aoi.utm_epsg == 32644, "Coringa sits in UTM zone 44N"


def test_bounds_must_not_be_inverted():
    with pytest.raises(aoi_mod.AOIError):
        aoi_mod.aoi_from_bounds(
            study_id="x", west=82.3, south=16.7, east=82.2, north=16.6,
            description="", source="",
        )


def test_empty_and_degenerate_polygons_rejected():
    with pytest.raises(aoi_mod.AOIError):
        aoi_mod.validate_polygon(Polygon(), study_id="empty")
    with pytest.raises(aoi_mod.AOIError):
        aoi_mod.validate_polygon(
            Polygon([(82.0, 16.0), (82.0, 16.0), (82.0, 16.0)]), study_id="pointy"
        )


def test_tiny_area_rejected():
    with pytest.raises(aoi_mod.AOIError, match="below"):
        aoi_mod.aoi_from_bounds(
            study_id="tiny", west=82.2450, south=16.7100, east=82.2452,
            north=16.7102, description="", source="",
        )


def test_oversized_area_rejected():
    with pytest.raises(aoi_mod.AOIError, match="above"):
        aoi_mod.aoi_from_bounds(
            study_id="huge", west=70.0, south=8.0, east=90.0, north=30.0,
            description="", source="",
        )


def test_longitude_out_of_range_rejected():
    with pytest.raises(aoi_mod.AOIError, match="longitude"):
        aoi_mod.validate_polygon(
            Polygon([(200.0, 16.0), (201.0, 16.0), (201.0, 17.0), (200.0, 17.0)]),
            study_id="lon",
        )


def test_geojson_round_trip(aoi):
    payload = aoi.to_geojson()
    restored = aoi_mod.aoi_from_geojson(aoi.study_id, payload)
    assert restored.polygon.equals(aoi.polygon)
    assert restored.utm_epsg == aoi.utm_epsg


def test_grid_transform_is_snapped_and_north_up(aoi):
    transform = aoi.grid_transform()
    assert transform.a == pytest.approx(10.0)
    assert transform.e == pytest.approx(-10.0)
    assert transform.b == 0.0 and transform.d == 0.0
    assert transform.c % 10.0 == pytest.approx(0.0)
    assert transform.f % 10.0 == pytest.approx(0.0)


def test_grid_shape_matches_transform(aoi):
    window = grid_mod.analysis_window(aoi)
    height, width = aoi.grid_shape()
    assert window.shape == (height, width)
    assert window.crs == f"EPSG:{aoi.utm_epsg}"


def test_aoi_mask_is_inside_polygon(aoi):
    window = grid_mod.analysis_window(aoi)
    mask = grid_mod.aoi_raster_mask(aoi, window)
    assert mask.dtype == bool
    assert mask.sum() > 0
    assert mask.sum() < mask.size, "AOI must not fill the buffered grid entirely"


def test_assert_same_grid_accepts_identical(aoi):
    window = grid_mod.analysis_window(aoi)
    grid_mod.assert_same_grid(window, window)


def test_assert_same_grid_rejects_transform_drift(aoi):
    window = grid_mod.analysis_window(aoi)
    drifted = grid_mod.AnalysisWindow(
        crs=window.crs,
        transform=Affine(10.0, 0.0, window.transform.c + 5.0, 0.0, -10.0, window.transform.f),
        height=window.height,
        width=window.width,
        resolution=window.resolution,
        utm_epsg=window.utm_epsg,
    )
    with pytest.raises(grid_mod.GridError, match="transform"):
        grid_mod.assert_same_grid(window, drifted)


def test_assert_same_grid_rejects_shape_and_crs(aoi):
    window = grid_mod.analysis_window(aoi)
    with pytest.raises(grid_mod.GridError):
        grid_mod.assert_same_grid(
            window,
            grid_mod.AnalysisWindow(
                crs="EPSG:32643", transform=window.transform,
                height=window.height + 1, width=window.width,
                resolution=window.resolution, utm_epsg=32643,
            ),
        )
    with pytest.raises(grid_mod.GridError):
        grid_mod.assert_same_grid(
            window,
            grid_mod.AnalysisWindow(
                crs="EPSG:32643", transform=window.transform,
                height=window.height, width=window.width,
                resolution=window.resolution, utm_epsg=32643,
            ),
        )


def test_write_geotiff_georeferencing(tmp_path, small_aoi):
    window = grid_mod.analysis_window(small_aoi)
    data = np.full(window.shape, 0.42, dtype=np.float32)
    path = grid_mod.write_geotiff(tmp_path / "out.tif", data, window, descriptions=("ndvi",))
    with rasterio.open(path) as src:
        assert src.crs.to_string() == window.crs
        assert (src.height, src.width) == window.shape
        np.testing.assert_allclose(np.array(src.transform)[:6], np.array(window.transform)[:6])
        assert src.descriptions[0] == "ndvi"
        assert src.tags()["grid_signature"] == window.signature()
        np.testing.assert_allclose(src.read(1), data, atol=1e-6)


def test_write_geotiff_rejects_shape_mismatch(tmp_path, small_aoi):
    window = grid_mod.analysis_window(small_aoi)
    with pytest.raises(grid_mod.GridError):
        grid_mod.write_geotiff(
            tmp_path / "bad.tif", np.zeros((3, 3), dtype=np.float32), window
        )


def test_grid_signature_changes_with_resolution(aoi):
    ten = grid_mod.analysis_window(aoi, 10.0)
    twenty = grid_mod.analysis_window(aoi, 20.0)
    assert ten.signature() != twenty.signature()


def test_window_size_cap_is_enforced(aoi):
    window = grid_mod.analysis_window(aoi)
    assert window.width * window.height <= 4_000_000
