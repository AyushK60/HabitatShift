"""Minimal local data API for the HabitatShift proof viewer.

M0 routes serve the original two-scene Coringa artefacts and are unchanged.
M1 routes serve the science-engine bundle (summary, status, layers, index
summaries, change statistics, provenance).  Nothing is computed here: every
number comes from a pipeline artefact, so the viewer cannot show a value the
engine did not measure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import config

app = FastAPI(
    title="HabitatShift proof API",
    description="Serves the M0 two-scene study and the M1 science-engine bundle.",
    version=config.M1_PIPELINE_VERSION,
)

FRONTEND_DIR = config.PROJECT_ROOT / "frontend"
SUMMARY_PATH = config.PROCESSED_DIR / "coringa_coastal" / "summary.json"
MANIFEST_PATH = config.MANIFEST_DIR / "m0_primary_study.json"

M1_ROOT = config.PROCESSED_M1_DIR
M1_PREVIEW_ROOT = config.PREVIEW_M1_DIR

_STUDY_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_SCOPES = ("processed", "previews")


def _scope_root(scope: str) -> Path:
    """Resolve a scope to its current root (not a path frozen at import time)."""
    return {"processed": M1_ROOT, "previews": M1_PREVIEW_ROOT}[scope]

_MEDIA_TYPES = {
    ".png": "image/png",
    ".json": "application/json",
    ".csv": "text/csv",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def _require(path: Path, kind: str, hint: str = "scripts/build_primary_study.py") -> Path:
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"{kind} not found at {config.relative(path)}; run `python {hint}` "
                f"first"
            ),
        )
    return path


def _safe_study_id(study_id: str) -> str:
    if not _STUDY_ID.fullmatch(study_id):
        raise HTTPException(status_code=400, detail="invalid study_id")
    return study_id


def _m1_dir(study_id: str) -> Path:
    directory = M1_ROOT / _safe_study_id(study_id)
    if not directory.is_dir():
        raise HTTPException(status_code=404, detail=f"unknown M1 study {study_id!r}")
    return directory


def _m1_summary_path(study_id: str) -> Path:
    return _m1_dir(study_id) / "summary.json"


def _m1_manifest_path(study_id: str) -> Path:
    return config.MANIFEST_DIR / f"m1_{_safe_study_id(study_id)}.json"


def _load_json(path: Path, kind: str, hint: str) -> dict:
    payload = json.loads(_require(path, kind, hint).read_text("utf-8"))
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail=f"{kind} is not a JSON object")
    return payload


def _m1_summary(study_id: str) -> dict:
    return _load_json(
        _m1_summary_path(study_id),
        "M1 study summary",
        "scripts/run_study.py --config studies/experiments/coringa_m1.yaml",
    )


def _m1_manifest(study_id: str) -> dict:
    return _load_json(
        _m1_manifest_path(study_id),
        "M1 manifest",
        "scripts/run_study.py --config studies/experiments/coringa_m1.yaml",
    )


def _available_m1_studies() -> list[str]:
    if not M1_ROOT.is_dir():
        return []
    return sorted(
        path.name
        for path in M1_ROOT.iterdir()
        if path.is_dir() and (path / "summary.json").exists()
    )


# --------------------------------------------------------------------------- #
# Health and M0 compatibility routes
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "service": "habitatshift-m0",
        "pipeline_version": config.PIPELINE_VERSION,
        "summary_present": SUMMARY_PATH.exists(),
        "manifest_present": MANIFEST_PATH.exists(),
        "m1_pipeline_version": config.M1_PIPELINE_VERSION,
        "m1_studies": _available_m1_studies(),
    }


@app.get("/api/study")
def study() -> JSONResponse:
    """Return the measured M0 summary exactly as the pipeline wrote it."""
    payload = json.loads(_require(SUMMARY_PATH, "study summary").read_text("utf-8"))
    return JSONResponse(payload)


@app.get("/api/manifest")
def manifest() -> JSONResponse:
    payload = json.loads(_require(MANIFEST_PATH, "manifest").read_text("utf-8"))
    return JSONResponse(payload)


@app.get("/api/legend")
def legend() -> JSONResponse:
    path = config.PREVIEW_DIR / "coringa_coastal" / "ndvi_legend.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="legend not generated yet")
    return JSONResponse(json.loads(path.read_text("utf-8")))


# --------------------------------------------------------------------------- #
# M1 science-engine routes
# --------------------------------------------------------------------------- #
@app.get("/api/m1/studies")
def m1_studies() -> dict[str, object]:
    """List M1 study bundles that can be served."""
    studies = []
    for study_id in _available_m1_studies():
        summary = json.loads(_m1_summary_path(study_id).read_text("utf-8"))
        status_path = M1_ROOT / study_id / "status.json"
        status = (
            json.loads(status_path.read_text("utf-8"))
            if status_path.exists()
            else {"status": "unknown"}
        )
        studies.append(
            {
                "study_id": study_id,
                "experiment_id": summary.get("experiment_id"),
                "title": (summary.get("study") or {}).get("title"),
                "generated_utc": summary.get("generated_utc"),
                "status": status.get("status"),
                "verification_passed": (
                    summary.get("verification") or {}
                ).get("all_passed"),
                "indices": sorted((summary.get("indices") or {}).keys()),
            }
        )
    return {"studies": studies}


@app.get("/api/m1/study/{study_id}")
def m1_study(study_id: str) -> JSONResponse:
    """Full M1 study summary (grid, periods, indices, change, verification)."""
    return JSONResponse(_m1_summary(study_id))


@app.get("/api/m1/study/{study_id}/status")
def m1_status(study_id: str) -> JSONResponse:
    directory = _m1_dir(study_id)
    path = directory / "status.json"
    if not path.exists():
        raise HTTPException(
            status_code=404, detail=f"no processing status for {study_id!r}"
        )
    return JSONResponse(json.loads(path.read_text("utf-8")))


@app.get("/api/m1/study/{study_id}/layers")
def m1_layers(study_id: str) -> dict[str, object]:
    """Available raster, preview, legend and summary artefacts."""
    summary = _m1_summary(study_id)
    layers = []
    preview_dir = (M1_PREVIEW_ROOT / study_id).resolve()
    processed_dir = (M1_ROOT / study_id).resolve()
    for name, record in sorted((summary.get("outputs") or {}).items()):
        relative = record.get("path")
        if not relative:
            continue
        path = (config.PROJECT_ROOT / relative).resolve()
        if preview_dir in path.parents:
            scope = "previews"
        elif processed_dir in path.parents:
            scope = "processed"
        else:
            continue
        layers.append(
            {
                "name": name,
                "kind": record.get("kind"),
                "scope": scope,
                "file": path.name,
                "url": f"/files/m1/{study_id}/{scope}/{path.name}",
                "bytes": record.get("bytes"),
                "sha256": record.get("sha256"),
                "content_type": _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
            }
        )
    return {
        "study_id": study_id,
        "grid": summary.get("grid"),
        "layers": layers,
    }


@app.get("/api/m1/study/{study_id}/indices")
def m1_indices(study_id: str) -> dict[str, object]:
    """Index definitions plus per-period statistics and change links."""
    summary = _m1_summary(study_id)
    periods = {
        period["period_id"]: {
            "observation_dates": period.get("observation_dates"),
            "observation_count": period.get("observation_count"),
            "indices": period.get("indices"),
            "previews": period.get("previews"),
        }
        for period in summary.get("periods") or []
    }
    return {
        "study_id": study_id,
        "indices": summary.get("indices"),
        "periods": periods,
        "change": summary.get("change"),
        "grid": summary.get("grid"),
    }


@app.get("/api/m1/study/{study_id}/change")
def m1_change(study_id: str) -> dict[str, object]:
    """Matched-valid difference statistics and threshold sensitivity."""
    summary = _m1_summary(study_id)
    return {
        "study_id": study_id,
        "change": summary.get("change"),
        "area_cross_check": summary.get("area_cross_check"),
        "limitations": summary.get("limitations"),
    }


@app.get("/api/m1/study/{study_id}/provenance")
def m1_provenance(study_id: str) -> JSONResponse:
    """Full reproducibility manifest: scenes, dates, grid, formulas, hashes."""
    return JSONResponse(_m1_manifest(study_id))


@app.get("/api/m1/study/{study_id}/manifest")
def m1_manifest_alias(study_id: str) -> JSONResponse:
    """Alias of :func:`m1_provenance` with an explicit name."""
    return JSONResponse(_m1_manifest(study_id))


# --------------------------------------------------------------------------- #
# Static artefacts
# --------------------------------------------------------------------------- #
@app.get("/files/{kind}/{name}")
def asset(kind: str, name: str) -> FileResponse:
    """Serve a generated M0 preview PNG by kind and file name."""
    roots = {
        "preview": config.PREVIEW_DIR / "coringa_coastal",
        "evidence": config.DOCS_DIR / "evidence" / "m0",
    }
    if kind not in roots:
        raise HTTPException(status_code=404, detail=f"unknown kind {kind!r}")
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="name must be a bare file name")
    path = roots[kind] / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(path, media_type=_MEDIA_TYPES.get(path.suffix.lower(), "image/png"))


@app.get("/files/m1/{study_id}/{scope}/{name}")
def m1_asset(study_id: str, scope: str, name: str) -> FileResponse:
    """Serve an M1 raster, preview, legend or summary file."""
    study_id = _safe_study_id(study_id)
    if scope not in _SCOPES:
        raise HTTPException(status_code=404, detail=f"unknown scope {scope!r}")
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="name must be a bare file name")
    root = _scope_root(scope) / study_id
    if not root.is_dir():
        raise HTTPException(status_code=404, detail=f"unknown M1 study {study_id!r}")
    path = root / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
    )


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
