"""Typed view over raw STAC items.

The catalog client returns :class:`SceneCandidate` objects rather than raw
dictionaries so that downstream code never has to re-implement defensive
``.get()`` chains, and so that malformed records fail loudly at the boundary.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from .. import config


class MetadataError(ValueError):
    """Raised when a STAC item is missing information M0 requires."""


def _parse_timestamp(value: str) -> dt.datetime:
    text = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise MetadataError(f"unparseable acquisition timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _band_scale_offset(asset: dict[str, Any]) -> tuple[float, float, int | None]:
    """Extract ``(scale, offset, nodata)`` from ``raster:bands`` metadata."""
    bands = asset.get("raster:bands") or []
    if not bands:
        return config.EXPECTED_SCALE, config.NO_OFFSET, None
    band = bands[0]
    scale = band.get("scale", config.EXPECTED_SCALE)
    offset = band.get("offset", config.NO_OFFSET)
    nodata = band.get("nodata")
    try:
        return float(scale), float(offset), None if nodata is None else int(nodata)
    except (TypeError, ValueError) as exc:
        raise MetadataError(f"unusable raster:bands metadata: {band!r}") from exc


@dataclass(frozen=True)
class AssetInfo:
    """Remote reference to a single spectral asset."""

    key: str
    href: str
    media_type: str
    scale: float
    offset: float
    nodata: int | None
    gsd: float | None
    shape: tuple[int, int] | None
    anonymous_access_ok: bool | None = None

    @classmethod
    def from_stac(cls, key: str, asset: dict[str, Any]) -> "AssetInfo":
        if "href" not in asset:
            raise MetadataError(f"asset {key!r} has no href")
        scale, offset, nodata = _band_scale_offset(asset)
        shape_raw = asset.get("proj:shape")
        shape = (
            (int(shape_raw[0]), int(shape_raw[1]))
            if isinstance(shape_raw, list) and len(shape_raw) == 2
            else None
        )
        gsd_raw = asset.get("gsd")
        return cls(
            key=key,
            href=asset["href"],
            media_type=asset.get("type", ""),
            scale=scale,
            offset=offset,
            nodata=nodata,
            gsd=float(gsd_raw) if gsd_raw is not None else None,
            shape=shape,
        )


@dataclass(frozen=True)
class SceneCandidate:
    """Normalised, provenance-complete description of one STAC item."""

    item_id: str
    collection: str
    acquired: dt.datetime
    platform: str
    constellation: str | None
    instrument: str | None
    cloud_cover: float | None
    footprint: dict[str, Any]
    epsg: int | None
    catalog_url: str
    processing_baseline: str | None
    assets: dict[str, AssetInfo] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    # -- derived ----------------------------------------------------------- #
    @property
    def date_str(self) -> str:
        return self.acquired.date().isoformat()

    @property
    def acquisition_iso(self) -> str:
        return self.acquired.isoformat().replace("+00:00", "Z")

    def asset(self, key: str) -> AssetInfo:
        try:
            return self.assets[key]
        except KeyError as exc:
            raise MetadataError(
                f"item {self.item_id} lacks required asset {key!r}"
            ) from exc

    def missing_assets(self, keys=config.REQUIRED_ASSETS) -> list[str]:
        return [key for key in keys if key not in self.assets]

    def cloud_fraction(self) -> float | None:
        return None if self.cloud_cover is None else self.cloud_cover / 100.0

    def to_provenance(self, keys=None) -> dict[str, Any]:
        """Serialise the fields that belong in a manifest.

        ``keys`` selects which assets are recorded.  M0 passes nothing and
        keeps its original asset set; M1 passes every band it actually read so
        the SWIR source is not dropped from provenance.
        """
        selected = config.REQUIRED_ASSETS if keys is None else keys
        return {
            "item_id": self.item_id,
            "collection": self.collection,
            "acquired_utc": self.acquisition_iso,
            "acquisition_date": self.date_str,
            "platform": self.platform,
            "constellation": self.constellation,
            "instrument": self.instrument,
            "cloud_cover_percent": self.cloud_cover,
            "epsg": self.epsg,
            "catalog_url": self.catalog_url,
            "processing_baseline": self.processing_baseline,
            "footprint": self.footprint,
            "assets": {
                key: {
                    "key": a.key,
                    "href": a.href,
                    "media_type": a.media_type,
                    "scale": a.scale,
                    "offset": a.offset,
                    "nodata": a.nodata,
                    "gsd_metres": a.gsd,
                    "shape": list(a.shape) if a.shape else None,
                    "anonymous_access_ok": a.anonymous_access_ok,
                }
                for key, a in self.assets.items()
                if key in selected
            },
        }

    # -- construction ------------------------------------------------------ #
    @classmethod
    def from_stac(
        cls,
        item: dict[str, Any],
        *,
        catalog_url: str,
        required_assets=config.REQUIRED_ASSETS,
    ) -> "SceneCandidate":
        if not isinstance(item, dict):
            raise MetadataError("STAC item is not an object")

        item_id = item.get("id")
        if not item_id:
            raise MetadataError("STAC item has no id")

        properties = item.get("properties") or {}
        acquired_raw = properties.get("datetime") or properties.get("start_datetime")
        if not acquired_raw:
            raise MetadataError(f"item {item_id} has no acquisition datetime")

        raw_assets = item.get("assets") or {}
        missing = [key for key in required_assets if key not in raw_assets]
        if missing:
            raise MetadataError(
                f"item {item_id} is missing required assets: {', '.join(missing)}"
            )
        assets = {
            key: AssetInfo.from_stac(key, raw_assets[key]) for key in required_assets
        }

        cloud = properties.get("eo:cloud_cover")
        proj_epsg = properties.get("proj:epsg")
        platform = properties.get("platform") or properties.get("constellation") or ""
        instruments = properties.get("instruments") or []

        return cls(
            item_id=str(item_id),
            collection=str(item.get("collection") or properties.get("collection") or ""),
            acquired=_parse_timestamp(str(acquired_raw)),
            platform=str(platform),
            constellation=properties.get("constellation"),
            instrument=str(instruments[0]) if instruments else None,
            cloud_cover=float(cloud) if cloud is not None else None,
            footprint=item.get("geometry") or {},
            epsg=int(proj_epsg) if proj_epsg is not None else None,
            catalog_url=catalog_url,
            processing_baseline=properties.get("processing:baseline")
            or properties.get("s2:processing_baseline")
            or properties.get("earthsearch:processingBaseline"),
            assets=assets,
            extra={
                "mgrs_tile": properties.get("grid:code"),
                "view_off_nadir": properties.get("view:off_nadir"),
                "sci_doi": properties.get("sci:doi"),
                # Authoritative switch for whether the -0.1 BOA offset is
                # already baked into the stored DNs of this product.
                "boa_offset_applied": properties.get("earthsearch:boa_offset_applied")
                if properties.get("earthsearch:boa_offset_applied") is not None
                else properties.get("s2:boa_offset_applied"),
            },
        )
