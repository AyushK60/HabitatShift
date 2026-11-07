"""Frozen M0/M1 inputs consumed by the M2 experiments.

There is no network access in this module.  Every array comes from:

* the content-addressed observation cache written by the M1 engine;
* the exported M1 analysis rasters in ``data/processed/m1``;
* the frozen M0 delta raster in ``data/processed``.

All arrays are checked against the configured grid signature before use.  A
mismatch is a hard error, not something to repair silently.
"""

from __future__ import annotations

import hashlib
import re
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from .. import config
from ..indices.spectral import INDEX_SPECS
from .config import M2Config, M2ConfigError


class M2InputError(RuntimeError):
    """Raised when a frozen input is missing, misaligned or inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ObservationRecord:
    """One cached acquisition, already masked and pinned to the analysis grid."""

    item_id: str
    period_id: str
    date: str
    valid: np.ndarray
    reflectance: dict[str, np.ndarray]
    indices: dict[str, np.ndarray]
    meta: dict[str, Any]
    meta_sha256: str
    npz_sha256: str
    npz_path: Path

    @property
    def valid_pixels(self) -> int:
        return int(self.valid.sum())


@dataclass(frozen=True)
class ObservationSet:
    records: dict[str, ObservationRecord]
    earlier: tuple[str, ...]
    later: tuple[str, ...]
    cache_dir: Path

    def for_period(self, period_id: str) -> tuple[ObservationRecord, ...]:
        ids = self.earlier if period_id == "earlier" else self.later
        return tuple(self.records[item_id] for item_id in ids)

    def hashes(self) -> dict[str, str]:
        payload: dict[str, str] = {}
        for item_id in sorted(self.records):
            record = self.records[item_id]
            payload[f"{item_id}:json"] = record.meta_sha256
            payload[f"{item_id}:npz"] = record.npz_sha256
        return payload


@dataclass(frozen=True)
class M1Bundle:
    processed_dir: Path
    preview_dir: Path
    summary: dict[str, Any]
    summary_path: Path
    summary_sha256: str
    index_paths: dict[str, dict[str, Path]]
    valid_mask_paths: dict[str, Path]
    delta_paths: dict[str, Path]
    common_paths: dict[str, Path]
    raster_paths: dict[str, Path]

    def file_hashes(self, indices: tuple[str, ...]) -> dict[str, str]:
        payload: dict[str, str] = {"summary": self.summary_sha256}
        for period_id in ("earlier", "later"):
            payload[f"{period_id}:valid_mask"] = sha256_file(
                self.valid_mask_paths[period_id]
            )
            for index in indices:
                payload[f"{period_id}:{index}"] = sha256_file(
                    self.index_paths[period_id][index]
                )
        for index in indices:
            payload[f"delta:{index}"] = sha256_file(self.delta_paths[index])
            payload[f"common:{index}"] = sha256_file(self.common_paths[index])
        return payload


@dataclass(frozen=True)
class M0Bundle:
    processed_dir: Path
    summary: dict[str, Any]
    summary_path: Path
    summary_sha256: str
    delta: np.ndarray
    delta_valid: np.ndarray
    delta_path: Path
    delta_sha256: str
    earlier_path: Path
    later_path: Path
    earlier_valid_path: Path
    later_valid_path: Path

    def file_hashes(self) -> dict[str, str]:
        return {
            "summary": self.summary_sha256,
            "delta_ndvi": self.delta_sha256,
            "earlier_ndvi": sha256_file(self.earlier_path),
            "later_ndvi": sha256_file(self.later_path),
            "earlier_valid_mask": sha256_file(self.earlier_valid_path),
            "later_valid_mask": sha256_file(self.later_valid_path),
        }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise M2InputError(f"required input missing: {config.relative(path)}") from exc
    except ValueError as exc:
        raise M2InputError(f"invalid JSON in {config.relative(path)}: {exc}") from exc


def read_raster(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    try:
        with rasterio.open(path) as src:
            array = src.read(1)
            profile = {
                "crs": src.crs.to_string() if src.crs else None,
                "transform": list(src.transform)[:6],
                "width": src.width,
                "height": src.height,
                "dtype": str(src.dtypes[0]),
                "nodata": src.nodata,
            }
    except FileNotFoundError as exc:
        raise M2InputError(f"required raster missing: {config.relative(path)}") from exc
    except rasterio.errors.RasterioIOError as exc:
        raise M2InputError(f"cannot read raster {config.relative(path)}: {exc}") from exc
    return array, profile


def index_from_reflectance(
    reflectance: dict[str, np.ndarray], index: str
) -> np.ndarray:
    spec = INDEX_SPECS[index]
    missing = [key for key in spec.bands if key not in reflectance]
    if missing:
        raise M2InputError(
            f"index {index!r} needs bands {missing}; available {sorted(reflectance)}"
        )
    with np.errstate(divide="ignore", invalid="ignore"):
        values = spec.compute(reflectance)
    return values.astype(np.float32)


def _date_from_item_id(item_id: str) -> str:
    """Sentinel-2 item ids embed the acquisition date as YYYYMMDD."""
    match = re.search(r"_(\d{8})_", item_id)
    if not match:
        raise M2InputError(
            f"cannot derive acquisition date from item id {item_id!r}"
        )
    digits = match.group(1)
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"


def load_observations(config_: M2Config) -> ObservationSet:
    cache_dir = config.OBSERVATION_CACHE_DIR
    if not cache_dir.is_dir():
        raise M2InputError(
            f"observation cache missing: {config.relative(cache_dir)}; "
            "run the M1 study first"
        )
    expected_signature = config_.grid_signature
    records: dict[str, ObservationRecord] = {}
    for meta_path in sorted(cache_dir.glob("*.json")):
        meta = _read_json(meta_path)
        item_id = str(meta.get("item_id") or "")
        if not item_id:
            raise M2InputError(f"{meta_path.name}: missing item_id")
        if item_id in records:
            raise M2InputError(f"duplicate cached observation for {item_id}")
        if meta.get("grid_signature") != expected_signature:
            raise M2InputError(
                f"{item_id}: cache grid {meta.get('grid_signature')!r} != "
                f"experiment grid {expected_signature!r}"
            )
        band_keys = tuple(meta.get("band_keys") or ())
        npz_path = meta_path.with_suffix(".npz")
        if not npz_path.exists():
            raise M2InputError(f"{item_id}: cached array missing {npz_path.name}")
        try:
            with np.load(npz_path) as data:
                valid = data["valid"].astype(bool)
                reflectance = {
                    key: data[f"reflectance_{key}"].astype(np.float32)
                    for key in band_keys
                }
        except (OSError, KeyError, ValueError) as exc:
            raise M2InputError(f"{item_id}: cannot read cached arrays: {exc}") from exc
        if not band_keys:
            raise M2InputError(f"{item_id}: cached band list is empty")
        shape = valid.shape
        for key, array in reflectance.items():
            if array.shape != shape:
                raise M2InputError(
                    f"{item_id}: band {key} shape {array.shape} != valid {shape}"
                )
        indices = {
            index: index_from_reflectance(reflectance, index)
            for index in config_.indices
        }
        period_id = str(meta.get("period_id") or "")
        if period_id not in {"earlier", "later"}:
            raise M2InputError(
                f"{item_id}: period_id must be earlier/later, got {period_id!r}"
            )
        records[item_id] = ObservationRecord(
            item_id=item_id,
            period_id=period_id,
            date=_date_from_item_id(item_id),
            valid=valid,
            reflectance=reflectance,
            indices=indices,
            meta=meta,
            meta_sha256=sha256_file(meta_path),
            npz_sha256=sha256_file(npz_path),
            npz_path=npz_path,
        )

    earlier = tuple(
        sorted(
            (item for item, rec in records.items() if rec.period_id == "earlier"),
            key=lambda item: (records[item].date, item),
        )
    )
    later = tuple(
        sorted(
            (item for item, rec in records.items() if rec.period_id == "later"),
            key=lambda item: (records[item].date, item),
        )
    )
    if not earlier or not later:
        raise M2InputError(
            f"cache needs both periods; found {len(earlier)} earlier and "
            f"{len(later)} later observation(s)"
        )
    return ObservationSet(
        records=records, earlier=earlier, later=later, cache_dir=cache_dir
    )


def _output_entry(outputs: dict[str, Any], key: str) -> tuple[Path, str | None]:
    """Resolve one M1 summary output entry to (path, recorded sha256 or None).

    M1 records outputs either as plain relative paths or as
    ``{"kind": ..., "path": ..., "sha256": ...}`` descriptors.  A recorded
    hash is verified here so a silently modified raster cannot enter an M2 run.
    """
    entry = outputs.get(key)
    if isinstance(entry, dict):
        relative = entry.get("path")
        recorded = entry.get("sha256")
    else:
        relative = entry
        recorded = None
    if not relative or not isinstance(relative, str):
        raise M2InputError(f"M1 summary has no usable output path for {key}")
    path = config.PROJECT_ROOT / relative
    if not path.exists():
        raise M2InputError(f"M1 raster missing: {relative}")
    if recorded and sha256_file(path) != recorded:
        raise M2InputError(
            f"M1 raster hash mismatch for {relative}: summary records "
            f"{recorded} but the file hashes to {sha256_file(path)}"
        )
    return path, recorded


def load_m1_bundle(config_: M2Config, observations: ObservationSet) -> M1Bundle:
    processed_dir = config_.m1.processed_dir
    preview_dir = config_.m1.preview_dir
    summary_path = processed_dir / "summary.json"
    summary = _read_json(summary_path)
    if summary.get("schema") != "habitatshift-m1-summary/1":
        raise M2InputError(
            f"unexpected M1 summary schema {summary.get('schema')!r}"
        )
    grid_signature = (summary.get("grid") or {}).get("signature")
    if grid_signature != config_.grid_signature:
        raise M2InputError(
            f"M1 summary grid {grid_signature!r} != experiment grid "
            f"{config_.grid_signature!r}"
        )

    outputs = summary.get("outputs") or {}
    index_paths: dict[str, dict[str, Path]] = {"earlier": {}, "later": {}}
    valid_mask_paths: dict[str, Path] = {}
    for period in summary.get("periods") or []:
        period_id = period.get("period_id")
        if period_id not in index_paths:
            raise M2InputError(f"unexpected M1 period id {period_id!r}")
        for index in config_.indices:
            path, _ = _output_entry(outputs, f"{period_id}_{index}_tif")
            index_paths[period_id][index] = path
        mask_path, _ = _output_entry(outputs, f"{period_id}_valid_mask_tif")
        valid_mask_paths[period_id] = mask_path

    delta_paths: dict[str, Path] = {}
    common_paths: dict[str, Path] = {}
    for index in config_.indices:
        block = (summary.get("change") or {}).get(index)
        if not block:
            raise M2InputError(f"M1 summary has no change block for {index}")
        delta_paths[index] = config.PROJECT_ROOT / block["delta_tif"]
        common_paths[index] = config.PROJECT_ROOT / block["common_valid_tif"]

    # The cached observations and the M1 summary must name the same scenes,
    # and the derived acquisition dates must agree with the M1 record.
    summary_dates: dict[str, str] = {}
    for period in summary.get("periods") or []:
        for item_id, date in zip(
            period.get("item_ids") or [], period.get("observation_dates") or []
        ):
            summary_dates[str(item_id)] = str(date)
    summary_items = set(summary_dates)
    if summary_items != set(observations.records):
        raise M2InputError(
            "observation cache and M1 summary disagree on scene inventory: "
            f"{sorted(summary_items)} != {sorted(observations.records)}"
        )
    for item_id, date in summary_dates.items():
        cached_date = observations.records[item_id].date
        if cached_date != date:
            raise M2InputError(
                f"{item_id}: derived date {cached_date!r} != M1 summary date {date!r}"
            )

    raster_paths: dict[str, Path] = {}
    for key, entry in outputs.items():
        if isinstance(entry, dict):
            relative = entry.get("path")
        else:
            relative = entry
        if isinstance(relative, str) and relative.endswith(".tif"):
            raster_paths[key] = config.PROJECT_ROOT / relative

    return M1Bundle(
        processed_dir=processed_dir,
        preview_dir=preview_dir,
        summary=summary,
        summary_path=summary_path,
        summary_sha256=sha256_file(summary_path),
        index_paths=index_paths,
        valid_mask_paths=valid_mask_paths,
        delta_paths=delta_paths,
        common_paths=common_paths,
        raster_paths=raster_paths,
    )


def load_m0_bundle(config_: M2Config) -> M0Bundle:
    processed_dir = config.PROCESSED_DIR / config_.study_id
    summary_path = processed_dir / "summary.json"
    summary = _read_json(summary_path)
    delta_path = processed_dir / "delta_ndvi.tif"
    delta, profile = read_raster(delta_path)
    grid = summary.get("grid") or {}
    if (profile["width"], profile["height"]) != (grid.get("width"), grid.get("height")):
        raise M2InputError("M0 delta raster shape disagrees with its summary grid")
    if profile["crs"] != grid.get("crs"):
        raise M2InputError("M0 delta CRS disagrees with its summary grid")
    earlier_path = processed_dir / "earlier_2020-03-26_ndvi.tif"
    later_path = processed_dir / "later_2025-03-25_ndvi.tif"
    earlier_valid_path = processed_dir / "earlier_2020-03-26_valid_mask.tif"
    later_valid_path = processed_dir / "later_2025-03-25_valid_mask.tif"
    for path in (earlier_path, later_path, earlier_valid_path, later_valid_path):
        if not path.exists():
            raise M2InputError(f"M0 raster missing: {config.relative(path)}")
    return M0Bundle(
        processed_dir=processed_dir,
        summary=summary,
        summary_path=summary_path,
        summary_sha256=sha256_file(summary_path),
        delta=delta.astype(np.float64),
        delta_valid=np.isfinite(delta),
        delta_path=delta_path,
        delta_sha256=sha256_file(delta_path),
        earlier_path=earlier_path,
        later_path=later_path,
        earlier_valid_path=earlier_valid_path,
        later_valid_path=later_valid_path,
    )


def input_inventory(
    config_: M2Config,
    observations: ObservationSet,
    m1: M1Bundle,
    m0: M0Bundle,
) -> dict[str, Any]:
    return {
        "experiment_id": config_.experiment_id,
        "study_id": config_.study_id,
        "grid_signature": config_.grid_signature,
        "m1_config": {
            "path": config.relative(config_.m1_config_path),
            "sha256": sha256_file(config_.m1_config_path),
        },
        "m1_summary": {
            "path": config.relative(m1.summary_path),
            "sha256": m1.summary_sha256,
            "generated_utc": m1.summary.get("generated_utc"),
        },
        "m0_summary": {
            "path": config.relative(m0.summary_path),
            "sha256": m0.summary_sha256,
            "generated_utc": m0.summary.get("generated_utc"),
        },
        "observations": [
            {
                "item_id": record.item_id,
                "period_id": record.period_id,
                "date": record.date,
                "valid_pixels": record.valid_pixels,
                "meta_sha256": record.meta_sha256,
                "npz_sha256": record.npz_sha256,
            }
            for _, record in sorted(observations.records.items())
        ],
        "m1_rasters": m1.file_hashes(config_.indices),
        "m0_rasters": m0.file_hashes(),
    }
