"""AOI geometry loading, validation and grid derivation.

An AOI is stored as a GeoJSON polygon in EPSG:4326 (WGS84).  Everything that
lands on disk is normalised through this module so that an invalid or
degenerate polygon fails before any network call happens.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyproj import CRS, Transformer
from rasterio.transform import Affine
from shapely.geometry import Polygon, box, shape
from shapely.ops import transform as shapely_transform

from .. import config


class AOIError(ValueError):
    """Raised when an AOI is invalid or unusable for analysis."""


@dataclass(frozen=True)
class AOI:
    """A validated study window in WGS84 plus its projected grid."""

    study_id: str
    polygon: Polygon                 # EPSG:4326, shapely
    description: str
    source: str

    # -- derived ----------------------------------------------------------- #
    @property
    def bounds_4326(self) -> tuple[float, float, float, float]:
        """``(min_lon, min_lat, max_lon, max_lat)``."""
        return self.polygon.bounds

    @property
    def bbox(self) -> list[float]:
        return list(self.bounds_4326)

    @property
    def utm_epsg(self) -> int:
        lon = self.polygon.centroid.x
        lat = self.polygon.centroid.y
        zone = int(math.floor((lon + 180.0) / 6.0) + 1)
        if 1 <= zone <= 60 and abs(lat) < 84:
            return (32600 if lat >= 0 else 32700) + zone
        return 6933  # equal-area fallback outside UTM coverage

    def projected(self) -> Polygon:
        """Reproject to the analysis CRS for metric work."""
        transformer = Transformer.from_crs(
            CRS.from_epsg(4326), CRS.from_epsg(self.utm_epsg), always_xy=True
        )
        return shapely_transform(transformer.transform, self.polygon)

    def area_km2(self) -> float:
        return self.projected().area / 1_000_000.0

    def grid_transform(self, resolution: float = config.GRID_RESOLUTION) -> Affine:
        """Snapped north-up transform covering the AOI, in the UTM CRS."""
        minx, miny, maxx, maxy = self.projected().bounds
        left = math.floor(minx / resolution) * resolution
        top = math.ceil(maxy / resolution) * resolution
        if self.grid_shape(resolution)[0] * self.grid_shape(resolution)[1] > (
            config.MAX_WINDOW_PIXELS
        ):
            raise AOIError(
                f"AOI {self.study_id!r} exceeds MAX_WINDOW_PIXELS "
                f"({config.MAX_WINDOW_PIXELS}) at {resolution} m"
            )
        return Affine(resolution, 0.0, left, 0.0, -resolution, top)

    def grid_shape(self, resolution: float = config.GRID_RESOLUTION) -> tuple[int, int]:
        minx, miny, maxx, maxy = self.projected().bounds
        width = math.ceil((maxx - minx) / resolution)
        height = math.ceil((maxy - miny) / resolution)
        return height, width

    def to_geojson(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "properties": {
                "study_id": self.study_id,
                "description": self.description,
                "source": self.source,
                "crs": "EPSG:4326",
                "area_km2": round(self.area_km2(), 6),
                "utm_epsg": self.utm_epsg,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [list(map(list, self.polygon.exterior.coords))],
            },
        }

    def covers(self, other: Polygon) -> bool:
        """True when ``other`` fully contains this AOI (scene coverage test)."""
        return other.covers(self.polygon)



def validate_polygon(
    polygon: Polygon,
    *,
    study_id: str = "unnamed",
    min_area_km2: float = 0.05,
    max_area_km2: float = 400.0,
) -> None:
    """Reject degenerate, unclosed, out-of-range or absurd AOIs."""
    if polygon.is_empty:
        raise AOIError(f"AOI {study_id!r} is empty")
    if not polygon.is_valid:
        raise AOIError(f"AOI {study_id!r} is not a valid polygon")
    if polygon.geom_type != "Polygon":
        raise AOIError(f"AOI {study_id!r} must be a Polygon, got {polygon.geom_type}")
    if len(polygon.exterior.coords) < 4:
        raise AOIError(f"AOI {study_id!r} has fewer than 4 ring coordinates")

    minx, miny, maxx, maxy = polygon.bounds
    if not (-180.0 <= minx <= 180.0 and -180.0 <= maxx <= 180.0):
        raise AOIError(f"AOI {study_id!r} longitude outside [-180, 180]")
    if not (-90.0 <= miny <= 90.0 and -90.0 <= maxy <= 90.0):
        raise AOIError(f"AOI {study_id!r} latitude outside [-90, 90]")

    area = _wgs84_area_km2(polygon)
    if area < min_area_km2:
        raise AOIError(f"AOI {study_id!r} area {area:.4f} km2 below {min_area_km2}")
    if area > max_area_km2:
        raise AOIError(f"AOI {study_id!r} area {area:.2f} km2 above {max_area_km2}")


def _wgs84_area_km2(polygon: Polygon) -> float:
    lon = polygon.centroid.x
    lat = polygon.centroid.y
    zone = int(math.floor((lon + 180.0) / 6.0) + 1)
    epsg = (32600 if lat >= 0 else 32700) + zone
    projected = shapely_transform(
        Transformer.from_crs(4326, epsg, always_xy=True).transform, polygon
    )
    return projected.area / 1_000_000.0


def aoi_from_bounds(
    *,
    study_id: str,
    west: float,
    south: float,
    east: float,
    north: float,
    description: str,
    source: str,
) -> AOI:
    """Build a rectangular AOI from WGS84 bounds."""
    if west >= east or south >= north:
        raise AOIError(f"bounds are inverted for {study_id!r}")
    polygon = box(west, south, east, north)
    validate_polygon(polygon, study_id=study_id)
    return AOI(
        study_id=study_id, polygon=polygon, description=description, source=source
    )


def aoi_from_geojson(study_id: str, payload: dict[str, Any]) -> AOI:
    geometry = payload.get("geometry", payload)
    try:
        polygon = shape(geometry)
    except Exception as exc:
        raise AOIError(f"cannot interpret AOI geometry for {study_id!r}: {exc}") from exc
    if not isinstance(polygon, Polygon):
        raise AOIError(f"AOI {study_id!r} is not a polygon geometry")
    validate_polygon(polygon, study_id=study_id)
    properties = payload.get("properties") or {}
    return AOI(
        study_id=study_id,
        polygon=polygon,
        description=str(properties.get("description", "")),
        source=str(properties.get("source", "")),
    )


def load_aoi(path: Path, study_id: str) -> AOI:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return aoi_from_geojson(study_id, payload)
