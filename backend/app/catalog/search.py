"""Construction of STAC search requests.

A :class:`SearchRequest` is a pure value object: given the same inputs it always
produces the same JSON body and the same cache key, which is what makes the M0
retrieval reproducible.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .. import config
from ..preprocess.aoi import AOI


class SearchError(ValueError):
    """Raised when a search request cannot be built."""


def _iso_utc(value: dt.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class SearchRequest:
    """A single, explicit, bounded catalogue query."""

    aoi: AOI
    start: dt.datetime
    end: dt.datetime
    collection: str = config.COLLECTION
    max_cloud_cover: float = 40.0
    limit: int = 100
    max_items: int = config.MAX_ITEMS_PER_SEARCH
    label: str = ""
    extra_filters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise SearchError("search start must precede end")
        if not 0.0 <= self.max_cloud_cover <= 100.0:
            raise SearchError("max_cloud_cover must be within [0, 100]")
        if self.limit < 1 or self.limit > self.max_items:
            raise SearchError(f"limit {self.limit} outside 1..{self.max_items}")
        if (self.end - self.start).days > 400:
            raise SearchError("search window longer than 400 days")

    # -- serialisation ----------------------------------------------------- #
    @property
    def datetime_range(self) -> str:
        return f"{_iso_utc(self.start)}/{_iso_utc(self.end)}"

    def to_stac_body(self) -> dict[str, Any]:
        """Build the POST /search body.

        ``intersects`` is used rather than ``bbox`` so the exact AOI polygon is
        honoured, and the cloud threshold is applied server-side to keep the
        page count small.
        """
        body: dict[str, Any] = {
            "collections": [self.collection],
            "intersects": {
                "type": "Polygon",
                "coordinates": [list(map(list, self.aoi.polygon.exterior.coords))],
            },
            "datetime": self.datetime_range,
            "limit": self.limit,
            "query": {"eo:cloud_cover": {"lte": self.max_cloud_cover}},
        }
        if self.extra_filters:
            body["query"].update(self.extra_filters)
        return body

    def to_query_params(self) -> dict[str, str]:
        """Equivalent GET parameters (kept for catalogue cross-checking)."""
        return {
            "collections": self.collection,
            "bbox": ",".join(f"{v:.6f}" for v in self.aoi.bbox),
            "datetime": self.datetime_range,
            "limit": str(self.limit),
            "query": json.dumps({"eo:cloud_cover": {"lte": self.max_cloud_cover}}),
        }

    def cache_key(self, catalog_url: str) -> str:
        canonical = {
            "catalog": catalog_url,
            "body": self.to_stac_body(),
        }
        return "search:" + hashlib.sha256(
            json.dumps(canonical, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def describe(self) -> dict[str, Any]:
        """Reproducible description for manifests."""
        return {
            "label": self.label,
            "collection": self.collection,
            "aoi_bounds_4326": list(self.aoi.bounds_4326),
            "start_utc": _iso_utc(self.start),
            "end_utc": _iso_utc(self.end),
            "max_cloud_cover_percent": self.max_cloud_cover,
            "limit": self.limit,
            "max_items": self.max_items,
            "request_body": self.to_stac_body(),
        }
