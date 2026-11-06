"""Spectral index registry and formula tests (synthetic arrays only)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.indices import spectral
from backend.app.indices.ndvi import normalised_difference


def _band(value: float, shape=(2, 2)) -> np.ndarray:
    return np.full(shape, value, dtype=np.float32)


def test_ndvi_matches_documented_formula():
    red = np.array([[0.10, 0.20], [0.05, 0.30]], dtype=np.float32)
    nir = np.array([[0.40, 0.20], [0.15, 0.60]], dtype=np.float32)
    result = spectral.compute_index("ndvi", {"red": red, "nir": nir})
    expected = (nir - red) / (nir + red)
    np.testing.assert_allclose(result, expected, rtol=0, atol=1e-6)


def test_known_index_values():
    bands = {
        "red": _band(0.10),
        "nir": _band(0.50),
        "green": _band(0.30),
        "swir16": _band(0.10),
    }
    assert spectral.compute_index("ndvi", bands)[0, 0] == pytest.approx(0.6666666, abs=1e-6)
    assert spectral.compute_index("ndwi", bands)[0, 0] == pytest.approx(-0.25, abs=1e-6)
    assert spectral.compute_index("mndwi", bands)[0, 0] == pytest.approx(0.5, abs=1e-6)
    # NDBI = (SWIR - NIR) / (SWIR + NIR)
    assert spectral.compute_index("ndbi", bands)[0, 0] == pytest.approx(-0.6666666, abs=1e-6)


def test_ndsi_is_same_algebra_as_mndwi_but_separate_spec():
    # Both are (Green - SWIR1)/(Green + SWIR1); the registry keeps them apart
    # so a cryosphere profile can never be labelled with a water index.
    bands = {"green": _band(0.35), "swir16": _band(0.05)}
    assert spectral.compute_index("ndsi", bands)[0, 0] == pytest.approx(
        spectral.compute_index("mndwi", bands)[0, 0]
    )
    assert spectral.INDEX_SPECS["ndsi"] is not spectral.INDEX_SPECS["mndwi"]
    assert spectral.INDEX_SPECS["ndsi"].ramp != spectral.INDEX_SPECS["mndwi"].ramp


def test_division_by_zero_and_non_finite_yield_nan():
    bands = {
        "red": np.array([0.0, np.nan, 0.2], dtype=np.float32),
        "nir": np.array([0.0, 0.3, -0.2], dtype=np.float32),
    }
    result = spectral.compute_index("ndvi", bands)
    assert np.all(np.isnan(result))


def test_out_of_range_values_are_rejected_not_clipped():
    # Negative reflectance can only come from an offset artefact; the derived
    # index is not interpretable and must not enter statistics.
    bands = {
        "red": np.array([-0.2], dtype=np.float32),
        "nir": np.array([0.1], dtype=np.float32),
    }
    assert np.isnan(spectral.compute_index("ndvi", bands)[0])


def test_shape_mismatch_raises():
    with pytest.raises(Exception):
        normalised_difference(
            np.zeros((2, 2), dtype=np.float32), np.zeros((2, 3), dtype=np.float32)
        )


def test_missing_band_raises_index_spec_error():
    with pytest.raises(spectral.IndexSpecError):
        spectral.compute_index("mndwi", {"green": _band(0.2)})


def test_required_bands_is_sorted_union():
    assert spectral.required_bands(("ndvi", "ndwi")) == ("green", "nir", "red")
    assert spectral.required_bands(("mndwi", "ndbi")) == ("green", "nir", "swir16")


def test_native_resolution_and_upsampling_flags():
    specs = spectral.INDEX_SPECS
    assert specs["ndvi"].native_resolution_m == 10.0
    assert specs["ndwi"].native_resolution_m == 10.0
    assert specs["mndwi"].native_resolution_m == 20.0
    assert specs["ndsi"].native_resolution_m == 20.0
    assert specs["ndbi"].native_resolution_m == 20.0

    ndvi = specs["ndvi"].to_dict(10.0)
    mndwi = specs["mndwi"].to_dict(10.0)
    assert ndvi["upsampled"] is False
    assert mndwi["upsampled"] is True
    assert "no genuine 10 m detail" in mndwi["resolution_note"]


def test_unknown_index_raises():
    with pytest.raises(spectral.IndexSpecError):
        spectral.get_index("does_not_exist")


def test_ramps_are_monotonic_and_cover_value_range():
    for key, spec in spectral.INDEX_SPECS.items():
        values = [stop for stop, _ in spec.ramp]
        assert values == sorted(values), key
        assert values[0] == spec.value_range[0]
        assert values[-1] == spec.value_range[1]
        assert spec.breaks == tuple(sorted(spec.breaks)), key
