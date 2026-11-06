"""M1 engine stages: selection, window reads, masking, cache and determinism.

All rasters below are synthetic files written to a temporary directory.  No
network access and no real satellite data are involved.
"""

from __future__ import annotations

import datetime as dt
import os

import numpy as np
import pytest
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine

from backend.app.acquisition.assets import RadiometryError
from backend.app.acquisition.cog import RasterReadError, WindowRequest, read_window
from backend.app.pipeline import engine as engine_mod
from backend.app.pipeline.config import PeriodSpec
from backend.app.preprocess.composite import observation_cache_key
from backend.app.preprocess.grid import analysis_window, aoi_raster_mask
from backend.tests.m1_factories import make_candidate, make_score

DATE = "2020-03-26T05:10:00Z"


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #
def _period_scores():
    return [
        make_score(item_id="A_20200321", acquired="2020-03-21T05:00:00Z"),
        make_score(item_id="A_20200326", acquired="2020-03-26T05:00:00Z", cloud=0.1),
        make_score(item_id="A_20200331", acquired="2020-03-31T05:00:00Z"),
        make_score(item_id="A_20200510", acquired="2020-05-10T05:00:00Z"),
        make_score(item_id="A_UNUSABLE", acquired="2020-03-25T05:00:00Z", usable=False),
    ]


def _candidates(scores):
    return {
        score.item_id: make_candidate(
            item_id=score.item_id, acquired=score.acquired
        )
        for score in scores
    }


@pytest.fixture
def period_spec() -> PeriodSpec:
    return PeriodSpec(
        period_id="earlier",
        anchor=dt.date(2020, 3, 26),
        search_start=dt.date(2020, 2, 25),
        search_end=dt.date(2020, 4, 25),
        max_offset_days=30,
    )


def test_selection_prefers_anchor_then_nearest_distinct_dates(period_spec):
    scores = _period_scores()
    chosen, report = engine_mod.select_period_observations(
        scores,
        _candidates(scores),
        period_spec,
        max_observations=2,
        min_observations=1,
    )
    ids = [score.item_id for score in chosen]
    assert ids[0] == "A_20200326"
    assert len(ids) == 2
    assert "A_UNUSABLE" not in ids
    assert "A_20200510" not in ids, "outside the anchor window must be excluded"
    assert report["within_anchor_window"] is True
    assert report["fallback_used"] is False
    assert len(set(report["chosen_dates"])) == len(report["chosen_dates"])


def test_selection_keeps_one_observation_per_calendar_date():
    scores = [
        make_score(item_id="A_CLOUDY", acquired="2020-03-26T05:00:00Z", cloud=45.0),
        make_score(item_id="A_CLEAR", acquired="2020-03-26T05:10:00Z", cloud=2.0),
    ]
    chosen, report = engine_mod.select_period_observations(
        scores,
        _candidates(scores),
        PeriodSpec(
            period_id="earlier",
            anchor=dt.date(2020, 3, 26),
            search_start=dt.date(2020, 3, 1),
            search_end=dt.date(2020, 4, 1),
            max_offset_days=30,
        ),
        max_observations=3,
        min_observations=1,
    )
    assert [score.item_id for score in chosen] == ["A_CLEAR"]
    assert report["chosen_dates"] == ["2020-03-26"]


def test_selection_falls_back_outside_anchor_window_and_reports_it():
    scores = [make_score(item_id="A_FAR", acquired="2020-06-20T05:00:00Z")]
    chosen, report = engine_mod.select_period_observations(
        scores,
        _candidates(scores),
        PeriodSpec(
            period_id="earlier",
            anchor=dt.date(2020, 3, 26),
            search_start=dt.date(2020, 2, 25),
            search_end=dt.date(2020, 7, 25),
            max_offset_days=30,
        ),
        max_observations=3,
        min_observations=1,
    )
    assert [score.item_id for score in chosen] == ["A_FAR"]
    assert report["fallback_used"] is True
    assert report["within_anchor_window"] is False


def test_selection_respects_minimum_observations(period_spec):
    scores = [make_score(item_id="A_UNUSABLE", acquired=DATE, usable=False)]
    with pytest.raises(engine_mod.EngineError, match="at least 2"):
        engine_mod.select_period_observations(
            scores,
            _candidates(scores),
            period_spec,
            max_observations=3,
            min_observations=2,
        )


# --------------------------------------------------------------------------- #
# Local synthetic rasters
# --------------------------------------------------------------------------- #
def _write_raster(path, array, *, crs, transform, dtype="uint16", nodata=0):
    array = np.asarray(array)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype=dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(array.astype(dtype), 1)
    return path


