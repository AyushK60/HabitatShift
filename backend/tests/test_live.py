"""Live integration tests: real catalogue and real COG bytes.

Run on their own with ``pytest -m live``.  They are the only tests that need
network access, and they are excluded from the default suite.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from backend.app import config
from backend.app.indices import ndvi as ndvi_mod
from backend.app.acquisition.assets import to_reflectance, verify_radiometry
from backend.app.acquisition.cog import WindowRequest, read_window, source_grid
from backend.app.catalog.search import SearchRequest
from backend.app.catalog.stac_client import CatalogClient
from backend.app.http import HttpSession
from backend.app.preprocess import masks
from backend.app.preprocess.grid import analysis_window
from backend.app.preprocess.scoring import measure_aoi_valid_fraction
from rasterio.enums import Resampling

pytestmark = pytest.mark.live

PROBE_AOI = dict(
    study_id="live_probe",
    west=82.2450,
    south=16.7100,
    east=82.2850,
    north=16.7450,
    description="live probe window",
    source="live integration test",
)


@pytest.fixture(scope="module")
def live_client():
    http = HttpSession(cache_dir=config.CACHE_DIR)
    client = CatalogClient(http)
    client.load_collection()
    return client


@pytest.fixture(scope="module")
def live_scene(live_client):
    from backend.app.preprocess.aoi import aoi_from_bounds

    aoi = aoi_from_bounds(**PROBE_AOI)
    request = SearchRequest(
        aoi=aoi,
        start=dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc),
        end=dt.datetime(2025, 1, 31, tzinfo=dt.timezone.utc),
        max_cloud_cover=30.0,
        limit=20,
        label="live",
    )
    result = live_client.search(request)
    if not result.items:
        pytest.skip("catalogue returned no scenes for the live probe window")
    return aoi, result.items[0]


def test_collection_exposes_required_assets(live_client):
    item_assets = live_client.collection_meta["item_assets"]
    for key in config.REQUIRED_ASSETS:
        assert key in item_assets
        bands = item_assets[key]["raster:bands"][0]
        if key == config.ASSET_SCL:
            # Categorical mask: no reflectance scale, but nodata must exist.
            assert bands["nodata"] == config.EXPECTED_NODATA
        else:
            assert bands["scale"] == pytest.approx(config.EXPECTED_SCALE)


def test_search_returns_real_items_with_assets(live_scene):
    _, scene = live_scene
    assert scene.item_id
    assert scene.acquired.year == 2025
    assert scene.missing_assets() == []
    assert scene.asset("red").href.startswith("http")


def test_asset_is_anonymously_readable(live_scene):
    _, scene = live_scene
    info = source_grid(scene.asset("scl").href)
    assert info["crs"] is not None
    assert info["width"] > 0
    assert info["driver"] == "GTiff"


def test_windowed_read_and_ndvi_on_real_pixels(live_scene):
    aoi, scene = live_scene
    window = analysis_window(aoi)
    request = WindowRequest(
        dst_crs=window.crs,
        dst_transform=window.transform,
        height=window.height,
        width=window.width,
        resampling=Resampling.bilinear,
        dtype="float32",
    )
    radiometry = verify_radiometry(scene)
    nir = to_reflectance(read_window(scene.asset("nir").href, request), radiometry["nir"])
    red = to_reflectance(read_window(scene.asset("red").href, request), radiometry["red"])

    assert nir.shape == window.shape
    finite = np.isfinite(nir) & np.isfinite(red)
    assert finite.mean() > 0.3, "expected a mostly readable window"

    ndvi = ndvi_mod.ndvi(nir, red)
    finite_ndvi = ndvi[np.isfinite(ndvi)]
    assert finite_ndvi.size > 0
    assert finite_ndvi.min() >= -1.0001
    assert finite_ndvi.max() <= 1.0001


def test_scl_read_gives_known_classes(live_scene):
    aoi, scene = live_scene
    fraction, report = measure_aoi_valid_fraction(scene, aoi)
    assert 0.0 <= fraction <= 1.0
    assert sum(report["class_histogram"].values()) == report["total_pixels"]


def test_scl_masking_on_real_scene(live_scene):
    aoi, scene = live_scene
    window = analysis_window(aoi)
    request = WindowRequest(
        dst_crs=window.crs,
        dst_transform=window.transform,
        height=window.height,
        width=window.width,
        resampling=Resampling.nearest,
        dtype="int32",
    )
    scl = read_window(scene.asset("scl").href, request)
    valid, report = masks.build_valid_mask(scl)
    assert valid.dtype == bool
    assert report.valid_pixels == int(valid.sum())
    # Cloud classes present must be excluded.
    assert not np.any(np.isin(scl[~valid], np.array(config.SCL_ALWAYS_INVALID)))
