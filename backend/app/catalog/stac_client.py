"""STAC catalogue client for Element 84 Earth Search.

Responsibilities:
  * verify the collection still exposes the asset keys and grid we rely on;
  * run bounded, paginated, rate-limited, cached searches;
  * convert hits into :class:`SceneCandidate` objects and record rejects;
  * confirm that asset URLs are actually anonymously readable.

Nothing here touches raster data; windowed reads live in
:mod:`backend.app.acquisition`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .. import config
from ..http import HttpSession, NetworkError
from .models import MetadataError, SceneCandidate
from .search import SearchRequest

LOGGER = logging.getLogger(__name__)


class CatalogUnavailable(RuntimeError):
    """The catalogue could not be reached or is not serving the collection."""


@dataclass
class SearchResult:
    """Outcome of one search, including honest reject accounting."""

    request: SearchRequest
    items: list[SceneCandidate] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)
    pages_fetched: int = 0
    matched_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.describe(),
            "returned_items": len(self.items) + len(self.rejected),
            "accepted_items": len(self.items),
            "pages_fetched": self.pages_fetched,
            "catalog_matched_count": self.matched_count,
            "rejected": self.rejected,
        }


class CatalogClient:
    """Minimal, defensive STAC client bound to one endpoint."""

    def __init__(
        self,
        http: HttpSession,
        *,
        catalog_url: str = config.CATALOG_URL,
        collection: str = config.COLLECTION,
        probe_assets: bool = True,
        required_assets: tuple[str, ...] = config.REQUIRED_ASSETS,
    ) -> None:
        self.http = http
        self.catalog_url = catalog_url.rstrip("/")
        self.collection = collection
        self.collection_meta: dict[str, Any] | None = None
        self.probe_assets = probe_assets
        #: Asset keys every accepted item must expose.  M0 uses the NDVI set;
        #: M1 widens it to the full spectral set so SWIR is not silently absent.
        self.required_assets = tuple(required_assets)

    # -- capability checks -------------------------------------------------- #
    def load_collection(self) -> dict[str, Any]:
        """Fetch and validate collection metadata (asset keys, GSD)."""
        url = f"{self.catalog_url}/collections/{self.collection}"
        try:
            meta = self.http.get_json(url, cache_key=f"collection:{url}")
        except NetworkError as exc:
            raise CatalogUnavailable(f"cannot read collection metadata: {exc}") from exc

        item_assets = meta.get("item_assets") or {}
        if not item_assets:
            raise CatalogUnavailable(
                f"collection {self.collection} exposes no item_assets"
            )
        missing = [k for k in self.required_assets if k not in item_assets]
        if missing:
            raise CatalogUnavailable(
                f"collection {self.collection} lacks assets: {', '.join(missing)}"
            )

        for key in self.required_assets:
            declared = item_assets[key].get("raster:bands") or [{}]
            gsd = declared[0].get("spatial_resolution")
            expected = config.EXPECTED_GSD[key]
            if gsd is not None and abs(float(gsd) - expected) > 1e-6:
                LOGGER.warning(
                    "asset %s native GSD %s m differs from expected %s m",
                    key, gsd, expected,
                )
        self.collection_meta = meta
        return meta

    # -- search ------------------------------------------------------------- #
    def search(self, request: SearchRequest) -> SearchResult:
        if request.collection != self.collection:
            raise ValueError(
                f"request collection {request.collection!r} != client "
                f"{self.collection!r}"
            )
        result = SearchResult(request=request)
        body = request.to_stac_body()
        url: str | None = f"{self.catalog_url}/search"
        pages = 0
        while url and pages < 20 and (
            len(result.items) + len(result.rejected) < request.max_items
        ):
            cache_key = request.cache_key(self.catalog_url) + f":page{pages}"
            try:
                payload = self.http.post_json(url, payload=body, cache_key=cache_key)
            except NetworkError as exc:
                if pages == 0:
                    raise CatalogUnavailable(str(exc)) from exc
                LOGGER.warning("pagination stopped early: %s", exc)
                result.rejected.append({"item_id": "<pagination>", "reason": str(exc)})
                break
            pages += 1

            if result.matched_count is None and isinstance(payload.get("context"), dict):
                result.matched_count = payload["context"].get("matched")

            for raw in payload.get("features") or []:
                item_id = str(raw.get("id", "<unknown>"))
                try:
                    candidate = SceneCandidate.from_stac(
                        raw,
                        catalog_url=self.catalog_url,
                        required_assets=self.required_assets,
                    )
                except MetadataError as exc:
                    result.rejected.append({"item_id": item_id, "reason": str(exc)})
                    continue
                result.items.append(candidate)
                if len(result.items) + len(result.rejected) >= request.max_items:
                    break

            follow = self._next_page(payload, body)
            if follow is None:
                url = None
            else:
                url, body = follow

        result.pages_fetched = pages
        LOGGER.info(
            "search %r: %d accepted, %d rejected, %d page(s)",
            request.label, len(result.items), len(result.rejected), pages,
        )
        if self.probe_assets and result.items:
            self._probe_asset_access(result)
        return result

    # -- helpers ------------------------------------------------------------ #
    @staticmethod
    def _next_page(
        payload: dict[str, Any], current_body: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """Resolve the next page.

        Earth Search returns ``rel=next`` POST links whose page token lives in
        the link ``body`` (``next`` key), optionally merged into the query.  The
        link body must therefore replace — never be discarded in favour of the
        original — or pagination repeats page one forever.
        """
        for link in payload.get("links") or []:
            if link.get("rel") != "next":
                continue
            href = link.get("href")
            if not href:
                continue
            if link.get("method", "GET").upper() == "POST":
                next_body = link.get("body")
                if not next_body:
                    continue
                merged = {**current_body, **next_body} if link.get("merge") else dict(next_body)
                return href, merged
            return href, current_body
        return None

    def _probe_asset_access(self, result: SearchResult) -> None:
        """HEAD one asset to prove anonymous readability of this catalogue."""
        candidate = result.items[0]
        red = candidate.assets.get(config.ASSET_RED)
        if red is None:
            return
        status, content_type = self.http.probe(red.href)
        ok = status == 200 and "tiff" in content_type.lower()
        LOGGER.info(
            "asset probe %s -> HTTP %s (%s)", candidate.item_id, status, content_type
        )
        if not ok:
            result.rejected.append(
                {
                    "item_id": candidate.item_id,
                    "reason": f"asset probe HTTP {status} ({content_type or 'no type'})",
                }
            )
            result.items.remove(candidate)

