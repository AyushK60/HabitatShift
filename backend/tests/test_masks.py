"""SCL masking policy: accepted classes, rejected classes, coverage accounting."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app import config
from backend.app.preprocess import masks


def test_cloud_shadow_cirrus_nodata_are_masked(scl_array):
    valid, report = masks.build_valid_mask(scl_array)
    assert not valid[0, 0], "nodata must be masked"
    assert not valid[0, 1], "saturated pixel must be masked"
    assert not valid[0, 2], "cloud shadow must be masked"
    assert not valid[0, 3], "medium cloud must be masked"
    assert not valid[0, 4], "high cloud must be masked"
    assert not valid[0, 5], "cirrus must be masked"
    assert report.valid_pixels == int(valid.sum())


def test_dark_water_unclassified_and_snow_are_kept(scl_array):
    valid, _ = masks.build_valid_mask(scl_array)
    assert valid[1, 0], "water class must remain valid"
    assert valid[1, 1], "snow must remain valid (cryosphere target class)"
    assert valid[1, 2], "bare/unvegetated must remain valid"
    assert valid[1, 3], "dark pixels must remain valid"
    assert valid[1, 4], "unclassified must remain valid"


def test_unknown_label_is_treated_as_invalid():
    array = np.full((4, 4), 4, dtype=np.int32)
    array[2, 2] = 99                      # label not in either policy list
    valid, report = masks.build_valid_mask(array)
    assert not valid[2, 2]
    assert 99 in report.class_counts


def test_report_percentages_and_semantics(scl_array):
    _, report = masks.build_valid_mask(scl_array)
    assert report.total_pixels == 64
    assert report.valid_percent == pytest.approx(report.valid_fraction * 100)
    payload = report.to_dict()
    assert payload["rejected_scl_classes"]["9"] == "cloud_high_probability"
    assert payload["accepted_scl_classes"]["6"] == "water"


def test_mask_policy_constants_are_disjoint():
    assert not set(config.SCL_VALID_CLASSES) & set(config.SCL_ALWAYS_INVALID)


def test_non_2d_scl_rejected():
    with pytest.raises(masks.MaskError):
        masks.build_valid_mask(np.zeros((2, 2, 2), dtype=np.int32))


def test_combine_masks_intersects():
    a = np.array([[True, True], [False, True]])
    b = np.array([[True, False], [True, True]])
    assert masks.combine_masks(a, b).tolist() == [[True, False], [False, True]]


def test_combine_masks_shape_mismatch():
    with pytest.raises(masks.MaskError):
        masks.combine_masks(np.ones((2, 2), bool), np.ones((3, 3), bool))


def test_combine_without_masks():
    with pytest.raises(masks.MaskError):
        masks.combine_masks()


def test_nan_reflectance_is_invalid():
    red = np.array([[0.1, np.nan], [0.2, 0.3]], dtype=np.float32)
    nir = np.array([[0.4, 0.4], [np.nan, 0.4]], dtype=np.float32)
    valid = masks.reflectance_valid_mask(red, nir)
    assert valid.tolist() == [[True, False], [False, True]]


def test_apply_mask_sets_fill_and_keeps_shape():
    array = np.ones((2, 2), dtype=np.uint16) * 500
    mask = np.array([[True, False], [True, True]])
    masked = masks.apply_mask(array, mask)
    assert masked.dtype == np.float32
    assert np.isnan(masked[0, 1])
    assert masked[0, 0] == pytest.approx(500.0)


def test_apply_mask_shape_mismatch():
    with pytest.raises(masks.MaskError):
        masks.apply_mask(np.ones((2, 2)), np.ones((3, 3), bool))
