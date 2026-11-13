"""The M1 raster-processing and temporal-change engine.

Stages, in execution order:

1. load the validated experiment configuration, AOI and common analysis grid;
2. search each period, score candidates on measured in-AOI valid coverage and
   choose up to ``max_observations`` distinct usable dates around the anchor;
3. read only the required COG windows, verify radiometry, convert DN to
   reflectance, mask with SCL + AOI + finite checks, and memoise each
   observation;
4. composite the observations per pixel (median by default), recording valid
   observation counts;
5. compute every registered spectral index on the composite;
6. intersect the two periods' valid masks per index and analyse differences,
   thresholds and projected areas;
7. write georeferenced rasters, previews, summary JSON/CSV and a validated
   reproducibility manifest;
8. re-open the written artefacts and independently verify the numbers.

Nothing in this module imports the web API or the frontend.  The backend can run
fully offline from the observation cache once the catalogue and SCL memos exist.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import Geod
from rasterio.enums import Resampling

from .. import config
from ..acquisition.assets import (
    RadiometryError,
    empirical_offset_rejection,
    to_reflectance,
    verify_radiometry,
    with_scale_only_offset,
)
from ..acquisition.cog import WindowRequest, read_window
from ..analysis.change import (
    CLASS_DECREASE,
    CLASS_INCREASE,
    CLASS_INVALID,
    CLASS_STABLE,
    change_summary,
    classify_delta,
)
from ..catalog.models import SceneCandidate
from ..catalog.search import SearchRequest
from ..catalog.stac_client import CatalogClient
from ..http import HttpSession
from ..indices import ndvi as ndvi_mod
from ..indices.spectral import INDEX_SPECS, required_bands
from ..preprocess import masks as mask_mod
from ..preprocess import preview
from ..preprocess.composite import (
    CompositeResult,
    Observation,
    composite_observations,
    observation_cache_key,
)
from ..preprocess.grid import (
    AnalysisWindow,
    analysis_window,
    aoi_raster_mask,
    write_geotiff,
)
from ..preprocess.scoring import SceneScore, score_candidates
from .config import PeriodSpec, StudyConfig
from .provenance import M1ManifestBuilder, output_record

LOGGER = logging.getLogger(__name__)

#: Band display order in the exported reflectance composite.
BAND_EXPORT_ORDER = (
    config.ASSET_BLUE,
    config.ASSET_GREEN,
    config.ASSET_RED,
    config.ASSET_NIR,
    config.ASSET_SWIR1,
)

BAND_DESCRIPTIONS = {
    config.ASSET_BLUE: "blue_B02",
    config.ASSET_GREEN: "green_B03",
    config.ASSET_RED: "red_B04",
    config.ASSET_NIR: "nir_B08",
    config.ASSET_SWIR1: "swir1_B11",
}

#: Deterministic seed for the independent sample re-checks.
VERIFY_SEED = 20261106
VERIFY_SAMPLE_SIZE = 400


class EngineError(RuntimeError):
    """Raised when an M1 study cannot be completed honestly."""


class ObservationCacheMiss(EngineError):
    """Raised when offline mode needs an observation that is not cached."""


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
class ObservationCache:
    """Memoised, grid-pinned observation arrays.

    The cache key covers the STAC item, the analysis-grid signature and the
    requested band set.  A cached record is only reused when the current STAC
    metadata still describes the same assets with the same resolved radiometry,
    so a silent provider change cannot be masked by a stale cache.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _npz(self, key: str) -> Path:
        return self.directory / f"{key}.npz"

    def _meta(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def load(
        self,
        key: str,
        candidate: SceneCandidate,
        window: AnalysisWindow,
        band_keys: tuple[str, ...],
    ) -> Observation | None:
        npz_path, meta_path = self._npz(key), self._meta(key)
        if not npz_path.exists() or not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except ValueError:
            return None
        if meta.get("item_id") != candidate.item_id:
            return None
        if meta.get("grid_signature") != window.signature():
            return None
        if tuple(meta.get("band_keys") or ()) != tuple(band_keys):
            return None
        expected_hrefs = {k: candidate.asset(k).href for k in band_keys}
        if meta.get("assets") != expected_hrefs:
            return None
        try:
            current_radiometry = verify_radiometry(candidate, band_keys)
        except Exception:
            return None
        # A cached record's radiometry must be consistent with its own
        # stored decision: records with empirical-correction evidence must
        # carry the deterministic scale-only correction of the declared
        # resolution; records without evidence must match the declared
        # resolution.  The cache key additionally carries the radiometry
        # policy version, so records written under an older policy can
        # never surface here at all.
        declared_form = {k: v.to_dict() for k, v in current_radiometry.items()}
        corrected_radiometry = {
            k: with_scale_only_offset(v) for k, v in current_radiometry.items()
        }
        corrected_form = {k: v.to_dict() for k, v in corrected_radiometry.items()}
        has_evidence = bool(meta.get("radiometry_evidence"))
        expected = corrected_form if has_evidence else declared_form
        if meta.get("radiometry") != expected:
            return None
        try:
            with np.load(npz_path) as data:
                reflectance = {
                    k: data[f"reflectance_{k}"].astype(np.float32)
                    for k in band_keys
                }
                valid = data["valid"].astype(bool)
        except (OSError, KeyError, ValueError):
            return None
        # Independent plausibility gate on the cached pixels themselves: a
        # record whose reflectance means fall below the physical floor is
        # corrupt or was written under a wrong convention, and is discarded
        # whatever its metadata claims.
        if empirical_offset_rejection(reflectance) is not None:
            LOGGER.warning(
                "observation cache record %s discarded: cached reflectance "
                "is physically implausible",
                candidate.item_id,
            )
            return None
        if valid.shape != window.shape:
            return None
        report = mask_mod.MaskReport(
            total_pixels=int(meta.get("total_pixels", int(valid.size))),
            valid_pixels=int(valid.sum()),
            class_counts={
                int(k): int(v)
                for k, v in (meta.get("class_counts") or {}).items()
            },
        )
        return Observation(
            period_id=str(meta.get("period_id", "")),
            candidate=candidate,
            reflectance=reflectance,
            valid=valid,
            mask_report=report,
            radiometry=(
                corrected_radiometry if has_evidence else current_radiometry
            ),
            grid_signature=window.signature(),
            radiometry_evidence=dict(meta.get("radiometry_evidence") or {}),
        )

    def save(self, key: str, observation: Observation) -> None:
        arrays: dict[str, np.ndarray] = {"valid": observation.valid.astype(np.uint8)}
        for band_key, values in observation.reflectance.items():
            arrays[f"reflectance_{band_key}"] = values.astype(np.float32)
        npz_path, meta_path = self._npz(key), self._meta(key)
        tmp_npz = self.directory / f"{key}.tmp.npz"
        np.savez_compressed(tmp_npz, **arrays)
        tmp_npz.replace(npz_path)
        meta = {
            "item_id": observation.item_id,
            "period_id": observation.period_id,
            "grid_signature": observation.grid_signature,
            "band_keys": sorted(observation.reflectance),
            "assets": {
                k: observation.candidate.asset(k).href
                for k in sorted(observation.reflectance)
            },
            "radiometry": {
                k: v.to_dict() for k, v in observation.radiometry.items()
            },
            "radiometry_evidence": dict(observation.radiometry_evidence),
            "total_pixels": observation.mask_report.total_pixels,
            "valid_pixels": observation.mask_report.valid_pixels,
            "class_counts": {
                str(k): v for k, v in observation.mask_report.class_counts.items()
            },
        }
        tmp_meta = self.directory / f"{key}.tmp.json"
        tmp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        tmp_meta.replace(meta_path)


# --------------------------------------------------------------------------- #
# Stage 1: observation selection
# --------------------------------------------------------------------------- #
def select_period_observations(
    scores: list[SceneScore],
    candidates_by_id: dict[str, SceneCandidate],
    period_spec: PeriodSpec,
    *,
    max_observations: int,
    min_observations: int,
) -> tuple[list[SceneScore], dict[str, Any]]:
    """Choose distinct usable dates nearest the period anchor.

    The anchor observation keeps M0's tie-break rule (whole-scene cloud, then
    item id) so the single-observation baseline is directly comparable with the
    M0 result.  One observation per calendar date is kept: repeat acquisitions on
    the same date add no temporal information.
    """
    by_date: dict[str, list[SceneScore]] = {}
    for score in scores:
        candidate = candidates_by_id.get(score.item_id)
        if candidate is None or not score.usable:
            continue
        by_date.setdefault(candidate.date_str, []).append(score)

    best_per_date: list[SceneScore] = []
    for date, group in by_date.items():
        group.sort(
            key=lambda s: (
                s.cloud_cover_percent if s.cloud_cover_percent is not None else 100.0,
                -(s.aoi_valid_fraction or 0.0),
                s.item_id,
            )
        )
        best_per_date.append(group[0])

    def offset(score: SceneScore) -> int:
        candidate = candidates_by_id[score.item_id]
        return period_spec.offset_days(candidate.acquired)

    best_per_date.sort(
        key=lambda s: (
            offset(s),
            candidates_by_id[s.item_id].acquired,
            s.item_id,
        )
    )
    within = [s for s in best_per_date if offset(s) <= period_spec.max_offset_days]
    fallback_used = False
    pool = within
    if not pool and best_per_date:
        pool = best_per_date
        fallback_used = True
    chosen = pool[: max(int(max_observations), 1)]
    chosen.sort(
        key=lambda s: (
            0 if candidates_by_id[s.item_id].date_str == period_spec.anchor.isoformat() else 1,
            offset(s),
            candidates_by_id[s.item_id].acquired,
            s.item_id,
        )
    )
    if len(chosen) < min_observations:
        raise EngineError(
            f"period {period_spec.period_id!r}: only {len(chosen)} usable "
            f"observation(s) found, but at least {min_observations} are required"
        )

    report = {
        "anchor_date": period_spec.anchor.isoformat(),
        "max_offset_days": period_spec.max_offset_days,
        "usable_candidate_total": sum(len(v) for v in by_date.values()),
        "distinct_usable_dates": sorted(by_date),
        "chosen_item_ids": [s.item_id for s in chosen],
        "chosen_dates": [
            candidates_by_id[s.item_id].date_str for s in chosen
        ],
        "offset_days": {
            s.item_id: offset(s) for s in chosen
        },
        "within_anchor_window": not fallback_used,
        "fallback_used": fallback_used,
        "single_observation_limitation": len(chosen) < max_observations,
    }
    return chosen, report


# --------------------------------------------------------------------------- #
# Stage 2: bounded reads, radiometry and masking
# --------------------------------------------------------------------------- #
def read_observation(
    candidate: SceneCandidate,
    window: AnalysisWindow,
    aoi_mask: np.ndarray,
    band_keys: tuple[str, ...],
    *,
    period_id: str,
    cache: ObservationCache | None = None,
    offline: bool = False,
) -> Observation:
    """Read, convert and mask one observation on the common grid."""
    band_keys = tuple(sorted(set(band_keys)))
    key = observation_cache_key(candidate.item_id, window.signature(), band_keys)
    if cache is not None:
        cached = cache.load(key, candidate, window, band_keys)
        if cached is not None:
            cached.period_id = period_id
            LOGGER.debug("observation cache hit %s", candidate.item_id)
            return cached
    if offline:
        raise ObservationCacheMiss(
            f"offline mode: observation {candidate.item_id} is not cached for "
            f"grid {window.signature()} and bands {list(band_keys)}"
        )

    radiometry = verify_radiometry(candidate, band_keys)
    LOGGER.info(
        "%s: reading %s (%s), %d band(s)",
        period_id, candidate.item_id, candidate.date_str, len(band_keys),
    )

    scl_request = WindowRequest(
        dst_crs=window.crs,
        dst_transform=window.transform,
        height=window.height,
        width=window.width,
        resampling=Resampling.nearest,       # categorical: never smoothed
        dtype="int32",
    )
    scl = read_window(candidate.asset(config.ASSET_SCL).href, scl_request)
    scl_valid, scl_report = mask_mod.build_valid_mask(scl)

    dn_bands: dict[str, np.ndarray] = {}
    for band_key in band_keys:
        request = WindowRequest(
            dst_crs=window.crs,
            dst_transform=window.transform,
            height=window.height,
            width=window.width,
            resampling=Resampling.bilinear,   # continuous reflectance
            dtype="float32",
        )
        dn_bands[band_key] = read_window(candidate.asset(band_key).href, request)

    reflectance = {
        band_key: to_reflectance(dn_bands[band_key], radiometry[band_key])
        for band_key in band_keys
    }
    # Empirical acceptance test on the applied DN convention: a window mean
    # below the physical floor is only reachable when the declared offset
    # does not match the stored DNs (2025 Earth Search reprocessing).  The
    # alternative Sentinel-2 convention - scale only, offset 0 - is then
    # tried and must itself be plausible, otherwise the observation is
    # refused outright.  The decision and its measured evidence are recorded.
    radiometry_evidence: dict[str, object] = {}
    rejection = empirical_offset_rejection(reflectance)
    if rejection is not None:
        alt_radiometry = {
            key: with_scale_only_offset(record) for key, record in radiometry.items()
        }
        alt_reflectance = {
            key: to_reflectance(dn_bands[key], alt_radiometry[key])
            for key in band_keys
        }
        alt_rejection = empirical_offset_rejection(alt_reflectance)
        if alt_rejection is not None:
            raise RadiometryError(
                f"item {candidate.item_id}: neither the declared DN->"
                f"reflectance transform nor the scale-only alternative "
                f"produces physically plausible reflectance over the read "
                f"window; refusing the observation"
            )
        LOGGER.warning(
            "%s: declared offset rejected empirically (%s); applied "
            "scale-only reflectance for %s",
            period_id, rejection.get("reason", ""), candidate.item_id,
        )
        radiometry = alt_radiometry
        reflectance = alt_reflectance
        radiometry_evidence = rejection

    finite = mask_mod.reflectance_valid_mask(
        *[reflectance[k] for k in band_keys]
    )
    valid = mask_mod.combine_masks(aoi_mask, scl_valid, finite)
    report = mask_mod.MaskReport(
        total_pixels=int(aoi_mask.sum()),
        valid_pixels=int(valid.sum()),
        class_counts=scl_report.class_counts,
    )
    masked = {
        key_: mask_mod.apply_mask(band, valid)
        for key_, band in reflectance.items()
    }
    observation = Observation(
        period_id=period_id,
        candidate=candidate,
        reflectance=masked,
        valid=valid,
        mask_report=report,
        radiometry=radiometry,
        grid_signature=window.signature(),
        radiometry_evidence=radiometry_evidence,
    )
    if cache is not None:
        cache.save(key, observation)
    return observation


# --------------------------------------------------------------------------- #
# Stage 3: compositing and indices
# --------------------------------------------------------------------------- #
@dataclass
class PeriodStudy:
    period_id: str
    spec: PeriodSpec
    composite: CompositeResult
    indices: dict[str, np.ndarray]
    index_stats: dict[str, ndvi_mod.IndexStats]
    anchor_item_id: str
    anchor_date: str
    anchor_indices: dict[str, np.ndarray]
    anchor_stats: dict[str, ndvi_mod.IndexStats]
    selection: dict[str, Any]
    stretch: dict[str, Any] = field(default_factory=dict)
    raster_paths: dict[str, Path] = field(default_factory=dict)
    preview_paths: dict[str, Path] = field(default_factory=dict)

    def index_payload(self, analysis_resolution_m: float) -> dict[str, Any]:
        return {
            key: {
                **INDEX_SPECS[key].to_dict(analysis_resolution_m),
                "stats": self.index_stats[key].to_dict(),
            }
            for key in self.indices
        }


def compose_period(
    observations: list[Observation],
    period_spec: PeriodSpec,
    indices: tuple[str, ...],
    *,
    method: str,
    min_observations: int,
) -> PeriodStudy:
    """Composite observations and compute every requested index."""
    composite = composite_observations(
        observations, method=method, min_observations=min_observations
    )
    index_arrays: dict[str, np.ndarray] = {}
    index_stats: dict[str, ndvi_mod.IndexStats] = {}
    for key in indices:
        spec = INDEX_SPECS[key]
        values = spec.compute(composite.bands).astype(np.float32)
        values = np.where(composite.valid, values, np.nan)
        index_arrays[key] = values
        index_stats[key] = ndvi_mod.summarise(values, composite.valid)

    anchor_observation = min(
        observations,
        key=lambda obs: (
            period_spec.offset_days(obs.candidate.acquired),
            obs.candidate.cloud_cover
            if obs.candidate.cloud_cover is not None
            else 100.0,
            obs.item_id,
        ),
    )
    anchor_indices: dict[str, np.ndarray] = {}
    anchor_stats: dict[str, ndvi_mod.IndexStats] = {}
    for key in indices:
        spec = INDEX_SPECS[key]
        values = spec.compute(anchor_observation.reflectance).astype(np.float32)
        values = np.where(anchor_observation.valid, values, np.nan)
        anchor_indices[key] = values
        anchor_stats[key] = ndvi_mod.summarise(values, anchor_observation.valid)

    return PeriodStudy(
        period_id=period_spec.period_id,
        spec=period_spec,
        composite=composite,
        indices=index_arrays,
        index_stats=index_stats,
        anchor_item_id=anchor_observation.item_id,
        anchor_date=anchor_observation.date,
        anchor_indices=anchor_indices,
        anchor_stats=anchor_stats,
        selection={},
    )


# --------------------------------------------------------------------------- #
# Stage 4: matched-valid change
# --------------------------------------------------------------------------- #
@dataclass
class ChangeLayer:
    index: str
    delta: np.ndarray
    common: np.ndarray
    classes: np.ndarray
    summary: dict[str, Any]
    class_counts: dict[str, int]


def compute_change_layers(
    earlier: PeriodStudy,
    later: PeriodStudy,
    *,
    indices: tuple[str, ...],
    aoi_pixels: int,
    pixel_area_m2: float,
    thresholds: tuple[float, ...],
    primary_threshold: float,
    min_comparable_fraction: float,
) -> dict[str, ChangeLayer]:
    """Intersect both periods and analyse the difference for each index."""
    layers: dict[str, ChangeLayer] = {}
    for key in indices:
        if key not in earlier.indices or key not in later.indices:
            raise EngineError(f"index {key!r} is missing from one period")
        delta = ndvi_mod.difference(later.indices[key], earlier.indices[key])
        common = (
            earlier.composite.valid
            & later.composite.valid
            & np.isfinite(earlier.indices[key])
            & np.isfinite(later.indices[key])
            & np.isfinite(delta)
        )
        delta = np.where(common, delta, np.nan).astype(np.float32)
        summary = change_summary(
            delta,
            common,
            aoi_pixels=aoi_pixels,
            pixel_area_m2=pixel_area_m2,
            thresholds=thresholds,
            primary_threshold=primary_threshold,
            index_key=key,
            min_comparable_fraction=min_comparable_fraction,
        )
        classes = classify_delta(
            delta, common, threshold=float(summary["primary_threshold"])
        )
        class_counts = {
            "decrease": int(np.count_nonzero(classes == CLASS_DECREASE)),
            "stable": int(np.count_nonzero(classes == CLASS_STABLE)),
            "increase": int(np.count_nonzero(classes == CLASS_INCREASE)),
            "invalid": int(np.count_nonzero(classes == CLASS_INVALID)),
        }
        layers[key] = ChangeLayer(
            index=key,
            delta=delta,
            common=common,
            classes=classes,
            summary=summary,
            class_counts=class_counts,
        )
    return layers


# --------------------------------------------------------------------------- #
# Stage 5: exports
# --------------------------------------------------------------------------- #
class _OutputRegistry:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def add(self, name: str, path: Path, kind: str) -> Path:
        self.records[name] = output_record(path, kind)
        return path


def _write_aoi_outline(image, aoi_mask):
    return preview.draw_aoi(image, aoi_mask)


def _export_period(
    period: PeriodStudy,
    window: AnalysisWindow,
    aoi_mask: np.ndarray,
    processed_dir: Path,
    preview_dir: Path,
    registry: _OutputRegistry,
    *,
    indices: tuple[str, ...],
    max_count: int,
) -> None:
    stem = period.period_id
    date_tag = period.anchor_date
    tag = f"{stem}_{date_tag}"

    # Export exactly the bands the composite actually holds, in canonical
    # order. Studies whose selected indices need no SWIR never read B11, so
    # the composite does not contain it; exporting a fabricated band would
    # misrepresent what was processed.
    export_keys = tuple(
        key for key in BAND_EXPORT_ORDER if key in period.composite.bands
    )
    bands = np.stack(
        [period.composite.bands[key] for key in export_keys]
    )
    path = write_geotiff(
        processed_dir / f"{tag}_reflectance_composite.tif",
        bands,
        window,
        descriptions=tuple(BAND_DESCRIPTIONS[key] for key in export_keys),
        producer="HabitatShift M1",
    )
    period.raster_paths["reflectance"] = path
    registry.add(f"{stem}_reflectance_tif", path, "raster")

    valid_path = write_geotiff(
        processed_dir / f"{tag}_valid_mask.tif",
        period.composite.valid.astype(np.uint8),
        window,
        dtype="uint8",
        nodata=0,
        descriptions=("valid",),
        producer="HabitatShift M1",
    )
    period.raster_paths["valid_mask"] = valid_path
    registry.add(f"{stem}_valid_mask_tif", valid_path, "mask")

    count_path = write_geotiff(
        processed_dir / f"{tag}_observation_count.tif",
        period.composite.counts.astype(np.int16),
        window,
        dtype="int16",
        nodata=0,
        descriptions=("valid_observation_count",),
        producer="HabitatShift M1",
    )
    period.raster_paths["observation_count"] = count_path
    registry.add(f"{stem}_observation_count_tif", count_path, "mask")

    for key in indices:
        spec = INDEX_SPECS[key]
        index_path = write_geotiff(
            processed_dir / f"{tag}_{key}.tif",
            period.indices[key],
            window,
            descriptions=(key,),
            producer="HabitatShift M1",
        )
        period.raster_paths[key] = index_path
        registry.add(f"{stem}_{key}_tif", index_path, "raster")
        image = preview.index_to_png(period.indices[key], period.composite.valid, spec)
        image = _write_aoi_outline(image, aoi_mask)
        png = preview.save(image, preview_dir / f"{tag}_{key}.png")
        period.preview_paths[key] = png
        registry.add(f"{stem}_{key}_png", png, "preview")

    red = period.composite.bands[config.ASSET_RED]
    green = period.composite.bands[config.ASSET_GREEN]
    blue = period.composite.bands[config.ASSET_BLUE]
    nir = period.composite.bands[config.ASSET_NIR]
    true_stretch = preview.stretch_bounds((red, green, blue))
    false_stretch = preview.stretch_bounds((nir, red, green))
    period.stretch = {
        "true_colour": true_stretch.to_dict(),
        "false_colour": false_stretch.to_dict(),
    }

    true_png = preview.save(
        _write_aoi_outline(
            preview.rgb_to_png(
                red, green, blue, period.composite.valid, true_stretch, gamma=1.35
            ),
            aoi_mask,
        ),
        preview_dir / f"{tag}_true_colour.png",
    )
    period.preview_paths["true_colour"] = true_png
    registry.add(f"{stem}_true_colour_png", true_png, "preview")

    false_png = preview.save(
        _write_aoi_outline(
            preview.false_colour_png(
                nir, red, green, period.composite.valid, false_stretch, gamma=1.2
            ),
            aoi_mask,
        ),
        preview_dir / f"{tag}_false_colour.png",
    )
    period.preview_paths["false_colour"] = false_png
    registry.add(f"{stem}_false_colour_png", false_png, "preview")

    mask_png = preview.save(
        _write_aoi_outline(
            preview.coverage_to_png(period.composite.valid), aoi_mask
        ),
        preview_dir / f"{tag}_valid_mask.png",
    )
    period.preview_paths["valid_mask"] = mask_png
    registry.add(f"{stem}_valid_mask_png", mask_png, "preview")

    count_png = preview.save(
        _write_aoi_outline(
            preview.observation_count_to_png(
                period.composite.counts, period.composite.valid, maximum=max_count
            ),
            aoi_mask,
        ),
        preview_dir / f"{tag}_observation_count.png",
    )
    period.preview_paths["observation_count"] = count_png
    registry.add(f"{stem}_observation_count_png", count_png, "preview")


def _export_change(
    layer: ChangeLayer,
    window: AnalysisWindow,
    aoi_mask: np.ndarray,
    processed_dir: Path,
    preview_dir: Path,
    registry: _OutputRegistry,
) -> None:
    key = layer.index
    delta_path = write_geotiff(
        processed_dir / f"delta_{key}.tif",
        layer.delta,
        window,
        descriptions=("delta_later_minus_earlier",),
        producer="HabitatShift M1",
    )
    registry.add(f"delta_{key}_tif", delta_path, "raster")

    classes_path = write_geotiff(
        processed_dir / f"change_classes_{key}.tif",
        layer.classes,
        window,
        dtype="int8",
        nodata=CLASS_INVALID,
        descriptions=("change_class_-1_0_1",),
        producer="HabitatShift M1",
    )
    registry.add(f"change_classes_{key}_tif", classes_path, "mask")

    common_path = write_geotiff(
        processed_dir / f"common_valid_{key}.tif",
        layer.common.astype(np.uint8),
        window,
        dtype="uint8",
        nodata=0,
        descriptions=("common_valid",),
        producer="HabitatShift M1",
    )
    registry.add(f"common_valid_{key}_tif", common_path, "mask")

    delta_png = preview.save(
        _write_aoi_outline(
            preview.change_to_png(layer.delta, layer.common), aoi_mask
        ),
        preview_dir / f"delta_{key}.png",
    )
    registry.add(f"delta_{key}_png", delta_png, "preview")
    layer.summary["delta_preview"] = config.relative(delta_png)

    common_png = preview.save(
        _write_aoi_outline(
            preview.coverage_to_png(layer.common, layer.common), aoi_mask
        ),
        preview_dir / f"common_valid_{key}.png",
    )
    registry.add(f"common_valid_{key}_png", common_png, "preview")
    layer.summary["common_valid_preview"] = config.relative(common_png)
    layer.summary["delta_tif"] = config.relative(delta_path)
    layer.summary["change_classes_tif"] = config.relative(classes_path)
    layer.summary["common_valid_tif"] = config.relative(common_path)
    layer.summary["class_counts"] = dict(layer.class_counts)
    layer.summary["interpretation_guardrail"] = (
        "observed index difference at the stated threshold; not a land-cover "
        "classification, deforestation/wetland-loss verdict, building count or "
        "causal attribution"
    )


def _export_legends(
    preview_dir: Path,
    registry: _OutputRegistry,
    indices: tuple[str, ...],
) -> None:
    for key in indices:
        png = preview.index_legend(preview_dir / f"{key}_legend.png", key)
        registry.add(f"{key}_legend_png", png, "legend")
        registry.add(f"{key}_legend_json", png.with_suffix(".json"), "legend")
    change_png = preview.change_legend(preview_dir / "change_legend.png")
    registry.add("change_legend_png", change_png, "legend")
    registry.add("change_legend_json", change_png.with_suffix(".json"), "legend")
    count_png = preview.observation_count_legend(
        preview_dir / "observation_count_legend.png"
    )
    registry.add("observation_count_legend_png", count_png, "legend")
    registry.add(
        "observation_count_legend_json", count_png.with_suffix(".json"), "legend"
    )


# --------------------------------------------------------------------------- #
# Stage 6: independent verification of written artefacts
# --------------------------------------------------------------------------- #
def _check(condition: bool, name: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"check": name, "passed": bool(condition), "details": details}


def _grid_check(path: Path, window: AnalysisWindow) -> dict[str, Any]:
    with rasterio.open(path) as src:
        shape_ok = (src.height, src.width) == window.shape
        crs_ok = src.crs is not None and src.crs.to_string().upper() == window.crs.upper()
        transform_ok = bool(
            np.allclose(
                np.array(src.transform)[:6],
                np.array(window.transform)[:6],
                rtol=0.0,
                atol=1e-6,
            )
        )
        tag_ok = src.tags().get("grid_signature") == window.signature()
    return _check(
        shape_ok and crs_ok and transform_ok and tag_ok,
        "grid_georeferencing",
        {
            "path": config.relative(path),
            "shape_matches": shape_ok,
            "crs_matches": crs_ok,
            "transform_matches": transform_ok,
            "grid_signature_tag_matches": tag_ok,
        },
    )


def _read_band_map(path: Path) -> dict[str, np.ndarray]:
    with rasterio.open(path) as src:
        return {
            description: src.read(index)
            for index, description in enumerate(src.descriptions, start=1)
        }


def _sample_indices(valid: np.ndarray, size: int = VERIFY_SAMPLE_SIZE) -> np.ndarray:
    flat = np.flatnonzero(valid.ravel())
    if flat.size == 0:
        return flat
    rng = np.random.default_rng(VERIFY_SEED)
    return rng.choice(flat, size=min(size, flat.size), replace=False)


def _verify_index_recompute(
    period: PeriodStudy,
    index_key: str,
    window: AnalysisWindow,
) -> dict[str, Any]:
    band_path = period.raster_paths["reflectance"]
    index_path = period.raster_paths[index_key]
    bands = _read_band_map(band_path)
    spec = INDEX_SPECS[index_key]
    first = bands[BAND_DESCRIPTIONS[spec.bands[0]]].ravel()
    second = bands[BAND_DESCRIPTIONS[spec.bands[1]]].ravel()
    with rasterio.open(index_path) as src:
        stored = src.read(1).ravel()
    mask = period.composite.valid.ravel()
    sample = _sample_indices(period.composite.valid)
    if sample.size == 0:
        return _check(False, f"index_recompute_{period.period_id}_{index_key}", {
            "reason": "no valid pixels",
        })
    with np.errstate(invalid="ignore", divide="ignore"):
        recomputed = (first[sample] - second[sample]) / (
            first[sample] + second[sample]
        )
    diff = np.abs(recomputed - stored[sample])
    finite = np.isfinite(diff)
    max_diff = float(np.nanmax(diff)) if finite.any() else float("inf")
    masked_are_nan = bool(np.all(np.isnan(stored[~mask])))
    return _check(
        max_diff <= 1e-5 and masked_are_nan,
        f"index_recompute_{period.period_id}_{index_key}",
        {
            "sample_size": int(sample.size),
            "max_abs_difference": max_diff,
            "masked_pixels_are_nan": masked_are_nan,
            "native_resolution_m": spec.native_resolution_m,
        },
    )


def _verify_delta_recompute(
    earlier: PeriodStudy,
    later: PeriodStudy,
    layer: ChangeLayer,
) -> dict[str, Any]:
    with rasterio.open(earlier.raster_paths[layer.index]) as src:
        early = src.read(1)
    with rasterio.open(later.raster_paths[layer.index]) as src:
        late = src.read(1)
    delta_path = layer.summary["delta_tif"]
    with rasterio.open(config.PROJECT_ROOT / delta_path) as src:
        stored = src.read(1)
    common = np.isfinite(early) & np.isfinite(late)
    sample = _sample_indices(common)
    if sample.size == 0:
        return _check(False, f"delta_recompute_{layer.index}", {
            "reason": "no common-valid pixels",
        })
    recomputed = late.ravel()[sample] - early.ravel()[sample]
    diff = np.abs(recomputed - stored.ravel()[sample])
    max_diff = float(np.nanmax(diff)) if np.isfinite(diff).any() else float("inf")
    return _check(
        max_diff <= 1e-6,
        f"delta_recompute_{layer.index}",
        {
            "sample_size": int(sample.size),
            "max_abs_difference": max_diff,
        },
    )


def _verify_threshold_counts(
    layer: ChangeLayer,
    window: AnalysisWindow,
) -> dict[str, Any]:
    with rasterio.open(config.PROJECT_ROOT / layer.summary["delta_tif"]) as src:
        delta = src.read(1)
    threshold = float(layer.summary["primary_threshold"])
    finite = np.isfinite(delta)
    values = delta[finite]
    decrease = int(np.count_nonzero(values <= -threshold))
    increase = int(np.count_nonzero(values >= threshold))
    primary = layer.summary["primary"]
    checks = {
        "decrease_matches": decrease == int(primary["decrease_pixels"]),
        "increase_matches": increase == int(primary["increase_pixels"]),
        "valid_matches": int(values.size) == int(primary["valid_pixels"]),
        "areas_conserve": (
            int(primary["decrease_pixels"])
            + int(primary["increase_pixels"])
            + int(primary["stable_pixels"])
            == int(primary["valid_pixels"])
        ),
    }
    return _check(
        all(checks.values()),
        f"threshold_counts_{layer.index}",
        {"threshold": threshold, **checks},
    )


def _verify_counts(
    period: PeriodStudy, window: AnalysisWindow
) -> dict[str, Any]:
    with rasterio.open(period.raster_paths["observation_count"]) as src:
        counts = src.read(1)
    with rasterio.open(period.raster_paths["valid_mask"]) as src:
        valid = src.read(1).astype(bool)
    matches = bool(np.array_equal(counts > 0, valid))
    within = bool(
        counts[valid].size == 0
        or (
            int(counts[valid].min()) >= 1
            and int(counts[valid].max()) <= period.composite.observation_count
        )
    )
    return _check(
        matches and within,
        f"observation_count_{period.period_id}",
        {
            "valid_mask_matches_count_positive": matches,
            "counts_within_observation_bounds": within,
            "max_count": int(counts.max()),
        },
    )


def verify_exports(
    periods: dict[str, PeriodStudy],
    layers: dict[str, ChangeLayer],
    window: AnalysisWindow,
    *,
    indices: tuple[str, ...],
) -> dict[str, Any]:
    """Re-open every written artefact and check the numbers independently."""
    checks: list[dict[str, Any]] = []
    for period in periods.values():
        for name in ("reflectance", "valid_mask", "observation_count", *indices):
            checks.append(_grid_check(period.raster_paths[name], window))
        checks.append(_verify_counts(period, window))
        for key in indices:
            checks.append(_verify_index_recompute(period, key, window))
    for layer in layers.values():
        checks.append(
            _verify_delta_recompute(
                periods["earlier"], periods["later"], layer
            )
        )
        checks.append(_verify_threshold_counts(layer, window))
    return {
        "checks": checks,
        "all_passed": all(check["passed"] for check in checks),
        "check_count": len(checks),
        "failed_checks": [c["check"] for c in checks if not c["passed"]],
    }


# --------------------------------------------------------------------------- #
# Stage 7: area cross-check, summary, manifest
# --------------------------------------------------------------------------- #
def area_cross_check(
    aoi, window: AnalysisWindow, aoi_mask: np.ndarray
) -> dict[str, Any]:
    """Compare polygon, geodesic and rasterised area on the projected grid."""
    polygon_projected = float(aoi.area_km2())
    geodesic_m2, _ = Geod(ellps="WGS84").geometry_area_perimeter(aoi.polygon)
    geodesic_km2 = abs(float(geodesic_m2)) / 1_000_000.0
    raster_km2 = float(aoi_mask.sum() * window.pixel_area_m2 / 1_000_000.0)
    grid_km2 = float(window.height * window.width * window.pixel_area_m2 / 1_000_000.0)
    denominator = max(polygon_projected, 1e-12)
    return {
        "method": (
            "projected polygon area, independent geodesic area on the WGS84 "
            "ellipsoid, and rasterised pixel-count area on the analysis grid"
        ),
        "analysis_crs": window.crs,
        "pixel_area_m2": window.pixel_area_m2,
        "aoi_polygon_projected_km2": round(polygon_projected, 6),
        "aoi_polygon_geodesic_km2": round(geodesic_km2, 6),
        "aoi_raster_km2": round(raster_km2, 6),
        "grid_extent_km2": round(grid_km2, 6),
        "geodesic_vs_projected_relative_difference": round(
            abs(geodesic_km2 - polygon_projected) / denominator, 8
        ),
        "raster_vs_projected_relative_difference": round(
            abs(raster_km2 - polygon_projected) / denominator, 8
        ),
        "note": (
            "the raster area differs from the polygon area by boundary "
            "rasterisation only; hectares and km2 are converted from projected "
            "square metres, not from degrees"
        ),
    }


def _generated_limitations(
    periods: dict[str, PeriodStudy],
    layers: dict[str, ChangeLayer],
    cfg: StudyConfig,
) -> list[str]:
    limits: list[str] = []
    for period in periods.values():
        if period.composite.observation_count < cfg.max_observations:
            limits.append(
                f"{period.period_id}: only {period.composite.observation_count} "
                f"usable observation(s) contributed to the composite "
                f"(requested up to {cfg.max_observations}); the two-scene "
                "baseline is preserved rather than extrapolated."
            )
        if not period.selection.get("within_anchor_window", True):
            limits.append(
                f"{period.period_id}: no usable observation fell within "
                f"+/-{period.spec.max_offset_days} days of the anchor; the "
                "nearest usable acquisition was used and the seasonal offset is "
                "reported."
            )
    upsampled = [
        key
        for key in cfg.indices
        if INDEX_SPECS[key].upsampled_to(cfg.resolution_m)
    ]
    if upsampled:
        limits.append(
            "The following indices use 20 m SWIR bands resampled to the "
            f"{cfg.resolution_m:g} m analysis grid and contain no genuine "
            f"{cfg.resolution_m:g} m SWIR detail: "
            + ", ".join(sorted(upsampled))
            + "."
        )
    limits.extend(
        [
            "Composites are robust within-period summaries of a few "
            "observations, not a dense time series; inter-annual change is "
            "represented by two period composites only.",
            "Index differences are candidate spectral signals. They are not "
            "verified deforestation, wetland loss, construction, glacier damage "
            "or any other causal land-cover label.",
            "Cloud, shadow and saturated-pixel exclusion relies on the provider "
            "SCL product; terrain shadow is not independently re-derived.",
            "Surface reflectance is the provider L2A product; no independent "
            "atmospheric correction is performed.",
            "Areas are planimetric on the documented projected grid; UTM scale "
            "distortion at this AOI is small but nonzero.",
        ]
    )
    if any(not layer.summary["suitable_for_comparison"] for layer in layers.values()):
        limits.append(
            "At least one index falls below the configured common-valid "
            "coverage threshold; its difference map is flagged unsuitable for "
            "comparison rather than being silently accepted."
        )
    return limits


def _period_payload(
    period: PeriodStudy, resolution: float, aoi_pixels: int
) -> dict[str, Any]:
    composite = period.composite
    aoi_denominator = max(int(aoi_pixels), 1)
    return {
        "period_id": period.period_id,
        "anchor_date": period.spec.anchor.isoformat(),
        "composite_method": composite.method,
        "min_observations": composite.min_observations,
        "observation_count": composite.observation_count,
        "observation_dates": composite.dates,
        "item_ids": composite.item_ids,
        "valid_pixels": composite.valid_pixels,
        "aoi_pixels": int(aoi_pixels),
        "valid_fraction": round(composite.valid_pixels / aoi_denominator, 6),
        "valid_fraction_of_grid": round(composite.valid_fraction, 6),
        "observation_count_stats": composite.count_stats(),
        "indices": period.index_payload(resolution),
        "anchor_single_observation": {
            "item_id": period.anchor_item_id,
            "date": period.anchor_date,
            "indices": {
                key: stats.to_dict() for key, stats in period.anchor_stats.items()
            },
            "note": (
                "single-observation reconstruction used only to compare the M1 "
                "composite against the M0 two-scene baseline; it is not the "
                "headline M1 result"
            ),
        },
        "selection": period.selection,
        "stretch": period.stretch,
        "previews": {
            name: config.relative(path)
            for name, path in period.preview_paths.items()
        },
    }


def _period_manifest_payload(
    period: PeriodStudy, resolution: float, aoi_pixels: int
) -> dict[str, Any]:
    payload = _period_payload(period, resolution, aoi_pixels)
    payload["observations"] = [
        observation.to_provenance() for observation in period.composite.observations
    ]
    payload["mask_policy"] = {
        observation.item_id: observation.mask_report.to_dict()
        for observation in period.composite.observations
    }
    payload["outputs"] = {
        name: config.relative(path) for name, path in period.raster_paths.items()
    }
    return payload


def _write_summary_csv(path: Path, summary: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["record", "index", "period", "key", "value"])
        for period in summary["periods"]:
            for key, block in period["indices"].items():
                stats = block["stats"]
                for field in (
                    "valid_count",
                    "total_count",
                    "valid_fraction",
                    "min",
                    "max",
                    "mean",
                    "std",
                ):
                    writer.writerow(
                        ["index_stats", key, period["period_id"], field, stats[field]]
                    )
                for quantile, value in stats["quantiles"].items():
                    writer.writerow(
                        ["index_quantile", key, period["period_id"], quantile, value]
                    )
        for key, block in summary["change"].items():
            writer.writerow(
                [
                    "change",
                    key,
                    "later_minus_earlier",
                    "common_valid_fraction_of_aoi",
                    block["common_valid_fraction_of_aoi"],
                ]
            )
            writer.writerow(
                ["change", key, "later_minus_earlier", "common_valid_pixels",
                 block["common_valid_pixels"]]
            )
            for field in ("min", "max", "mean", "std"):
                writer.writerow(
                    ["change_delta_stats", key, "later_minus_earlier", field,
                     block["delta_stats"][field]]
                )
            for quantile, value in block["delta_stats"]["quantiles"].items():
                writer.writerow(
                    ["change_delta_quantile", key, "later_minus_earlier",
                     quantile, value]
                )
            for threshold in block["thresholds"]:
                for field in (
                    "valid_pixels",
                    "decrease_pixels",
                    "increase_pixels",
                    "stable_pixels",
                    "decrease_area_ha",
                    "increase_area_ha",
                    "decrease_percent_of_common",
                    "increase_percent_of_common",
                ):
                    writer.writerow(
                        [
                            "threshold",
                            key,
                            "later_minus_earlier",
                            f"{threshold['threshold']}:{field}",
                            threshold[field],
                        ]
                    )
        for field, value in summary["area_cross_check"].items():
            if isinstance(value, (int, float)):
                writer.writerow(["area_cross_check", "", "", field, value])
    return path


# --------------------------------------------------------------------------- #
# Engine orchestration
# --------------------------------------------------------------------------- #
class M1Engine:
    """Run one configured M1 study end to end."""

    def __init__(
        self,
        cfg: StudyConfig,
        *,
        http: HttpSession | None = None,
        client: CatalogClient | None = None,
        offline: bool = False,
        cache_dir: Path | None = None,
        observation_cache_dir: Path | None = None,
    ) -> None:
        self.cfg = cfg
        self.aoi = cfg.aoi()
        self.window = analysis_window(self.aoi, cfg.resolution_m)
        self.aoi_mask = aoi_raster_mask(self.aoi, self.window)
        self.offline = offline
        self.http = http or HttpSession(
            cache_dir=cache_dir or config.CACHE_DIR, offline=offline
        )
        self.client = client or CatalogClient(
            self.http,
            required_assets=tuple(
                dict.fromkeys(config.SPECTRAL_ASSETS + (config.ASSET_SCL,))
            ),
        )
        self.observation_cache = ObservationCache(
            observation_cache_dir or config.OBSERVATION_CACHE_DIR
        )
        self.band_keys = tuple(
            sorted(set(required_bands(cfg.indices)) | {config.ASSET_BLUE})
        )
        missing = [
            key for key in self.band_keys if key not in config.SPECTRAL_ASSETS
        ]
        if missing:
            raise EngineError(f"unsupported spectral assets requested: {missing}")
        if self.window.height * self.window.width > config.MAX_WINDOW_PIXELS:
            raise EngineError(
                f"analysis window {self.window.shape} exceeds MAX_WINDOW_PIXELS"
            )
        self.status: dict[str, Any] = {}
        self.outputs = _OutputRegistry()

    # -- status ------------------------------------------------------------ #
    def _write_status(self, payload: dict[str, Any]) -> None:
        self.cfg.status_path.parent.mkdir(parents=True, exist_ok=True)
        self.cfg.status_path.write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        self.status = payload

    def _stage(self, name: str, fn):
        started = dt.datetime.now(dt.timezone.utc)
        LOGGER.info("stage: %s", name)
        try:
            result = fn()
        except Exception as exc:
            self.status.setdefault("stages", []).append(
                {
                    "stage": name,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "duration_seconds": round(
                        (dt.datetime.now(dt.timezone.utc) - started).total_seconds(),
                        3,
                    ),
                }
            )
            raise
        self.status.setdefault("stages", []).append(
            {
                "stage": name,
                "status": "ok",
                "duration_seconds": round(
                    (dt.datetime.now(dt.timezone.utc) - started).total_seconds(), 3
                ),
            }
        )
        self._write_status(self.status)
        return result

    # -- preparation ------------------------------------------------------- #
    def _prepare_dirs(self) -> None:
        for directory in (self.cfg.processed_dir, self.cfg.preview_dir):
            directory.mkdir(parents=True, exist_ok=True)
        # Remove only generated rasters/previews so stale layers from a previous
        # configuration can never be served next to this run's numbers.
        for path in self.cfg.processed_dir.glob("*.tif"):
            path.unlink()
        for path in self.cfg.processed_dir.glob("*.csv"):
            path.unlink()
        for path in self.cfg.preview_dir.glob("*.png"):
            path.unlink()
        for path in self.cfg.preview_dir.glob("*.json"):
            path.unlink()

    # -- search / selection ------------------------------------------------ #
    def _search_period(self, period_spec: PeriodSpec) -> tuple[list[SceneScore], dict[str, SceneCandidate], dict[str, Any]]:
        start = dt.datetime.combine(
            period_spec.search_start, dt.time.min, tzinfo=dt.timezone.utc
        )
        end = dt.datetime.combine(
            period_spec.search_end, dt.time.max, tzinfo=dt.timezone.utc
        )
        request = SearchRequest(
            aoi=self.aoi,
            start=start,
            end=end,
            max_cloud_cover=self.cfg.max_cloud_cover,
            limit=100,
            label=(
                f"{period_spec.period_id}:"
                f"{period_spec.search_start.isoformat()}.."
                f"{period_spec.search_end.isoformat()}"
            ),
        )
        result = self.client.search(request)
        scores = score_candidates(
            result.items,
            self.aoi,
            min_valid_fraction=self.cfg.min_scene_valid_fraction,
            max_measured=self.cfg.measurement_budget,
            cache_dir=config.SCL_MEASUREMENT_CACHE_DIR,
            offline=self.offline,
        )
        candidates = {candidate.item_id: candidate for candidate in result.items}
        search_record = {
            **result.to_dict(),
            "selection_policy": {
                "measurement_budget": self.cfg.measurement_budget,
                "decision_metric": "measured in-AOI SCL valid fraction",
                "usable_threshold": self.cfg.min_scene_valid_fraction,
                "anchor": period_spec.anchor.isoformat(),
                "max_offset_days": period_spec.max_offset_days,
                "max_observations": self.cfg.max_observations,
                "min_observations": self.cfg.min_observations,
                "one_observation_per_calendar_date": True,
                "unmeasured_candidates_are_unusable": True,
            },
            "scores": [score.to_dict() for score in scores],
        }
        return scores, candidates, search_record

    # -- main -------------------------------------------------------------- #
    def run(self) -> dict[str, Any]:
        started = dt.datetime.now(dt.timezone.utc)
        self._prepare_dirs()
        self._write_status(
            {
                "study_id": self.cfg.study_id,
                "experiment_id": self.cfg.experiment_id,
                "status": "running",
                "started_utc": started.isoformat(),
                "stages": [],
                "error": None,
            }
        )
        try:
            summary = self._run(started)
        except Exception as exc:
            failed = dict(self.status)
            failed.update(
                {
                    "status": "failed",
                    "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            self._write_status(failed)
            raise
        return summary

    def _run(self, started: dt.datetime) -> dict[str, Any]:
        collection_meta = self.client.load_collection()
        LOGGER.info(
            "collection %s verified on %s",
            self.client.collection, self.client.catalog_url,
        )

        search_manifest: dict[str, Any] = {}
        periods: dict[str, PeriodStudy] = {}
        chosen_ids: set[str] = set()

        def search_and_compose_all():
            for period_id in ("earlier", "later"):
                period_spec = self.cfg.periods[period_id]
                scores, candidates, search_record = self._search_period(period_spec)
                chosen, selection = select_period_observations(
                    scores,
                    candidates,
                    period_spec,
                    max_observations=self.cfg.max_observations,
                    min_observations=self.cfg.min_observations,
                )
                duplicate = chosen_ids.intersection(
                    score.item_id for score in chosen
                )
                if duplicate:
                    raise EngineError(
                        f"period {period_id!r} resolved to item(s) already used "
                        f"in the other period: {sorted(duplicate)}"
                    )
                chosen_ids.update(score.item_id for score in chosen)
                observations = [
                    read_observation(
                        candidates[score.item_id],
                        self.window,
                        self.aoi_mask,
                        self.band_keys,
                        period_id=period_id,
                        cache=self.observation_cache,
                        offline=self.offline,
                    )
                    for score in chosen
                ]
                period = compose_period(
                    observations,
                    period_spec,
                    self.cfg.indices,
                    method=self.cfg.composite_method,
                    min_observations=self.cfg.min_observations,
                )
                period.selection = selection
                search_record["selection"] = selection
                search_record["selected_observations"] = [
                    {
                        "item_id": obs.item_id,
                        "date": obs.date,
                        "scene_cloud_cover_percent": obs.candidate.cloud_cover,
                        "aoi_valid_fraction": round(
                            obs.mask_report.valid_fraction, 6
                        ),
                    }
                    for obs in observations
                ]
                search_manifest[period_id] = search_record
                periods[period_id] = period

        self._stage("search_select_read_composite", search_and_compose_all)

        earlier, later = periods["earlier"], periods["later"]
        aoi_pixels = int(self.aoi_mask.sum())
        layers = self._stage(
            "change_analysis",
            lambda: compute_change_layers(
                earlier,
                later,
                indices=self.cfg.indices,
                aoi_pixels=aoi_pixels,
                pixel_area_m2=self.window.pixel_area_m2,
                thresholds=self.cfg.thresholds,
                primary_threshold=self.cfg.primary_threshold,
                min_comparable_fraction=self.cfg.min_comparable_valid_fraction,
            ),
        )

        max_count = max(
            int(period.composite.counts.max()) for period in periods.values()
        )

        def export_all():
            for period in periods.values():
                _export_period(
                    period,
                    self.window,
                    self.aoi_mask,
                    self.cfg.processed_dir,
                    self.cfg.preview_dir,
                    self.outputs,
                    indices=self.cfg.indices,
                    max_count=max_count,
                )
            for layer in layers.values():
                _export_change(
                    layer,
                    self.window,
                    self.aoi_mask,
                    self.cfg.processed_dir,
                    self.cfg.preview_dir,
                    self.outputs,
                )
            _export_legends(self.cfg.preview_dir, self.outputs, self.cfg.indices)

        self._stage("export_rasters_previews", export_all)

        verification = self._stage(
            "verify_written_artefacts",
            lambda: verify_exports(
                periods, layers, self.window, indices=self.cfg.indices
            ),
        )
        areas = area_cross_check(self.aoi, self.window, self.aoi_mask)
        limitations = _generated_limitations(periods, layers, self.cfg)

        summary_payload, manifest_payload = self._build_payloads(
            periods,
            layers,
            search_manifest,
            collection_meta,
            verification,
            areas,
            limitations,
            started,
        )

        def write_documents():
            summary_path = self.cfg.processed_dir / "summary.json"
            summary_path.write_text(
                json.dumps(summary_payload, indent=2), encoding="utf-8"
            )
            csv_path = _write_summary_csv(
                self.cfg.processed_dir / "summary.csv", summary_payload
            )
            self.outputs.add("summary_json", summary_path, "summary")
            self.outputs.add("summary_csv", csv_path, "summary")
            manifest_payload["outputs"] = dict(self.outputs.records)
            builder = M1ManifestBuilder()
            builder.update(manifest_payload)
            builder.write(self.cfg.manifest_path)
            return summary_path

        self._stage("write_summary_manifest", write_documents)

        finished = dt.datetime.now(dt.timezone.utc)
        status = dict(self.status)
        status.update(
            {
                "status": "complete" if verification["all_passed"] else "verification_failed",
                "finished_utc": finished.isoformat(),
                "duration_seconds": round((finished - started).total_seconds(), 3),
                "error": None,
                "summary_path": config.relative(
                    self.cfg.processed_dir / "summary.json"
                ),
                "manifest_path": config.relative(self.cfg.manifest_path),
                "verification_all_passed": verification["all_passed"],
            }
        )
        self._write_status(status)
        return summary_payload

    # -- payload assembly -------------------------------------------------- #
    def _build_payloads(
        self,
        periods: dict[str, PeriodStudy],
        layers: dict[str, ChangeLayer],
        search_manifest: dict[str, Any],
        collection_meta: dict[str, Any],
        verification: dict[str, Any],
        areas: dict[str, Any],
        limitations: list[str],
        started: dt.datetime,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        study_meta = self.cfg.study_meta()
        generated = dt.datetime.now(dt.timezone.utc).isoformat()
        aoi_pixels = int(self.aoi_mask.sum())
        indices_payload = {
            key: INDEX_SPECS[key].to_dict(self.cfg.resolution_m)
            for key in self.cfg.indices
        }
        period_payloads = [
            _period_payload(periods[key], self.cfg.resolution_m, aoi_pixels)
            for key in ("earlier", "later")
        ]
        change_payload = {
            key: dict(layer.summary) for key, layer in layers.items()
        }

        common = {
            "schema": "habitatshift-m1-summary/1",
            "experiment_id": self.cfg.experiment_id,
            "study": study_meta,
            "aoi": {
                "geojson": self.aoi.to_geojson(),
                "bounds_4326": list(self.aoi.bounds_4326),
                "analysis_crs": self.window.crs,
                "area_km2": round(self.aoi.area_km2(), 6),
                "aoi_pixels": int(self.aoi_mask.sum()),
            },
            "grid": {
                **self.window.to_dict(),
                "pixel_area_m2": self.window.pixel_area_m2,
                "native_band_resolutions_m": {
                    key: config.EXPECTED_GSD[key] for key in self.band_keys
                },
            },
            "catalog": {
                "endpoint": self.client.catalog_url,
                "collection": self.client.collection,
                "provider": config.PROVIDER_NAME,
                "license": config.DATA_LICENSE,
                "collection_license": collection_meta.get("license"),
            },
            "periods": period_payloads,
            "indices": indices_payload,
            "change": change_payload,
            "area_cross_check": areas,
            "verification": {
                "all_passed": verification["all_passed"],
                "check_count": verification["check_count"],
                "failed_checks": verification["failed_checks"],
            },
            "limitations": list(dict.fromkeys(study_meta.get("limitations", []) + limitations)),
            "pipeline_version": config.M1_PIPELINE_VERSION,
            "generated_utc": generated,
            "attribution": config.ATTRIBUTION,
            "outputs": dict(self.outputs.records),
        }

        processing = {
            "pipeline_version": config.M1_PIPELINE_VERSION,
            "profile": config.M1_PROCESSING_PROFILE,
            "operations": [
                "STAC search per period with AOI polygon and bounded date range",
                "in-AOI SCL valid-fraction scoring under a measurement budget",
                "anchor-window observation selection, one scene per calendar date",
                "bounded COG window reads via WarpedVRT (bilinear reflectance, "
                "nearest SCL)",
                "per-item radiometry verification and DN->reflectance scaling",
                "AOI + SCL + finite-reflectance masking, no interpolation",
                "per-pixel temporal composite with valid-observation counts",
                "spectral index computation on composite reflectance",
                "shared-valid difference maps, candidate thresholds and projected "
                "areas",
                "georeferenced raster, preview, JSON/CSV and manifest export",
                "independent re-open and numerical verification of exports",
            ],
            "parameters": {
                "resolution_m": self.cfg.resolution_m,
                "indices": list(self.cfg.indices),
                "composite_method": self.cfg.composite_method,
                "composite_median_even_rule": (
                    "NumPy nanmedian: mean of the two central values when the "
                    "observation count is even"
                ),
                "max_observations": self.cfg.max_observations,
                "min_observations": self.cfg.min_observations,
                "anchor_max_offset_days": self.cfg.anchor_max_offset_days,
                "thresholds": list(self.cfg.thresholds),
                "primary_threshold": self.cfg.primary_threshold,
                "resampling_continuous": "bilinear",
                "resampling_categorical": "nearest",
                "scale": config.EXPECTED_SCALE,
                "offset_policy": {
                    "pre_04.00": config.NO_OFFSET,
                    "04.00_or_later_not_baked_in": config.BOA_ADD_OFFSET,
                    "04.00_or_later_baked_in": config.NO_OFFSET,
                    "rule": (
                        "apply raster:bands offset unless "
                        "earthsearch:boa_offset_applied=true"
                    ),
                },
                "nodata": config.EXPECTED_NODATA,
                "scl_accepted": list(config.SCL_VALID_CLASSES),
                "scl_rejected": list(config.SCL_ALWAYS_INVALID),
                "mask_policy": (
                    "valid = inside AOI AND SCL class accepted AND every fetched "
                    "reflectance band finite"
                ),
                "area_convention": (
                    "projected pixel area on the analysis grid; ha = m2/10000, "
                    "km2 = m2/1000000"
                ),
            },
        }

        manifest_payload = {
            "manifest_version": "m1-1.0",
            "generated_utc": generated,
            "experiment_id": self.cfg.experiment_id,
            "study": study_meta,
            "aoi": {
                "geojson": self.aoi.to_geojson(),
                "bounds_4326": list(self.aoi.bounds_4326),
                "crs": "EPSG:4326",
                "analysis_crs": self.window.crs,
                "area_km2": round(self.aoi.area_km2(), 6),
                "grid": {
                    **self.window.to_dict(),
                    "pixel_area_m2": self.window.pixel_area_m2,
                },
            },
            "grid": {
                **self.window.to_dict(),
                "pixel_area_m2": self.window.pixel_area_m2,
            },
            "catalog": common["catalog"],
            "periods": [
                _period_manifest_payload(
                    periods[key], self.cfg.resolution_m, aoi_pixels
                )
                for key in ("earlier", "later")
            ],
            "indices": indices_payload,
            "change": change_payload,
            "processing": processing,
            "search": search_manifest,
            "config": self.cfg.to_dict(),
            "area_cross_check": areas,
            "verification": verification,
            "software": config.software_versions(),
            "attribution": {
                "text": config.ATTRIBUTION,
                "license": config.DATA_LICENSE,
                "provider": config.PROVIDER_NAME,
                "access_date_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
            "limitations": common["limitations"],
            "outputs": dict(self.outputs.records),
            "http_requests": getattr(self.http, "request_count", 0),
            "bytes_downloaded": getattr(self.http, "bytes_downloaded", 0),
            "started_utc": started.isoformat(),
        }
        return common, manifest_payload


__all__ = [
    "ChangeLayer",
    "EngineError",
    "M1Engine",
    "ObservationCache",
    "ObservationCacheMiss",
    "PeriodStudy",
    "area_cross_check",
    "compose_period",
    "compute_change_layers",
    "read_observation",
    "select_period_observations",
    "verify_exports",
]
