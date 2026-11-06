"""Factories for M1 unit tests.

Everything here is synthetic.  Real-image results are checked by the engine's
own independent re-read pass and by the audit script, never by these factories.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from backend.app.acquisition.assets import Radiometry
from backend.app.catalog.models import SceneCandidate
from backend.app.preprocess.composite import Observation
from backend.app.preprocess.masks import MaskReport
from backend.app.preprocess.scoring import SceneScore

DEFAULT_ASSETS = ("blue", "green", "red", "nir", "swir16", "scl")


def make_item(
    *,
    item_id: str = "S2B_44QPD_20250119_0_L2A",
    acquired: str = "2025-01-19T05:14:06.775000Z",
    cloud: float | None = 0.88,
    assets: tuple[str, ...] = DEFAULT_ASSETS,
    href_prefix: str = "https://example.invalid/",
    scale: float = 0.0001,
    offset: float = 0.0,
    nodata: int = 0,
    baseline: str | None = "05.00",
    gsd_by_asset: dict[str, float] | None = None,
) -> dict:
    """Build an Earth-Search-shaped STAC item with SWIR assets."""
    gsd_by_asset = gsd_by_asset or {}
    payload = {}
    for key in assets:
        gsd = gsd_by_asset.get(
            key, 20.0 if key in {"scl", "swir16", "swir22"} else 10.0
        )
        payload[key] = {
            "href": f"{href_prefix}{item_id}_{key}.tif",
            "type": "image/tiff; application=geotiff; profile=cloud-optimized",
            "gsd": gsd,
            "raster:bands": [
                {
                    "nodata": nodata,
                    "data_type": "uint16",
                    "spatial_resolution": gsd,
                    "scale": scale,
                    "offset": offset,
                }
            ],
        }
    properties: dict = {
        "platform": "sentinel-2b",
        "constellation": "sentinel-2",
        "instruments": ["msi"],
        "eo:cloud_cover": cloud,
        "proj:epsg": 32644,
        "grid:code": "MGRS-44QPD",
        "datetime": acquired,
    }
    if baseline is not None:
        properties["processing:baseline"] = baseline
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
        "assets": payload,
        "links": [],
    }


def make_candidate(
    *,
    item_id: str = "S2B_44QPD_20250119_0_L2A",
    acquired: str = "2025-01-19T05:14:06.775000Z",
    cloud: float | None = 0.88,
    assets: tuple[str, ...] = DEFAULT_ASSETS,
    href_prefix: str = "https://example.invalid/",
    scale: float = 0.0001,
    offset: float = 0.0,
    nodata: int = 0,
    baseline: str | None = "05.00",
    gsd_by_asset: dict[str, float] | None = None,
) -> SceneCandidate:
    return SceneCandidate.from_stac(
        make_item(
            item_id=item_id,
            acquired=acquired,
            cloud=cloud,
            assets=assets,
            href_prefix=href_prefix,
            scale=scale,
            offset=offset,
            nodata=nodata,
            baseline=baseline,
            gsd_by_asset=gsd_by_asset,
        ),
        catalog_url="https://example.invalid/v1",
        required_assets=assets,
    )


def radiometry_for(
    candidate: SceneCandidate, keys: tuple[str, ...] = ("red",)
) -> dict[str, Radiometry]:
    return {
        key: Radiometry(
            asset_key=key,
            scale=candidate.asset(key).scale,
            offset=candidate.asset(key).offset,
            nodata=candidate.asset(key).nodata,
            gsd=candidate.asset(key).gsd,
            source="test",
        )
        for key in keys
    }


def make_observation(
    *,
    period_id: str = "earlier",
    item_id: str = "S2B_44QPD_20250119_0_L2A",
    date: str = "2025-01-19T05:14:06.775000Z",
    bands: dict[str, np.ndarray] | None = None,
    valid: np.ndarray | None = None,
    signature: str = "grid-a",
    cloud: float | None = 1.0,
) -> Observation:
    bands = bands or {"red": np.array([[0.1, 0.2]], dtype=np.float32)}
    valid = valid if valid is not None else np.ones(next(iter(bands.values())).shape, dtype=bool)
    candidate = make_candidate(item_id=item_id, acquired=date, cloud=cloud)
    keys = tuple(bands)
    report = MaskReport(
        total_pixels=int(valid.size),
        valid_pixels=int(valid.sum()),
        class_counts={4: int(valid.sum())},
    )
    return Observation(
        period_id=period_id,
        candidate=candidate,
        reflectance={key: np.where(valid, value, np.nan) for key, value in bands.items()},
        valid=valid,
        mask_report=report,
        radiometry=radiometry_for(candidate, keys),
        grid_signature=signature,
    )


def make_score(
    *,
    item_id: str,
    acquired: str,
    cloud: float | None = 1.0,
    valid: float | None = 0.9,
    usable: bool = True,
    intersection: float = 1.0,
) -> SceneScore:
    return SceneScore(
        item_id=item_id,
        acquired=acquired,
        cloud_cover_percent=cloud,
        aoi_intersection_fraction=intersection,
        aoi_valid_fraction=valid,
        usable=usable,
    )


def utc(text: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
