"""Measured uncertainty: coverage, threshold range, temporal robustness, bootstrap.

Nothing here assumes a probability model for the landscape.  The spatial block
bootstrap is an explicit resampling design with stated assumptions:

* the grid is partitioned into contiguous square blocks;
* blocks are exchangeable for the purpose of estimating the sampling
  variability of an area fraction;
* within-block spatial dependence is retained, between-block dependence is
  ignored;
* the threshold and the validity mask are held fixed.

That is a defensible small-area sensitivity statement, not a population
confidence interval for all mangroves.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .config import M2Config
from .inputs import ObservationSet


def coverage_summary(
    config: M2Config,
    m1_summary: dict[str, Any],
    observations: ObservationSet,
) -> dict[str, Any]:
    grid = m1_summary["grid"]
    aoi_pixels = int(m1_summary["aoi"]["aoi_pixels"])
    grid_pixels = int(grid["width"]) * int(grid["height"])
    periods = []
    for period in m1_summary["periods"]:
        period_id = period["period_id"]
        records = observations.for_period(period_id)
        periods.append(
            {
                "period_id": period_id,
                "anchor_date": period["anchor_date"],
                "observation_count": int(period["observation_count"]),
                "item_ids": list(period["item_ids"]),
                "dates": list(period["observation_dates"]),
                "valid_pixels": int(period["valid_pixels"]),
                "valid_fraction_of_aoi": float(period["valid_fraction"]),
                "valid_fraction_of_grid": float(period["valid_fraction_of_grid"]),
                "observation_count_stats": period.get("observation_count_stats"),
                "cached_valid_pixels": {
                    record.item_id: record.valid_pixels for record in records
                },
            }
        )
    change = []
    for index, block in sorted((m1_summary.get("change") or {}).items()):
        change.append(
            {
                "index": index,
                "common_valid_pixels": int(block["common_valid_pixels"]),
                "common_valid_fraction_of_aoi": float(
                    block["common_valid_fraction_of_aoi"]
                ),
                "common_valid_area_ha": float(block["common_valid_area_ha"]),
                "suitable_for_comparison": bool(block["suitable_for_comparison"]),
            }
        )
    common_fractions = [item["common_valid_fraction_of_aoi"] for item in change]
    return {
        "aoi_pixels": aoi_pixels,
        "grid_pixels": grid_pixels,
        "aoi_area_km2": float(m1_summary["aoi"]["area_km2"]),
        "pixel_area_m2": float(grid["pixel_area_m2"]),
        "periods": periods,
        "change": change,
        "minimum_common_valid_fraction_of_aoi": min(common_fractions),
        "all_indices_suitable": all(
            item["suitable_for_comparison"] for item in change
        ),
        "min_comparable_valid_fraction": config.min_comparable_valid_fraction,
    }


def temporal_robustness(
    results: list[dict[str, Any]],
    index: str,
    thresholds: tuple[float, ...],
) -> dict[str, Any]:
    """Spread of change fractions across genuine observation selections."""
    families = {"single_pairs", "leave_one_out", "composite"}
    selected = [
        result
        for result in results
        if result["index"] == index and result["family"] in families
    ]
    if not selected:
        return {"available": False, "reason": "no temporal estimators for this index"}
    rows = []
    for threshold in thresholds:
        decreases = []
        increases = []
        means = []
        for result in selected:
            row = next(
                item
                for item in result["thresholds"]
                if abs(item["threshold"] - threshold) <= 1e-9
            )
            decreases.append(row["decrease_percent_of_common"])
            increases.append(row["increase_percent_of_common"])
            means.append(result["delta_stats"]["mean"])

        def spread(values: list[float]) -> dict[str, float]:
            array = np.asarray(values, dtype=np.float64)
            return {
                "min": float(array.min()),
                "max": float(array.max()),
                "range": float(array.max() - array.min()),
                "mean": float(array.mean()),
                "std": float(array.std(ddof=0)),
                "count": int(array.size),
            }

        rows.append(
            {
                "threshold": float(threshold),
                "decrease_percent_of_common": spread(decreases),
                "increase_percent_of_common": spread(increases),
                "delta_mean": spread(means),
            }
        )
    return {
        "available": True,
        "index": index,
        "estimator_ids": sorted(result["estimator_id"] for result in selected),
        "families": sorted(families),
        "rows": rows,
        "interpretation": (
            "Range across single-scene pairs, leave-one-out medians and the "
            "median/mean composites. It measures observation-selection "
            "sensitivity, not a confidence interval."
        ),
    }


def block_bootstrap(
    *,
    delta: np.ndarray,
    common: np.ndarray,
    thresholds: tuple[float, ...],
    block_size_px: int,
    iterations: int,
    seed: int,
    pixel_area_m2: float,
) -> dict[str, Any]:
    """Spatial block bootstrap for change-area fractions and mean delta."""
    if iterations == 0:
        return {"enabled": False, "reason": "bootstrap_iterations is 0"}
    if delta.shape != common.shape:
        raise ValueError("delta and common shapes differ")
    if block_size_px < 1:
        raise ValueError("block_size_px must be positive")
    height, width = common.shape
    n_row_blocks = (height + block_size_px - 1) // block_size_px
    n_col_blocks = (width + block_size_px - 1) // block_size_px
    n_blocks = n_row_blocks * n_col_blocks
    rows = np.arange(height) // block_size_px
    cols = np.arange(width) // block_size_px
    block_id = rows[:, None] * n_col_blocks + cols[None, :]
    flat_blocks = block_id.ravel()

    valid_count = np.bincount(
        flat_blocks[common.ravel()], minlength=n_blocks
    ).astype(np.float64)
    delta_sum = np.bincount(
        flat_blocks[common.ravel()],
        weights=delta.ravel()[common.ravel()],
        minlength=n_blocks,
    )
    threshold_blocks: list[dict[str, Any]] = []
    for threshold in thresholds:
        decrease = common & (delta <= -threshold)
        increase = common & (delta >= threshold)
        threshold_blocks.append(
            {
                "threshold": float(threshold),
                "decrease": np.bincount(
                    flat_blocks[decrease.ravel()], minlength=n_blocks
                ).astype(np.float64),
                "increase": np.bincount(
                    flat_blocks[increase.ravel()], minlength=n_blocks
                ).astype(np.float64),
            }
        )

    rng = np.random.default_rng(seed)
    decrease_samples: dict[float, list[float]] = {
        float(item["threshold"]): [] for item in threshold_blocks
    }
    increase_samples: dict[float, list[float]] = {
        float(item["threshold"]): [] for item in threshold_blocks
    }
    delta_mean_samples: list[float] = []
    for _ in range(iterations):
        sampled = rng.integers(0, n_blocks, size=n_blocks)
        valid_boot = valid_count[sampled].sum()
        if valid_boot <= 0:
            continue
        delta_mean_samples.append(float(delta_sum[sampled].sum() / valid_boot))
        for item in threshold_blocks:
            threshold = float(item["threshold"])
            decrease_samples[threshold].append(
                float(item["decrease"][sampled].sum() / valid_boot)
            )
            increase_samples[threshold].append(
                float(item["increase"][sampled].sum() / valid_boot)
            )

    def interval(values: list[float]) -> dict[str, float]:
        array = np.asarray(values, dtype=np.float64)
        p025, p50, p975 = np.percentile(array, [2.5, 50, 97.5])
        return {
            "p2_5": float(p025),
            "p50": float(p50),
            "p97_5": float(p975),
        }

    valid_total = int(common.sum())
    rows_out = []
    for item in threshold_blocks:
        threshold = float(item["threshold"])
        decrease_total = int(item["decrease"].sum())
        increase_total = int(item["increase"].sum())
        p_decrease = decrease_total / valid_total
        p_increase = increase_total / valid_total
        se_decrease = float(np.sqrt(p_decrease * (1 - p_decrease) / valid_total))
        se_increase = float(np.sqrt(p_increase * (1 - p_increase) / valid_total))
        rows_out.append(
            {
                "threshold": threshold,
                "decrease_fraction": p_decrease,
                "increase_fraction": p_increase,
                "decrease_area_ha": decrease_total * pixel_area_m2 / 10_000.0,
                "increase_area_ha": increase_total * pixel_area_m2 / 10_000.0,
                "decrease_fraction_ci95": interval(
                    decrease_samples[threshold]
                ),
                "increase_fraction_ci95": interval(
                    increase_samples[threshold]
                ),
                "naive_pixel_binomial_ci95": {
                    "decrease": {
                        "p2_5": p_decrease - 1.96 * se_decrease,
                        "p97_5": p_decrease + 1.96 * se_decrease,
                    },
                    "increase": {
                        "p2_5": p_increase - 1.96 * se_increase,
                        "p97_5": p_increase + 1.96 * se_increase,
                    },
                    "note": (
                        "Pixel-independent approximation shown only for "
                        "comparison; it understates spatial dependence."
                    ),
                },
            }
        )

    delta_array = np.asarray(delta_mean_samples, dtype=np.float64)
    delta_ci = np.percentile(delta_array, [2.5, 50, 97.5]) if delta_array.size else [np.nan] * 3
    blocks_with_data = int(np.count_nonzero(valid_count > 0))
    return {
        "enabled": True,
        "method": "spatial_block_bootstrap",
        "block_size_px": block_size_px,
        "block_size_m": block_size_px * float(np.sqrt(pixel_area_m2)),
        "blocks_total": int(n_blocks),
        "blocks_with_valid_data": blocks_with_data,
        "iterations_requested": int(iterations),
        "iterations_used": int(delta_array.size),
        "seed": int(seed),
        "thresholds": rows_out,
        "delta_mean_ci95": {
            "p2_5": float(delta_ci[0]),
            "p50": float(delta_ci[1]),
            "p97_5": float(delta_ci[2]),
        },
        "assumptions": [
            "Contiguous square blocks are exchangeable for estimating area-fraction variability.",
            "Within-block spatial dependence is retained; between-block dependence is ignored.",
            "The valid mask and threshold are held fixed, not resampled.",
            "The interval describes this AOI and grid, not the wider delta or other mangroves.",
        ],
    }
