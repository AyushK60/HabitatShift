"""Scene Classification Layer (SCL) masking.

The mask is derived from the real SCL raster, class by class, and the accepted
and rejected class inventory is returned alongside the boolean mask so the
policy in force can be written into the provenance manifest and audited later.
Cloudy pixels are masked, never interpolated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import config


@dataclass
class MaskReport:
    """Counts and percentages backing one mask decision."""

    total_pixels: int
    valid_pixels: int
    class_counts: dict[int, int] = field(default_factory=dict)

    @property
    def valid_fraction(self) -> float:
        if self.total_pixels == 0:
            return 0.0
        return self.valid_pixels / self.total_pixels

    @property
    def valid_percent(self) -> float:
        return self.valid_fraction * 100.0

    def to_dict(self) -> dict[str, object]:
        return {
            "total_pixels": self.total_pixels,
            "valid_pixels": self.valid_pixels,
            "valid_fraction": round(self.valid_fraction, 6),
            "valid_percent": round(self.valid_percent, 3),
            "accepted_scl_classes": {
                str(c): config.SCL_SEMANTICS.get(c, "unknown")
                for c in config.SCL_VALID_CLASSES
            },
            "rejected_scl_classes": {
                str(c): config.SCL_SEMANTICS.get(c, "unknown")
                for c in config.SCL_ALWAYS_INVALID
            },
            "class_histogram": {str(k): v for k, v in sorted(self.class_counts.items())},
        }


class MaskError(ValueError):
    """Raised when the SCL raster cannot support a decision."""


def build_valid_mask(
    scl: np.ndarray,
    *,
    valid_classes=config.SCL_VALID_CLASSES,
    always_invalid=config.SCL_ALWAYS_INVALID,
) -> tuple[np.ndarray, MaskReport]:
    """Return ``(valid_mask, report)`` from an SCL array.

    Any class label present in the raster but absent from both policy lists is
    treated as invalid and reported, so an unseen label never silently passes.
    """
    if scl.ndim != 2:
        raise MaskError(f"SCL array must be 2-D, got shape {scl.shape}")
    integer = scl.astype(np.int32, copy=False)

    valid_mask = np.isin(integer, np.asarray(valid_classes, dtype=np.int32))
    for reject in always_invalid:
        valid_mask &= integer != reject

    classes, counts = np.unique(integer, return_counts=True)
    histogram = {int(c): int(n) for c, n in zip(classes, counts)}
    known = set(valid_classes) | set(always_invalid)
    for label in histogram:
        if label not in known:
            valid_mask &= integer != label

    report = MaskReport(
        total_pixels=int(integer.size),
        valid_pixels=int(valid_mask.sum()),
        class_counts=histogram,
    )
    return valid_mask, report


def combine_masks(*masks: np.ndarray) -> np.ndarray:
    """AND several boolean masks (validity intersection)."""
    if not masks:
        raise MaskError("combine_masks needs at least one mask")
    result = np.ones_like(masks[0], dtype=bool)
    for mask in masks:
        if mask.shape != result.shape:
            raise MaskError(f"mask shapes differ: {mask.shape} vs {result.shape}")
        result &= mask.astype(bool)
    return result


def reflectance_valid_mask(*reflectance_bands: np.ndarray) -> np.ndarray:
    """Pixels where every supplied reflectance band is finite."""
    if not reflectance_bands:
        raise MaskError("reflectance_valid_mask needs at least one band")
    result = np.ones(reflectance_bands[0].shape, dtype=bool)
    for band in reflectance_bands:
        result &= np.isfinite(band)
    return result


def apply_mask(array: np.ndarray, mask: np.ndarray, fill=np.nan) -> np.ndarray:
    """Return a float copy of ``array`` with masked pixels set to ``fill``."""
    if array.shape != mask.shape:
        raise MaskError(f"array shape {array.shape} != mask shape {mask.shape}")
    out = array.astype(np.float32, copy=True)
    out[~mask] = fill
    return out
