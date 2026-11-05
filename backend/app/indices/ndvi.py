"""Normalised Difference Vegetation Index and descriptive statistics.

NDVI = (NIR - RED) / (NIR + RED) on surface reflectance.  Division by zero,
non-finite inputs and masked pixels all resolve to ``NaN`` so that no fabricated
vegetation value can enter a statistic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: Tolerance below which the denominator is treated as zero.
DENOM_EPS = 1e-6


class IndexError_(ValueError):
    """Raised when index inputs are malformed."""


@dataclass
class IndexStats:
    """Distribution summary over valid pixels only."""

    valid_count: int
    total_count: int
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    std: float | None = None
    quantiles: dict[str, float] = field(default_factory=dict)

    @property
    def valid_fraction(self) -> float:
        return 0.0 if self.total_count == 0 else self.valid_count / self.total_count

    def to_dict(self) -> dict[str, object]:
        return {
            "valid_count": self.valid_count,
            "total_count": self.total_count,
            "valid_fraction": round(self.valid_fraction, 6),
            "min": None if self.minimum is None else round(self.minimum, 6),
            "max": None if self.maximum is None else round(self.maximum, 6),
            "mean": None if self.mean is None else round(self.mean, 6),
            "std": None if self.std is None else round(self.std, 6),
            "quantiles": {k: round(v, 6) for k, v in self.quantiles.items()},
        }


def normalised_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Generic ``(a - b) / (a + b)`` with NaN-safe denominator handling."""
    if a.shape != b.shape:
        raise IndexError_(f"input shapes differ: {a.shape} vs {b.shape}")
    first = a.astype(np.float32, copy=True)
    second = b.astype(np.float32, copy=True)
    denominator = first + second
    with np.errstate(invalid="ignore", divide="ignore"):
        result = (first - second) / denominator
    result[np.abs(denominator) < DENOM_EPS] = np.nan
    result[~np.isfinite(result)] = np.nan
    # For non-negative surface reflectance the index is bounded by [-1, 1].
    # Values outside that range can only arise from negative reflectance (the
    # L2A BOA offset on near-dark pixels) and are not interpretable, so they
    # are excluded rather than allowed to dominate statistics.
    result[np.abs(result) > 1.0] = np.nan
    return result


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Return NDVI, masked to ``NaN`` wherever it is not computable."""
    return normalised_difference(nir, red)


def difference(later: np.ndarray, earlier: np.ndarray) -> np.ndarray:
    """Per-pixel ``later - earlier``, preserving ``NaN`` where either is invalid."""
    if later.shape != earlier.shape:
        raise IndexError_(f"array shapes differ: {later.shape} vs {earlier.shape}")
    result = later.astype(np.float32, copy=True) - earlier.astype(np.float32)
    result[~np.isfinite(result)] = np.nan
    return result


def summarise(values: np.ndarray, mask: np.ndarray | None = None) -> IndexStats:
    """Summarise finite values, optionally restricted by a boolean mask."""
    flat = values.astype(np.float32, copy=True)
    if mask is not None:
        if mask.shape != flat.shape:
            raise IndexError_(f"mask shape {mask.shape} != array shape {flat.shape}")
        flat[~mask] = np.nan
    finite = flat[np.isfinite(flat)]
    stats = IndexStats(valid_count=int(finite.size), total_count=int(flat.size))
    if finite.size == 0:
        return stats
    stats.minimum = float(finite.min())
    stats.maximum = float(finite.max())
    stats.mean = float(finite.mean())
    stats.std = float(finite.std())
    stats.quantiles = {
        "p05": float(np.quantile(finite, 0.05)),
        "p25": float(np.quantile(finite, 0.25)),
        "p50": float(np.quantile(finite, 0.50)),
        "p75": float(np.quantile(finite, 0.75)),
        "p95": float(np.quantile(finite, 0.95)),
    }
    return stats


def thresholded_area(
    delta: np.ndarray,
    mask: np.ndarray,
    *,
    threshold: float,
    pixel_area_m2: float,
) -> dict[str, float]:
    """Area statistics for a thresholded delta, in m2 and hectares."""
    if delta.shape != mask.shape:
        raise IndexError_("delta and mask shapes differ")
    valid = mask & np.isfinite(delta)
    usable = delta[valid]
    decrease = int(np.count_nonzero(usable <= -abs(threshold)))
    increase = int(np.count_nonzero(usable >= abs(threshold)))
    stable = int(usable.size - decrease - increase)
    return {
        "threshold": threshold,
        "valid_pixels": int(usable.size),
        "decrease_pixels": decrease,
        "increase_pixels": increase,
        "stable_pixels": stable,
        "valid_area_ha": round(usable.size * pixel_area_m2 / 10_000.0, 4),
        "decrease_area_ha": round(decrease * pixel_area_m2 / 10_000.0, 4),
        "increase_area_ha": round(increase * pixel_area_m2 / 10_000.0, 4),
    }
