"""Spectral index registry: formulas, bands, native resolution and legends.

Every index is a normalised difference ``(a - b) / (a + b)`` on surface
reflectance.  The registry is the single source of truth for which assets an
index needs, what its native resolution is, and which fixed colour ramp and
legend breaks belong to it, so previews, manifests and tests cannot drift.

Native-resolution note: SWIR bands (B11/B12) are delivered at 20 m.  When an
index uses them it is computed on the 10 m analysis grid by bilinear resampling
of the reflectance band.  That does **not** create genuine 10 m information;
:attr:`IndexSpec.native_resolution_m` and
:attr:`IndexSpec.upsampled_to_analysis_grid` record the difference.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import config
from .ndvi import normalised_difference


class IndexSpecError(ValueError):
    """Raised when an index is unknown or its bands are missing."""


Colour = tuple[int, int, int]


@dataclass(frozen=True)
class IndexSpec:
    """Immutable description of one spectral index."""

    key: str
    label: str
    formula: str
    bands: tuple[str, str]          # (positive numerator, negative numerator)
    native_resolution_m: float
    value_range: tuple[float, float]
    description: str
    breaks: tuple[float, ...]
    ramp: tuple[tuple[float, Colour], ...]

    def compute(self, bands: dict[str, np.ndarray]) -> np.ndarray:
        """Compute the index from a band dictionary keyed by asset name."""
        missing = [key for key in self.bands if key not in bands]
        if missing:
            raise IndexSpecError(
                f"index {self.key!r} needs bands {missing}; got {sorted(bands)}"
            )
        return normalised_difference(bands[self.bands[0]], bands[self.bands[1]])

    def upsampled_to(self, analysis_resolution_m: float) -> bool:
        return analysis_resolution_m < self.native_resolution_m

    def to_dict(self, analysis_resolution_m: float | None = None) -> dict[str, object]:
        payload: dict[str, object] = {
            "key": self.key,
            "label": self.label,
            "formula": self.formula,
            "bands": list(self.bands),
            "native_resolution_m": self.native_resolution_m,
            "value_range": list(self.value_range),
            "description": self.description,
            "legend_breaks": list(self.breaks),
        }
        if analysis_resolution_m is not None:
            payload["analysis_resolution_m"] = analysis_resolution_m
            payload["upsampled"] = self.upsampled_to(analysis_resolution_m)
            payload["resolution_note"] = (
                f"computed on a {analysis_resolution_m:g} m grid from "
                f"{self.native_resolution_m:g} m native bands; upsampled data "
                f"contain no genuine {analysis_resolution_m:g} m detail"
                if self.upsampled_to(analysis_resolution_m)
                else f"native {self.native_resolution_m:g} m band resolution"
            )
        return payload


#: Fixed ramps.  Each is semantically ordered for its index (water, snow,
#: built-up); none is a brand palette, and masked pixels never take a ramp
#: colour (see :mod:`backend.app.preprocess.preview`).
NDVI_RAMP: tuple[tuple[float, Colour], ...] = (
    (-1.00, (36, 66, 82)),
    (-0.40, (86, 112, 106)),
    (-0.15, (168, 158, 124)),
    (-0.02, (196, 178, 132)),
    (0.10, (176, 186, 138)),
    (0.25, (140, 168, 122)),
    (0.45, (86, 138, 96)),
    (0.65, (44, 108, 78)),
    (1.00, (18, 74, 56)),
)

NDWI_RAMP: tuple[tuple[float, Colour], ...] = (
    (-1.00, (122, 96, 72)),
    (-0.30, (176, 152, 116)),
    (-0.10, (208, 198, 176)),
    (0.00, (232, 229, 216)),
    (0.10, (176, 205, 219)),
    (0.30, (102, 163, 204)),
    (0.60, (48, 110, 178)),
    (1.00, (22, 62, 128)),
)

MNDWI_RAMP: tuple[tuple[float, Colour], ...] = (
    (-1.00, (116, 104, 80)),
    (-0.30, (170, 160, 120)),
    (-0.10, (204, 202, 184)),
    (0.00, (228, 230, 223)),
    (0.10, (158, 206, 208)),
    (0.30, (74, 166, 177)),
    (0.60, (32, 116, 142)),
    (1.00, (12, 66, 92)),
)

NDSI_RAMP: tuple[tuple[float, Colour], ...] = (
    (-1.00, (58, 74, 58)),
    (-0.30, (120, 132, 104)),
    (-0.10, (176, 178, 158)),
    (0.00, (214, 214, 200)),
    (0.20, (206, 222, 235)),
    (0.40, (170, 206, 232)),
    (0.60, (120, 178, 220)),
    (1.00, (60, 120, 190)),
)

NDBI_RAMP: tuple[tuple[float, Colour], ...] = (
    (-1.00, (40, 96, 72)),
    (-0.30, (120, 158, 110)),
    (-0.10, (182, 190, 160)),
    (0.00, (216, 208, 190)),
    (0.10, (218, 188, 158)),
    (0.30, (206, 150, 112)),
    (0.60, (178, 104, 76)),
    (1.00, (132, 62, 52)),
)


INDEX_SPECS: dict[str, IndexSpec] = {
    "ndvi": IndexSpec(
        key="ndvi",
        label="NDVI",
        formula="(NIR - Red) / (NIR + Red)",
        bands=(config.ASSET_NIR, config.ASSET_RED),
        native_resolution_m=10.0,
        value_range=(-1.0, 1.0),
        description="Normalised Difference Vegetation Index (Rouse et al. 1974)",
        breaks=(-0.6, -0.35, -0.12, 0.02, 0.16, 0.30, 0.50),
        ramp=NDVI_RAMP,
    ),
    "ndwi": IndexSpec(
        key="ndwi",
        label="NDWI",
        formula="(Green - NIR) / (Green + NIR)",
        bands=(config.ASSET_GREEN, config.ASSET_NIR),
        native_resolution_m=10.0,
        value_range=(-1.0, 1.0),
        description="McFeeters Normalised Difference Water Index (1996)",
        breaks=(-0.3, -0.1, 0.0, 0.1, 0.3),
        ramp=NDWI_RAMP,
    ),
    "mndwi": IndexSpec(
        key="mndwi",
        label="MNDWI",
        formula="(Green - SWIR1) / (Green + SWIR1)",
        bands=(config.ASSET_GREEN, config.ASSET_SWIR1),
        native_resolution_m=20.0,
        value_range=(-1.0, 1.0),
        description="Xu Modified Normalised Difference Water Index (2006)",
        breaks=(-0.3, -0.1, 0.0, 0.1, 0.3),
        ramp=MNDWI_RAMP,
    ),
    "ndsi": IndexSpec(
        key="ndsi",
        label="NDSI",
        formula="(Green - SWIR1) / (Green + SWIR1)",
        bands=(config.ASSET_GREEN, config.ASSET_SWIR1),
        native_resolution_m=20.0,
        value_range=(-1.0, 1.0),
        description=(
            "Normalised Difference Snow Index, identical band algebra to MNDWI "
            "but a different physical interpretation; gated for cryosphere "
            "profiles only"
        ),
        breaks=(-0.1, 0.0, 0.2, 0.4),
        ramp=NDSI_RAMP,
    ),
    "ndbi": IndexSpec(
        key="ndbi",
        label="NDBI",
        formula="(SWIR1 - NIR) / (SWIR1 + NIR)",
        bands=(config.ASSET_SWIR1, config.ASSET_NIR),
        native_resolution_m=20.0,
        value_range=(-1.0, 1.0),
        description=(
            "Normalised Difference Built-up Index feature (Zha et al. 2003); "
            "a candidate signal, never a building label"
        ),
        breaks=(-0.1, 0.0, 0.1, 0.3),
        ramp=NDBI_RAMP,
    ),
}


def get_index(key: str) -> IndexSpec:
    try:
        return INDEX_SPECS[key]
    except KeyError as exc:
        raise IndexSpecError(
            f"unknown index {key!r}; known: {sorted(INDEX_SPECS)}"
        ) from exc


def compute_index(key: str, bands: dict[str, np.ndarray]) -> np.ndarray:
    """Compute one registered index from already-resampled reflectance bands."""
    return get_index(key).compute(bands)


def required_bands(keys) -> tuple[str, ...]:
    """Sorted union of assets needed to compute the given indices."""
    needed: set[str] = set()
    for key in keys:
        needed.update(get_index(key).bands)
    return tuple(sorted(needed))
