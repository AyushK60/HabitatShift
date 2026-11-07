"""Estimator comparison for the M2 experiments.

The M1 headline result is a **median composite of reflectance** followed by an
index calculation.  It is not the median of per-observation indices, and it is
not a single scene.  M2 therefore compares:

* the M1 median composite (reproduction check);
* a mean composite (different aggregation, same observations);
* the anchor single observation pair used by M0;
* every genuine earlier × later single-scene pair from the cache;
* leave-one-out median composites (one observation removed at a time);
* the frozen M0 single-scene raster.

All products use the same index formula and the same threshold rule.  A
difference between estimators is reported as an estimator/observation-selection
effect, never as a processing regression.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from ..indices.spectral import INDEX_SPECS
from .config import M2Config
from .inputs import ObservationRecord, ObservationSet, index_from_reflectance
from .thresholds import delta_statistics, threshold_sweep


class EstimatorError(RuntimeError):
    """Raised when an estimator cannot be built on the common grid."""


@dataclass(frozen=True)
class DeltaSurface:
    """One estimator's matched-valid difference surface for one index."""

    estimator_id: str
    label: str
    family: str
    index: str
    delta: np.ndarray
    common: np.ndarray
    earlier: dict[str, Any]
    later: dict[str, Any]
    notes: tuple[str, ...] = ()

    @property
    def common_pixels(self) -> int:
        return int(self.common.sum())


def composite_bands(
    records: Iterable[ObservationRecord], method: str
) -> tuple[dict[str, np.ndarray], np.ndarray, dict[str, Any]]:
    """Composite reflectance exactly as the M1 engine does, then compute indices."""
    records = tuple(records)
    if not records:
        raise EstimatorError("cannot composite an empty observation set")
    if method not in {"median", "mean"}:
        raise EstimatorError(f"unknown composite method {method!r}")
    shape = records[0].valid.shape
    band_keys: set[str] | None = None
    for record in records:
        if record.valid.shape != shape:
            raise EstimatorError("composite observations do not share one shape")
        keys = set(record.reflectance)
        band_keys = keys if band_keys is None else band_keys & keys
    if not band_keys:
        raise EstimatorError("composite observations share no bands")

    counts = np.zeros(shape, dtype=np.int16)
    for record in records:
        counts += record.valid.astype(np.int16)
    valid = counts >= 1

    bands: dict[str, np.ndarray] = {}
    with np.errstate(invalid="ignore"):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="All-NaN slice encountered", category=RuntimeWarning
            )
            warnings.filterwarnings(
                "ignore", message="Mean of empty slice", category=RuntimeWarning
            )
            for key in sorted(band_keys):
                stack = np.stack(
                    [
                        np.where(record.valid, record.reflectance[key], np.nan)
                        for record in records
                    ]
                )
                combined = (
                    np.nanmedian(stack, axis=0)
                    if method == "median"
                    else np.nanmean(stack, axis=0)
                )
                combined = combined.astype(np.float32)
                combined[~valid] = np.nan
                bands[key] = combined

    # Compute every index whose bands are present; the caller selects the
    # configured subset.
    indices = {
        index: index_from_reflectance(bands, index)
        for index in INDEX_SPECS
        if all(band in bands for band in INDEX_SPECS[index].bands)
    }
    provenance = {
        "method": method,
        "observation_count": len(records),
        "item_ids": [record.item_id for record in records],
        "dates": [record.date for record in records],
        "counts": {
            "min": int(counts[valid].min()) if valid.any() else 0,
            "max": int(counts[valid].max()) if valid.any() else 0,
            "mean": float(counts[valid].mean()) if valid.any() else 0.0,
        },
    }
    return indices, valid, provenance


def _surface(
    *,
    estimator_id: str,
    label: str,
    family: str,
    index: str,
    earlier_values: np.ndarray,
    later_values: np.ndarray,
    earlier_valid: np.ndarray,
    later_valid: np.ndarray,
    earlier_source: dict[str, Any],
    later_source: dict[str, Any],
    notes: tuple[str, ...] = (),
) -> DeltaSurface:
    common = earlier_valid & later_valid
    if not common.any():
        raise EstimatorError(f"{estimator_id}/{index}: empty common-valid footprint")
    with np.errstate(invalid="ignore"):
        delta = (
            later_values.astype(np.float32) - earlier_values.astype(np.float32)
        ).astype(np.float64)
    delta[~common] = np.nan
    if not np.all(np.isfinite(delta[common])):
        raise EstimatorError(
            f"{estimator_id}/{index}: non-finite delta inside common footprint"
        )
    return DeltaSurface(
        estimator_id=estimator_id,
        label=label,
        family=family,
        index=index,
        delta=delta,
        common=common,
        earlier=earlier_source,
        later=later_source,
        notes=notes,
    )


