"""Radiometric metadata validation and DN -> surface-reflectance conversion.

Sentinel-2 L2A stores 15-bit DNs that are meaningless as spectral values until
``reflectance = DN * scale + offset`` is applied.  Both constants are read from
the item's own ``raster:bands`` metadata and compared with the collection
definition; a mismatch is a hard error, never a silent guess.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import config
from ..catalog.models import SceneCandidate


class RadiometryError(ValueError):
    """Raised when an asset's radiometric metadata is missing or unexpected."""


@dataclass(frozen=True)
class Radiometry:
    """Verified scaling triple for one asset."""

    asset_key: str
    scale: float
    offset: float
    nodata: int | None
    gsd: float | None
    source: str

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_key": self.asset_key,
            "scale": self.scale,
            "offset": self.offset,
            "nodata": self.nodata,
            "gsd_metres": self.gsd,
            "source": self.source,
            "transform": "reflectance = DN * scale + offset",
        }


def verify_radiometry(candidate: SceneCandidate) -> dict[str, Radiometry]:
    """Validate every required asset and return its scaling record.

    Raises :class:`RadiometryError` when the catalog declares something other
    than the expected Sentinel-2 L2A scaling or a differing native GSD, which
    would mean the pipeline's assumptions no longer hold for this item.
    """
    verified: dict[str, Radiometry] = {}
    for key in config.REQUIRED_ASSETS:
        try:
            asset = candidate.asset(key)
        except Exception as exc:
            raise RadiometryError(f"item {candidate.item_id}: {exc}") from exc

        if abs(asset.scale - config.EXPECTED_SCALE) > 1e-9:
            raise RadiometryError(
                f"item {candidate.item_id} asset {key}: unexpected scale "
                f"{asset.scale} (expected {config.EXPECTED_SCALE})"
            )
        if abs(asset.offset - config.EXPECTED_OFFSET) > 1e-9:
            raise RadiometryError(
                f"item {candidate.item_id} asset {key}: unexpected offset "
                f"{asset.offset} (expected {config.EXPECTED_OFFSET})"
            )
        if asset.nodata is not None and asset.nodata != config.EXPECTED_NODATA:
            raise RadiometryError(
                f"item {candidate.item_id} asset {key}: unexpected nodata "
                f"{asset.nodata} (expected {config.EXPECTED_NODATA})"
            )
        expected_gsd = config.EXPECTED_GSD[key]
        if asset.gsd is not None and abs(asset.gsd - expected_gsd) > 1e-6:
            raise RadiometryError(
                f"item {candidate.item_id} asset {key}: native GSD {asset.gsd} m "
                f"does not match the analysis grid expectation {expected_gsd} m"
            )

        verified[key] = Radiometry(
            asset_key=key,
            scale=asset.scale,
            offset=asset.offset,
            nodata=asset.nodata,
            gsd=asset.gsd,
            source=f"stac:item.{candidate.item_id}.assets.{key}.raster:bands",
        )
    return verified


def to_reflectance(dn: np.ndarray, radiometry: Radiometry) -> np.ndarray:
    """Convert integer DNs to float32 reflectance with nodata handled first."""
    work = dn.astype(np.float32, copy=True)
    if radiometry.nodata is not None:
        work[dn == radiometry.nodata] = np.nan
    work *= np.float32(radiometry.scale)
    if radiometry.offset:
        work += np.float32(radiometry.offset)
    # L2A offset is 0 today, but a negative offset applied to a 0 DN would
    # otherwise leave a plausible-looking -0.1; keep nodata masked regardless.
    work[~np.isfinite(work)] = np.nan
    return work