@pytest.fixture
def synthetic_scene(tmp_path, small_aoi):
    window = analysis_window(small_aoi, 10.0)
    aoi_mask = aoi_raster_mask(small_aoi, window)
    item_id = "S2B_TEST_20200326_0_L2A"

    scl = np.full(window.shape, 4, dtype=np.int32)
    scl[2:4, 2:5] = 9          # cloud
    scl[10, 12] = 0            # nodata

    hrefs = {}
    hrefs["scl"] = _write_raster(
        tmp_path / f"{item_id}_scl.tif",
        scl,
        crs=window.crs,
        transform=window.transform,
    )
    reflectance_by_band = {"green": 0.2, "red": 0.1, "nir": 0.5, "swir16": 0.3}
    for band, value in reflectance_by_band.items():
        dn = int(round(value / 0.0001))
        if band == "swir16":
            # Native 20 m SWIR: half-resolution source grid, constant value.
            transform = window.transform @ Affine.scale(2.0, 2.0)
            height = window.height // 2 + 2
            width = window.width // 2 + 2
            hrefs[band] = _write_raster(
                tmp_path / f"{item_id}_{band}.tif",
                np.full((height, width), dn, dtype=np.uint16),
                crs=window.crs,
                transform=transform,
            )
        else:
            hrefs[band] = _write_raster(
                tmp_path / f"{item_id}_{band}.tif",
                np.full(window.shape, dn, dtype=np.uint16),
                crs=window.crs,
                transform=window.transform,
            )
    candidate = make_candidate(
        item_id=item_id,
        acquired=DATE,
        href_prefix=str(tmp_path) + os.sep,
        assets=("green", "red", "nir", "swir16", "scl"),
    )
    return window, aoi_mask, candidate, reflectance_by_band


def test_read_observation_applies_scale_and_scl_mask(synthetic_scene):
    window, aoi_mask, candidate, expected = synthetic_scene
    keys = ("green", "nir", "red", "swir16", "scl")
    observation = engine_mod.read_observation(
        candidate,
        window,
        aoi_mask,
        keys,
        period_id="earlier",
        cache=None,
    )
    cy, cx = window.height // 2, window.width // 2

    # Cloud/nodata pixels are invalid; inside-AOI clear pixels are valid.
    assert observation.valid.dtype == bool
    assert not observation.valid[2, 2]
    assert not observation.valid[10, 12]
    assert observation.valid[cy, cx]

    # Radiometry: DN * 0.0001, no offset on this baseline.
    assert observation.reflectance["green"][cy, cx] == pytest.approx(
        expected["green"], abs=2e-4
    )
    assert observation.reflectance["nir"][cy, cx] == pytest.approx(
        expected["nir"], abs=2e-4
    )
    # 20 m SWIR bilinearly resampled to 10 m remains the same constant field.
    assert observation.reflectance["swir16"][cy, cx] == pytest.approx(
        expected["swir16"], abs=2e-4
    )
    # Invalid pixels are NaN, never interpolated.
    assert np.isnan(observation.reflectance["green"][2, 2])


def test_observation_cache_round_trip_and_offline_miss(synthetic_scene, tmp_path):
    window, aoi_mask, candidate, _ = synthetic_scene
    keys = ("green", "nir", "red", "swir16", "scl")
    cache = engine_mod.ObservationCache(tmp_path / "obs")
    first = engine_mod.read_observation(
        candidate, window, aoi_mask, keys, period_id="earlier", cache=cache
    )
    second = engine_mod.read_observation(
        candidate, window, aoi_mask, keys, period_id="earlier", cache=cache
    )
    for key in keys:
        np.testing.assert_array_equal(first.reflectance[key], second.reflectance[key])
    np.testing.assert_array_equal(first.valid, second.valid)

    empty_cache = engine_mod.ObservationCache(tmp_path / "empty")
    with pytest.raises(engine_mod.ObservationCacheMiss):
        engine_mod.read_observation(
            candidate,
            window,
            aoi_mask,
            keys,
            period_id="earlier",
            cache=empty_cache,
            offline=True,
        )


def test_corrupt_observation_cache_is_ignored(synthetic_scene, tmp_path):
    window, aoi_mask, candidate, _ = synthetic_scene
    keys = ("green", "nir", "red", "swir16", "scl")
    cache = engine_mod.ObservationCache(tmp_path / "obs")
    engine_mod.read_observation(
        candidate, window, aoi_mask, keys, period_id="earlier", cache=cache
    )
    key = observation_cache_key(candidate.item_id, window.signature(), keys)
    (tmp_path / "obs" / f"{key}.npz").write_bytes(b"not a numpy archive")
    assert cache.load(key, candidate, window, keys) is None
    # A corrupt cache falls back to a real read online, and is a hard miss offline.
    with pytest.raises(engine_mod.ObservationCacheMiss):
        engine_mod.read_observation(
            candidate,
            window,
            aoi_mask,
            keys,
            period_id="earlier",
            cache=cache,
            offline=True,
        )


def test_missing_band_raises_radiometry_error(synthetic_scene, tmp_path):
    window, aoi_mask, candidate, _ = synthetic_scene
    without_nir = make_candidate(
        item_id=candidate.item_id,
        acquired=DATE,
        href_prefix=str(tmp_path) + os.sep,
        assets=("green", "red", "scl"),
    )
    with pytest.raises(RadiometryError):
        engine_mod.read_observation(
            without_nir,
            window,
            aoi_mask,
            ("green", "nir", "red", "scl"),
            period_id="earlier",
            cache=None,
        )