def _single_source(record: ObservationRecord) -> dict[str, Any]:
    return {
        "kind": "single_observation",
        "item_ids": [record.item_id],
        "dates": [record.date],
        "valid_pixels": record.valid_pixels,
    }


def _composite_source(records: Iterable[ObservationRecord], method: str) -> dict[str, Any]:
    records = tuple(records)
    return {
        "kind": f"{method}_composite",
        "item_ids": [record.item_id for record in records],
        "dates": [record.date for record in records],
        "observation_count": len(records),
    }


def _anchor_record(
    period_payload: dict[str, Any], observations: ObservationSet
) -> ObservationRecord:
    period_id = period_payload["period_id"]
    item_ids = list(period_payload.get("item_ids") or [])
    if not item_ids:
        raise EstimatorError(f"period {period_id} has no item ids in the M1 summary")
    anchor_date = str(period_payload.get("anchor_date") or "")
    candidates = observations.for_period(period_id)
    by_id = {record.item_id: record for record in candidates}
    if item_ids[0] in by_id and by_id[item_ids[0]].date == anchor_date:
        return by_id[item_ids[0]]
    for record in candidates:
        if record.date == anchor_date:
            return record
    raise EstimatorError(
        f"period {period_id}: no cached observation matches anchor {anchor_date}"
    )


