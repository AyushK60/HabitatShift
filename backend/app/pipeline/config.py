"""Validated experiment configuration for the M1 study engine.

An M1 run is described by one YAML file (``studies/experiments/*.yaml``).  The
file is parsed into :class:`StudyConfig`, which is the *only* source of run
parameters.  Nothing about a particular run is hardcoded in the engine, so a
second study is a configuration change rather than a code change.

The configuration deliberately separates:

* the **study registry entry** (AOI geometry, title, limitations), which is
  reused unchanged from M0;
* the **experiment** (anchors, search windows, compositing, indices,
  thresholds), which is M1-specific.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .. import config
from ..indices.spectral import INDEX_SPECS
from ..preprocess.aoi import AOI, aoi_from_bounds


class ConfigError(ValueError):
    """Raised when an M1 experiment configuration is incomplete or invalid."""


_PERIOD_ORDER = ("earlier", "later")


def _as_date(value: Any, *, field_name: str) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ConfigError(f"{field_name}: {value!r} is not an ISO date") from exc


def _resolve(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else config.PROJECT_ROOT / path


@dataclass(frozen=True)
class PeriodSpec:
    """Search window and anchor date for one period of the comparison."""

    period_id: str
    anchor: dt.date
    search_start: dt.date
    search_end: dt.date
    max_offset_days: int

    @property
    def anchor_datetime(self) -> dt.datetime:
        return dt.datetime.combine(self.anchor, dt.time(), tzinfo=dt.timezone.utc)

    def offset_days(self, acquired: dt.datetime) -> int:
        return abs((acquired.date() - self.anchor).days)

    def to_dict(self) -> dict[str, object]:
        return {
            "period_id": self.period_id,
            "anchor_date": self.anchor.isoformat(),
            "search_start": self.search_start.isoformat(),
            "search_end": self.search_end.isoformat(),
            "max_offset_days": self.max_offset_days,
        }


@dataclass(frozen=True)
class StudyConfig:
    """Every parameter required to reproduce one M1 run."""

    experiment_id: str
    study_id: str
    registry_path: Path
    indices: tuple[str, ...]
    resolution_m: float
    composite_method: str
    max_observations: int
    min_observations: int
    max_cloud_cover: float
    min_scene_valid_fraction: float
    min_comparable_valid_fraction: float
    measurement_budget: int
    anchor_max_offset_days: int
    thresholds: tuple[float, ...]
    primary_threshold: float
    periods: dict[str, PeriodSpec]
    processed_dir: Path
    preview_dir: Path
    manifest_path: Path
    status_path: Path
    raw: dict[str, Any] = field(default_factory=dict)

    # -- derived ----------------------------------------------------------- #
    def load_registry_study(self) -> dict[str, Any]:
        try:
            registry = yaml.safe_load(
                self.registry_path.read_text(encoding="utf-8")
            ) or {}
        except FileNotFoundError as exc:
            raise ConfigError(
                f"study registry not found: {config.relative(self.registry_path)}"
            ) from exc
        for study in registry.get("studies") or []:
            if study.get("study_id") == self.study_id:
                return study
        raise ConfigError(
            f"study {self.study_id!r} not found in "
            f"{config.relative(self.registry_path)}"
        )

    def aoi(self) -> AOI:
        study = self.load_registry_study()
        bounds = (study.get("aoi") or {}).get("bounds") or {}
        try:
            return aoi_from_bounds(
                study_id=self.study_id,
                west=float(bounds["west"]),
                south=float(bounds["south"]),
                east=float(bounds["east"]),
                north=float(bounds["north"]),
                description=str((study.get("aoi") or {}).get("kind", "")),
                source=str((study.get("aoi") or {}).get("boundary_source", "")),
            )
        except KeyError as exc:
            raise ConfigError(
                f"study {self.study_id!r} has no complete aoi.bounds block"
            ) from exc

    def study_meta(self) -> dict[str, Any]:
        study = self.load_registry_study()
        return {
            "study_id": study.get("study_id", self.study_id),
            "title": study.get("title", self.study_id),
            "study_type": study.get("study_type", ""),
            "question": " ".join(str(study.get("question", "")).split()),
            "phenomena": list(study.get("phenomena") or []),
            "limitations": list(study.get("limitations") or []),
            "status": study.get("status", ""),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "study_id": self.study_id,
            "indices": list(self.indices),
            "resolution_m": self.resolution_m,
            "composite_method": self.composite_method,
            "max_observations": self.max_observations,
            "min_observations": self.min_observations,
            "max_cloud_cover_percent": self.max_cloud_cover,
            "min_scene_valid_fraction": self.min_scene_valid_fraction,
            "min_comparable_valid_fraction": self.min_comparable_valid_fraction,
            "measurement_budget": self.measurement_budget,
            "anchor_max_offset_days": self.anchor_max_offset_days,
            "thresholds": list(self.thresholds),
            "primary_threshold": self.primary_threshold,
            "periods": {k: v.to_dict() for k, v in self.periods.items()},
            "processed_dir": config.relative(self.processed_dir),
            "preview_dir": config.relative(self.preview_dir),
            "manifest_path": config.relative(self.manifest_path),
        }


def load_study_config(path: Path) -> StudyConfig:
    """Parse and validate one experiment YAML file."""
    path = Path(path)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise ConfigError(f"experiment config not found: {path}") from exc

    experiment_id = str(payload.get("experiment_id") or "").strip()
    study_id = str(payload.get("study_id") or "").strip()
    if not experiment_id:
        raise ConfigError("experiment_id is required")
    if not study_id:
        raise ConfigError("study_id is required")

    analysis = payload.get("analysis") or {}
    composite = analysis.get("composite") or {}
    selection = analysis.get("selection") or {}
    change = payload.get("change") or {}
    outputs = payload.get("outputs") or {}
    periods_raw = payload.get("periods") or {}
    if not isinstance(periods_raw, dict):
        raise ConfigError("periods must be a mapping keyed by earlier/later")

    indices = tuple(str(v).lower() for v in analysis.get("indices") or ["ndvi", "ndwi", "mndwi"])
    unknown = [key for key in indices if key not in INDEX_SPECS]
    if unknown:
        raise ConfigError(
            f"unknown indices {unknown}; available: {sorted(INDEX_SPECS)}"
        )
    if not indices:
        raise ConfigError("at least one index is required")

    method = str(composite.get("method", "median")).lower()
    if method not in {"median", "mean"}:
        raise ConfigError(f"composite method must be median or mean, got {method!r}")

    max_obs = int(composite.get("max_observations", 3))
    min_obs = int(composite.get("min_observations", 1))
    if max_obs < 1 or min_obs < 1 or min_obs > max_obs:
        raise ConfigError(
            f"invalid observation bounds: min={min_obs}, max={max_obs}"
        )

    max_offset = int(composite.get("anchor_max_offset_days", 30))
    if max_offset < 0:
        raise ConfigError("anchor_max_offset_days must be non-negative")

    thresholds = tuple(
        float(t) for t in change.get("thresholds") or config.M1_CHANGE_THRESHOLDS
    )
    if not thresholds or any(t <= 0 for t in thresholds):
        raise ConfigError("change thresholds must be positive")
    primary = float(
        change.get("primary_threshold", config.M1_PRIMARY_THRESHOLD)
    )
    if primary <= 0:
        raise ConfigError("primary_threshold must be positive")

    periods: dict[str, PeriodSpec] = {}
    for period_id in _PERIOD_ORDER:
        block = periods_raw.get(period_id)
        if not isinstance(block, dict):
            raise ConfigError(f"period {period_id!r} is required")
        anchor = _as_date(block.get("anchor"), field_name=f"periods.{period_id}.anchor")
        radius = int(block.get("search_radius_days", 45))
        start = _as_date(
            block.get("search_start") or (anchor - dt.timedelta(days=radius)),
            field_name=f"periods.{period_id}.search_start",
        )
        end = _as_date(
            block.get("search_end") or (anchor + dt.timedelta(days=radius)),
            field_name=f"periods.{period_id}.search_end",
        )
        if start >= end:
            raise ConfigError(f"period {period_id}: search_start must precede search_end")
        if not start <= anchor <= end:
            raise ConfigError(
                f"period {period_id}: anchor {anchor} outside search window"
            )
        periods[period_id] = PeriodSpec(
            period_id=period_id,
            anchor=anchor,
            search_start=start,
            search_end=end,
            max_offset_days=int(block.get("max_offset_days", max_offset)),
        )

    processed_dir = _resolve(
        outputs.get("processed_dir", f"data/processed/m1/{study_id}")
    )
    preview_dir = _resolve(outputs.get("preview_dir", f"data/previews/m1/{study_id}"))
    manifest_path = _resolve(
        outputs.get("manifest", f"data/manifests/m1_{study_id}.json")
    )
    status_path = _resolve(
        outputs.get("status", str(processed_dir / "status.json"))
    )

    return StudyConfig(
        experiment_id=experiment_id,
        study_id=study_id,
        registry_path=_resolve(payload.get("registry", "studies/registry.yaml")),
        indices=indices,
        resolution_m=float(analysis.get("resolution_m", config.GRID_RESOLUTION)),
        composite_method=method,
        max_observations=max_obs,
        min_observations=min_obs,
        max_cloud_cover=float(selection.get("max_cloud_cover", 60.0)),
        min_scene_valid_fraction=float(
            selection.get("min_scene_valid_fraction", config.MIN_SCENE_VALID_FRACTION)
        ),
        min_comparable_valid_fraction=float(
            selection.get(
                "min_comparable_valid_fraction",
                config.MIN_COMPARABLE_VALID_FRACTION,
            )
        ),
        measurement_budget=int(
            selection.get("measurement_budget", config.MAX_MEASURED_CANDIDATES)
        ),
        anchor_max_offset_days=max_offset,
        thresholds=tuple(sorted(set(thresholds))),
        primary_threshold=primary,
        periods=periods,
        processed_dir=processed_dir,
        preview_dir=preview_dir,
        manifest_path=manifest_path,
        status_path=status_path,
        raw=payload,
    )
