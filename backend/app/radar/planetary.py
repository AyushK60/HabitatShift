"""Microsoft Planetary Computer access: Sentinel-1 RTC scenes and the Copernicus 30 m DEM.

Search is anonymous. Reading pixels needs a short-lived, free read token that the Planetary Computer
issues without an account (``/api/sas/v1/token/<collection>``). Scenes are warped onto a caller-defined
UTM grid so scenes from different orbits and UTM zones stack pixel for pixel.
"""
from __future__ import annotations

import datetime as dt
import math
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.transform import Affine, from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"
S1_COLLECTION = "sentinel-1-rtc"
DEM_COLLECTION = "cop-dem-glo-30"
S1_NODATA = -32768.0


class PlanetaryError(RuntimeError):
    """Raised when the catalogue or a pixel read finally fails."""


def utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180.0) // 6.0) + 1
    return (32600 if lat >= 0 else 32700) + zone


@dataclass(frozen=True)
class Grid:
    """A fixed raster grid in a metric CRS."""

    crs: str
    transform: Affine
    width: int
    height: int
    res: float

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)


def make_grid(bbox: tuple[float, float, float, float], res: float = 10.0) -> Grid:
    """UTM grid covering a lon/lat bounding box, snapped to multiples of ``res``."""
    west, south, east, north = bbox
    crs = f"EPSG:{utm_epsg((west + east) / 2, (south + north) / 2)}"
    left, bottom, right, top = transform_bounds("EPSG:4326", crs, west, south, east, north)
    left, bottom = math.floor(left / res) * res, math.floor(bottom / res) * res
    right, top = math.ceil(right / res) * res, math.ceil(top / res) * res
    width, height = int(round((right - left) / res)), int(round((top - bottom) / res))
    return Grid(crs=crs, transform=from_origin(left, top, res, res), width=width, height=height, res=res)


class PlanetaryClient:
    def __init__(self, *, timeout: float = 60.0, attempts: int = 4) -> None:
        self._http = requests.Session()
        self._timeout = timeout
        self._attempts = attempts
        self._tokens: dict[str, tuple[str, float]] = {}
        self._token_lock = threading.Lock()

    # ------------------------------------------------------------------ http
    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        last: Exception | None = None
        for attempt in range(self._attempts):
            try:
                response = self._http.request(method, url, timeout=self._timeout, **kwargs)
                if response.status_code in (429, 500, 502, 503, 504):
                    raise PlanetaryError(f"HTTP {response.status_code} from {url}")
                response.raise_for_status()
                return response
            except (requests.RequestException, PlanetaryError) as exc:
                last = exc
                time.sleep(1.5 * (2**attempt))
        raise PlanetaryError(f"request failed after {self._attempts} attempts: {last}")

    # ---------------------------------------------------------------- search
    def search(
        self,
        collection: str,
        bbox: tuple[float, float, float, float],
        start: dt.date | None = None,
        end: dt.date | None = None,
        *,
        max_items: int = 2000,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"collections": [collection], "bbox": list(bbox), "limit": 100}
        if start and end:
            body["datetime"] = f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z"
        items: list[dict[str, Any]] = []
        url, payload = f"{STAC_URL}/search", body
        while url and len(items) < max_items:
            page = self._request("POST", url, json=payload).json()
            items.extend(page.get("features", []))
            nxt = next((link for link in page.get("links", []) if link.get("rel") == "next"), None)
            url, payload = (nxt["href"], nxt.get("body")) if nxt else (None, None)
        items.sort(key=lambda feature: feature["properties"]["datetime"])
        return items

    # ----------------------------------------------------------------- token
    def _token(self, collection: str) -> str:
        with self._token_lock:  # one thread refreshes, the rest reuse it (avoids HTTP 429)
            cached = self._tokens.get(collection)
            if cached and cached[1] - time.time() > 300:
                return cached[0]
            data = self._request("GET", TOKEN_URL.format(collection=collection)).json()
            expiry = dt.datetime.fromisoformat(data["msft:expiry"].replace("Z", "+00:00")).timestamp()
            self._tokens[collection] = (data["token"], expiry)
            return data["token"]

    def signed_href(self, item: dict[str, Any], asset: str, collection: str) -> str:
        return f"{item['assets'][asset]['href']}?{self._token(collection)}"

    # ------------------------------------------------------------------ read
    def read_to_grid(
        self,
        item: dict[str, Any],
        asset: str,
        collection: str,
        grid: Grid,
        *,
        resampling: Resampling = Resampling.bilinear,
    ) -> np.ndarray:
        """Read one asset warped onto ``grid`` as float32 with NaN where there is no data."""
        last: Exception | None = None
        for attempt in range(self._attempts):
            try:
                href = self.signed_href(item, asset, collection)
                with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_TIMEOUT="60", GDAL_HTTP_CONNECTTIMEOUT="20"):
                    with rasterio.open(href) as src:
                        nodata = src.nodata if src.nodata is not None else S1_NODATA
                        with WarpedVRT(
                            src,
                            crs=grid.crs,
                            transform=grid.transform,
                            width=grid.width,
                            height=grid.height,
                            resampling=resampling,
                            src_nodata=nodata,
                            nodata=nodata,
                        ) as vrt:
                            band = vrt.read(1).astype("float32")
                band[band == nodata] = np.nan
                return band
            except rasterio.errors.RasterioError as exc:
                last = exc
                time.sleep(1.5 * (2**attempt))
        raise PlanetaryError(f"pixel read failed for {item['id']}: {last}")

    def read_dem(self, bbox: tuple[float, float, float, float], grid: Grid) -> np.ndarray:
        """Copernicus GLO-30 elevation (m) on ``grid``; tiles are mosaicked, gaps stay NaN."""
        out = np.full(grid.shape, np.nan, dtype="float32")
        for item in self.search(DEM_COLLECTION, bbox):
            tile = self.read_to_grid(item, "data", DEM_COLLECTION, grid)
            fill = np.isnan(out) & ~np.isnan(tile)
            out[fill] = tile[fill]
        return out
