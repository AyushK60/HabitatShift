"""Minimal local data API for the M0 proof viewer.

Serves only artefacts that a real pipeline run produced: the manifest summary,
the PNG previews and the NDVI legend.  Nothing is computed here, so the viewer
cannot show a number the pipeline did not measure.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import config

app = FastAPI(
    title="HabitatShift M0 proof API",
    description="Serves the artifacts of the M0 Coringa comparison.",
    version=config.PIPELINE_VERSION,
)

FRONTEND_DIR = config.PROJECT_ROOT / "frontend"
SUMMARY_PATH = config.PROCESSED_DIR / "coringa_coastal" / "summary.json"
MANIFEST_PATH = config.MANIFEST_DIR / "m0_primary_study.json"


def _require(path: Path, kind: str) -> Path:
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"{kind} not found at {config.relative(path)}; run "
                f"`python scripts/build_primary_study.py` first"
            ),
        )
    return path


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "service": "habitatshift-m0",
        "pipeline_version": config.PIPELINE_VERSION,
        "summary_present": SUMMARY_PATH.exists(),
        "manifest_present": MANIFEST_PATH.exists(),
    }


@app.get("/api/study")
def study() -> JSONResponse:
    """Return the measured summary exactly as the pipeline wrote it."""
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


@app.get("/files/{kind}/{name}")
def asset(kind: str, name: str) -> FileResponse:
    """Serve a generated preview PNG by kind and file name."""
    roots = {
        "preview": config.PREVIEW_DIR / "coringa_coastal",
        "evidence": config.DOCS_DIR / "evidence" / "m0",
    }
    if kind not in roots:
        raise HTTPException(status_code=404, detail=f"unknown kind {kind!r}")
    # Guard against path traversal: only a bare file name is accepted.
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="name must be a bare file name")
    path = roots[kind] / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(path, media_type="image/png")


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
