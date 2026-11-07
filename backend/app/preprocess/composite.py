"""Temporal compositing on one analysis grid.

A period may contain several usable observations.  Compositing combines their
*reflectance* per pixel (median or mean) and records how many valid observations
contributed to every pixel.  Pixels below the configured minimum observation
count are invalid; nothing is interpolated across time or space.

Rules enforced here:

* every observation must be on the identical grid signature and shape;
* only observations with the same band set can be combined;
* a pixel contributes to a band only when that observation's valid mask is true
  there (AOI + SCL + finite reflectance);
* the composite is invalid wherever fewer than ``min_observations``
  observations contributed, so a two-observation period cannot masquerade as a
  fully observed one.
"""

from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass, field

import numpy as np

from ..acquisition.assets import Radiometry
from ..catalog.models import SceneCandidate
from ..preprocess.masks import MaskReport


class CompositeError(ValueError):
    """Raised when observations cannot be combined safely."""


@dataclass
class Observation:
    """One acquired scene read onto the common analysis grid."""

    period_id: str
    candidate: SceneCandidate
    reflectance: dict[str, np.ndarray]
    valid: np.ndarray
    mask_report: MaskReport
    radiometry: dict[str, Radiometry]
    grid_signature: str = ""
    radiometry_evidence: dict[str, object] = field(default_factory=dict)

    @property
    def item_id(self) -> str:
        return self.candidate.item_id

    @property
    def date(self) -> str:
        return self.candidate.date_str

    def to_provenance(self) -> dict[str, object]:
        return {
            "item_id": self.candidate.item_id,
            "acquisition_date": self.candidate.date_str,
            "acquisition_utc": self.candidate.acquisition_iso,
            "scene_cloud_cover_percent": self.candidate.cloud_cover,
            "processing_baseline": self.candidate.processing_baseline,
            "aoi_valid_fraction": round(self.mask_report.valid_fraction, 6),
            "grid_signature": self.grid_signature,
            "assets": {
                key: {
                    "href": asset.href,
                    "gsd_metres": asset.gsd,
                }
                for key, asset in self.candidate.assets.items()
                if key in self.reflectance
            },
            "radiometry": {
                key: record.to_dict() for key, record in self.radiometry.items()
            },
            "radiometry_evidence": dict(self.radiometry_evidence),
        }


@dataclass
class CompositeResult:
    """Per-pixel composite of one period plus its observation accounting."""

    period_id: str
    method: str
    min_observations: int
    bands: dict[str, np.ndarray]
    valid: np.ndarray
    counts: np.ndarray
    observations: list[Observation] = field(default_factory=list)

    @property
    def observation_count(self) -> int:
        return len(self.observations)

    @property
    def dates(self) -> list[str]:
        return [observation.date for observation in self.observations]

    @property
    def item_ids(self) -> list[str]:
        return [observation.item_id for observation in self.observations]

    @property
    def valid_pixels(self) -> int:
        return int(self.valid.sum())

    @property
    def valid_fraction(self) -> float:
        return 0.0 if self.valid.size == 0 else self.valid_pixels / self.valid.size

    def count_stats(self) -> dict[str, object]:
        values = self.counts[self.valid]
        if values.size == 0:
            return {"min": 0, "max": 0, "mean": 0.0, "median": 0.0}
        return {
            "min": int(values.min()),
            "max": int(values.max()),
            "mean": round(float(values.mean()), 6),
            "median": float(np.median(values)),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "period_id": self.period_id,
            "method": self.method,
            "min_observations": self.min_observations,
            "observation_count": self.observation_count,
            "observation_dates": self.dates,
            "item_ids": self.item_ids,
            "valid_pixels": self.valid_pixels,
            "valid_fraction": round(self.valid_fraction, 6),
            "observation_count_stats": self.count_stats(),
            "observations": [obs.to_provenance() for obs in self.observations],
        }


def _check_alignment(observations: list[Observation]) -> tuple[str, tuple[int, int]]:
    if not observations:
        raise CompositeError("cannot composite an empty observation list")
    first = observations[0]
    signature = first.grid_signature
    shape = first.valid.shape
    for observation in observations[1:]:
        if observation.grid_signature != signature:
            raise CompositeError(
                f"grid signature mismatch: {observation.grid_signature!r} != "
                f"{signature!r}"
            )
        if observation.valid.shape != shape:
            raise CompositeError(
                f"shape mismatch: {observation.valid.shape} != {shape}"
            )
        if set(observation.reflectance) != set(first.reflectance):
            raise CompositeError(
                f"band set mismatch: {sorted(observation.reflectance)} != "
                f"{sorted(first.reflectance)}"
            )
    return signature, shape


def composite_observations(
    observations: list[Observation],
    *,
    method: str = "median",
    min_observations: int = 1,
) -> CompositeResult:
    """Combine observations into one reflectance composite.

    ``method`` is ``"median"`` or ``"mean"``.  The median of an even number of
    observations is the mean of the two central values (NumPy behaviour),
    recorded here so the method is not mistaken for a lower/upper median.
    """
    if method not in {"median", "mean"}:
        raise CompositeError(f"unknown composite method {method!r}")
    signature, shape = _check_alignment(observations)
    min_observations = max(int(min_observations), 1)
    if min_observations > len(observations):
        raise CompositeError(
            f"min_observations={min_observations} exceeds "
            f"{len(observations)} acquired observation(s)"
        )

    counts = np.zeros(shape, dtype=np.int16)
    for observation in observations:
        counts += observation.valid.astype(np.int16)
    valid = counts >= min_observations

    band_keys = sorted(observations[0].reflectance)
    bands: dict[str, np.ndarray] = {}
    for key in band_keys:
        stack = np.stack(
            [
                np.where(observation.valid, observation.reflectance[key], np.nan)
                for observation in observations
            ]
        )
        with np.errstate(invalid="ignore"):
            # Pixels with no valid observation are all-NaN slices by design;
            # the aggregate stays NaN and is masked below.  Silence only that
            # expected warning rather than hiding genuine numeric warnings.
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="All-NaN slice encountered", category=RuntimeWarning
                )
                if method == "median":
                    combined = np.nanmedian(stack, axis=0)
                else:
                    combined = np.nanmean(stack, axis=0)
        combined = combined.astype(np.float32)
        combined[~valid] = np.nan
        bands[key] = combined

    return CompositeResult(
        period_id=observations[0].period_id,
        method=method,
        min_observations=min_observations,
        bands=bands,
        valid=valid,
        counts=counts,
        observations=list(observations),
    )


#: Version of the radiometry resolution policy baked into observation cache
#: keys.  Bump when the DN -> reflectance policy changes so no record read
#: under an older policy can ever be silently reused.  The 2026-11-07 bump
#: covers the empirical physical-plausibility check added after the 2025
#: Earth Search reprocessing stored baseline-05.11 DNs without the baked
#: offset while their metadata still declared it.
RADIOMETRY_POLICY_VERSION = "2026-11-07-empirical-boa-1"


def observation_cache_key(
    item_id: str, grid_signature: str, band_keys: tuple[str, ...]
) -> str:
    """Stable cache key for one observation on one grid with one band set."""
    payload = "|".join(
        (
            RADIOMETRY_POLICY_VERSION,
            item_id,
            grid_signature,
            ",".join(sorted(band_keys)),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
