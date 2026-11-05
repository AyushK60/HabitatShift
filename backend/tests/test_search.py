"""STAC query construction and cache-key determinism."""

from __future__ import annotations

import datetime as dt

import pytest

from backend.app.catalog.search import SearchError, SearchRequest


def make_request(aoi, **kwargs) -> SearchRequest:
    defaults = dict(
        aoi=aoi,
        start=dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc),
        end=dt.datetime(2020, 5, 31, tzinfo=dt.timezone.utc),
        max_cloud_cover=40.0,
        limit=50,
        label="unit",
    )
    defaults.update(kwargs)
    return SearchRequest(**defaults)


def test_body_contains_collection_aoi_window_and_cloud(aoi):
    body = make_request(aoi).to_stac_body()
    assert body["collections"] == ["sentinel-2-l2a"]
    assert body["datetime"] == "2020-01-01T00:00:00Z/2020-05-31T00:00:00Z"
    assert body["query"]["eo:cloud_cover"]["lte"] == 40.0
    assert body["intersects"]["type"] == "Polygon"
    ring = body["intersects"]["coordinates"][0]
    assert len(ring) >= 4
    assert ring[0] == ring[-1], "polygon ring must be closed"


def test_body_polygon_matches_aoi_bounds(aoi):
    body = make_request(aoi).to_stac_body()
    lons = [x for x, _ in body["intersects"]["coordinates"][0]]
    lats = [y for _, y in body["intersects"]["coordinates"][0]]
    assert min(lons) == pytest.approx(aoi.bounds_4326[0])
    assert max(lons) == pytest.approx(aoi.bounds_4326[2])
    assert min(lats) == pytest.approx(aoi.bounds_4326[1])
    assert max(lats) == pytest.approx(aoi.bounds_4326[3])


def test_cache_key_is_deterministic_and_sensitive(aoi):
    url = "https://earth-search.aws.element84.com/v1"
    first = make_request(aoi).cache_key(url)
    second = make_request(aoi).cache_key(url)
    assert first == second
    other = make_request(aoi, max_cloud_cover=10.0).cache_key(url)
    assert other != first


def test_naive_datetimes_are_treated_as_utc(aoi):
    request = make_request(aoi, start=dt.datetime(2020, 2, 1), end=dt.datetime(2020, 3, 1))
    assert request.to_stac_body()["datetime"].endswith("Z")


def test_inverted_window_rejected(aoi):
    with pytest.raises(SearchError):
        make_request(
            aoi,
            start=dt.datetime(2020, 5, 1, tzinfo=dt.timezone.utc),
            end=dt.datetime(2020, 4, 1, tzinfo=dt.timezone.utc),
        )


def test_cloud_cover_bounds(aoi):
    with pytest.raises(SearchError):
        make_request(aoi, max_cloud_cover=140.0)
    with pytest.raises(SearchError):
        make_request(aoi, max_cloud_cover=-1.0)


def test_limit_bounds(aoi):
    with pytest.raises(SearchError):
        make_request(aoi, limit=0)
    with pytest.raises(SearchError):
        make_request(aoi, limit=5000)


def test_window_longer_than_400_days_rejected(aoi):
    with pytest.raises(SearchError):
        make_request(
            aoi,
            start=dt.datetime(2019, 1, 1, tzinfo=dt.timezone.utc),
            end=dt.datetime(2021, 1, 1, tzinfo=dt.timezone.utc),
        )


def test_describe_records_reproducible_parameters(aoi):
    described = make_request(aoi).describe()
    assert described["collection"] == "sentinel-2-l2a"
    assert described["max_cloud_cover_percent"] == 40.0
    assert "request_body" in described


def test_query_params_carry_bbox(aoi):
    params = make_request(aoi).to_query_params()
    assert set(params["bbox"].split(",")) == {
        f"{v:.6f}" for v in aoi.bbox
    }
