"""Reflectance scaling, radiometry verification and offset handling."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app import config
from backend.app.acquisition.assets import (
    Radiometry,
    RadiometryError,
    resolve_offset,
    to_reflectance,
    verify_radiometry,
)
from backend.app.catalog.models import SceneCandidate

CATALOG = "https://earth-search.aws.element84.com/v1"


def test_dn_scaled_by_metadata_factor():
    radiometry = Radiometry("red", 0.0001, 0.0, 0, 10.0, "test")
    dn = np.array([[1000, 2500]], dtype=np.uint16)
    result = to_reflectance(dn, radiometry)
    np.testing.assert_allclose(result, [[0.1, 0.25]], atol=1e-7)
    assert result.dtype == np.float32


def test_nodata_becomes_nan_before_scaling():
    radiometry = Radiometry("red", 0.0001, 0.0, 0, 10.0, "test")
    dn = np.array([[0, 2000]], dtype=np.uint16)
    result = to_reflectance(dn, radiometry)
    assert np.isnan(result[0, 0])
    assert result[0, 1] == pytest.approx(0.2)


def test_negative_offset_applied_when_declared():
    radiometry = Radiometry("red", 0.0001, -0.1, 0, 10.0, "test")
    result = to_reflectance(np.array([[2000]], dtype=np.uint16), radiometry)
    assert result[0, 0] == pytest.approx(0.1)


def test_input_array_not_mutated():
    radiometry = Radiometry("red", 0.0001, 0.0, 0, 10.0, "test")
    dn = np.array([[1500]], dtype=np.uint16)
    to_reflectance(dn, radiometry)
    assert dn[0, 0] == 1500


def test_verify_radiometry_accepts_expected_metadata(stac_item_factory):
    candidate = SceneCandidate.from_stac(stac_item_factory(), catalog_url=CATALOG)
    verified = verify_radiometry(candidate)
    assert set(verified) == set(config.REQUIRED_ASSETS)
    assert verified["red"].scale == pytest.approx(config.EXPECTED_SCALE)


def test_pre_baseline_04_requires_zero_offset(stac_item_factory):
    """Pre-04.00 products predate BOA_ADD_OFFSET and must declare 0.0."""
    item = stac_item_factory(offset=0.0)
    item["properties"]["processing:baseline"] = "03.01"
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    verified = verify_radiometry(candidate)
    assert verified["red"].offset == pytest.approx(0.0)
    assert "03.01" in verified["red"].source


def test_modern_baseline_accepts_zero_offset(stac_item_factory):
    """Earth Search bakes the offset into some COGs, leaving offset 0."""
    item = stac_item_factory()
    item["properties"]["processing:baseline"] = "05.00"
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    assert verify_radiometry(candidate)["red"].offset == pytest.approx(0.0)


def test_boa_flag_prevents_double_applying_offset(stac_item_factory):
    """Earth Search leaves -0.1 in metadata even when it baked it into the DNs."""
    item = stac_item_factory(offset=-0.1)
    item["properties"]["processing:baseline"] = "05.11"
    item["properties"]["earthsearch:boa_offset_applied"] = True
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    verified = verify_radiometry(candidate)
    assert verified["red"].offset == pytest.approx(0.0)
    assert "already baked" in verified["red"].source


def test_unapplied_boa_offset_is_honoured(stac_item_factory):
    item = stac_item_factory(offset=-0.1)
    item["properties"]["processing:baseline"] = "05.11"
    item["properties"]["earthsearch:boa_offset_applied"] = False
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    verified = verify_radiometry(candidate)
    assert verified["red"].offset == pytest.approx(-0.1)
    assert "05.11" in verified["red"].source


def test_missing_baseline_is_rejected(stac_item_factory):
    item = stac_item_factory()
    item["properties"].pop("processing:baseline", None)
    item["properties"].pop("s2:processing_baseline", None)
    item["properties"].pop("earthsearch:processingBaseline", None)
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    with pytest.raises(RadiometryError, match="indeterminate"):
        verify_radiometry(candidate)


def test_resolve_offset_uses_declared_value_without_flag(stac_item_factory):
    item = stac_item_factory(offset=-0.1)
    item["properties"]["processing:baseline"] = "05.11"
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    offset, reason = resolve_offset(candidate, -0.1, asset_key="red")
    assert offset == pytest.approx(config.BOA_ADD_OFFSET)
    assert "05.11" in reason and "boa_offset_applied=None" in reason

    item = stac_item_factory(offset=0.0)
    item["properties"]["processing:baseline"] = "02.14"
    legacy = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    assert resolve_offset(legacy, 0.0, asset_key="red")[0] == config.NO_OFFSET


def test_verify_radiometry_rejects_wrong_scale(stac_item_factory):
    item = stac_item_factory(scale=0.00001)
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    with pytest.raises(RadiometryError, match="scale"):
        verify_radiometry(candidate)


def test_verify_radiometry_rejects_wrong_offset(stac_item_factory):
    item = stac_item_factory(offset=-0.1)
    item["properties"]["processing:baseline"] = "02.14"
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    with pytest.raises(RadiometryError, match="offset"):
        verify_radiometry(candidate)


def test_verify_radiometry_rejects_unexpected_nodata(stac_item_factory):
    item = stac_item_factory(nodata=1)
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    with pytest.raises(RadiometryError, match="nodata"):
        verify_radiometry(candidate)


def test_verify_radiometry_rejects_gsd_mismatch(stac_item_factory):
    item = stac_item_factory()
    item["assets"]["red"]["gsd"] = 20          # claim 20 m for a 10 m band
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    with pytest.raises(RadiometryError, match="GSD"):
        verify_radiometry(candidate)
