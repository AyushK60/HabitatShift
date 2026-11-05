"""NDVI mathematics: exactness, division-by-zero, NaN handling, intersection."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.indices import ndvi as ndvi_mod


def test_ndvi_matches_formula():
    red = np.array([[0.10, 0.20], [0.05, 0.30]], dtype=np.float32)
    nir = np.array([[0.40, 0.20], [0.15, 0.60]], dtype=np.float32)
    result = ndvi_mod.ndvi(nir, red)
    expected = (nir - red) / (nir + red)
    np.testing.assert_allclose(result, expected, rtol=0, atol=1e-6)


def test_ndvi_known_values():
    assert ndvi_mod.ndvi(np.array([0.5], np.float32), np.array([0.1], np.float32))[0] == pytest.approx(
        0.6666666, abs=1e-6
    )
    assert ndvi_mod.ndvi(np.array([0.2], np.float32), np.array([0.6], np.float32))[0] == pytest.approx(
        -0.5, abs=1e-6
    )
    assert ndvi_mod.ndvi(np.array([0.3], np.float32), np.array([0.3], np.float32))[0] == pytest.approx(0.0)


def test_zero_denominator_yields_nan():
    red = np.array([0.0, 0.0], dtype=np.float32)
    nir = np.array([0.0, 0.4], dtype=np.float32)
    result = ndvi_mod.ndvi(nir, red)
    assert np.isnan(result[0])
    assert not np.isnan(result[1])


def test_tiny_denominator_guarded():
    red = np.array([0.4], dtype=np.float32)
    nir = np.array([-0.4 + 1e-9], dtype=np.float32)
    assert np.isnan(ndvi_mod.ndvi(nir, red)[0])


def test_nan_inputs_propagate_as_nan():
    red = np.array([[np.nan, 0.2]], dtype=np.float32)
    nir = np.array([[0.4, np.nan]], dtype=np.float32)
    result = ndvi_mod.ndvi(nir, red)
    assert np.isnan(result).all()


def test_shape_mismatch_rejected():
    with pytest.raises(ndvi_mod.IndexError_):
        ndvi_mod.ndvi(np.zeros((2, 2)), np.zeros((3, 3)))


def test_difference_preserves_nan():
    later = np.array([[0.5, np.nan]], dtype=np.float32)
    earlier = np.array([[0.2, 0.3]], dtype=np.float32)
    result = ndvi_mod.difference(later, earlier)
    assert result[0, 0] == pytest.approx(0.3)
    assert np.isnan(result[0, 1])


def test_constant_images_produce_zero_change():
    band = np.full((4, 4), 0.33, dtype=np.float32)
    assert np.allclose(ndvi_mod.difference(band, band), 0.0)


def test_common_valid_intersection_excludes_pixels():
    earlier = np.array([[0.2, np.nan], [0.1, 0.4]], dtype=np.float32)
    later = np.array([[0.5, 0.5], [np.nan, 0.4]], dtype=np.float32)
    mask = np.array([[True, True], [True, True]])
    common = mask & np.isfinite(earlier) & np.isfinite(later)
    assert common.tolist() == [[True, False], [False, True]]
    delta = ndvi_mod.difference(later, earlier)
    delta[~common] = np.nan
    assert int(np.isfinite(delta).sum()) == 2


def test_summarise_ignores_masked_and_nan():
    values = np.array([[0.2, 0.4], [np.nan, 0.6]], dtype=np.float32)
    mask = np.array([[True, False], [True, True]])
    stats = ndvi_mod.summarise(values, mask)
    assert stats.valid_count == 2
    assert stats.mean == pytest.approx(0.4)


def test_summarise_empty_returns_none_fields():
    stats = ndvi_mod.summarise(np.full((2, 2), np.nan, dtype=np.float32))
    assert stats.valid_count == 0
    assert stats.mean is None
    assert stats.to_dict()["mean"] is None


def test_thresholded_area_counts_and_converts():
    delta = np.array([[-0.3, -0.05], [0.02, 0.4]], dtype=np.float32)
    mask = np.ones((2, 2), dtype=bool)
    result = ndvi_mod.thresholded_area(
        delta, mask, threshold=0.15, pixel_area_m2=100.0
    )
    assert result["decrease_pixels"] == 1
    assert result["increase_pixels"] == 1
    assert result["stable_pixels"] == 2
    assert result["decrease_area_ha"] == pytest.approx(0.01)


def test_normalised_difference_clips_nonfinite():
    a = np.array([np.inf], dtype=np.float32)
    b = np.array([0.2], dtype=np.float32)
    assert np.isnan(ndvi_mod.normalised_difference(a, b)[0])
