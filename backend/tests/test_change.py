"""Matched-valid change analysis tests (synthetic arrays only)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.analysis import change
from backend.app.indices import ndvi as ndvi_mod


def _delta(values) -> np.ndarray:
    return np.asarray(values, dtype=np.float32)


def test_classify_delta_codes_and_invalid_sentinel():
    delta = _delta([[-0.5, -0.15, -0.149, 0.0, 0.149, 0.15, 0.5, np.nan]])
    common = np.array([[True] * 7 + [False]])
    classes = change.classify_delta(delta, common, threshold=0.15)
    assert classes.tolist() == [[
        change.CLASS_DECREASE,
        change.CLASS_DECREASE,
        change.CLASS_STABLE,
        change.CLASS_STABLE,
        change.CLASS_STABLE,
        change.CLASS_INCREASE,
        change.CLASS_INCREASE,
        change.CLASS_INVALID,
    ]]
    assert classes.dtype == np.int8
    assert change.CLASS_INVALID == -128


def test_threshold_boundary_is_inclusive():
    delta = _delta([-0.2, -0.1, 0.1, 0.2])
    common = np.ones(4, dtype=bool)
    result = change.threshold_result(delta, common, threshold=0.1)
    assert result.decrease_pixels == 2
    assert result.increase_pixels == 2
    assert result.stable_pixels == 0
    assert result.valid_pixels == 4


def test_non_finite_and_masked_pixels_are_excluded():
    delta = _delta([np.nan, 0.3, 0.9])
    common = np.array([True, False, True])
    result = change.threshold_result(delta, common, threshold=0.15)
    assert result.valid_pixels == 1
    assert result.increase_pixels == 1
    assert result.stable_pixels == 0


def test_area_conservation_and_unit_conversion():
    delta = _delta([-0.4, 0.0, 0.4, 0.2])
    common = np.ones(4, dtype=bool)
    result = change.threshold_result(delta, common, threshold=0.15)
    payload = result.to_dict(pixel_area_m2=100.0)
    # 4 pixels * 100 m2 = 400 m2 = 0.04 ha = 0.0004 km2
    assert payload["valid_area_m2"] == pytest.approx(400.0)
    assert payload["valid_area_ha"] == pytest.approx(0.04)
    assert payload["valid_area_km2"] == pytest.approx(0.0004)
    assert payload["decrease_area_ha"] == pytest.approx(0.01)
    assert payload["increase_area_ha"] == pytest.approx(0.02)
    conservation = change.area_conservation(result, 100.0)
    assert conservation["pixels_sum_to_valid"] is True
    assert conservation["area_sum_matches"] is True
    assert conservation["total_area_ha"] == pytest.approx(0.04)


def test_percentages_are_of_common_valid_footprint_not_aoi():
    delta = _delta([0.3, 0.3, np.nan, np.nan])
    common = np.array([True, True, False, False])
    summary = change.change_summary(
        delta,
        common,
        aoi_pixels=10,                      # AOI is much larger than valid data
        pixel_area_m2=100.0,
        thresholds=(0.15,),
        primary_threshold=0.15,
        index_key="ndvi",
    )
    assert summary["common_valid_pixels"] == 2
    assert summary["common_valid_fraction_of_aoi"] == pytest.approx(0.2)
    primary = summary["primary"]
    assert primary["increase_percent_of_common"] == pytest.approx(100.0)
    assert primary["decrease_percent_of_common"] == pytest.approx(0.0)
    assert summary["suitable_for_comparison"] is False


def test_threshold_sensitivity_is_monotonic():
    delta = _delta([-0.25, -0.12, 0.0, 0.12, 0.25])
    common = np.ones(5, dtype=bool)
    summary = change.change_summary(
        delta,
        common,
        aoi_pixels=5,
        pixel_area_m2=100.0,
        thresholds=(0.10, 0.15, 0.20),
        primary_threshold=0.15,
        index_key="ndvi",
    )
    by_threshold = {b["threshold"]: b for b in summary["thresholds"]}
    assert by_threshold[0.10]["decrease_pixels"] >= by_threshold[0.15]["decrease_pixels"]
    assert by_threshold[0.15]["decrease_pixels"] >= by_threshold[0.20]["decrease_pixels"]
    assert by_threshold[0.10]["increase_pixels"] >= by_threshold[0.15]["increase_pixels"]
    assert by_threshold[0.15]["increase_pixels"] >= by_threshold[0.20]["increase_pixels"]
    assert [b["threshold"] for b in summary["thresholds"]] == [0.10, 0.15, 0.20]
    assert summary["primary_threshold"] == pytest.approx(0.15)


def test_common_mask_larger_than_aoi_raises():
    delta = _delta([0.1, 0.1])
    common = np.ones(2, dtype=bool)
    with pytest.raises(change.ChangeError):
        change.change_summary(
            delta,
            common,
            aoi_pixels=1,
            pixel_area_m2=100.0,
            index_key="ndvi",
        )


def test_shape_mismatch_raises():
    with pytest.raises(change.ChangeError):
        change.threshold_result(
            _delta([0.1, 0.2]),
            np.ones(3, dtype=bool),
            threshold=0.15,
        )


def test_non_positive_pixel_area_raises():
    with pytest.raises(change.ChangeError):
        change.change_summary(
            _delta([0.1]),
            np.ones(1, dtype=bool),
            aoi_pixels=1,
            pixel_area_m2=0.0,
            index_key="ndvi",
        )


def test_no_positive_threshold_raises():
    with pytest.raises(change.ChangeError):
        change.normalise_thresholds((0.0, -0.1), 0.0)


def test_difference_map_preserves_nan_and_common_intersection():
    earlier = _delta([[0.5, 0.4, np.nan]])
    later = _delta([[0.3, np.nan, 0.2]])
    delta = ndvi_mod.difference(later, earlier)
    assert delta[0, 0] == pytest.approx(-0.2)
    assert np.isnan(delta[0, 1])
    assert np.isnan(delta[0, 2])

    common = np.isfinite(earlier) & np.isfinite(later)
    assert common.tolist() == [[True, False, False]]


def test_primary_threshold_not_in_list_is_added():
    values, primary = change.normalise_thresholds((0.1, 0.2), 0.15)
    assert values == (0.1, 0.15, 0.2)
    assert primary == pytest.approx(0.15)
