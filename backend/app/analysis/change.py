"""Matched-valid-area change analysis for normalised-difference indices.

The analysis answers one bounded question: where the later-period index exceeds
the earlier-period index by at least a candidate threshold (or falls below the
negative threshold), and how much projected area that corresponds to.  It does
not attach a land-cover or causal label to those pixels.

Area conventions:

* pixel area is the projected pixel area of the analysis grid (10 m -> 100 m²);
* hectares = m² / 10 000, square kilometres = m² / 1 000 000;
* percentages of directional change are relative to the **common-valid
  footprint**, not the full AOI, so masked pixels never inflate the result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import config
from ..indices.ndvi import IndexStats, summarise

M2_PER_HA = 10_000.0
M2_PER_KM2 = 1_000_000.0

#: Candidate thresholds used for the sensitivity table (index units).
DEFAULT_THRESHOLDS = (0.10, 0.15, 0.20)

#: Class codes for the exported categorical raster.
CLASS_DECREASE = -1
CLASS_STABLE = 0
CLASS_INCREASE = 1
#: Nodata for the int8 categorical raster (255 does not fit in int8).
CLASS_INVALID = -128


class ChangeError(ValueError):
    """Raised when change inputs are inconsistent."""


def _validate(delta: np.ndarray, common: np.ndarray, pixel_area_m2: float) -> None:
    if delta.shape != common.shape:
        raise ChangeError(f"delta shape {delta.shape} != mask shape {common.shape}")
    if pixel_area_m2 <= 0:
        raise ChangeError("pixel_area_m2 must be positive")


def normalise_thresholds(
    thresholds, primary: float | None = None
) -> tuple[tuple[float, ...], float]:
    values = sorted({abs(float(t)) for t in thresholds if float(t) > 0})
    if not values:
        raise ChangeError("at least one positive threshold is required")
    chosen = abs(float(primary)) if primary is not None else values[len(values) // 2]
    if chosen <= 0:
        raise ChangeError("primary threshold must be positive")
    if not any(abs(chosen - value) <= 1e-12 for value in values):
        values = sorted(set(values) | {chosen})
    return tuple(values), chosen


def classify_delta(
    delta: np.ndarray,
    common: np.ndarray,
    *,
    threshold: float,
) -> np.ndarray:
    """Return int8 classes: -1 decrease, 0 stable, 1 increase, -128 invalid."""
    _validate(delta, common, 1.0)
    classes = np.full(delta.shape, CLASS_INVALID, dtype=np.int8)
    usable = common & np.isfinite(delta)
    values = delta[usable]
    result = np.zeros(values.shape, dtype=np.int8)
    result[values <= -abs(threshold)] = CLASS_DECREASE
    result[values >= abs(threshold)] = CLASS_INCREASE
    classes[usable] = result
    return classes


@dataclass
class ThresholdResult:
    """Directional counts and areas at one candidate threshold."""

    threshold: float
    decrease_pixels: int
    increase_pixels: int
    stable_pixels: int
    valid_pixels: int

    def to_dict(self, pixel_area_m2: float) -> dict[str, object]:
        valid_area = self.valid_pixels * pixel_area_m2
        return {
            "threshold": self.threshold,
            "valid_pixels": self.valid_pixels,
            "decrease_pixels": self.decrease_pixels,
            "increase_pixels": self.increase_pixels,
            "stable_pixels": self.stable_pixels,
            "valid_area_m2": round(valid_area, 3),
            "valid_area_ha": round(valid_area / M2_PER_HA, 4),
            "valid_area_km2": round(valid_area / M2_PER_KM2, 6),
            "decrease_area_ha": round(
                self.decrease_pixels * pixel_area_m2 / M2_PER_HA, 4
            ),
            "increase_area_ha": round(
                self.increase_pixels * pixel_area_m2 / M2_PER_HA, 4
            ),
            "decrease_percent_of_common": round(
                100.0 * self.decrease_pixels / self.valid_pixels, 6
            )
            if self.valid_pixels
            else 0.0,
            "increase_percent_of_common": round(
                100.0 * self.increase_pixels / self.valid_pixels, 6
            )
            if self.valid_pixels
            else 0.0,
        }


def threshold_result(
    delta: np.ndarray,
    common: np.ndarray,
    *,
    threshold: float,
) -> ThresholdResult:
    _validate(delta, common, 1.0)
    usable = common & np.isfinite(delta)
    values = delta[usable]
    decrease = int(np.count_nonzero(values <= -abs(threshold)))
    increase = int(np.count_nonzero(values >= abs(threshold)))
    stable = int(values.size - decrease - increase)
    return ThresholdResult(
        threshold=float(abs(threshold)),
        decrease_pixels=decrease,
        increase_pixels=increase,
        stable_pixels=stable,
        valid_pixels=int(values.size),
    )


def change_summary(
    delta: np.ndarray,
    common: np.ndarray,
    *,
    aoi_pixels: int,
    pixel_area_m2: float,
    thresholds=DEFAULT_THRESHOLDS,
    primary_threshold: float | None = None,
    index_key: str,
    min_comparable_fraction: float | None = None,
) -> dict[str, object]:
    """Compact, auditable change record for one index."""
    _validate(delta, common, pixel_area_m2)
    if aoi_pixels < int(common.sum()):
        raise ChangeError("common mask contains more pixels than the AOI")

    threshold_floor = (
        config.MIN_COMPARABLE_VALID_FRACTION
        if min_comparable_fraction is None
        else float(min_comparable_fraction)
    )
    normalised, primary = normalise_thresholds(thresholds, primary_threshold)
    usable = common & np.isfinite(delta)
    common_pixels = int(usable.sum())
    comparable_fraction = common_pixels / aoi_pixels if aoi_pixels else 0.0

    per_threshold = [
        threshold_result(delta, common, threshold=value).to_dict(pixel_area_m2)
        for value in normalised
    ]
    primary_block = next(
        block
        for block in per_threshold
        if abs(float(block["threshold"]) - primary) <= 1e-12
    )

    stats: IndexStats = summarise(delta, common)
    return {
        "index": index_key,
        "label": "observed index difference (later - earlier); not a land-cover verdict",
        "common_valid_pixels": common_pixels,
        "aoi_pixels": int(aoi_pixels),
        "common_valid_fraction_of_aoi": round(comparable_fraction, 6),
        "common_valid_area_ha": round(common_pixels * pixel_area_m2 / M2_PER_HA, 4),
        "common_valid_area_km2": round(
            common_pixels * pixel_area_m2 / M2_PER_KM2, 6
        ),
        "suitable_for_comparison": (
            comparable_fraction >= threshold_floor
        ),
        "primary_threshold": primary,
        "primary": primary_block,
        "thresholds": per_threshold,
        "delta_stats": stats.to_dict(),
        "pixel_area_m2": round(pixel_area_m2, 6),
        "area_convention": (
            "planimetric pixel area on the projected analysis grid; hectares and "
            "square kilometres converted from square metres"
        ),
    }


def area_conservation(
    threshold: ThresholdResult, pixel_area_m2: float
) -> dict[str, object]:
    """Verify pixel/area arithmetic for one threshold (used in tests/audit)."""
    total_pixels = (
        threshold.decrease_pixels + threshold.increase_pixels + threshold.stable_pixels
    )
    total_area_m2 = total_pixels * pixel_area_m2
    parts_area_m2 = (
        threshold.decrease_pixels + threshold.increase_pixels
    ) * pixel_area_m2 + threshold.stable_pixels * pixel_area_m2
    return {
        "pixels_sum_to_valid": total_pixels == threshold.valid_pixels,
        "area_sum_matches": abs(total_area_m2 - parts_area_m2) < 1e-9,
        "total_area_m2": round(total_area_m2, 6),
        "total_area_ha": round(total_area_m2 / M2_PER_HA, 6),
    }
