"""Bounded Cloud Optimized GeoTIFF reads.

Remote assets are opened as a :class:`rasterio.vrt.WarpedVRT` pinned to the
analysis grid, so GDAL fetches only the byte ranges and overview levels needed
for the requested window instead of the whole 10980x10980 scene.

Resampling policy is explicit per asset class: bilinear for continuous
reflectance, nearest neighbour for the categorical SCL mask.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Iterator

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT

LOGGER = logging.getLogger(__name__)

#: Bytes-per-pixel ceilings used to budget download volume before reading.
BYTES_PER_PIXEL = {
    "uint8": 1,
    "int8": 1,
    "uint16": 2,
    "int16": 2,
    "float32": 4,
}

GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MULTIPLEXING": "YES",
    "GDAL_HTTP_VERSION": "2",
    "AWS_NO_SIGN_REQUEST": "YES",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "67108864",
    "GDAL_NUM_THREADS": "ALL_CPUS",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff,.TIF,.TIFF",
}


class RasterReadError(RuntimeError):
    """Raised when a remote raster cannot be opened or read."""


@dataclass
class WindowRequest:
    """Explicit description of the window to extract."""

    dst_crs: str
    dst_transform: Affine
    height: int
    width: int
    resampling: Resampling
    dtype: str = "float32"

    @property
    def pixel_count(self) -> int:
        return self.height * self.width

    def estimated_bytes(self) -> int:
        return self.pixel_count * BYTES_PER_PIXEL.get(self.dtype, 4)


@contextlib.contextmanager
def open_vrt(href: str, request: WindowRequest) -> Iterator[rasterio.io.DatasetReader]:
    """Open ``href`` warped onto the requested analysis grid."""
    with rasterio.Env(**GDAL_ENV):
        try:
            with rasterio.open(href) as src:
                if src.count < 1:
                    raise RasterReadError(f"{href} has no raster bands")
                with WarpedVRT(
                    src,
                    crs=request.dst_crs,
                    transform=request.dst_transform,
                    width=request.width,
                    height=request.height,
                    resampling=request.resampling,
                    dtype=request.dtype,
                    nodata=src.nodata,
                ) as vrt:
                    yield vrt
        except RasterReadError:
            raise
        except Exception as exc:                              # pragma: no cover - net
            raise RasterReadError(f"cannot open {href}: {exc}") from exc


def read_window(href: str, request: WindowRequest) -> np.ndarray:
    """Read one band of ``href`` resampled onto the analysis grid."""
    with open_vrt(href, request) as vrt:
        try:
            band = vrt.read(1, out_dtype=request.dtype)
        except Exception as exc:                              # pragma: no cover - net
            raise RasterReadError(f"cannot read window from {href}: {exc}") from exc
    if band.shape != (request.height, request.width):
        raise RasterReadError(
            f"{href} produced shape {band.shape}, expected "
            f"{(request.height, request.width)}"
        )
    LOGGER.debug("read %s %s px from %s", request.height, request.width, href)
    return band


def source_grid(href: str) -> dict[str, object]:
    """Inspect an asset's native transform/CRS/size without reading pixels."""
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(href) as src:
            return {
                "crs": src.crs.to_string() if src.crs else None,
                "transform": tuple(src.transform),
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "dtype": src.dtypes[0],
                "nodata": src.nodata,
                "res": tuple(src.res),
                "overviews": src.overviews(1),
                "driver": src.driver,
                "is_tiled": src.profile.get("tiled"),
            }
