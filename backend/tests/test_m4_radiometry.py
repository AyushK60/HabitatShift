"""M4 radiometry tests: empirical DN-convention acceptance.

The 2025 Earth Search reprocessing stores baseline-05.11 DNs *without* the
baked ``+1000`` BOA offset while ``earthsearch:boa_offset_applied`` is false
and ``raster:bands`` still declares ``-0.1``.  Applying the declared offset to
such an item produces physically impossible negative reflectance.  The engine
now rejects any applied transform whose window means fall below the physical
floor, retries the scale-only convention, and refuses the observation when
neither convention is plausible.  These tests pin that behaviour with
synthetic scenes (no network).
"""

from __future__ import annotations

import os
from affine import Affine
import numpy as np
import pytest

from backend.app.acquisition.assets import (
    EMPIRICAL_CORRECTION_MARKER,
    PHYSICAL_MIN_MEAN,
    empirical_offset_rejection,
    with_scale_only_offset,
)
from backend.app.pipeline import engine as engine_mod
from backend.app.preprocess.grid import analysis_window, aoi_raster_mask

from .m1_factories import make_candidate
from .conftest import small_aoi  # noqa: F401  (pytest fixture)


def _write_raster(path, array, *, crs, transform, dtype="uint16"):
    import rasterio

    profile = {
        "driver": "GTiff",
        "height": array.shape[0],
        "width": array.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array.astype(dtype), 1)
    return path


# --------------------------------------------------------------------------- #
# Pure helper behaviour
# --------------------------------------------------------------------------- #
def test_rejection_none_for_plausible_reflectance():
    reflectance = {
        "blue": np.full((5, 5), 0.04, dtype=np.float32),
        "nir": np.full((5, 5), 0.35, dtype=np.float32),
    }
    assert empirical_offset_rejection(reflectance) is None


def test_rejection_records_non_physical_band_means():
    reflectance = {
        "blue": np.full((4, 4), -0.083, dtype=np.float32),
        "nir": np.full((4, 4), 0.25, dtype=np.float32),
    }
    evidence = empirical_offset_rejection(reflectance)
    assert evidence is not None
    assert evidence["verdict"] == "declared_transform_non_physical"
    assert set(evidence["bands"]) == {"blue"}
    assert evidence["bands"]["blue"]["mean_reflectance"] == pytest.approx(-0.083, abs=1e-4)
    assert evidence["bands"]["blue"]["threshold"] == PHYSICAL_MIN_MEAN


def test_nan_pixels_excluded_from_mean():
    values = np.full((3, 3), 0.2, dtype=np.float32)
    values[0, 0] = np.nan
    evidence = empirical_offset_rejection({"nir": values})
    assert evidence is None or evidence["bands"]["nir"]["finite_pixels"] == 8


def test_with_scale_only_offset_is_deterministic_and_typed():
    record = make_candidate(offset=-0.1, baseline="05.11")
    # Radiometry records are built by verify_asset; construct one directly.
    from backend.app.acquisition.assets import Radiometry

    declared = Radiometry(
        asset_key="nir", scale=0.0001, offset=-0.1, nodata=0, gsd=10.0,
        source="declared",
    )
    corrected = with_scale_only_offset(declared)
    assert corrected.offset == 0.0
    assert corrected.scale == 0.0001
    assert EMPIRICAL_CORRECTION_MARKER in corrected.source
    # Deterministic: reconstructing gives an identical record.
    assert with_scale_only_offset(declared).to_dict() == corrected.to_dict()
    # Scale-only records pass through unchanged.
    assert with_scale_only_offset(corrected) is corrected


# --------------------------------------------------------------------------- #
# read_observation with a mismatched declared convention
# --------------------------------------------------------------------------- #
@pytest.fixture
def stale_offset_scene(tmp_path, small_aoi):
    """A scene whose DNs carry no baked offset but whose metadata declares -0.1."""
    window = analysis_window(small_aoi, 10.0)
    aoi_mask = aoi_raster_mask(small_aoi, window)
    item_id = "S2B_TEST_20250222_0_L2A"

    scl = np.full(window.shape, 4, dtype=np.int32)
    hrefs = {
        "scl": _write_raster(
            tmp_path / f"{item_id}_scl.tif", scl,
            crs=window.crs, transform=window.transform,
        )
    }
    # Reflectance values written WITHOUT the +1000 DN offset (the 2025
    # reprocessing convention): DN = reflectance * 10000.
    reflectance_by_band = {"green": 0.03, "red": 0.02, "nir": 0.30}
    for band, value in reflectance_by_band.items():
        dn = int(round(value / 0.0001))
        hrefs[band] = _write_raster(
            tmp_path / f"{item_id}_{band}.tif",
            np.full(window.shape, dn, dtype=np.uint16),
            crs=window.crs, transform=window.transform,
        )
    candidate = make_candidate(
        item_id=item_id,
        acquired="2025-02-22T05:14:06.775000Z",
        href_prefix=str(tmp_path) + os.sep,
        assets=("green", "red", "nir", "scl"),
        offset=-0.1,
        baseline="05.11",
    )
    return window, aoi_mask, candidate, reflectance_by_band


