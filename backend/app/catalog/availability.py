"""Bounded scene-availability check for a user-drawn area (scene DISCOVERY only).

This is the first, safe stage of a custom-AOI mode: before anyone asks for
processing, show honestly which Sentinel-2 L2A scenes exist over a small box and
how cloudy they are. No imagery is downloaded and nothing is processed.

Hard limits (all enforced server-side, all returned in errors):
  * box area between 0.05 and 100 km2
  * date window at most 400 days (the existing SearchRequest rule)
  * Sentinel-2 L2A only; start not before 2015-06-23 (first launch); end not in the future
  * at most 100 scenes returned
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from .. import config
from ..http import HttpSession
from ..preprocess.aoi import AOIError, aoi_from_bounds
from .search import SearchError, SearchRequest
from .stac_client import CatalogClient

MAX_AREA_KM2 = 100.0
MIN_AREA_KM2 = 0.05
MAX_SCENES = 100
SENTINEL2_FIRST_DATE = dt.date(2015, 6, 23)


class AvailabilityError(ValueError):
    """Invalid user input (maps to HTTP 422)."""


def _client() -> CatalogClient:
    return CatalogClient(HttpSession(cache_dir=config.CACHE_DIR), probe_assets=False)


def check_availability(
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    start: dt.date,
    end: dt.date,
    max_cloud: float = 60.0,
    client: CatalogClient | None = None,
    today: dt.date | None = None,
) -> dict[str, Any]:
    today = today or dt.date.today()
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise AvailabilityError("bounds must satisfy -180<=west<east<=180 and -90<=south<north<=90")
    if start < SENTINEL2_FIRST_DATE:
        raise AvailabilityError(f"Sentinel-2 L2A starts on {SENTINEL2_FIRST_DATE}; earlier dates have no scenes")
    if end > today:
        raise AvailabilityError("end date is in the future")
    if start >= end:
        raise AvailabilityError("start must precede end")
    if (end - start).days > 400:
        raise AvailabilityError("date window longer than 400 days")
    if not 0 <= max_cloud <= 100:
        raise AvailabilityError("max_cloud must be between 0 and 100")
    try:
        aoi = aoi_from_bounds(
            study_id="custom_aoi", west=west, south=south, east=east, north=north,
            description="user-drawn availability check", source="user",
        )
    except AOIError as exc:
        message = str(exc)
        if "above" in message:
            message = message.replace("above", "exceeds the limit of")
        raise AvailabilityError(message) from exc
    area = aoi.area_km2()
    if area > MAX_AREA_KM2:
        raise AvailabilityError(f"area {area:.1f} km2 exceeds the {MAX_AREA_KM2:.0f} km2 limit")
    if area < MIN_AREA_KM2:
        raise AvailabilityError(f"area {area:.3f} km2 is below the {MIN_AREA_KM2} km2 minimum")

    request = SearchRequest(
        aoi=aoi,
        start=dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc),
        end=dt.datetime.combine(end, dt.time.min, tzinfo=dt.timezone.utc),
        max_cloud_cover=max_cloud,
        limit=MAX_SCENES,
        max_items=MAX_SCENES,
        label="availability",
    )
    try:
        result = (client or _client()).search(request)
    except SearchError as exc:
        raise AvailabilityError(str(exc)) from exc
    scenes = sorted(result.items, key=lambda s: s.acquired)
    return {
        "schema": "habitatshift-aoi-availability/1",
        "aoi": {"bounds_4326": [west, south, east, north], "area_km2": round(area, 3)},
        "window": {"start": start.isoformat(), "end": end.isoformat(), "max_scene_cloud_percent": max_cloud},
        "scenes_found": len(scenes),
        "truncated_at_limit": len(scenes) + len(result.rejected) >= MAX_SCENES,
        "catalog_matched_count": result.matched_count,
        "scenes": [
            {"id": s.item_id, "date": s.date_str, "scene_cloud_percent": s.cloud_cover, "platform": s.platform}
            for s in scenes
        ],
        "honest_notes": [
            "Scene-level cloud cover is a scene-wide figure, not the cloud fraction inside your box; "
            "usable-pixel coverage is only known after masking.",
            "Availability is not analysis: no imagery was read and nothing was processed.",
            "Sentinel-2 L2A covers 2015-06 onwards; this check never implies longer native 10 m records.",
        ],
    }