def build_surfaces(
    config: M2Config,
    observations: ObservationSet,
    m1_summary: dict[str, Any],
    m0_delta: np.ndarray | None,
    m0_valid: np.ndarray | None,
    m0_source: dict[str, Any] | None = None,
) -> list[DeltaSurface]:
    """Expand the configured families into concrete estimator surfaces."""
    surfaces: list[DeltaSurface] = []
    periods = {period["period_id"]: period for period in m1_summary["periods"]}
    earlier_records = observations.for_period("earlier")
    later_records = observations.for_period("later")
    anchor_earlier = _anchor_record(periods["earlier"], observations)
    anchor_later = _anchor_record(periods["later"], observations)

    composite_cache: dict[tuple[tuple[str, ...], str], tuple[dict[str, np.ndarray], np.ndarray, dict[str, Any]]] = {}

    def composite(records: tuple[ObservationRecord, ...], method: str):
        key = (tuple(record.item_id for record in records), method)
        if key not in composite_cache:
            composite_cache[key] = composite_bands(records, method)
        return composite_cache[key]

    earlier_median, earlier_median_valid, earlier_median_meta = composite(
        earlier_records, "median"
    )
    later_median, later_median_valid, later_median_meta = composite(
        later_records, "median"
    )

    if "composite" in config.estimator_families:
        earlier_mean, earlier_mean_valid, _ = composite(earlier_records, "mean")
        later_mean, later_mean_valid, _ = composite(later_records, "mean")
        for index in config.indices:
            surfaces.append(
                _surface(
                    estimator_id="composite_median",
                    label=f"M1 median composite · {len(earlier_records)}×{len(later_records)} observations",
                    family="composite",
                    index=index,
                    earlier_values=earlier_median[index],
                    later_values=later_median[index],
                    earlier_valid=earlier_median_valid,
                    later_valid=later_median_valid,
                    earlier_source=_composite_source(earlier_records, "median"),
                    later_source=_composite_source(later_records, "median"),
                    notes=("reproduces the M1 headline estimator",),
                )
            )
            surfaces.append(
                _surface(
                    estimator_id="composite_mean",
                    label="Mean composite · same observations",
                    family="composite",
                    index=index,
                    earlier_values=earlier_mean[index],
                    later_values=later_mean[index],
                    earlier_valid=earlier_mean_valid,
                    later_valid=later_mean_valid,
                    earlier_source=_composite_source(earlier_records, "mean"),
                    later_source=_composite_source(later_records, "mean"),
                    notes=("aggregation sensitivity: mean instead of median",),
                )
            )

    if "anchor_single" in config.estimator_families:
        for index in config.indices:
            surfaces.append(
                _surface(
                    estimator_id="anchor_single",
                    label=(
                        "Anchor single observation · "
                        f"{anchor_earlier.date} × {anchor_later.date}"
                    ),
                    family="anchor_single",
                    index=index,
                    earlier_values=anchor_earlier.indices[index],
                    later_values=anchor_later.indices[index],
                    earlier_valid=anchor_earlier.valid,
                    later_valid=anchor_later.valid,
                    earlier_source=_single_source(anchor_earlier),
                    later_source=_single_source(anchor_later),
                    notes=("same acquisition dates as the M0 baseline",),
                )
            )

    if "single_pairs" in config.estimator_families:
        for index in config.indices:
            for earlier in earlier_records:
                for later in later_records:
                    surfaces.append(
                        _surface(
                            estimator_id=f"single__{earlier.item_id}__{later.item_id}",
                            label=(
                                f"Single scenes · {earlier.date} × {later.date}"
                            ),
                            family="single_pairs",
                            index=index,
                            earlier_values=earlier.indices[index],
                            later_values=later.indices[index],
                            earlier_valid=earlier.valid,
                            later_valid=later.valid,
                            earlier_source=_single_source(earlier),
                            later_source=_single_source(later),
                            notes=("one genuine scene per period; no compositing",),
                        )
                    )

    if "leave_one_out" in config.estimator_families:
        for index in config.indices:
            for period_id, records, other_values, other_valid, other_source in (
                (
                    "earlier",
                    earlier_records,
                    later_median[index],
                    later_median_valid,
                    _composite_source(later_records, "median"),
                ),
                (
                    "later",
                    later_records,
                    earlier_median[index],
                    earlier_median_valid,
                    _composite_source(earlier_records, "median"),
                ),
            ):
                for dropped in records:
                    remaining = tuple(
                        record for record in records if record.item_id != dropped.item_id
                    )
                    values, valid, _ = composite(remaining, "median")
                    if period_id == "earlier":
                        earlier_values, earlier_valid, earlier_source = (
                            values[index],
                            valid,
                            _composite_source(remaining, "median"),
                        )
                        later_values, later_valid, later_source = (
                            other_values,
                            other_valid,
                            other_source,
                        )
                    else:
                        earlier_values, earlier_valid, earlier_source = (
                            other_values,
                            other_valid,
                            other_source,
                        )
                        later_values, later_valid, later_source = (
                            values[index],
                            valid,
                            _composite_source(remaining, "median"),
                        )
                    surfaces.append(
                        _surface(
                            estimator_id=(
                                f"loo_{period_id}_without_{dropped.item_id}"
                            ),
                            label=(
                                f"Leave-one-out median · {period_id} without "
                                f"{dropped.date}"
                            ),
                            family="leave_one_out",
                            index=index,
                            earlier_values=earlier_values,
                            later_values=later_values,
                            earlier_valid=earlier_valid,
                            later_valid=later_valid,
                            earlier_source=earlier_source,
                            later_source=later_source,
                            notes=("temporal robustness: one observation removed",),
                        )
                    )

    if (
        "m0_single_scene" in config.estimator_families
        and "ndvi" in config.indices
        and m0_delta is not None
        and m0_valid is not None
    ):
        common = np.asarray(m0_valid, dtype=bool) & np.isfinite(m0_delta)
        surfaces.append(
            DeltaSurface(
                estimator_id="m0_anchor_single_scene",
                label="M0 frozen single-scene NDVI baseline",
                family="m0_single_scene",
                index="ndvi",
                delta=np.where(common, m0_delta, np.nan).astype(np.float64),
                common=common,
                earlier={"kind": "frozen_m0_raster", "item_ids": [m0_source.get("earlier_item_id")] if m0_source else [], "dates": [m0_source.get("earlier_date")] if m0_source else []},
                later={"kind": "frozen_m0_raster", "item_ids": [m0_source.get("later_item_id")] if m0_source else [], "dates": [m0_source.get("later_date")] if m0_source else []},
                notes=(
                    "independent M0 pipeline; different mask policy and a slightly "
                    "smaller common footprint",
                ),
            )
        )

    if not surfaces:
        raise EstimatorError("no estimator surfaces were built")
    surfaces.sort(key=lambda surface: (surface.index, surface.estimator_id))
    return surfaces


