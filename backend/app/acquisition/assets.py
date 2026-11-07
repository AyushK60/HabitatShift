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


def _baseline_number(candidate: SceneCandidate) -> tuple[float, str]:
    """Parse the item's processing baseline, or fail loudly."""
    baseline = candidate.processing_baseline
    if baseline is None:
        raise RadiometryError(
            f"item {candidate.item_id} declares no processing baseline, so the "
            f"reflectance offset convention is indeterminate"
        )
    try:
        major, _, minor = str(baseline).partition(".")
        return float(f"{major}.{minor or '0'}"), str(baseline)
    except ValueError as exc:
        raise RadiometryError(
            f"item {candidate.item_id} has unparseable baseline {baseline!r}"
        ) from exc


def resolve_offset(
    candidate: SceneCandidate, declared: float, *, asset_key: str
) -> tuple[float, str]:
    """Return the offset that must actually be applied, plus its provenance.

    Sentinel-2 L2A baseline 04.00 (25 Jan 2022) introduced
    ``BOA_ADD_OFFSET = -1000``, i.e. ``reflectance = DN * 0.0001 - 0.1``;
    older products carry no offset.  During COG conversion Earth Search baked
    that offset into some items and flagged this with
    ``earthsearch:boa_offset_applied = true``, while leaving the generic
    ``raster:bands`` offset at -0.1.  Applying -0.1 again to those items would
    double-correct every pixel, so the flag takes precedence there and the
    effective offset becomes 0.0.  When the flag is absent or false, the
    asset's declared offset is applied.  Values outside the two valid
    Sentinel-2 conventions, or a BOA offset on a pre-04.00 product, are hard
    errors rather than silent guesses.

    See https://github.com/Element84/earth-search/blob/main/docs/collections/sentinel-2-l2a.md
    ("Gain/Offset in Items after Jan 25, 2022").
    """
    numeric, raw = _baseline_number(candidate)
    if not any(
        abs(declared - valid) <= 1e-9
        for valid in (config.NO_OFFSET, config.BOA_ADD_OFFSET)
    ):
        raise RadiometryError(
            f"item {candidate.item_id} asset {asset_key}: declared offset "
            f"{declared} is not a Sentinel-2 L2A convention "
            f"(0.0 or {config.BOA_ADD_OFFSET})"
        )
    if numeric < config.BASELINE_OFFSET_THRESHOLD and abs(declared) > 1e-9:
        raise RadiometryError(
            f"item {candidate.item_id} asset {asset_key}: baseline {raw} "
            f"predates 04.00 but declares offset {declared}"
        )

    applied = candidate.extra.get("boa_offset_applied")
    if applied is True and abs(declared) > 1e-9:
        return config.NO_OFFSET, (
            f"baseline {raw}; earthsearch:boa_offset_applied=true so the "
            f"declared {declared:+.1f} is already baked into the DNs and is "
            f"not applied again"
        )
    return declared, (
        f"baseline {raw}; declared offset {declared:+.1f} "
        f"(boa_offset_applied={applied!r})"
    )


def verify_asset(candidate: SceneCandidate, key: str) -> Radiometry:
    """Validate one asset's radiometry and return its scaling record.

    Raises :class:`RadiometryError` when the catalog declares something other
    than the Sentinel-2 L2A scaling required by this item's baseline, or a
    differing native GSD, which would mean the pipeline's assumptions no longer
    hold.
    """
    try:
        asset = candidate.asset(key)
    except Exception as exc:
        raise RadiometryError(f"item {candidate.item_id}: {exc}") from exc

    if abs(asset.scale - config.EXPECTED_SCALE) > 1e-9:
        raise RadiometryError(
            f"item {candidate.item_id} asset {key}: unexpected scale "
            f"{asset.scale} (expected {config.EXPECTED_SCALE})"
        )
    offset, offset_reason = resolve_offset(candidate, asset.offset, asset_key=key)
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

    return Radiometry(
        asset_key=key,
        scale=asset.scale,
        offset=offset,
        nodata=asset.nodata,
        gsd=asset.gsd,
        source=(
            f"stac:item.{candidate.item_id}.assets.{key}.raster:bands "
            f"({offset_reason})"
        ),
    )


def verify_radiometry(
    candidate: SceneCandidate, keys: tuple[str, ...] = config.REQUIRED_ASSETS
) -> dict[str, Radiometry]:
    """Validate a set of assets and return their scaling records."""
    return {key: verify_asset(candidate, key) for key in keys}


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


#: Smallest window-mean reflectance any natural surface produces.  Individual
#: dark pixels can be slightly negative from sensor noise, but a window *mean*
#: below this can only come from a wrongly applied offset convention, so it is
#: used as an empirical acceptance test on the transform that was applied.
PHYSICAL_MIN_MEAN = -0.005

#: Provenance marker embedded in the source string of empirically corrected
#: records.  Kept free of pixel statistics so a cached record can be
#: re-validated deterministically from metadata alone.
EMPIRICAL_CORRECTION_MARKER = (
    "empirical correction: declared transform rejected as non-physical "
    "(see radiometry_evidence), applied scale-only"
)


def empirical_offset_rejection(
    reflectance: dict[str, np.ndarray]
) -> dict[str, object] | None:
    """Return rejection evidence when the applied transform is non-physical.

    BOA reflectance of any daytime natural surface is essentially
    non-negative; deep water, shadowed terrain and sensor noise keep the
    window *mean* of every band at or above :data:`PHYSICAL_MIN_MEAN`.  A mean
    below that is only reachable when the declared DN convention does not
    match the stored DNs — observed on the 2025 Earth Search reprocessing,
    where baseline-05.11 items store ``reflectance * 10000`` without the
    baked ``+1000`` offset while ``earthsearch:boa_offset_applied`` is false
    and ``raster:bands`` still declares ``-0.1``.

    Returns ``None`` while the applied transform is physically plausible,
    otherwise a dict recording which bands failed and their means (over
    finite pixels only), for the run's provenance.
    """
    evidence: dict[str, object] = {}
    for key in sorted(reflectance):
        values = reflectance[key]
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            continue
        mean = float(finite.mean())
        if mean < PHYSICAL_MIN_MEAN:
            evidence[key] = {
                "mean_reflectance": round(mean, 6),
                "threshold": PHYSICAL_MIN_MEAN,
                "finite_pixels": int(finite.size),
            }
    if not evidence:
        return None
    return {
        "verdict": "declared_transform_non_physical",
        "bands": evidence,
        "reason": (
            "window-mean reflectance below "
            f"{PHYSICAL_MIN_MEAN} after the declared transform; BOA "
            "reflectance of natural surfaces is non-negative in the mean, so "
            "the declared DN convention does not match the stored DNs"
        ),
    }


def with_scale_only_offset(record: Radiometry) -> Radiometry:
    """Return a scale-only copy of one radiometry record.

    The corrected source string appends a deterministic marker (no pixel
    statistics) so a cached record can be re-validated from metadata alone;
    the measured evidence is stored separately per observation.
    """
    if record.offset == 0.0:
        return record
    return Radiometry(
        asset_key=record.asset_key,
        scale=record.scale,
        offset=0.0,
        nodata=record.nodata,
        gsd=record.gsd,
        source=f"{record.source} ; {EMPIRICAL_CORRECTION_MARKER}",
    )
