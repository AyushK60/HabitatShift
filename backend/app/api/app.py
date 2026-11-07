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
G0_PREVIEW_ROOT = config.PREVIEW_G0_DIR

_STUDY_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_SCOPES = ("processed", "previews")


def _scope_root(scope: str) -> Path:
    """Resolve a scope to its current root (not a path frozen at import time)."""
    return {"processed": M1_ROOT, "previews": M1_PREVIEW_ROOT}[scope]

_MEDIA_TYPES = {
    ".png": "image/png",
    ".json": "application/json",
    ".csv": "text/csv",
    ".svg": "image/svg+xml",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}

EXPERIMENT_OUTPUT_ROOT = config.DATA_DIR / "experiments"


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


@app.get("/api/m1/study/{study_id}/presentation")
def m1_presentation(study_id: str) -> JSONResponse:
    """Presentation-only M2-G0 validity assets derived from the M1 masks.

    These assets do not modify the M1 summary, statistics or manifest.  The
    endpoint is explicit so a reviewer can tell presentation derivatives from
    scientific outputs.
    """
    directory = G0_PREVIEW_ROOT / _safe_study_id(study_id)
    path = directory / "quality.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"no G0 presentation assets for {study_id!r}; run "
                "`python scripts/build_g0_presentation.py --study "
                f"{study_id}`"
            ),
        )
    return JSONResponse(json.loads(path.read_text("utf-8")))


# --------------------------------------------------------------------------- #
# M2 research-experiment routes
# --------------------------------------------------------------------------- #
def _experiment_run_dirs(experiment_id: str) -> list[Path]:
    """All run directories of one experiment, newest first."""
    directory = EXPERIMENT_OUTPUT_ROOT / "m2" / _safe_experiment_id(experiment_id)
    if not directory.is_dir():
        return []
    return sorted(
        (run for run in directory.iterdir()
         if run.is_dir() and (run / "result.json").exists()),
        key=lambda run: run.name,
        reverse=True,
    )


def _safe_experiment_id(experiment_id: str) -> str:
    if not _STUDY_ID.fullmatch(experiment_id):
        raise HTTPException(status_code=400, detail="invalid experiment_id")
    return experiment_id


def _experiment_run(experiment_id: str, run_id: str) -> Path:
    directory = EXPERIMENT_OUTPUT_ROOT / "m2" / _safe_experiment_id(experiment_id)
    if not _STUDY_ID.fullmatch(run_id) or "_" not in run_id:
        # run ids look like 20261107T100530Z_d70f3978
        raise HTTPException(status_code=400, detail="invalid run_id")
    run_dir = directory / run_id
    if not run_dir.is_dir() or not (run_dir / "result.json").exists():
        raise HTTPException(status_code=404, detail=f"unknown run {run_id!r}")
    return run_dir


def _experiment_result(experiment_id: str, run_id: str) -> dict:
    return json.loads(
        (_experiment_run(experiment_id, run_id) / "result.json").read_text("utf-8")
    )


@app.get("/api/experiments")
def experiments() -> dict[str, object]:
    """List M2 experiments and their recorded runs."""
    root = EXPERIMENT_OUTPUT_ROOT / "m2"
    listing = []
    if root.is_dir():
        for directory in sorted(root.iterdir()):
            if not directory.is_dir():
                continue
            runs = []
            for run_dir in _experiment_run_dirs(directory.name):
                try:
                    result = json.loads(
                        (run_dir / "result.json").read_text("utf-8")
                    )
                except ValueError:
                    continue
                runs.append(
                    {
                        "run_id": result.get("run_id"),
                        "generated_utc": result.get("generated_utc"),
                        "fingerprint": result.get("fingerprint"),
                    }
                )
            if runs:
                listing.append({"experiment_id": directory.name, "runs": runs})
    return {"experiments": listing}


