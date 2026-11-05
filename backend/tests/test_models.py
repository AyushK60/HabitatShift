"""STAC item parsing, including missing/malformed metadata handling."""

from __future__ import annotations

import pytest

from backend.app.catalog.models import MetadataError, SceneCandidate

CATALOG = "https://earth-search.aws.element84.com/v1"


def test_parse_valid_item(stac_item_factory):
    candidate = SceneCandidate.from_stac(
        stac_item_factory(), catalog_url=CATALOG
    )
    assert candidate.item_id == "S2B_44QPD_20250119_0_L2A"
    assert candidate.date_str == "2025-01-19"
    assert candidate.acquisition_iso.endswith("Z")
    assert candidate.cloud_cover == pytest.approx(0.88)
    assert candidate.epsg == 32644
    assert candidate.platform == "sentinel-2b"
    assert candidate.processing_baseline == "05.00"
    assert candidate.missing_assets() == []


def test_asset_metadata_is_read_from_stac(stac_item_factory):
    candidate = SceneCandidate.from_stac(stac_item_factory(), catalog_url=CATALOG)
    red = candidate.asset("red")
    assert red.scale == pytest.approx(0.0001)
    assert red.offset == pytest.approx(0.0)
    assert red.nodata == 0
    assert red.gsd == 10
    assert candidate.asset("scl").gsd == 20


def test_missing_datetime_is_rejected(stac_item_factory):
    with pytest.raises(MetadataError):
        SceneCandidate.from_stac(
            stac_item_factory(datetime_present=False), catalog_url=CATALOG
        )


def test_missing_asset_is_rejected(stac_item_factory):
    item = stac_item_factory(include_assets=("blue", "green", "red", "nir"))
    with pytest.raises(MetadataError, match="scl"):
        SceneCandidate.from_stac(item, catalog_url=CATALOG)


def test_item_without_id_is_rejected(stac_item_factory):
    item = stac_item_factory()
    item["id"] = ""
    with pytest.raises(MetadataError):
        SceneCandidate.from_stac(item, catalog_url=CATALOG)


def test_non_object_item_is_rejected():
    with pytest.raises(MetadataError):
        SceneCandidate.from_stac(["not", "an", "item"], catalog_url=CATALOG)


def test_unparseable_timestamp_is_rejected(stac_item_factory):
    with pytest.raises(MetadataError):
        SceneCandidate.from_stac(
            stac_item_factory(acquired="not-a-date"), catalog_url=CATALOG
        )


def test_missing_cloud_cover_tolerated(stac_item_factory):
    candidate = SceneCandidate.from_stac(
        stac_item_factory(cloud=None), catalog_url=CATALOG
    )
    assert candidate.cloud_cover is None
    assert candidate.cloud_fraction() is None


def test_missing_gsd_and_shape_tolerated(stac_item_factory):
    item = stac_item_factory()
    for asset in item["assets"].values():
        asset.pop("gsd", None)
    candidate = SceneCandidate.from_stac(item, catalog_url=CATALOG)
    assert candidate.asset("red").gsd is None
    assert candidate.asset("red").shape is None


def test_asset_without_href_is_rejected(stac_item_factory):
    item = stac_item_factory()
    del item["assets"]["nir"]["href"]
    with pytest.raises(MetadataError, match="href"):
        SceneCandidate.from_stac(item, catalog_url=CATALOG)


def test_missing_asset_lookup_raises(stac_item_factory):
    candidate = SceneCandidate.from_stac(stac_item_factory(), catalog_url=CATALOG)
    candidate.assets.pop("red")
    with pytest.raises(MetadataError, match="red"):
        candidate.asset("red")


def test_provenance_contains_required_fields(stac_item_factory):
    candidate = SceneCandidate.from_stac(stac_item_factory(), catalog_url=CATALOG)
    provenance = candidate.to_provenance()
    for key in (
        "item_id",
        "collection",
        "acquired_utc",
        "acquisition_date",
        "platform",
        "cloud_cover_percent",
        "epsg",
        "catalog_url",
        "assets",
    ):
        assert key in provenance
    assert set(provenance["assets"]) == {"blue", "green", "red", "nir", "scl"}
