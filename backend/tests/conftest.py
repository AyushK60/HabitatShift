"""Shared, deterministic test fixtures (synthetic data unless stated)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.preprocess.aoi import AOI, aoi_from_bounds        # noqa: E402


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def seam_study() -> dict:
    """A small, valid coastal AOI descriptor reused across tests."""
    return {
        "study_id": "test_coastal",
        "title": "Test coastal AOI",
        "study_type": "coastal_ecotone",
        "question": "Does the pipeline read what it claims?",
        "phenomena": ["vegetation"],
        "limitations": ["synthetic"],
        "aoi": {
            "kind": "test window",
            "boundary_source": "unit test",
            "bounds": {
                "west": 82.2450,
                "south": 16.7100,
                "east": 82.2850,
                "north": 16.7450,
            },
        },
    }


@pytest.fixture
def aoi(seam_study) -> AOI:
    b = seam_study["aoi"]["bounds"]
    return aoi_from_bounds(
        study_id=seam_study["study_id"],
        west=b["west"],
        south=b["south"],
        east=b["east"],
        north=b["north"],
        description=seam_study["aoi"]["kind"],
        source=seam_study["aoi"]["boundary_source"],
    )


@pytest.fixture
def small_aoi() -> AOI:
    """~1.1 km window: keeps synthetic rasters tiny."""
    return aoi_from_bounds(
        study_id="test_small",
        west=82.2600,
        south=16.7200,
        east=82.2700,
        north=16.7300,
        description="tiny window",
        source="unit test",
    )


@pytest.fixture
def scl_array() -> np.ndarray:
    """8x8 SCL with one pixel of each policy case."""
    array = np.full((8, 8), 4, dtype=np.int32)      # vegetation
    array[0, 0] = 0                                  # nodata
    array[0, 1] = 1                                  # saturated
    array[0, 2] = 3                                  # cloud shadow
    array[0, 3] = 8                                  # medium cloud
    array[0, 4] = 9                                  # high cloud
    array[0, 5] = 10                                 # cirrus
    array[1, 0] = 6                                  # water
    array[1, 1] = 11                                 # snow
    array[1, 2] = 5                                  # not vegetated
    array[1, 3] = 2                                  # dark pixels
    array[1, 4] = 7                                  # unclassified
    return array


def make_item(
    *,
    item_id: str = "S2B_44QPD_20250119_0_L2A",
    acquired: str = "2025-01-19T05:14:06.775000Z",
    cloud: float | None = 0.88,
    include_assets: tuple[str, ...] = ("blue", "green", "red", "nir", "scl"),
    datetime_present: bool = True,
    href_prefix: str = "https://example.invalid/",
    scale: float = 0.0001,
    offset: float = 0.0,
    nodata: int = 0,
) -> dict:
    """Build a STAC item shaped like an Earth Search result."""
    assets = {
        key: {
            "href": f"{href_prefix}{item_id}_{key}.tif",
            "type": "image/tiff; application=geotiff; profile=cloud-optimized",
            "gsd": 20 if key == "scl" else 10,
            "raster:bands": [
                {
                    "nodata": nodata,
                    "data_type": "uint16",
                    "spatial_resolution": 20 if key == "scl" else 10,
                    "scale": scale,
                    "offset": offset,
                }
            ],
        }
        for key in include_assets
    }
    properties: dict = {
        "platform": "sentinel-2b",
        "constellation": "sentinel-2",
        "instruments": ["msi"],
        "eo:cloud_cover": cloud,
        "proj:epsg": 32644,
        "grid:code": "MGRS-44QPD",
        "processing:baseline": "05.00",
    }
    if datetime_present:
        properties["datetime"] = acquired
    return {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": item_id,
        "collection": "sentinel-2-l2a",
        "bbox": [82.2, 16.6, 82.4, 16.8],
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[82.2, 16.6], [82.4, 16.6], [82.4, 16.8], [82.2, 16.8], [82.2, 16.6]]
            ],
        },
        "properties": properties,
        "assets": assets,
        "links": [],
    }


@pytest.fixture
def stac_item_factory():
    return make_item


class FakeHttp:
    """Minimal stand-in for :class:`backend.app.http.HttpSession`."""

    def __init__(self, responses: list[dict], fail_after: int | None = None) -> None:
        self.responses = list(responses)
        self.fail_after = fail_after
        self.calls: list[dict] = []
        self.request_count = 0
        self.bytes_downloaded = 0

    def post_json(self, url, *, payload=None, cache_key=None, use_cache=True):
        self.calls.append({"url": url, "payload": payload})
        self.request_count += 1
        if self.fail_after is not None and self.request_count > self.fail_after:
            from backend.app.http import NetworkError

            raise NetworkError("simulated outage")
        if not self.responses:
            return {"type": "FeatureCollection", "features": [], "links": []}
        return self.responses.pop(0)

    def get_json(self, url, *, params=None, cache_key=None, use_cache=True):
        self.calls.append({"url": url})
        self.request_count += 1
        return self.responses.pop(0) if self.responses else {}

    def probe(self, url):
        return 200, "image/tiff; application=geotiff; profile=cloud-optimized"


@pytest.fixture
def fake_http_factory():
    return FakeHttp


@pytest.fixture
def registry_yaml() -> dict:
    return yaml.safe_load(
        (PROJECT_ROOT / "studies" / "registry.yaml").read_text("utf-8")
    )