def evaluate_surface(
    surface: DeltaSurface,
    *,
    thresholds: tuple[float, ...],
    primary_threshold: float,
    pixel_area_m2: float,
    aoi_pixels: int,
    grid_pixels: int,
    min_comparable_valid_fraction: float,
) -> dict[str, Any]:
    stats = delta_statistics(surface.delta, surface.common)
    sweep = threshold_sweep(
        surface.delta, surface.common, thresholds, pixel_area_m2
    )
    primary = next(
        row
        for row in sweep
        if abs(row["threshold"] - primary_threshold) <= 1e-9
    )
    common_pixels = surface.common_pixels
    common_fraction = common_pixels / aoi_pixels if aoi_pixels else 0.0
    return {
        "estimator_id": surface.estimator_id,
        "label": surface.label,
        "family": surface.family,
        "index": surface.index,
        "common_valid_pixels": common_pixels,
        "common_valid_fraction_of_aoi": common_fraction,
        "common_valid_fraction_of_grid": (
            common_pixels / grid_pixels if grid_pixels else 0.0
        ),
        "common_valid_area_m2": common_pixels * pixel_area_m2,
        "common_valid_area_ha": common_pixels * pixel_area_m2 / 10_000.0,
        "common_valid_area_km2": common_pixels * pixel_area_m2 / 1_000_000.0,
        "suitable_for_comparison": common_fraction >= min_comparable_valid_fraction,
        "delta_stats": stats,
        "thresholds": sweep,
        "primary_threshold": primary_threshold,
        "primary": primary,
        "sources": {"earlier": surface.earlier, "later": surface.later},
        "notes": list(surface.notes),
        "area_conservation_all_ok": all(
            row["area_conservation"]["ok"] for row in sweep
        ),
    }


def evaluate_surfaces(
    surfaces: list[DeltaSurface],
    config: M2Config,
    m1_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    grid = m1_summary["grid"]
    aoi_pixels = int(m1_summary["aoi"]["aoi_pixels"])
    grid_pixels = int(grid["width"]) * int(grid["height"])
    pixel_area_m2 = float(grid["pixel_area_m2"])
    return [
        evaluate_surface(
            surface,
            thresholds=config.thresholds,
            primary_threshold=config.primary_threshold,
            pixel_area_m2=pixel_area_m2,
            aoi_pixels=aoi_pixels,
            grid_pixels=grid_pixels,
            min_comparable_valid_fraction=config.min_comparable_valid_fraction,
        )
        for surface in surfaces
    ]


def cross_pipeline_comparison(
    results: list[dict[str, Any]],
    surfaces: list[DeltaSurface],
    m0_bundle: Any,
) -> dict[str, Any]:
    """Compare the M0 raster with the M1 anchor on their shared footprint.

    Estimator ids repeat across indices (one surface per index), so the
    selection must filter on the index as well as the id.
    """
    anchor = next(
        (
            surface
            for surface in surfaces
            if surface.estimator_id == "anchor_single" and surface.index == "ndvi"
        ),
        None,
    )
    m0 = next(
        (
            surface
            for surface in surfaces
            if surface.estimator_id == "m0_anchor_single_scene"
            and surface.index == "ndvi"
        ),
        None,
    )
    if anchor is None or m0 is None:
        return {
            "available": False,
            "reason": "anchor_single or m0_anchor_single_scene estimator is absent",
        }
    shared = anchor.common & m0.common
    if not shared.any():
        return {"available": False, "reason": "estimators share no valid pixels"}
    difference = m0.delta[shared] - anchor.delta[shared]
    return {
        "available": True,
        "index": "ndvi",
        "shared_pixels": int(shared.sum()),
        "anchor_common_pixels": anchor.common_pixels,
        "m0_common_pixels": m0.common_pixels,
        "m0_only_pixels": int((m0.common & ~anchor.common).sum()),
        "anchor_only_pixels": int((anchor.common & ~m0.common).sum()),
        "anchor_mean_delta": float(anchor.delta[shared].mean()),
        "m0_mean_delta": float(m0.delta[shared].mean()),
        "mean_difference": float(difference.mean()),
        "max_abs_difference": float(np.abs(difference).max()),
        "pixels_identical_within_1e_9": int(
            np.count_nonzero(np.abs(difference) <= 1e-9)
        ),
        "interpretation": (
            "M0 and the M1 anchor use the same two dates and NDVI formula. "
            "Agreement on the shared footprint isolates the composite/observation-"
            "selection effect from a pipeline regression."
        ),
    }
