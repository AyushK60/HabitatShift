"""Build portable showcase bundles from processed study outputs (M4-G3/G4).

One bundle per study, written to ``frontend/public/studies/<study_id>/``:

* ``bundle.json``  - schema ``habitatshift-m4-bundle/1``: study metadata, AOI,
  per-experiment M1 summaries (periods, index stats, change sweeps), georeferenced
  grid placement, distilled chart series (from recorded experiment results —
  never recomputed), event context for the Himalayan investigations, quality
  information, limitations, interpretation guardrails, provenance and
  SHA-256 checksums.
* ``previews/*.png`` - copies of the georeferenced preview PNGs the map and
  inspector render.

The bundle is self-contained: the website can render a completed study with no
Python backend running.  Nothing here reprocesses imagery or recomputes a
scientific value; every number is copied from a stored artefact.

Usage:
    python scripts/build_showcase_bundles.py                # all studies
    python scripts/build_showcase_bundles.py --study chilika_wetland
    python scripts/build_showcase_bundles.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml                                                       # noqa: E402

from backend.app import config                                   # noqa: E402

LOGGER = logging.getLogger("build_showcase_bundles")

BUNDLE_SCHEMA = "habitatshift-m4-bundle/1"
BUNDLE_VERSION = "1"

#: study_id -> experiments to embed, in presentation order.
STUDY_EXPERIMENTS: dict[str, dict[str, Any]] = {
    "coringa_coastal": {
        "m1": ["coringa_m1"],
        "m2": "coringa_m2",
    },
    "chilika_wetland": {
        "m1": ["chilika_m4_dry", "chilika_m4_postmonsoon"],
        "labels": {
            "chilika_m4_dry": "Matched dry season (Feb 2020 vs Feb 2025)",
            "chilika_m4_postmonsoon": "Matched post-monsoon (Nov 2020 vs Nov 2025)",
        },
    },
    "western_ghats_forest": {"m1": ["western_ghats_m4"]},
    "himalaya_purepu_2025": {"m1": ["himalaya_purepu_2025_m4"]},
    "himalaya_langtang_2026": {"m1": ["himalaya_langtang_2026_m4"]},
    "kathmandu_urban": {"m1": ["kathmandu_m4"]},
}

#: Study-specific interpretation guardrails, embedded verbatim.  They state
#: what the recorded numbers can and cannot support; no values are hardcoded.
INTERPRETATION: dict[str, dict[str, Any]] = {
    "coringa_coastal": {
        "can_conclude": [
            "Masked NDVI/NDWI/MNDWI differences between seasonally matched 2020 and 2025 observations on one grid, with the shared-valid footprint stated.",
            "How the candidate-change area responds as the difference threshold tightens (threshold sweep).",
            "How much the estimate moves under single-pair versus composite estimators and leave-one-out resampling for this AOI and grid.",
        ],
        "cannot_conclude": [
            "Proven mangrove loss or gain, ecological causation, or tidal-stage effects.",
            "Any population-level confidence interval: the uncertainty recorded is resampling variability for this AOI and grid.",
        ],
    },
    "chilika_wetland": {
        "can_conclude": [
            "Candidate surface-water extent signals (NDWI/MNDWI threshold classes) for matched dry-season and matched post-monsoon pairs.",
            "That dry-season and post-monsoon signals must be read together: the pair-level difference between seasons bounds how much of any 2020-to-2025 change could be seasonal.",
            "Per-pixel observation support (how many valid acquisitions back each composite pixel).",
        ],
        "cannot_conclude": [
            "Permanent wetland loss or gain: water level, seasonality and turbidity dominate this site.",
            "Hydrological causes, discharge changes or any claim about the lagoon mouth.",
        ],
        "note": "The dry-season pair at this window is broadly similar between 2020 and 2025; seasonal amplitude at this particular window is modest because it sits over the main lagoon. Seasonal sensitivity is documented by comparing the two experiments, not by a single pair.",
    },
    "western_ghats_forest": {
        "can_conclude": [
            "Masked NDVI differences between matched dry-season observations (3-day day-of-year gap) on one grid.",
            "Whether candidate change areas are spatially associated with terrain: the bundle embeds Copernicus DEM elevation context for the same window.",
            "Threshold sensitivity of the candidate-change area.",
        ],
        "cannot_conclude": [
            "Deforestation: an NDVI decrease is a candidate spectral signal only.",
            "Separation of plantation from natural forest, or of dry-season leaf-drop from disturbance.",
        ],
    },
    "himalaya_purepu_2025": {
        "can_conclude": [
            "Which optical observations exist before and after the 8 July 2025 event, at what validity, and where the observation gaps are.",
            "Candidate snow/ice and surface-water index changes between April 2025 (before the monsoon) and October 2025 (after the monsoon) under an explicit seasonal caveat.",
        ],
        "cannot_conclude": [
            "Discharged water volume, flood depth or discharge: lake surface area is not discharged-water volume.",
            "The causal mechanism, or any casualty/damage claim from satellite differencing.",
            "A clean immediate before/after pair: the only usable post-event July observation is the same-day pass at 63.2% validity.",
        ],
        "note": "Feasibility verdict PARTIAL (docs/M4_FEASIBILITY.md): presented as evidence under constraint.",
    },
    "himalaya_langtang_2026": {
        "can_conclude": [
            "Which optical observations bracket the 26 August 2026 event and at what validity (a usable pair 14 days before and 33 days after).",
            "Candidate optical change at the source zone between those dates, with snow-cover evolution recorded as the dominant seasonal confounder.",
        ],
        "cannot_conclude": [
            "Debris volume, flood routing or discharge.",
            "Any InSAR deformation claim: radar-based findings in external research remain external, cited literature.",
            "A conventional-GLOF description: this investigation is a rock-ice collapse with a cascading debris-laden flood, a distinct mechanism.",
        ],
    },
    "kathmandu_urban": {
        "can_conclude": [
            "Candidate built-up spectral signal (NDBI) and vegetation/water context between matched-season 2020 and 2025 observations.",
            "Where the built-up signal and the vegetation signal disagree — the inspection panel for bare-soil, construction-site and riverbed confounders.",
        ],
        "cannot_conclude": [
            "Buildings constructed, impervious area in hectares, or population change: NDBI is a spectral feature, not a building detector.",
            "Any classifier accuracy: no independent reference labels exist for this AOI (docs/M2_LABEL_FEASIBILITY.md), so the supervised path stays blocked.",
        ],
    },
}

ATTRIBUTION = (
    "Contains modified Copernicus Sentinel data (2020-2026), processed by ESA; "
    "L2A products distributed by the Element 84 Earth Search STAC catalogue "
    "(AWS Open Data). DEM: Copernicus DEM GLO-30 (ESA/DLR) where included. "
    "Event context: NDRRMA (2025) and ICIMOD (2026) situation reporting, cited "
    "as external literature, not project measurements."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_registry() -> dict[str, dict[str, Any]]:
    registry = yaml.safe_load(
        (config.STUDIES_DIR / "registry.yaml").read_text(encoding="utf-8")
    )
    return {study["study_id"]: study for study in registry["studies"]}


def load_m1_summary(experiment_id: str) -> dict[str, Any]:
    """Load the processed summary of one M1 experiment by its config file."""
    cfg_path = config.STUDIES_DIR / "experiments" / f"{experiment_id}.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    processed = config.PROJECT_ROOT / cfg["outputs"]["processed_dir"]
    summary_path = processed / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "experiment_id": experiment_id,
        "config_path": str(cfg_path.relative_to(config.PROJECT_ROOT)).replace("\\", "/"),
        "config_sha256": sha256_file(cfg_path),
        "summary_sha256": sha256_file(summary_path),
        "label": (STUDY_EXPERIMENTS.get(summary["study"]["study_id"], {}).get("labels") or {}).get(
            experiment_id, None
        ),
        "summary": summary,
    }


def load_findings(experiment_id: str) -> dict[str, Any] | None:
    """Load the generated What-Changed findings for one experiment (M4-R1)."""
    path = config.PROJECT_ROOT / "data" / "findings" / f"{experiment_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def raster_georef(raster_path: Path) -> dict[str, Any]:
    """Georeferenced placement of one exported raster, in WGS84 lon/lat."""
    import rasterio
    from rasterio.warp import transform_bounds

    with rasterio.open(raster_path) as src:
        left, bottom, right, top = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        return {
            "native_crs": src.crs.to_string(),
            "native_bounds": [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top],
            "native_transform": list(src.transform)[:6],
            "shape": [src.height, src.width],
            "resolution_m": [abs(src.transform.a), abs(src.transform.e)],
            "nodata": src.nodata,
            "lonlat_bounds": [left, bottom, right, top],
            "lonlat_corners": {
                "upper_left": [left, top],
                "upper_right": [right, top],
                "lower_left": [left, bottom],
                "lower_right": [right, bottom],
            },
        }


def collect_previews(summaries: list[dict[str, Any]], out_dir: Path) -> dict[str, dict[str, Any]]:
    """Copy every referenced preview PNG into the bundle, flat-named.

    Returns the asset table mapping "<experiment_id>/<preview_key>" to the
    bundle-relative path plus checksum.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, dict[str, Any]] = {}
    for entry in summaries:
        experiment_id = entry["experiment_id"]
        periods = entry["summary"]["periods"]
        relative_paths: list[str] = []
        for period in periods:
            relative_paths.extend(period.get("previews", {}).values())
        for block in entry["summary"]["change"].values():
            for key in ("delta_preview", "common_valid_preview"):
                if block.get(key):
                    relative_paths.append(block[key])
        # Legends are shared per experiment; include any legend PNG present.
        preview_root = config.PROJECT_ROOT / periods[0]["previews"]["true_colour"]
        for legend in sorted(preview_root.parent.glob("*legend.png")):
            relative_paths.append(str(legend).replace("\\", "/"))
        for relative in sorted(set(relative_paths)):
            source = config.PROJECT_ROOT / relative
            if not source.exists():
                LOGGER.warning("missing preview artefact: %s", relative)
                continue
            flat = f"{experiment_id}__{source.name}"
            shutil.copyfile(source, out_dir / flat)
            assets[f"{experiment_id}/{source.name}"] = {
                "path": f"previews/{flat}",
                "sha256": sha256_file(out_dir / flat),
            }
    return assets


