"""Bounded change analysis for a user-drawn box (the engine, unchanged, on a new AOI).

This is deliberately small and honest rather than a general service:

* one job at a time (a second request while one is running is refused, not queued);
* box area limited to MAX_AREA_KM2 so the analysis grid stays small and a run takes about a minute;
* a date window around each anchor, clipped to the catalogue's history and to today;
* the same audited engine, indices, masking, compositing and verification as the recorded studies,
  writing into a sandbox directory under data/custom_runs/ (never into recorded outputs);
* the most recent MAX_KEPT_RUNS runs are kept, older ones are deleted.

Nothing here weakens a limitation: a custom run is descriptive, has no reference data, and says so.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import re
import shutil
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import config
from ..preprocess.aoi import AOI, aoi_from_bounds
from . import engine as engine_mod
from .config import PeriodSpec, StudyConfig, load_study_config

MAX_AREA_KM2 = 6.0
MIN_AREA_KM2 = 0.2
MIN_GAP_DAYS = 90
SEARCH_RADIUS_DAYS = 30
MAX_KEPT_RUNS = 8
SENTINEL2_FIRST_DATE = dt.date(2015, 8, 1)
INDICES = ("ndvi", "ndwi")
RUNS_ROOT = config.PROJECT_ROOT / "data" / "custom_runs"
TEMPLATE_CONFIG = config.PROJECT_ROOT / "studies" / "experiments" / "kathmandu_m4.yaml"

_FILE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+\.(png|json)$")
_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


class CustomRunError(ValueError):
    """Invalid user input (HTTP 422)."""


class CustomRunBusy(RuntimeError):
    """Another run is in progress (HTTP 429)."""


@dataclass(frozen=True)
class CustomStudyConfig(StudyConfig):
    bounds: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def aoi(self) -> AOI:
        west, south, east, north = self.bounds
        return aoi_from_bounds(
            study_id=self.study_id, west=west, south=south, east=east, north=north,
            description="user-drawn box", source="user input (custom run)",
        )

    def study_meta(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "title": "Custom area (user-drawn box)",
            "study_type": "custom",
            "question": "Descriptive Sentinel-2 change between two seasons for a user-drawn box.",
            "phenomena": [],
            "limitations": [
                "Custom run: no reference data exist for this area, so nothing here is a validated measurement.",
                "Two seasonal composites only; seasonal, tidal and phenological differences can look like change.",
            ],
            "status": "custom",
        }


def _validate(
    west: float, south: float, east: float, north: float,
    earlier: dt.date, later: dt.date, today: dt.date,
) -> AOI:
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise CustomRunError("bounds must satisfy west<east and south<north within valid coordinates")
    if earlier < SENTINEL2_FIRST_DATE:
        raise CustomRunError(f"earlier date must be on or after {SENTINEL2_FIRST_DATE}")
    if later - earlier < dt.timedelta(days=MIN_GAP_DAYS):
        raise CustomRunError(f"the two dates must be at least {MIN_GAP_DAYS} days apart")
    if later > today - dt.timedelta(days=5):
        raise CustomRunError("later date must be at least 5 days in the past")
    from shapely.geometry import box

    from ..preprocess.aoi import _wgs84_area_km2

    approx = _wgs84_area_km2(box(west, south, east, north))
    if approx > MAX_AREA_KM2:
        raise CustomRunError(f"box area {approx:.2f} km2 is above the {MAX_AREA_KM2} km2 limit for custom runs")
    try:
        aoi = aoi_from_bounds(
            study_id="custom", west=west, south=south, east=east, north=north,
            description="user-drawn box", source="user input",
        )
    except Exception as exc:  # AOIError text is user-facing
        raise CustomRunError(str(exc)) from exc
    area = aoi.area_km2()
    if area < MIN_AREA_KM2:
        raise CustomRunError(f"box area {area:.2f} km2 is below the {MIN_AREA_KM2} km2 minimum")
    if area > MAX_AREA_KM2:
        raise CustomRunError(f"box area {area:.2f} km2 is above the {MAX_AREA_KM2} km2 limit for custom runs")
    return aoi


def _build_config(run_id: str, bounds, earlier: dt.date, later: dt.date, today: dt.date) -> CustomStudyConfig:
    base = load_study_config(TEMPLATE_CONFIG)
    root = RUNS_ROOT / run_id
    periods = {}
    for pid, anchor in (("earlier", earlier), ("later", later)):
        periods[pid] = PeriodSpec(
            period_id=pid, anchor=anchor,
            search_start=anchor - dt.timedelta(days=SEARCH_RADIUS_DAYS),
            search_end=min(anchor + dt.timedelta(days=SEARCH_RADIUS_DAYS), today),
            max_offset_days=SEARCH_RADIUS_DAYS,
        )
    values = {f.name: getattr(base, f.name) for f in dataclasses.fields(StudyConfig)}
    values.update(
        experiment_id=f"custom_{run_id}", study_id=f"custom_{run_id}", indices=INDICES,
        periods=periods, measurement_budget=16,
        processed_dir=root / "processed", preview_dir=root / "previews",
        manifest_path=root / "manifest.json", status_path=root / "processed" / "status.json",
    )
    return CustomStudyConfig(**values, bounds=tuple(bounds))


def _prune() -> None:
    if not RUNS_ROOT.exists():
        return
    runs = sorted((p for p in RUNS_ROOT.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in runs[MAX_KEPT_RUNS:]:
        shutil.rmtree(old, ignore_errors=True)
        _JOBS.pop(old.name, None)


def _worker(run_id: str, cfg: CustomStudyConfig) -> None:
    job = _JOBS[run_id]
    job["status"] = "running"
    try:
        eng = engine_mod.M1Engine(cfg)
        summary = eng.run()
        job["summary"] = _public_summary(run_id, cfg, summary)
        job["status"] = "done"
    except Exception as exc:  # surfaced verbatim, never swallowed
        job["status"] = "failed"
        job["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        job["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        _LOCK.release()


def _public_summary(run_id: str, cfg: CustomStudyConfig, summary: dict[str, Any]) -> dict[str, Any]:
    def preview(rel: str | None) -> str | None:
        return None if not rel else f"/api/aoi/run/{run_id}/file/{Path(rel).name}"

    periods = []
    for p in summary.get("periods", []):
        periods.append({
            "period_id": p["period_id"],
            "observation_dates": p.get("observation_dates"),
            "item_ids": p.get("item_ids"),
            "observation_count": p.get("observation_count"),
            "valid_fraction": p.get("valid_fraction"),
            "true_colour": preview((p.get("previews") or {}).get("true_colour")),
        })
    change = {}
    for key, block in (summary.get("change") or {}).items():
        primary = block.get("primary") or {}
        change[key] = {
            "label": block.get("label"),
            "threshold": block.get("primary_threshold"),
            "common_valid_area_ha": block.get("common_valid_area_ha"),
            "decrease_area_ha": primary.get("decrease_area_ha"),
            "increase_area_ha": primary.get("increase_area_ha"),
            "decrease_percent": primary.get("decrease_percent_of_common"),
            "increase_percent": primary.get("increase_percent_of_common"),
            "delta_preview": preview(block.get("delta_preview")),
            "suitable_for_comparison": block.get("suitable_for_comparison"),
            "guardrail": block.get("interpretation_guardrail"),
        }
    return {
        "run_id": run_id,
        "bounds_4326": list(cfg.bounds),
        "area_km2": (summary.get("aoi") or {}).get("area_km2"),
        "grid": summary.get("grid"),
        "periods": periods,
        "change": change,
        "limitations": summary.get("limitations", []),
        "verification_passed": (summary.get("verification") or {}).get("all_passed"),
    }


def start_run(
    *, west: float, south: float, east: float, north: float,
    earlier: dt.date, later: dt.date, today: dt.date | None = None,
) -> dict[str, Any]:
    today = today or dt.date.today()
    _validate(west, south, east, north, earlier, later, today)
    if not _LOCK.acquire(blocking=False):
        raise CustomRunBusy("another custom analysis is running; try again in a minute")
    try:
        key = f"{west:.5f},{south:.5f},{east:.5f},{north:.5f},{earlier},{later}"
        run_id = hashlib.sha256((key + uuid.uuid4().hex).encode()).hexdigest()[:12]
        cfg = _build_config(run_id, (west, south, east, north), earlier, later, today)
        _prune()
        _JOBS[run_id] = {
            "run_id": run_id, "status": "queued", "error": None,
            "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "summary": None,
            "status_path": str(cfg.status_path),
        }
        threading.Thread(target=_worker, args=(run_id, cfg), daemon=True).start()
    except Exception:
        _LOCK.release()
        raise
    return {"run_id": run_id, "status": "queued"}


def job_status(run_id: str) -> dict[str, Any]:
    job = _JOBS.get(run_id)
    if job is None:
        raise KeyError(run_id)
    stages: list[dict[str, Any]] = []
    try:
        stages = json.loads(Path(job["status_path"]).read_text("utf-8")).get("stages", [])
    except Exception:
        pass
    return {
        "run_id": run_id, "status": job["status"], "error": job["error"],
        "stages": [s["stage"] for s in stages if s.get("status") == "ok"],
        "summary": job["summary"] if job["status"] == "done" else None,
    }


def preview_path(run_id: str, name: str) -> Path:
    if run_id not in _JOBS or not _FILE_NAME.match(name):
        raise KeyError(name)
    root = (RUNS_ROOT / run_id / "previews").resolve()
    path = (root / name).resolve()
    if root not in path.parents or not path.is_file():
        raise KeyError(name)
    return path