def test_corrupt_raster_raises_read_error(tmp_path, small_aoi):
    window = analysis_window(small_aoi, 10.0)
    bad = tmp_path / "bad.tif"
    bad.write_text("this is not a TIFF", encoding="utf-8")
    request = WindowRequest(
        dst_crs=window.crs,
        dst_transform=window.transform,
        height=window.height,
        width=window.width,
        resampling=Resampling.bilinear,
        dtype="float32",
    )
    with pytest.raises(RasterReadError):
        read_window(str(bad), request)


def test_reprojection_from_wgs84_lands_on_analysis_grid(tmp_path, small_aoi):
    window = analysis_window(small_aoi, 10.0)
    west, south, east, north = small_aoi.bounds_4326
    margin = 0.002
    array = np.full((64, 64), 1234, dtype=np.uint16)
    transform = Affine(
        (east - west + 2 * margin) / 64,
        0.0,
        west - margin,
        0.0,
        -(north - south + 2 * margin) / 64,
        north + margin,
    )
    path = _write_raster(
        tmp_path / "wgs84.tif", array, crs="EPSG:4326", transform=transform
    )
    request = WindowRequest(
        dst_crs=window.crs,
        dst_transform=window.transform,
        height=window.height,
        width=window.width,
        resampling=Resampling.bilinear,
        dtype="float32",
    )
    result = read_window(str(path), request)
    assert result.shape == window.shape
    assert np.nanmedian(result) == pytest.approx(1234.0, abs=1.0)


def test_nearest_vs_bilinear_resampling_policy(tmp_path, small_aoi):
    window = analysis_window(small_aoi, 10.0)
    # 20 m checkerboard categorical raster over the same extent.
    transform = window.transform @ Affine.scale(2.0, 2.0)
    height, width = window.height // 2 + 2, window.width // 2 + 2
    checker = np.indices((height, width)).sum(axis=0) % 2
    array = np.where(checker == 0, 4, 9).astype(np.uint16)
    path = _write_raster(
        tmp_path / "checker.tif", array, crs=window.crs, transform=transform
    )

    def read(resampling):
        request = WindowRequest(
            dst_crs=window.crs,
            dst_transform=window.transform,
            height=window.height,
            width=window.width,
            resampling=resampling,
            dtype="float32",
        )
        return read_window(str(path), request)

    nearest = read(Resampling.nearest)
    bilinear = read(Resampling.bilinear)
    assert set(np.unique(nearest)).issubset({4.0, 9.0})
    # Bilinear produces intermediate values, which is exactly why it must never
    # be used for a categorical mask.
    assert len(np.unique(bilinear)) > 2


def test_read_observation_is_deterministic(synthetic_scene):
    window, aoi_mask, candidate, _ = synthetic_scene
    keys = ("green", "nir", "red", "swir16", "scl")
    first = engine_mod.read_observation(
        candidate, window, aoi_mask, keys, period_id="earlier"
    )
    second = engine_mod.read_observation(
        candidate, window, aoi_mask, keys, period_id="earlier"
    )
    for key in keys:
        np.testing.assert_array_equal(first.reflectance[key], second.reflectance[key])
    np.testing.assert_array_equal(first.valid, second.valid)


# --------------------------------------------------------------------------- #
# Export geometry checks
# --------------------------------------------------------------------------- #
def test_grid_check_rejects_wrong_georeferencing(tmp_path, small_aoi):
    from backend.app.preprocess.grid import write_geotiff

    window = analysis_window(small_aoi, 10.0)
    good = write_geotiff(
        tmp_path / "good.tif", np.zeros(window.shape, dtype=np.float32), window
    )
    assert engine_mod._grid_check(good, window)["passed"] is True

    shifted = analysis_window(small_aoi, 10.0)
    shifted = type(window)(
        crs=window.crs,
        transform=window.transform @ Affine.translation(10.0, 0.0),
        height=window.height,
        width=window.width,
        resolution=window.resolution,
        utm_epsg=window.utm_epsg,
    )
    bad = write_geotiff(
        tmp_path / "bad.tif",
        np.zeros(window.shape, dtype=np.float32),
        shifted,
    )
    result = engine_mod._grid_check(bad, window)
    assert result["passed"] is False
    assert result["details"]["transform_matches"] is False


def test_area_cross_check_uses_projected_pixels(small_aoi):
    window = analysis_window(small_aoi, 10.0)
    mask = aoi_raster_mask(small_aoi, window)
    payload = engine_mod.area_cross_check(small_aoi, window, mask)
    assert payload["pixel_area_m2"] == pytest.approx(100.0)
    assert payload["aoi_raster_km2"] == pytest.approx(mask.sum() * 100.0 / 1e6, rel=1e-6)
    assert payload["aoi_polygon_geodesic_km2"] == pytest.approx(
        payload["aoi_polygon_projected_km2"], rel=1e-2
    )
    assert payload["geodesic_vs_projected_relative_difference"] >= 0.0
