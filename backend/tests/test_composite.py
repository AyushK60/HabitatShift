"""Temporal compositing tests (synthetic arrays only)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.preprocess.composite import (
    CompositeError,
    composite_observations,
    observation_cache_key,
)
from backend.tests.m1_factories import make_observation


def test_median_of_three_observations():
    bands = [
        {"red": np.array([[0.1, 0.4]], dtype=np.float32)},
        {"red": np.array([[0.2, 0.5]], dtype=np.float32)},
        {"red": np.array([[0.6, 0.3]], dtype=np.float32)},
    ]
    observations = [make_observation(bands=b, item_id=f"S2_{i}") for i, b in enumerate(bands)]
    result = composite_observations(observations, method="median", min_observations=1)
    np.testing.assert_allclose(result.bands["red"], [[0.2, 0.4]])
    assert result.counts.tolist() == [[3, 3]]


def test_even_median_is_mean_of_middle_two():
    bands = [
        {"red": np.array([[0.1]], dtype=np.float32)},
        {"red": np.array([[0.4]], dtype=np.float32)},
    ]
    observations = [make_observation(bands=b, item_id=f"S2_{i}") for i, b in enumerate(bands)]
    result = composite_observations(observations, method="median")
    assert result.bands["red"][0, 0] == pytest.approx(0.25)


def test_mean_composite():
    bands = [
        {"red": np.array([[0.1]], dtype=np.float32)},
        {"red": np.array([[0.4]], dtype=np.float32)},
    ]
    observations = [make_observation(bands=b, item_id=f"S2_{i}") for i, b in enumerate(bands)]
    result = composite_observations(observations, method="mean")
    assert result.bands["red"][0, 0] == pytest.approx(0.25)


def test_pixel_counts_and_min_observations_masking():
    first = make_observation(
        bands={"red": np.array([[0.2, 0.2]], dtype=np.float32)},
        valid=np.array([[True, False]]),
        item_id="S2_A",
    )
    second = make_observation(
        bands={"red": np.array([[0.4, 0.4]], dtype=np.float32)},
        valid=np.array([[True, True]]),
        item_id="S2_B",
    )
    one = composite_observations([first, second], min_observations=1)
    two = composite_observations([first, second], min_observations=2)
    assert one.counts.tolist() == [[2, 1]]
    assert one.valid.tolist() == [[True, True]]
    # Pixel with a single observation cannot satisfy a two-observation rule.
    assert two.valid.tolist() == [[True, False]]
    assert np.isnan(two.bands["red"][0, 1])
    assert two.counts[0, 1] == 1


def test_all_masked_pixels_stay_nan_without_warning():
    observation = make_observation(
        bands={"red": np.array([[0.2]], dtype=np.float32)},
        valid=np.array([[False]]),
    )
    result = composite_observations([observation])
    assert np.isnan(result.bands["red"][0, 0])
    assert result.valid_pixels == 0
    assert result.count_stats()["max"] == 0


def test_temporal_change_in_cloud_coverage_is_recorded_not_interpolated():
    cloudy = make_observation(
        bands={"red": np.array([[0.1, 0.1, 0.1]], dtype=np.float32)},
        valid=np.array([[True, False, False]]),
        item_id="S2_CLOUDY",
    )
    clear = make_observation(
        bands={"red": np.array([[0.3, 0.3, 0.3]], dtype=np.float32)},
        valid=np.array([[True, True, True]]),
        item_id="S2_CLEAR",
    )
    result = composite_observations([cloudy, clear])
    assert result.counts.tolist() == [[2, 1, 1]]
    # Cloudy pixel is represented only by the clear observation, and the
    # observation gap is visible in the count rather than hidden.
    np.testing.assert_allclose(result.bands["red"], [[0.2, 0.3, 0.3]], atol=1e-7)


def test_grid_signature_mismatch_raises():
    first = make_observation(signature="grid-a", item_id="S2_A")
    second = make_observation(signature="grid-b", item_id="S2_B")
    with pytest.raises(CompositeError, match="grid signature"):
        composite_observations([first, second])


def test_shape_mismatch_raises():
    first = make_observation(
        bands={"red": np.zeros((2, 2), dtype=np.float32)}, item_id="S2_A"
    )
    second = make_observation(
        bands={"red": np.zeros((2, 3), dtype=np.float32)}, item_id="S2_B"
    )
    with pytest.raises(CompositeError, match="shape"):
        composite_observations([first, second])


def test_band_set_mismatch_raises():
    first = make_observation(bands={"red": np.zeros((2, 2), np.float32)}, item_id="S2_A")
    second = make_observation(
        bands={
            "red": np.zeros((2, 2), np.float32),
            "nir": np.zeros((2, 2), np.float32),
        },
        item_id="S2_B",
    )
    with pytest.raises(CompositeError, match="band set"):
        composite_observations([first, second])


def test_empty_observation_list_raises():
    with pytest.raises(CompositeError):
        composite_observations([])


def test_min_observations_above_available_raises():
    observation = make_observation()
    with pytest.raises(CompositeError):
        composite_observations([observation], min_observations=2)


def test_unknown_method_raises():
    observation = make_observation()
    with pytest.raises(CompositeError, match="method"):
        composite_observations([observation], method="mode")


def test_cache_key_is_deterministic_and_band_order_insensitive():
    a = observation_cache_key("S2_X", "grid", ("red", "nir"))
    b = observation_cache_key("S2_X", "grid", ("nir", "red"))
    c = observation_cache_key("S2_X", "other-grid", ("red", "nir"))
    d = observation_cache_key("S2_X", "grid", ("red",))
    assert a == b
    assert a != c
    assert a != d
    assert len(a) == 32
