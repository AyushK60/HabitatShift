"""Resilient HTTP access with retries, backoff, rate limiting and caching.

All catalogue/asset traffic in M0 goes through this module so that timeouts,
retry policy and rate limiting are defined in exactly one place.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from . import config

LOGGER = logging.getLogger(__name__)

RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


class NetworkError(RuntimeError):
    """Raised when a remote catalogue or asset request finally fails."""


@dataclass
class CacheEntry:
    path: Path
    age_seconds: float

    @property
    def fresh(self) -> bool:
        return self.age_seconds <= config.CACHE_TTL


class HttpSession:
    """Thin wrapper over :mod:`requests` with project-wide policy."""

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        min_interval: float = config.HTTP_MIN_INTERVAL,
        max_retries: int = config.HTTP_MAX_RETRIES,
        timeout: float = config.HTTP_TIMEOUT,
    ) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": config.USER_AGENT})
        adapter = requests.adapters.HTTPAdapter(pool_maxsize=8)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_call = 0.0
        self.request_count = 0
        self.bytes_downloaded = 0

    # -- public API -------------------------------------------------------- #
    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        cache_key: str | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """GET a JSON document, honouring the on-disk response cache."""
        if use_cache and self.cache_dir is not None and cache_key:
            entry = self._cache_lookup(cache_key)
            if entry is not None and entry.fresh:
                LOGGER.debug("cache hit %s", cache_key)
                return json.loads(entry.path.read_text(encoding="utf-8"))

        response = self._request("GET", url, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise NetworkError(f"Response from {url} was not JSON: {exc}") from exc

        if self.cache_dir is not None and cache_key:
            self._cache_path(cache_key).write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        return payload

    def post_json(
        self,
        url: str,
        *,
        payload: dict[str, Any],
        cache_key: str | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """POST a STAC search body, honouring the on-disk response cache."""
        if use_cache and self.cache_dir is not None and cache_key:
            entry = self._cache_lookup(cache_key)
            if entry is not None and entry.fresh:
                LOGGER.debug("cache hit %s", cache_key)
                return json.loads(entry.path.read_text(encoding="utf-8"))

        response = self._request("POST", url, json_body=payload)
        try:
            data = response.json()
        except ValueError as exc:
            raise NetworkError(f"Response from {url} was not JSON: {exc}") from exc

        if self.cache_dir is not None and cache_key:
            self._cache_path(cache_key).write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        return data

    def probe(self, url: str) -> tuple[int, str]:
        """Cheap availability probe: ``(status, content_type)``."""
        try:
            response = self._request("HEAD", url)
            return response.status_code, response.headers.get("Content-Type", "")
        except NetworkError as exc:                          # pragma: no cover
            LOGGER.warning("probe failed for %s: %s", url, exc)
            return 0, ""

    # -- internals --------------------------------------------------------- #
    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle()
            self.request_count += 1
            try:
                response = self._session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                    timeout=(config.HTTP_CONNECT_TIMEOUT, self.timeout),
                )
            except requests.RequestException as exc:
                last_error = exc
                LOGGER.warning(
                    "%s %s failed (attempt %d/%d): %s",
                    method, url, attempt + 1, self.max_retries + 1, exc,
                )
            else:
                if response.status_code < 400:
                    if method != "HEAD":
                        self.bytes_downloaded += len(response.content)
                    return response
                if response.status_code not in RETRY_STATUS:
                    raise NetworkError(
                        f"{method} {url} returned HTTP {response.status_code}: "
                        f"{response.text[:300]}"
                    )
                last_error = NetworkError(f"HTTP {response.status_code} from {url}")
                LOGGER.warning(
                    "%s %s retryable HTTP %s (attempt %d/%d)",
                    method, url, response.status_code,
                    attempt + 1, self.max_retries + 1,
                )

            if attempt < self.max_retries:
                delay = min(
                    config.HTTP_BACKOFF_MAX, config.HTTP_BACKOFF_BASE ** attempt
                )
                time.sleep(delay + random.uniform(0, 0.35))

        raise NetworkError(
            f"{method} {url} failed after {self.max_retries + 1} attempts: {last_error}"
        )

    def _cache_path(self, cache_key: str) -> Path:
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:40]
        assert self.cache_dir is not None
        return self.cache_dir / f"{digest}.json"

    def _cache_lookup(self, cache_key: str) -> CacheEntry | None:
        path = self._cache_path(cache_key)
        if not path.exists():
            return None
        return CacheEntry(path=path, age_seconds=time.time() - path.stat().st_mtime)

    def read_range(self, url: str, start: int, end: int) -> bytes:
        """Read an inclusive byte range from a remote Cloud Optimized GeoTIFF."""
        response = self._request("GET", url, headers={"Range": f"bytes={start}-{end}"})
        return response.content
