"""Threshold classification, delta statistics and area conservation.

The classification rule is fixed and symmetric:

* ``decrease``: ``delta <= -threshold``
* ``increase``: ``delta >=  threshold``
* ``stable``:   ``-threshold < delta < threshold``

A pixel belongs to exactly one class on the common-valid footprint.  Every
area is derived from an integer pixel count on the documented projected grid
(100 m² per 10 m pixel), so the three class areas must sum to the common-valid
area of the estimator being evaluated.  That identity is checked for every
threshold and every estimator, not assumed.
"""

from __future__ import annotations

from typing import Any

import numpy as np


class ThresholdError(ValueError):
    """Raised when a threshold sweep cannot be computed honestly."""


def delta_statistics(delta: np.ndarray, common: np.ndarray) -> dict[str, Any]:
    """Descriptive statistics of one estimator on its common-valid footprint."""
    if delta.shape != common.shape:
        raise ThresholdError(
            f"delta shape {delta.shape} != common shape {common.shape}"
        )
    values = np.asarray(delta, dtype=np.float64)[common]
    if values.size == 0:
        raise ThresholdError("common-valid footprint is empty")
    if not np.all(np.isfinite(values)):
        raise ThresholdError("common-valid footprint contains non-finite delta values")
    quantiles = np.percentile(values, [5, 25, 50, 75, 95])
    return {
        "valid_count": int(values.size),
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "std": float(values.std(ddof=0)),
        "quantiles": {
            "p05": float(quantiles[0]),
            "p25": float(quantiles[1]),
            "p50": float(quantiles[2]),
            "p75": float(quantiles[3]),
            "p95": float(quantiles[4]),
        },
    }


def classify_delta(
    delta: np.ndarray, common: np.ndarray, threshold: float
) -> dict[str, np.ndarray]:
    """Boolean masks for the three mutually exclusive change classes."""
    if threshold <= 0:
        raise ThresholdError("threshold must be strictly positive")
    decrease = common & (delta <= -threshold)
    increase = common & (delta >= threshold)
    stable = common & ~(decrease | increase)
    if np.any(decrease & increase):
        raise ThresholdError("decrease and increase masks overlap")
    if not np.array_equal(decrease | stable | increase, common):
        raise ThresholdError("threshold classes do not cover the common footprint")
    return {"decrease": decrease, "stable": stable, "increase": increase}


def threshold_row(
    delta: np.ndarray,
    common: np.ndarray,
    threshold: float,
    pixel_area_m2: float,
) -> dict[str, Any]:
    masks = classify_delta(delta, common, threshold)
    valid_pixels = int(common.sum())
    decrease = int(masks["decrease"].sum())
    stable = int(masks["stable"].sum())
    increase = int(masks["increase"].sum())
    area = lambda pixels: float(pixels) * float(pixel_area_m2)  # noqa: E731
    row = {
        "threshold": float(threshold),
        "valid_pixels": valid_pixels,
        "decrease_pixels": decrease,
        "stable_pixels": stable,
        "increase_pixels": increase,
        "valid_area_m2": area(valid_pixels),
        "decrease_area_m2": area(decrease),
        "stable_area_m2": area(stable),
        "increase_area_m2": area(increase),
        "valid_area_ha": area(valid_pixels) / 10_000.0,
        "decrease_area_ha": area(decrease) / 10_000.0,
        "stable_area_ha": area(stable) / 10_000.0,
        "increase_area_ha": area(increase) / 10_000.0,
        "decrease_percent_of_common": 100.0 * decrease / valid_pixels,
        "increase_percent_of_common": 100.0 * increase / valid_pixels,
        "stable_percent_of_common": 100.0 * stable / valid_pixels,
    }
    row["area_conservation"] = check_area_conservation(row)
    return row


def check_area_conservation(row: dict[str, Any]) -> dict[str, Any]:
    """Verify that the three class areas reconstruct the common-valid area."""
    pixel_residual = (
        row["decrease_pixels"] + row["stable_pixels"] + row["increase_pixels"]
        - row["valid_pixels"]
    )
    area_residual = (
        row["decrease_area_m2"]
        + row["stable_area_m2"]
        + row["increase_area_m2"]
        - row["valid_area_m2"]
    )
    percent_residual = (
        row["decrease_percent_of_common"]
        + row["stable_percent_of_common"]
        + row["increase_percent_of_common"]
        - 100.0
    )
    return {
        "pixel_residual": int(pixel_residual),
        "area_residual_m2": float(area_residual),
        "percent_residual": float(percent_residual),
        "ok": bool(
            pixel_residual == 0
            and abs(area_residual) <= 1e-6
            and abs(percent_residual) <= 1e-9
        ),
    }


def threshold_sweep(
    delta: np.ndarray,
    common: np.ndarray,
    thresholds: tuple[float, ...] | list[float],
    pixel_area_m2: float,
) -> list[dict[str, Any]]:
    """Compute the full threshold response and check monotonicity."""
    rows = [
        threshold_row(delta, common, float(threshold), pixel_area_m2)
        for threshold in thresholds
    ]
    for row in rows:
        if not row["area_conservation"]["ok"]:
            raise ThresholdError(
                f"area conservation failed at threshold {row['threshold']}: "
                f"{row['area_conservation']}"
            )

    ordered = sorted(rows, key=lambda item: item["threshold"])
    violations: list[str] = []
    for previous, current in zip(ordered, ordered[1:]):
        if current["decrease_pixels"] > previous["decrease_pixels"]:
            violations.append(
                f"decrease grew from {previous['decrease_pixels']} to "
                f"{current['decrease_pixels']} between thresholds "
                f"{previous['threshold']} and {current['threshold']}"
            )
        if current["increase_pixels"] > previous["increase_pixels"]:
            violations.append(
                f"increase grew from {previous['increase_pixels']} to "
                f"{current['increase_pixels']} between thresholds "
                f"{previous['threshold']} and {current['threshold']}"
            )
        if current["stable_pixels"] < previous["stable_pixels"]:
            violations.append(
                f"stable shrank from {previous['stable_pixels']} to "
                f"{current['stable_pixels']} between thresholds "
                f"{previous['threshold']} and {current['threshold']}"
            )
    if violations:
        raise ThresholdError("threshold response is not monotone: " + "; ".join(violations))
    return rows