def distill_threshold_series(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Recorded threshold sweep per index, straight from the change blocks."""
    series = []
    for key, block in summary["change"].items():
        sweep = block.get("thresholds") or []
        points = [
            {
                "threshold": point["threshold"],
                "decrease_percent_of_common": point["decrease_percent_of_common"],
                "increase_percent_of_common": point["increase_percent_of_common"],
                "decrease_area_ha": point["decrease_area_ha"],
                "increase_area_ha": point["increase_area_ha"],
                "valid_pixels": point["valid_pixels"],
            }
            for point in sweep
        ]
        if points:
            series.append({
                "index": key,
                "label": block.get("label", key),
                "primary_threshold": block.get("primary_threshold"),
                "common_valid_fraction_of_aoi": block.get("common_valid_fraction_of_aoi"),
                "common_valid_pixels": block.get("common_valid_pixels"),
                "interpretation_guardrail": block.get("interpretation_guardrail"),
                "points": points,
            })
    return series


def distill_period_index_means(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-period mean index values with valid denominators, for comparison."""
    rows = []
    for period in summary["periods"]:
        for key, block in period["indices"].items():
            stats = block["stats"]
            rows.append({
                "period_id": period["period_id"],
                "anchor_date": period["anchor_date"],
                "index": key,
                "mean": stats["mean"],
                "std": stats["std"],
                "valid_count": stats["valid_count"],
                "total_count": stats["total_count"],
                "valid_fraction": stats["valid_fraction"],
            })
    return rows


def distill_delta_stats(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, block in summary["change"].items():
        stats = block.get("delta_stats") or {}
        rows.append({
            "index": key,
            "mean": stats.get("mean"),
            "std": stats.get("std"),
            "min": stats.get("min"),
            "max": stats.get("max"),
            "quantiles": stats.get("quantiles"),
            "valid_count": stats.get("valid_count"),
            "common_valid_pixels": block.get("common_valid_pixels"),
        })
    return rows


def distill_m2_charts(experiment_id: str) -> dict[str, Any] | None:
    """Distilled interactive-chart series from the recorded M2 result, if any."""
    root = config.PROJECT_ROOT / "data" / "experiments" / "m2" / experiment_id
    run_dirs = sorted((root).glob("*"))
    run_dirs = [d for d in run_dirs if d.is_dir()]
    if not run_dirs:
        return None
    result_path = run_dirs[-1] / "result.json"
    if not result_path.exists():
        return None
    result = json.loads(result_path.read_text(encoding="utf-8"))

    threshold_series: list[dict[str, Any]] = []
    for estimator in result.get("estimators", []):
        if estimator.get("family") != "composite":
            continue
        points = [
            {
                "threshold": point["threshold"],
                "decrease_percent_of_common": point["decrease_percent_of_common"],
                "increase_percent_of_common": point["increase_percent_of_common"],
                "valid_pixels": point["valid_pixels"],
            }
            for point in estimator.get("thresholds", [])
        ]
        if points:
            threshold_series.append({
                "index": estimator["index"],
                "estimator_id": estimator["estimator_id"],
                "label": estimator["label"],
                "common_valid_pixels": estimator["common_valid_pixels"],
                "points": points,
            })

    estimator_comparison: list[dict[str, Any]] = []
    for estimator in result.get("estimators", []):
        if not estimator.get("suitable_for_comparison"):
            continue
        estimator_comparison.append({
            "estimator_id": estimator["estimator_id"],
            "family": estimator["family"],
            "index": estimator["index"],
            "label": estimator["label"],
            "delta_mean": (estimator.get("delta_stats") or {}).get("mean"),
            "delta_std": (estimator.get("delta_stats") or {}).get("std"),
            "decrease_percent_of_common": (estimator.get("primary") or {}).get(
                "decrease_percent_of_common"
            ),
            "primary_threshold": estimator.get("primary_threshold"),
            "common_valid_pixels": estimator.get("common_valid_pixels"),
        })

    bootstrap: dict[str, Any] = {}
    block = result.get("uncertainty", {}).get("block_bootstrap", {})
    for index, payload in block.items():
        if not isinstance(payload, dict) or not payload.get("enabled"):
            continue
        bootstrap[index] = {
            "method": payload.get("method"),
            "block_size_px": payload.get("block_size_px"),
            "iterations_used": payload.get("iterations_used"),
            "delta_mean_ci95": payload.get("delta_mean_ci95"),
            "thresholds": payload.get("thresholds"),
            "assumptions": payload.get("assumptions"),
        }

    return {
        "source": {
            "result_path": str(result_path.relative_to(config.PROJECT_ROOT)).replace("\\", "/"),
            "result_sha256": sha256_file(result_path),
            "run_id": result.get("run_id"),
            "fingerprint": result.get("fingerprint"),
        },
        "hypothesis_verdicts": result.get("hypothesis_verdicts", []),
        "threshold_series": threshold_series,
        "estimator_comparison": estimator_comparison,
        "bootstrap": bootstrap,
        "interpretation_guardrails": result.get("interpretation_guardrails"),
    }


def dem_context(study_id: str, bounds: dict[str, float]) -> dict[str, Any] | None:
    """Copernicus GLO-30 elevation statistics over the study AOI (bounded read)."""
    if study_id != "western_ghats_forest":
        return None
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform_bounds

    try:
        import urllib.request

        body = {
            "collections": ["cop-dem-glo-30"],
            "intersects": {
                "type": "Polygon",
                "coordinates": [[
                    [bounds["west"], bounds["south"]],
                    [bounds["east"], bounds["south"]],
                    [bounds["east"], bounds["north"]],
                    [bounds["west"], bounds["north"]],
                    [bounds["west"], bounds["south"]],
                ]],
            },
            "limit": 1,
        }
        request = urllib.request.Request(
            "https://earth-search.aws.element84.com/v1/search",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "habitatshift-m4"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
        features = payload.get("features") or []
        if not features:
            return {"available": False, "reason": "no DEM item covers the AOI"}
        item = features[0]
        href = item["assets"]["data"]["href"]
        with rasterio.Env(AWS_NO_SIGN_REQUEST="YES"):
            with rasterio.open(href) as src:
                native = transform_bounds(
                    "EPSG:4326", src.crs,
                    bounds["west"], bounds["south"], bounds["east"], bounds["north"],
                )
                from rasterio.windows import from_bounds as window_from_bounds

                window = window_from_bounds(*native, src.transform)
                data = src.read(1, window=window, resampling=Resampling.bilinear).astype("float32")
                nodata = src.nodata
                if nodata is not None:
                    data[data == nodata] = float("nan")
                finite = data[data == data]
        return {
            "available": True,
            "collection": "cop-dem-glo-30",
            "item_id": item["id"],
            "elevation_min_m": round(float(finite.min()), 1),
            "elevation_max_m": round(float(finite.max()), 1),
            "elevation_mean_m": round(float(finite.mean()), 1),
            "role": (
                "Terrain context for interpreting topographic shadow and slope "
                "effects on the NDVI signal; the DEM is not a co-registered "
                "input to the index computation."
            ),
            "license": "Copernicus DEM GLO-30 - ESA/DLR, free and open with attribution",
        }
    except Exception as exc:                                       # pragma: no cover - net
        LOGGER.warning("DEM context unavailable: %s", exc)
        return {"available": False, "reason": f"DEM lookup failed: {exc}"}


#: Event-relevant observations recorded by the feasibility probes
#: (docs/M0_HIMALAYAN_DATA_FEASIBILITY.md, docs/M4_FEASIBILITY.md) that are
#: deliberately NOT part of any processed difference pair.  Listed so the
#: event timeline can show the real acquisition record, including what was
#: unusable or excluded, instead of only the processed subset.
KNOWN_EVENT_OBSERVATIONS: dict[str, list[dict[str, Any]]] = {
    "himalaya_purepu_2025": [
        {
            "item_id": "S2C_45RUM_20250708_0_L2A",
            "date": "2025-07-08",
            "relative_days": 0,
            "in_aoi_valid_fraction": 0.632,
            "status": (
                "same-day acquisition; usable as a single-date context view "
                "but not used as a difference baseline - no clean post-event "
                "July observation exists (all later July passes fail validity)"
            ),
        },
        {
            "item_id": "S2B_45RUM_20250723_0_L2A",
            "date": "2025-07-23",
            "relative_days": 15,
            "in_aoi_valid_fraction": 0.317,
            "status": "monsoon-obscured; below the 0.60 validity threshold",
        },
    ],
    "himalaya_langtang_2026": [
        {
            "item_id": "S2B_45RUM_20260916_0_L2A",
            "date": "2026-09-16",
            "relative_days": 21,
            "in_aoi_valid_fraction": 0.791,
            "status": "additional usable post-event observation; not part of the processed pair (2026-09-28 used instead)",
        },
        {
            "item_id": "S2C_45RUM_20260918_0_L2A",
            "date": "2026-09-18",
            "relative_days": 23,
            "in_aoi_valid_fraction": 0.167,
            "status": "cloud-obscured; below the 0.60 validity threshold",
        },
    ],
}


def event_context(study_entry: dict[str, Any], experiments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Event-relative timing for the Himalayan investigations."""
    import datetime as dt

    event_date = study_entry.get("event_date")
    if not event_date:
        return None
    event = dt.date.fromisoformat(str(event_date))
    references = {
        "himalaya_purepu_2025": [{
            "title": "NDRRMA situation report on the Rasuwa flood event of 8 July 2025",
            "role": "external event context (cited literature, not a project measurement)",
        }],
        "himalaya_langtang_2026": [{
            "title": "ICIMOD preliminary synthesis on the Langtang Lirung rock-ice collapse of 26 August 2026",
            "role": "external event context (cited literature, not a project measurement)",
        }],
    }
    observations = []
    for entry in experiments:
        for period in entry["summary"]["periods"]:
            for date in period.get("observation_dates", []):
                observations.append({
                    "date": date,
                    "relative_days": (dt.date.fromisoformat(date) - event).days,
                    "experiment_id": entry["experiment_id"],
                    "period_id": period["period_id"],
                })
    observations.sort(key=lambda row: row["relative_days"])
    gaps = [
        {
            "statement": (
                f"Nearest usable observation {abs(row['relative_days'])} days "
                f"{'after' if row['relative_days'] > 0 else 'before'} the event"
            )
        }
        for row in (observations[:1] + observations[-1:])
    ]
    return {
        "event_date": str(event_date),
        "event_mechanism": study_entry.get("event_mechanism"),
        "external_references": references.get(study_entry.get("study_id", ""), []),
        "observations_relative_to_event": observations,
        "known_unprocessed_observations": KNOWN_EVENT_OBSERVATIONS.get(
            study_entry.get("study_id", ""), []
        ),
        "observation_gaps": gaps,
        "insar_note": (
            "Sentinel-1 InSAR findings discussed in external research remain "
            "external evidence; HabitatShift has not implemented or validated "
            "an InSAR workflow, and no radar product is used here."
        ),
    }


def build_bundle(
    study_entry: dict[str, Any],
    experiments: list[dict[str, Any]],
    m2: dict[str, Any] | None,
    assets: dict[str, dict[str, Any]],
    out_dir: Path,
) -> dict[str, Any]:
    study_id = study_entry["study_id"]
    primary = experiments[0]["summary"]
    georef_raster = None
    for block in primary["change"].values():
        if block.get("delta_tif"):
            georef_raster = config.PROJECT_ROOT / block["delta_tif"]
            break
    if georef_raster is None:
        period = primary["periods"][0]
        georef_raster = config.PROJECT_ROOT / period["previews"]["true_colour"]
    aoi = study_entry["aoi"]["bounds"]
    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "bundle_version": BUNDLE_VERSION,
        "study_id": study_id,
        # Evidence verdict for the interface: "partial" marks studies the
        # feasibility review restricted (docs/M4_FEASIBILITY.md).  The
        # registry's own status word is preserved in study.status.
        "evidence_status": "partial" if study_id == "himalaya_purepu_2025" else "processed",
        "study": {
            "study_id": study_id,
            "id": study_entry.get("id"),
            "slug": study_entry.get("slug"),
            "title": study_entry.get("title"),
            "study_type": study_entry.get("study_type"),
            "status": study_entry.get("status"),
            "question": " ".join(str(study_entry.get("question", "")).split()),
            "phenomena": study_entry.get("phenomena", []),
            "limitations": study_entry.get("limitations", []),
            "target_periods": study_entry.get("target_periods"),
            "aoi": {
                "crs": study_entry["aoi"].get("crs"),
                "kind": study_entry["aoi"].get("kind"),
                "boundary_source": " ".join(
                    str(study_entry["aoi"].get("boundary_source", "")).split()
                ),
                "bounds": aoi,
                "approx_km": study_entry["aoi"].get("approx_km"),
            },
        },
        "interpretation": INTERPRETATION.get(study_id, {}),
        "attribution": ATTRIBUTION,
        "catalog": primary.get("catalog"),
        "georef": raster_georef(georef_raster),
        "experiments": [
            {
                "experiment_id": entry["experiment_id"],
                "label": entry["label"],
                "config_path": entry["config_path"],
                "config_sha256": entry["config_sha256"],
                "summary_sha256": entry["summary_sha256"],
                "summary": entry["summary"],
                # M4-R1 §15: the "What Changed?" findings, generated from the
                # frozen difference rasters by scripts/generate_findings.py.
                # Optional: experiments without a findings file simply omit it.
                "findings": load_findings(entry["experiment_id"]),
            }
            for entry in experiments
        ],
        "charts": {
            "threshold_series": distill_threshold_series(primary),
            "period_index_means": distill_period_index_means(primary),
            "delta_stats": distill_delta_stats(primary),
        },
        "assets": assets,
        "sources": {
            "registry": {
                "path": "studies/registry.yaml",
                "sha256": sha256_file(config.STUDIES_DIR / "registry.yaml"),
            },
            "m2_experiment": m2,
        },
    }
    dem = dem_context(study_id, aoi)
    if dem is not None:
        bundle["dem_context"] = dem
    event = event_context(study_entry, experiments)
    if event is not None:
        bundle["event"] = event
    return bundle


def _sanitize(value: Any) -> Any:
    """Replace non-finite floats with None so the bundle is strict JSON.

    Raster nodata fields can be NaN; browsers' JSON.parse rejects NaN
    literals, so the bundle must never contain them.
    """
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else None
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def build_study(study_id: str, studies_root: Path) -> Path:
    registry = load_registry()
    if study_id not in registry:
        raise SystemExit(f"unknown study_id: {study_id}")
    study_entry = registry[study_id]
    plan = STUDY_EXPERIMENTS.get(study_id)
    if plan is None:
        raise SystemExit(f"no experiment plan for study {study_id}")

    experiments = [load_m1_summary(experiment_id) for experiment_id in plan["m1"]]
    m2 = distill_m2_charts(plan["m2"]) if plan.get("m2") else None

    out_dir = studies_root / study_id
    previews_dir = out_dir / "previews"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    assets = collect_previews(experiments, previews_dir)

    bundle = _sanitize(build_bundle(study_entry, experiments, m2, assets, out_dir))
    bundle_path = out_dir / "bundle.json"
    bundle["bundle_sha256_inputs"] = {
        "previews": sorted(assets.keys()),
    }
    bundle_path.write_text(
        json.dumps(bundle, indent=1, sort_keys=False, allow_nan=False),
        encoding="utf-8",
    )
    LOGGER.info(
        "%s: bundle written (%d assets, %d bytes)",
        study_id, len(assets), bundle_path.stat().st_size,
    )
    return bundle_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", action="append", help="study_id to build (repeatable)")
    parser.add_argument("--list", action="store_true", help="list planned studies")
    parser.add_argument(
        "--out",
        default=str(config.PROJECT_ROOT / "frontend" / "public" / "studies"),
        help="output root (default frontend/public/studies)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.list:
        for study_id in STUDY_EXPERIMENTS:
            print(study_id)
        return 0

    studies_root = Path(args.out)
    studies_root.mkdir(parents=True, exist_ok=True)
    # Static registry copy: the landing page and gallery render without any
    # backend.  Content is the parsed registry YAML, unchanged.
    registry = yaml.safe_load(
        (config.STUDIES_DIR / "registry.yaml").read_text(encoding="utf-8")
    )
    registry_path = studies_root / "registry.json"
    registry_path.write_text(
        json.dumps(_sanitize(registry), indent=1, allow_nan=False), encoding="utf-8"
    )
    LOGGER.info("registry.json written")
    targets = args.study or list(STUDY_EXPERIMENTS)
    for study_id in targets:
        build_study(study_id, studies_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
