"""The single analysis grid: derivation, equality checks and GeoTIFF writing.

Both periods are forced onto the *identical* grid produced here; a comparison is
refused when transforms, shapes or CRSs differ.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import Affine

from .. import config
from ..preprocess.aoi import AOI


class GridError(ValueError):
    """Raised when rasters cannot be treated as a common grid."""


@dataclass(frozen=True)
class AnalysisWindow:
    """A projected, snapped window that both observation dates share."""

    crs: str
    transform: Affine
    height: int
    width: int
    resolution: float
    utm_epsg: int

    @property
    def pixel_area_m2(self) -> float:
        return self.resolution * self.resolution

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        left, top = self.transform.c, self.transform.f
        return left, top - self.height * self.resolution, left + self.width * self.resolution, top

    def signature(self) -> str:
        payload = (
            f"{self.crs}|{tuple(self.transform)}|{self.height}|{self.width}|{self.resolution}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, object]:
        return {
            "crs": self.crs,
            "resolution_m": self.resolution,
            "width": self.width,
            "height": self.height,
            "transform": list(self.transform)[:6],
            "bounds": list(self.bounds),
            "signature": self.signature(),
            "utm_epsg": self.utm_epsg,
        }


def analysis_window(
    aoi: AOI, resolution: float = config.GRID_RESOLUTION
) -> AnalysisWindow:
    """Derive the common analysis window for an AOI."""
    width = aoi.grid_shape(resolution)[1]
    height = aoi.grid_shape(resolution)[0]
    return AnalysisWindow(
        crs=f"EPSG:{aoi.utm_epsg}",
        transform=aoi.grid_transform(resolution),
        height=height,
        width=width,
        resolution=resolution,
        utm_epsg=aoi.utm_epsg,
    )


def aoi_raster_mask(aoi: AOI, window: AnalysisWindow) -> np.ndarray:
    """Boolean raster that is True inside the AOI polygon."""
    geometry = {
        "type": "Polygon",
        "coordinates": [list(map(list, aoi.polygon.exterior.coords))],
    }
    from pyproj import CRS, Transformer
    from shapely.geometry import shape
    from shapely.ops import transform as shapely_transform

    transformer = Transformer.from_crs(
        CRS.from_epsg(4326), CRS.from_epsg(window.utm_epsg), always_xy=True
    )
    projected = shapely_transform(transformer.transform, shape(geometry))
    mask = geometry_mask(
        [projected],
        out_shape=(window.height, window.width),
        transform=window.transform,
        invert=True,
    )
    return mask


def assert_same_grid(
    reference: AnalysisWindow, other: AnalysisWindow, *, label: str = "period"
) -> None:
    if reference.shape != other.shape:
        raise GridError(
            f"{label} shape {other.shape} != reference {reference.shape}"
        )
    if reference.crs != other.crs:
        raise GridError(f"{label} CRS {other.crs} != reference {reference.crs}")
    if not np.allclose(
        np.array(reference.transform)[:6],
        np.array(other.transform)[:6],
        rtol=0.0,
        atol=1e-6,
    ):
        raise GridError(f"{label} transform differs from reference")


def write_geotiff(
    path: Path,
    array: np.ndarray,
    window: AnalysisWindow,
    *,
    dtype: str = "float32",
    nodata: float = float("nan"),
    descriptions: tuple[str, ...] = ("band1",),
) -> Path:
    """Write a single- or multi-band GeoTIFF on the analysis grid."""
    data = array if array.ndim == 3 else array[np.newaxis, ...]
    band_count, height, width = data.shape
    if (height, width) != window.shape:
        raise GridError(
            f"array shape {(height, width)} does not match window {window.shape}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": band_count,
        "dtype": dtype,
        "crs": window.crs,
        "transform": window.transform,
        "nodata": nodata,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "deflate",
        "predictor": 3 if dtype.startswith("float") else 2,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype(dtype))
        for index, description in enumerate(descriptions[:band_count], start=1):
            dst.set_band_description(index, description)
        dst.update_tags(
            analysis_crs=window.crs,
            resolution_m=str(window.resolution),
            grid_signature=window.signature(),
            producer="HabitatShift M0",
        )
    return path
