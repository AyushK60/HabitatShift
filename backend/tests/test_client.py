"""Catalogue client behaviour: pagination, bounded results, outage handling."""

from __future__ import annotations

import datetime as dt

import pytest

from backend.app.catalog.search import SearchRequest
from backend.app.catalog.stac_client import CatalogClient, CatalogUnavailable


def make_request(aoi, **kwargs) -> SearchRequest:
    defaults = dict(
        aoi=aoi,
        start=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
        end=dt.datetime(2020, 5, 31, tzinfo=dt.timezone.utc),
        max_cloud_cover=40.0,
        limit=2,
        max_items=4,
        label="unit",
    )
    defaults.update(kwargs)
    return SearchRequest(**defaults)


def test_total_outage_raises_catalog_unavailable(aoi, fake_http_factory):
    http = fake_http_factory([], fail_after=0)
    client = CatalogClient(http, probe_assets=False)
    with pytest.raises(CatalogUnavailable):
        client.search(make_request(aoi))


def test_empty_result_is_not_an_error(aoi, fake_http_factory):
    http = fake_http_factory([{"type": "FeatureCollection", "features": [], "links": []}])
    client = CatalogClient(http, probe_assets=False)
    result = client.search(make_request(aoi))
    assert result.items == []
    assert result.pages_fetched == 1


def test_malformed_items_are_recorded_not_fatal(aoi, fake_http_factory, stac_item_factory):
    good = stac_item_factory(item_id="GOOD")
    bad = stac_item_factory(item_id="BAD", datetime_present=False)
    http = fake_http_factory(
        [{"type": "FeatureCollection", "features": [good, bad], "links": []}]
    )
    client = CatalogClient(http, probe_assets=False)
    result = client.search(make_request(aoi))
    assert [i.item_id for i in result.items] == ["GOOD"]
    assert result.rejected[0]["item_id"] == "BAD"


def test_pagination_follows_next_post_body(aoi, fake_http_factory, stac_item_factory):
    """The next-page token lives in the link body; page two must use it."""
    page_two = {
        "type": "FeatureCollection",
        "features": [stac_item_factory(item_id="P2")],
        "links": [],
    }
    page_one = {
        "type": "FeatureCollection",
        "features": [stac_item_factory(item_id="P1")],
        "links": [
            {
                "rel": "next",
                "method": "POST",
                "href": "https://example.invalid/search",
                "body": {"next": "TOKEN", "collections": ["sentinel-2-l2a"]},
            }
        ],
        "context": {"matched": 2},
    }
    http = fake_http_factory([page_one, page_two])
    client = CatalogClient(http, probe_assets=False)
    result = client.search(make_request(aoi))
    assert [i.item_id for i in result.items] == ["P1", "P2"]
    assert http.calls[1]["payload"]["next"] == "TOKEN"
    assert http.calls[1]["payload"]["collections"] == ["sentinel-2-l2a"]


def test_max_items_bounds_result_count(aoi, fake_http_factory, stac_item_factory):
    features = [stac_item_factory(item_id=f"I{n}") for n in range(5)]
    http = fake_http_factory(
        [{"type": "FeatureCollection", "features": features, "links": []}]
    )
    client = CatalogClient(http, probe_assets=False)
    result = client.search(make_request(aoi, max_items=3))
    assert len(result.items) == 3


def test_pagination_failure_after_first_page_keeps_partial(aoi, fake_http_factory, stac_item_factory):
    page_one = {
        "type": "FeatureCollection",
        "features": [stac_item_factory()],
        "links": [{"rel": "next", "method": "POST", "href": "https://example.invalid/search",
                   "body": {"next": "T"}}],
    }
    http = fake_http_factory([page_one], fail_after=1)
    client = CatalogClient(http, probe_assets=False)
    result = client.search(make_request(aoi))
    assert len(result.items) == 1
    assert any(r["item_id"] == "<pagination>" for r in result.rejected)


def test_asset_probe_failure_rejects_item(aoi, fake_http_factory, stac_item_factory):
    http = fake_http_factory(
        [{"type": "FeatureCollection", "features": [stac_item_factory()], "links": []}]
    )
    http.probe = lambda url: (403, "application/json")
    client = CatalogClient(http, probe_assets=True)
    result = client.search(make_request(aoi))
    assert result.items == []
    assert "403" in result.rejected[0]["reason"]


def test_collection_without_required_assets_rejected(fake_http_factory):
    http = fake_http_factory([{"id": "sentinel-2-l2a", "item_assets": {"red": {}}}])
    client = CatalogClient(http)
    with pytest.raises(CatalogUnavailable, match="lacks assets"):
        client.load_collection()


def test_collection_with_required_assets_accepted(fake_http_factory):
    assets = {
        key: {"raster:bands": [{"spatial_resolution": 20 if key == "scl" else 10}]}
        for key in ("blue", "green", "red", "nir", "scl")
    }
    http = fake_http_factory([{"id": "sentinel-2-l2a", "item_assets": assets}])
    client = CatalogClient(http)
    meta = client.load_collection()
    assert meta["id"] == "sentinel-2-l2a"


def test_collection_metadata_outage(aoi, fake_http_factory):
    http = fake_http_factory([], fail_after=0)
    client = CatalogClient(http)
    with pytest.raises(CatalogUnavailable):
        client.load_collection()


def test_request_collection_mismatch(aoi, fake_http_factory):
    http = fake_http_factory([{"features": [], "links": []}])
    client = CatalogClient(http)
    with pytest.raises(ValueError):
        client.search(make_request(aoi, collection="sentinel-2-c1-l2a"))
