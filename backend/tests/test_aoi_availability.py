"""Custom-AOI availability: bounds/date/area limits and honest output (no network)."""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from backend.app.api import app as api_module
from backend.app.catalog.availability import AvailabilityError, check_availability
from backend.app.catalog.stac_client import CatalogClient, CatalogUnavailable

D = dt.date
# roughly 4 km x 4 km box near Chilika
BOX = dict(west=85.30, south=19.70, east=85.34, north=19.74)
OK = dict(start=D(2024, 1, 1), end=D(2024, 3, 1), today=D(2026, 11, 1))


def client_with(fake_http_factory, items):
    http = fake_http_factory([{"type": "FeatureCollection", "features": items, "links": []}])
    return CatalogClient(http, probe_assets=False)


def test_returns_sorted_scenes_with_honest_notes(fake_http_factory, stac_item_factory):
    items = [stac_item_factory(), stac_item_factory()]
    items[0]["id"], items[1]["id"] = "S2B_B_20240210", "S2A_A_20240105"
    out = check_availability(**BOX, **OK, client=client_with(fake_http_factory, items))
    assert out["scenes_found"] == 2
    assert out["aoi"]["area_km2"] < 100
    assert any("not analysis" in note.lower() for note in out["honest_notes"])


def test_empty_result_is_zero_not_error(fake_http_factory):
    out = check_availability(**BOX, **OK, client=client_with(fake_http_factory, []))
    assert out["scenes_found"] == 0 and out["scenes"] == []


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        (dict(west=85.0, south=19.0, east=86.5, north=20.5), "limit"),
        (dict(west=85.30, south=19.70, east=85.3001, north=19.7001), "below"),
        (dict(west=86.0, east=85.0), "bounds"),
        (dict(south=95.0, north=96.0), "bounds"),
        (dict(start=D(2010, 1, 1), end=D(2010, 3, 1)), "Sentinel-2"),
        (dict(start=D(2024, 1, 1), end=D(2026, 12, 1)), "future"),
        (dict(start=D(2022, 1, 1), end=D(2024, 3, 1)), "400"),
        (dict(start=D(2024, 3, 1), end=D(2024, 1, 1)), "precede"),
        (dict(max_cloud=150), "max_cloud"),
    ],
)
def test_invalid_inputs_are_rejected_before_any_request(fake_http_factory, overrides, fragment):
    params = {**BOX, **OK, **overrides}
    http = fake_http_factory([])
    with pytest.raises(AvailabilityError, match=fragment):
        check_availability(**params, client=CatalogClient(http, probe_assets=False))
    assert http.request_count == 0


def test_catalogue_outage_surfaces_as_unavailable(fake_http_factory):
    client = CatalogClient(fake_http_factory([], fail_after=0), probe_assets=False)
    with pytest.raises(CatalogUnavailable):
        check_availability(**BOX, **OK, client=client)


def test_api_route_maps_errors_to_http_codes(monkeypatch):
    test_client = TestClient(api_module.app)
    good = dict(west=85.3, south=19.7, east=85.34, north=19.74, start="2024-01-01", end="2024-03-01")
    r = test_client.get("/api/aoi/availability", params={**good, "west": 85.0, "south": 19.0, "east": 86.5, "north": 20.5})
    assert r.status_code == 422 and "limit" in r.json()["detail"]
    r = test_client.get("/api/aoi/availability", params={**good, "start": "not-a-date"})
    assert r.status_code == 422

    def boom(**kwargs):
        raise CatalogUnavailable("down")

    monkeypatch.setattr(api_module, "check_availability", boom)
    r = test_client.get("/api/aoi/availability", params=good)
    assert r.status_code == 502