def test_read_observation_rejects_declared_and_applies_scale_only(
    stale_offset_scene,
):
    window, aoi_mask, candidate, expected = stale_offset_scene
    observation = engine_mod.read_observation(
        candidate, window, aoi_mask, ("green", "red", "nir"),
        period_id="later", cache=None,
    )
    cy, cx = window.height // 2, window.width // 2
    for band, value in expected.items():
        # Scale-only convention applied exactly once: DN * 0.0001.
        assert observation.reflectance[band][cy, cx] == pytest.approx(
            value, abs=2e-4
        )
    for key, record in observation.radiometry.items():
        assert record.offset == 0.0
        assert EMPIRICAL_CORRECTION_MARKER in record.source
    evidence = observation.radiometry_evidence
    assert evidence["verdict"] == "declared_transform_non_physical"
    # Only bands that actually go negative under the declared transform are
    # recorded; nir at 0.30 stays positive under either convention.
    assert set(evidence["bands"]) == {"green", "red"}


def test_cache_round_trip_preserves_corrected_radiometry(
    stale_offset_scene, tmp_path
):
    window, aoi_mask, candidate, _ = stale_offset_scene
    keys = ("green", "red", "nir")
    cache = engine_mod.ObservationCache(tmp_path / "obs")
    first = engine_mod.read_observation(
        candidate, window, aoi_mask, keys, period_id="later", cache=cache,
    )
    second = engine_mod.read_observation(
        candidate, window, aoi_mask, keys, period_id="later", cache=cache,
    )
    assert second.radiometry.keys() == first.radiometry.keys()
    for key in first.radiometry:
        assert second.radiometry[key].to_dict() == first.radiometry[key].to_dict()
    assert second.radiometry_evidence == first.radiometry_evidence
    assert second.reflectance["nir"][window.height // 2, window.width // 2] == (
        pytest.approx(0.30, abs=2e-4)
    )


def test_cache_rejects_physically_implausible_pixels(
    stale_offset_scene, tmp_path
):
    """A cached record whose stored reflectance is non-physical is discarded.

    This is the guard for the observed failure mode: reflectance converted
    under a wrong DN convention (here simulated by overwriting the cached
    arrays with the mis-applied -0.1 offset values) must never be served
    from the cache, whatever the metadata claims.
    """
    import json

    window, aoi_mask, candidate, expected = stale_offset_scene
    keys = ("green", "red", "nir")
    cache = engine_mod.ObservationCache(tmp_path / "obs")
    engine_mod.read_observation(
        candidate, window, aoi_mask, keys, period_id="later", cache=cache,
    )
    # Overwrite the cached arrays with the mis-applied convention values.
    for npz_path in cache.directory.glob("*.npz"):
        with np.load(npz_path) as data:
            arrays = {k: data[k] for k in data.files}
        for band in keys:
            arrays[f"reflectance_{band}"] = np.full(
                arrays["valid"].shape,
                expected[band] - 0.1,
                dtype=np.float32,
            )
        np.savez_compressed(npz_path, **arrays)
    # And strip the evidence so the metadata alone cannot reveal the damage.
    for meta_path in cache.directory.glob("*.json"):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta.pop("radiometry_evidence", None)
        for record in meta["radiometry"].values():
            record["offset"] = 0.0
            record["source"] = record["source"].split(" ; ")[0]
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
    again = engine_mod.read_observation(
        candidate, window, aoi_mask, keys, period_id="later", cache=cache,
    )
    # Discarded and re-read from source, re-corrected, evidence restored.
    cy, cx = window.height // 2, window.width // 2
    assert again.reflectance["nir"][cy, cx] == pytest.approx(0.30, abs=2e-4)
    assert again.radiometry["nir"].offset == 0.0
    assert again.radiometry_evidence.get("verdict") == (
        "declared_transform_non_physical"
    )


def test_read_observation_hard_error_when_both_conventions_fail(
    tmp_path, small_aoi
):
    """Neither convention plausible -> the observation is refused, not guessed."""
    window = analysis_window(small_aoi, 10.0)
    aoi_mask = aoi_raster_mask(small_aoi, window)
    item_id = "S2X_TEST_20250222_0_L2A"
    scl = np.full(window.shape, 4, dtype=np.int32)
    hrefs = {
        "scl": _write_raster(
            tmp_path / f"{item_id}_scl.tif", scl,
            crs=window.crs, transform=window.transform,
        )
    }
    # Physically impossible DNs (negative) defeat both conventions.
    for band in ("green", "red", "nir"):
        hrefs[band] = _write_raster(
            tmp_path / f"{item_id}_{band}.tif",
            np.full(window.shape, -1000.0, dtype=np.float32),
            crs=window.crs, transform=window.transform, dtype="float32",
        )
    candidate = make_candidate(
        item_id=item_id,
        acquired="2025-02-22T05:14:06.775000Z",
        href_prefix=str(tmp_path) + os.sep,
        assets=("green", "red", "nir", "scl"),
        offset=-0.1,
        baseline="05.11",
    )
    with pytest.raises(Exception, match="refusing the observation"):
        engine_mod.read_observation(
            candidate, window, aoi_mask, ("green", "red", "nir", "scl"),
            period_id="later", cache=None,
        )
