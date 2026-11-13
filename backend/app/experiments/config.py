"""Validated configuration for one M2 research experiment.

An M2 experiment is a *consumer* of frozen M1 inputs: the M1 experiment config,
its summary, its exported rasters and the observation cache.  This file
therefore validates both the M2-specific analysis plan and the existence of the
inputs it names, so a run cannot start from a half-specified plan.

The configuration separates:

* **hypotheses** - stated before the sweep is executed;
* **estimators** - which observation-selection families are compared;
* **thresholds** - the default required sweep plus any additional values;
* **uncertainty** - spatial block size, bootstrap iterations and seed;
* **labels** - candidate independent label roots and whether they are required.

Nothing about a particular study is hardcoded here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .. import config
from ..indices.spectral import INDEX_SPECS
from ..pipeline.config import ConfigError as M1ConfigError
from ..pipeline.config import StudyConfig, load_study_config


class M2ConfigError(ValueError):
    """Raised when an M2 experiment configuration is incomplete or invalid."""


#: The threshold sweep required by the M2 specification.  A config may add
#: further thresholds; it may only omit these when it explicitly sets
#: ``require_default_thresholds: false`` and documents why.
REQUIRED_THRESHOLDS: tuple[float, ...] = (0.05, 0.10, 0.15, 0.20, 0.25)

KNOWN_ESTIMATOR_FAMILIES: frozenset[str] = frozenset(
    {
        "composite",
        "anchor_single",
        "single_pairs",
        "leave_one_out",
        "m0_single_scene",
    }
)

DEFAULT_OUTPUT_ROOT = "data/experiments/m2"


def _resolve(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else config.PROJECT_ROOT / path


def _float_list(value: Any, *, name: str) -> tuple[float, ...]:
    if value is None:
        raise M2ConfigError(f"{name} is required")
    if not isinstance(value, (list, tuple)):
        raise M2ConfigError(f"{name} must be a list of numbers")
    try:
        items = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise M2ConfigError(f"{name} must contain only numbers") from exc
    if not items:
        raise M2ConfigError(f"{name} must not be empty")
    if any(not item > 0 for item in items):
        raise M2ConfigError(f"{name} values must be strictly positive")
    return items


def _string_list(value: Any, *, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise M2ConfigError(f"{name} must be a list of strings")
    items = tuple(str(item).strip() for item in value if str(item).strip())
    if len(set(items)) != len(items):
        raise M2ConfigError(f"{name} contains duplicate entries")
    return items


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class M2Config:
    """Every parameter required to reproduce one M2 run."""

    experiment_id: str
    study_id: str
    m1_config_path: Path
    m1: StudyConfig
    indices: tuple[str, ...]
    thresholds: tuple[float, ...]
    primary_threshold: float
    require_default_thresholds: bool
    estimator_families: tuple[str, ...]
    block_size_px: int
    bootstrap_iterations: int
    bootstrap_seed: int
    min_comparable_valid_fraction: float
    output_root: Path
    label_paths: tuple[Path, ...]
    hypotheses: tuple[str, ...]
    source_path: Path
    source_sha256: str
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def grid_signature(self) -> str:
        from ..preprocess.grid import analysis_window

        return analysis_window(self.m1.aoi(), self.m1.resolution_m).signature()

    @property
    def threshold_text(self) -> list[float]:
        return [round(value, 6) for value in self.thresholds]

    def canonical(self) -> dict[str, Any]:
        """Deterministic, path-normalised payload used for the run fingerprint."""
        return {
            "schema": "m2-config/1",
            "experiment_id": self.experiment_id,
            "study_id": self.study_id,
            "m1_config": config.relative(self.m1_config_path),
            "m1_experiment_id": self.m1.experiment_id,
            "indices": list(self.indices),
            "thresholds": [round(value, 6) for value in self.thresholds],
            "primary_threshold": round(self.primary_threshold, 6),
            "require_default_thresholds": self.require_default_thresholds,
            "estimator_families": list(self.estimator_families),
            "block_size_px": self.block_size_px,
            "bootstrap_iterations": self.bootstrap_iterations,
            "bootstrap_seed": self.bootstrap_seed,
            "min_comparable_valid_fraction": self.min_comparable_valid_fraction,
            "output_root": config.relative(self.output_root),
            "label_paths": [config.relative(path) for path in self.label_paths],
            "hypotheses": list(self.hypotheses),
            "source_sha256": self.source_sha256,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.canonical(),
            "source_path": config.relative(self.source_path),
            "m1_periods": {
                key: spec.to_dict() for key, spec in self.m1.periods.items()
            },
            "m1_composite_method": self.m1.composite_method,
            "m1_max_observations": self.m1.max_observations,
            "m1_min_observations": self.m1.min_observations,
            "grid_signature": self.grid_signature,
        }


def _validate_hypotheses(value: Any) -> tuple[str, ...]:
    items = _string_list(value, name="hypotheses")
    if len(items) < 2:
        raise M2ConfigError(
            "at least two hypotheses/questions are required, stated before the sweep"
        )
    return items


def load_m2_config(path: Path) -> M2Config:
    """Parse and validate one M2 experiment YAML file."""
    path = Path(path)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise M2ConfigError(f"M2 experiment config not found: {path}") from exc
    if not isinstance(payload, dict):
        raise M2ConfigError("M2 experiment config must be a YAML mapping")

    experiment_id = str(payload.get("experiment_id") or "").strip()
    study_id = str(payload.get("study_id") or "").strip()
    if not experiment_id:
        raise M2ConfigError("experiment_id is required")
    if not study_id:
        raise M2ConfigError("study_id is required")
    if experiment_id == study_id:
        raise M2ConfigError("experiment_id and study_id must differ")

    m1_config_path = _resolve(payload.get("m1_config") or "")
    if not str(payload.get("m1_config") or "").strip():
        raise M2ConfigError("m1_config is required")
    try:
        m1 = load_study_config(m1_config_path)
    except M1ConfigError as exc:
        raise M2ConfigError(f"invalid m1_config: {exc}") from exc
    if m1.study_id != study_id:
        raise M2ConfigError(
            f"m1_config study_id {m1.study_id!r} != experiments study_id {study_id!r}"
        )

    analysis = payload.get("analysis") or {}
    if not isinstance(analysis, dict):
        raise M2ConfigError("analysis must be a mapping")

    indices = tuple(
        str(item).strip().lower()
        for item in analysis.get("indices") or m1.indices
        if str(item).strip()
    )
    if not indices:
        raise M2ConfigError("analysis.indices must not be empty")
    unknown = [key for key in indices if key not in INDEX_SPECS]
    if unknown:
        raise M2ConfigError(
            f"unknown indices {unknown}; available: {sorted(INDEX_SPECS)}"
        )

    thresholds = _float_list(
        analysis.get("thresholds", list(REQUIRED_THRESHOLDS)),
        name="analysis.thresholds",
    )
    thresholds = tuple(sorted(set(round(value, 6) for value in thresholds)))
    require_default = analysis.get("require_default_thresholds", True)
    if not isinstance(require_default, bool):
        raise M2ConfigError("analysis.require_default_thresholds must be a boolean")
    if require_default:
        missing = [
            value
            for value in REQUIRED_THRESHOLDS
            if not any(abs(value - item) <= 1e-9 for item in thresholds)
        ]
        if missing:
            raise M2ConfigError(
                f"analysis.thresholds must include {list(REQUIRED_THRESHOLDS)}; "
                f"missing {missing}. Set require_default_thresholds: false to override."
            )

    primary = float(analysis.get("primary_threshold", 0.15))
    if primary <= 0:
        raise M2ConfigError("analysis.primary_threshold must be positive")
    if not any(abs(primary - item) <= 1e-9 for item in thresholds):
        raise M2ConfigError("analysis.primary_threshold must be one of the thresholds")

    families = tuple(
        str(item).strip().lower()
        for item in analysis.get("estimator_families")
        or ["composite", "anchor_single", "single_pairs", "leave_one_out"]
    )
    unknown_families = sorted(set(families) - KNOWN_ESTIMATOR_FAMILIES)
    if unknown_families:
        raise M2ConfigError(
            f"unknown estimator families {unknown_families}; "
            f"available: {sorted(KNOWN_ESTIMATOR_FAMILIES)}"
        )
    if len(set(families)) != len(families):
        raise M2ConfigError("analysis.estimator_families contains duplicates")
    if not families:
        raise M2ConfigError("analysis.estimator_families must not be empty")

    uncertainty = payload.get("uncertainty") or {}
    if not isinstance(uncertainty, dict):
        raise M2ConfigError("uncertainty must be a mapping")
    block_size = int(uncertainty.get("block_size_px", 15))
    if block_size < 5:
        raise M2ConfigError("uncertainty.block_size_px must be at least 5")
    iterations = int(uncertainty.get("bootstrap_iterations", 200))
    if iterations != 0 and iterations < 20:
        raise M2ConfigError(
            "uncertainty.bootstrap_iterations must be 0 (disabled) or at least 20"
        )
    seed = int(uncertainty.get("bootstrap_seed", 20260326))
    if seed < 0:
        raise M2ConfigError("uncertainty.bootstrap_seed must be non-negative")

    labels = payload.get("labels") or {}
    if not isinstance(labels, dict):
        raise M2ConfigError("labels must be a mapping")
    label_paths = tuple(
        _resolve(item) for item in _string_list(labels.get("paths"), name="labels.paths")
    )
    for label_path in label_paths:
        if not label_path.exists():
            raise M2ConfigError(
                f"labels.paths entry does not exist: {config.relative(label_path)}"
            )

    outputs = payload.get("outputs") or {}
    if not isinstance(outputs, dict):
        raise M2ConfigError("outputs must be a mapping")
    output_root = _resolve(outputs.get("root", DEFAULT_OUTPUT_ROOT))

    min_fraction = float(
        analysis.get(
            "min_comparable_valid_fraction",
            m1.min_comparable_valid_fraction,
        )
    )
    if not 0 < min_fraction <= 1:
        raise M2ConfigError("analysis.min_comparable_valid_fraction must be in (0, 1]")

    hypotheses = _validate_hypotheses(payload.get("hypotheses"))

    return M2Config(
        experiment_id=experiment_id,
        study_id=study_id,
        m1_config_path=m1_config_path,
        m1=m1,
        indices=indices,
        thresholds=thresholds,
        primary_threshold=round(primary, 6),
        require_default_thresholds=require_default,
        estimator_families=families,
        block_size_px=block_size,
        bootstrap_iterations=iterations,
        bootstrap_seed=seed,
        min_comparable_valid_fraction=min_fraction,
        output_root=output_root,
        label_paths=label_paths,
        hypotheses=hypotheses,
        source_path=path,
        source_sha256=_sha256(path),
        raw=payload,
    )