@app.get("/api/experiments/{experiment_id}/latest")
def experiment_latest(experiment_id: str) -> JSONResponse:
    """Summary of the newest recorded run, shaped for the viewer."""
    runs = _experiment_run_dirs(_safe_experiment_id(experiment_id))
    if not runs:
        raise HTTPException(
            status_code=404,
            detail=(
                f"no recorded runs for {experiment_id!r}; run "
                "`python scripts/run_experiment.py --config "
                "studies/experiments/coringa_m2.yaml`"
            ),
        )
    result = _experiment_result(experiment_id, runs[0].name)
    run_id = result["run_id"]
    file_base = f"/files/experiments/{experiment_id}/{run_id}"

    composite = [
        item for item in result["estimators"]
        if item["estimator_id"] == "composite_median"
    ]
    primary = result["config"]["primary_threshold"]
    estimators_at_primary = [
        {
            "estimator_id": item["estimator_id"],
            "family": item["family"],
            "label": item["label"],
            "index": item["index"],
            "common_valid_pixels": item["common_valid_pixels"],
            "common_valid_fraction_of_aoi": item["common_valid_fraction_of_aoi"],
            "delta_mean": item["delta_stats"]["mean"],
            "delta_std": item["delta_stats"]["std"],
            "decrease_area_ha": item["primary"]["decrease_area_ha"],
            "increase_area_ha": item["primary"]["increase_area_ha"],
            "decrease_percent_of_common": item["primary"]["decrease_percent_of_common"],
            "increase_percent_of_common": item["primary"]["increase_percent_of_common"],
            "earlier": item["sources"]["earlier"],
            "later": item["sources"]["later"],
        }
        for item in result["estimators"]
    ]
    charts = {}
    for chart in (
        "threshold_response",
        "delta_histogram_ndvi",
        "delta_histogram_ndwi",
        "delta_histogram_mndwi",
        "estimator_comparison_ndvi",
        "estimator_comparison_ndwi",
        "estimator_comparison_mndwi",
        "bootstrap_ndvi",
        "bootstrap_ndwi",
        "bootstrap_mndwi",
    ):
        if (runs[0] / "charts" / f"{chart}.svg").exists():
            charts[chart] = f"{file_base}/charts/{chart}.svg"
    return JSONResponse(
        {
            "schema": "habitatshift-m2-experiment-summary/1",
            "experiment_id": experiment_id,
            "study_id": result["study_id"],
            "run_id": run_id,
            "generated_utc": result["generated_utc"],
            "fingerprint": result["fingerprint"],
            "hypotheses": result["hypotheses"],
            "hypothesis_verdicts": result["hypothesis_verdicts"],
            "config": {
                "indices": result["config"]["indices"],
                "thresholds": result["config"]["thresholds"],
                "primary_threshold": primary,
                "estimator_families": result["config"]["estimator_families"],
                "block_size_px": result["config"]["block_size_px"],
                "bootstrap_iterations": result["config"]["bootstrap_iterations"],
                "bootstrap_seed": result["config"]["bootstrap_seed"],
                "m1_composite_method": result["config"]["m1_composite_method"],
            },
            "coverage": result["coverage"],
            "verification": result["verification"],
            "primary_threshold_rows": {
                item["index"]: item["thresholds"] for item in composite
            },
            "estimators_at_primary": estimators_at_primary,
            "temporal_robustness": result["temporal_robustness"],
            "bootstrap": result["uncertainty"]["block_bootstrap"],
            "cross_pipeline": result["cross_pipeline"],
            "guardrails": result["interpretation_guardrails"],
            "artifacts": {
                "result": f"{file_base}/result.json",
                "manifest": f"{file_base}/manifest.json",
                "estimator_thresholds_csv": f"{file_base}/estimator_thresholds.csv",
                "threshold_sensitivity_csv": f"{file_base}/threshold_sensitivity.csv",
                "charts": charts,
            },
        }
    )


@app.get("/api/experiments/{experiment_id}/run/{run_id}/result")
def experiment_result(experiment_id: str, run_id: str) -> JSONResponse:
    """Full recorded result.json of one run (verbatim, no recomputation)."""
    return JSONResponse(_experiment_result(experiment_id, run_id))


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


@app.get("/files/g0/{study_id}/{name}")
def g0_asset(study_id: str, name: str) -> FileResponse:
    """Serve a presentation-only M2-G0 validity preview or overlay."""
    study_id = _safe_study_id(study_id)
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="name must be a bare file name")
    root = G0_PREVIEW_ROOT / study_id
    if not root.is_dir():
        raise HTTPException(status_code=404, detail=f"unknown G0 study {study_id!r}")
    path = root / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
    )


@app.get("/files/experiments/{experiment_id}/{run_id}/{subpath:path}")
def experiment_asset(experiment_id: str, run_id: str, subpath: str) -> FileResponse:
    """Serve one recorded run artifact (result/manifest JSON, CSV, chart SVG)."""
    run_dir = _experiment_run(experiment_id, run_id)
    if not subpath or ".." in subpath or subpath.startswith(("/", "\\")):
        raise HTTPException(status_code=400, detail="invalid artifact path")
    path = (run_dir / subpath).resolve()
    if run_dir.resolve() not in path.parents:
        raise HTTPException(status_code=400, detail="artifact escapes run directory")
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
    )


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
