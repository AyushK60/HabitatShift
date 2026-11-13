"""Generate defensible "What Changed?" findings from processed change rasters
(M4-R1 additional feature §15.8).

A finding is a spatially explicit, threshold-defined candidate change region
extracted from the FROZEN M1 difference rasters:

- the recorded primary threshold of each index defines the candidate mask
  (later − earlier ≤ −t for decrease, ≥ +t for increase, inside the
  common-valid footprint only);
- connected components (4-connectivity) are labelled on that mask;
- components smaller than the documented minimum mapping unit (25 px =
  0.25 ha on the 10 m grid) are discarded, so tiny isolated pixel clusters
  never become findings;
- the top regions per index and direction (by area, deterministic order)
  become findings with true polygon geometry extracted from the raster grid
  (rasterio.features.shapes on the native UTM grid, projected to WGS84 with
  pyproj — never hand-drawn);

and each finding records the full audit trail: source experiment, threshold,
pixel count, measured area in the projected CRS, mean/median Δ, the
common-valid denominator, the acquisition periods and the study's recorded
limitations. Interpretation strings are deterministic templates keyed to the
study's science framework (brief §15.4); no AI text and no invented numbers.

Output: ``data/findings/<experiment_id>/findings.json``
(schema ``habitatshift-findings/2``; per-finding Evidence Records schema
``habitatshift-evidence-record/1`` — see ``docs/M4_R2_EVIDENCE_SCHEMA.md``).
The bundle builder embeds this file per experiment so map overlays and
descriptions use exactly these measurements.

Usage:
    python scripts/generate_findings.py               # all experiments
    python scripts/generate_findings.py --experiment kathmandu_m4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rasterio                                                      # noqa: E402
from rasterio.features import shapes as rio_shapes                   # noqa: E402
from scipy import ndimage                                            # noqa: E402

LOGGER = logging.getLogger("generate_findings")

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MINIMUM_MAPPING_UNIT_PX = 25          # 0.25 ha on the 10 m grid
MAX_REGIONS_PER_INDEX_DIRECTION = 5   # top regions by area, deterministic
CONNECTIVITY_STRUCTURE = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)

#: experiment_id -> processed directory (relative to the project root).
EXPERIMENTS = {
    "coringa_m1": "data/processed/m1/coringa_coastal",
    "chilika_m4_dry": "data/processed/m4/chilika_m4_dry",
    "chilika_m4_postmonsoon": "data/processed/m4/chilika_m4_postmonsoon",
    "western_ghats_m4": "data/processed/m4/western_ghats_m4",
    "himalaya_purepu_2025_m4": "data/processed/m4/himalaya_purepu_2025_m4",
    "himalaya_langtang_2026_m4": "data/processed/m4/himalaya_langtang_2026_m4",
    "kathmandu_m4": "data/processed/m4/kathmandu_m4",
}

# ---------------------------------------------------------------------------
# Study-specific interpretation templates (brief §15.4). Deterministic: every
# value is interpolated from the recorded measurement; the framing sentences
# are fixed per study and reviewed against its recorded guardrails.
# ---------------------------------------------------------------------------


def _pct(value: float) -> str:
    return f"{value:.2f} %"


def _ha(value: float) -> str:
    return f"{value:.2f} ha"


def _delta(value: float) -> str:
    return f"{value:+.3f} index units"


def _template(study_id: str) -> dict[str, Any]:
    """Fixed study-specific framing for meaning / explanations / strength."""
    return {
        "coringa_coastal": {
            "meaning": (
                "A lower {index} value here means the later composite reads "
                "{direction_word} in {index} than the earlier composite. In a "
                "mangrove/tidal delta context a {index} {direction} can reflect "
                "canopy change, water-level or turbidity differences between the "
                "acquisition windows, or tidal state — it is not, by itself, "
                "evidence of mangrove destruction."
            ),
            "explanations": [
                "Seasonal or tidal water-level differences change the spectral mix of the cell.",
                "Turbidity and sun-glint differences between the composite windows.",
                "Genuine canopy thinning or regrowth — plausible, but it cannot be separated from the options above using optical indices alone.",
            ],
            "cannot": [
                "That mangrove was destroyed or restored (no independent labels).",
                "Which fraction of the signal is tidal versus vegetation change.",
            ],
        },
        "chilika_wetland": {
            "meaning": (
                "A {index} {direction} here marks where the later composite reads "
                "{direction_word} in {index}. In Chilika this most often tracks "
                "water-surface extent and exposed lakebed between the two seasons; "
                "episodic exposed lakebed is a normal seasonal state, not permanent "
                "wetland loss."
            ),
            "explanations": [
                "Seasonal water-level change exposing or re-submerging lakebed.",
                "Turbidity and aquatic-vegetation differences between the windows.",
                "Longer-term wetland change — possible, but it cannot be separated from the seasonal signal with one matched pair.",
            ],
            "cannot": [
                "That exposed lakebed became permanent wetland loss.",
                "Whether the signal persists outside the compared seasons.",
            ],
        },
        "western_ghats_forest": {
            "meaning": (
                "A {index} {direction} here marks where the later forest composite "
                "reads {direction_word} in {index}. In this terrain the validity "
                "footprint is complete, but terrain shadow and illumination "
                "geometry can still colour the spectral comparison."
            ),
            "explanations": [
                "Terrain shadow and illumination differences between acquisitions.",
                "Canopy density or phenology differences between the windows.",
                "Canopy disturbance — candidate only; independent evidence would be required to establish it.",
            ],
            "cannot": [
                "That deforestation occurred (no independent verification).",
                "A distinction between shadow effects and real canopy change.",
            ],
        },
        "himalaya_purepu_2025": {
            "meaning": (
                "A {index} {direction} here marks where the later composite reads "
                "{direction_word} in {index}. This investigation is PARTIAL: no "
                "clean immediate post-event observation exists, and the processed "
                "pair is seasonal (April → October), so snow, ice and seasonal "
                "spectral evolution dominate the comparison."
            ),
            "explanations": [
                "Seasonal snow and ice evolution between the two acquisition windows.",
                "Cloud, shadow and topographic effects at the mask boundary.",
                "Event-related surface change — cannot be established from this seasonal pair.",
            ],
            "cannot": [
                "Discharged volume, flood depth, or confirmed event damage from these optical differences.",
                "Any attribution of the mapped difference to the event itself.",
            ],
        },
        "himalaya_langtang_2026": {
            "meaning": (
                "A {index} {direction} here marks where the later composite reads "
                "{direction_word} in {index}. Snow/ice spectral context dominates "
                "this scene: NDSI-type signals read snow-cover state, and the "
                "event is not a conventional GLOF, so highlighted regions must not "
                "automatically be read as part of a collapse footprint."
            ),
            "explanations": [
                "Seasonal snow-cover evolution between the acquisition windows.",
                "Debris or exposed-ground signatures where observable.",
                "Cloud and topographic visibility limits at the mask boundary.",
            ],
            "cannot": [
                "That every highlighted region belongs to the collapse footprint.",
                "Discharge, depth or damage assessments from optical differences.",
            ],
        },
        "kathmandu_urban": {
            "meaning": (
                "A {index} {direction} here marks where the later composite reads "
                "{direction_word} in {index}. For NDBI this is a candidate "
                "built-up/impervious-surface signal — NOT a building detector; "
                "bare soil and construction sites raise NDBI the same way."
            ),
            "explanations": [
                "New or extended impervious surfaces (candidate built-up change).",
                "Bare soil, construction sites or cleared ground between the windows.",
                "Vegetation loss on the ΔNDVI counter-evidence panel.",
            ],
            "cannot": [
                "That individual buildings were newly constructed (10 m pixels cannot resolve buildings).",
                "Verified urban expansion without independent evidence.",
            ],
        },
    }[study_id]


def _direction_word(direction: str) -> str:
    return "lower" if direction == "decrease" else "higher"


def _interpretation(study_id: str, finding: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    tpl = _template(study_id)
    index = finding["index"].upper()
    direction = finding["direction"]
    fmt = {
        "index": index,
        "direction": direction,
        "direction_word": _direction_word(direction),
    }
    arrow = "▼" if direction == "decrease" else "▲"
    title = f"{arrow} Candidate {index} {direction} · {finding['display_id']}"
    return {
        "title": title,
        "location": (
            f"{finding['display_id']} · centroid {finding['centroid_lonlat'][0]:.4f}°E, "
            f"{finding['centroid_lonlat'][1]:.4f}°N · {finding['area_ha']:.2f} ha"
        ),
        "observation_period": (
            f"{ctx['earlier_date']} → {ctx['later_date']} "
            f"({ctx['composite_method']} composites)"
        ),
        "observed_measurement": (
            f"Mean Δ{index} {_delta(finding['mean_delta'])} (median "
            f"{_delta(finding['median_delta'])}) at the recorded threshold "
            f"|Δ| ≥ {finding['threshold']}; {finding['pixel_count']:,} px = "
            f"{_ha(finding['area_ha'])} = {_pct(finding['share_of_common_valid_percent'])} "
            f"of the {finding['common_valid_pixels']:,}-px shared-valid footprint."
        ),
        "meaning": tpl["meaning"].format(**fmt),
        "explanations": tpl["explanations"],
        "evidence_strength": (
            f"Shared-valid coverage for this comparison is {_pct(ctx['common_valid_fraction_of_aoi'] * 100)} "
            f"of the AOI ({finding['common_valid_pixels']:,} px). The region is a connected "
            f"{finding['pixel_count']:,}-px component at a stated threshold — adjacent pixels are "
            f"not independent observations, so no significance is claimed. "
            + (
                "PARTIAL evidence study: the comparison is seasonal and explicitly caveated."
                if ctx.get("evidence_status") == "partial"
                else "Candidate spectral signal with stated thresholds, not independently verified change."
            )
        ),
        "cannot_conclude": tpl["cannot"],
        "source": {
            "experiment_id": ctx["experiment_id"],
            "input_raster": finding["input_raster"],
            "valid_mask": finding["valid_mask"],
            "method": ctx["method"],
        },
    }


#: Neighbour thresholds (± 0.05 index units) for the per-finding
#: threshold-sensitivity evaluation (M4-R2 G6).
SENSITIVITY_NEIGHBOURS = (0.05,)


def _threshold_sensitivity(
    *,
    delta: np.ndarray,
    usable: np.ndarray,
    region_mask: np.ndarray,
    threshold: float,
    direction: str,
    pixel_area_m2: float,
) -> dict[str, Any]:
    """Evaluate the recorded region under neighbour thresholds.

    Transparent descriptive categories — never a confidence score:
    the region's pixels are a subset of the looser (t − 0.05) mask, so the
    informative quantities are component growth at t − 0.05 and the retained
    fraction of the region plus component shrinkage at t + 0.05. Labels and
    their exact rules are recorded with the result.
    """
    label_rules = (
        "spatially persistent across tested thresholds: ≥ 80 % of the region's "
        "pixels remain candidates at t + 0.05 AND the containing component "
        "area stays within 2× at both neighbour thresholds; "
        "threshold-sensitive: < 50 % retained at t + 0.05 OR the component "
        "grows/shrinks beyond 3×/⅓× at a neighbour; otherwise moderately "
        "threshold-sensitive"
    )
    neighbours: dict[str, Any] = {}
    growth = 1.0
    shrink = 1.0
    retention_hi = 1.0
    for delta_t in SENSITIVITY_NEIGHBOURS:
        t_lo = round(threshold - delta_t, 6)
        t_hi = round(threshold + delta_t, 6)
        if t_lo <= 0:
            continue
        for tag, t_value in ((f"t_minus_{delta_t}", t_lo), (f"t_plus_{delta_t}", t_hi)):
            mask = (
                usable & (delta >= t_value)
                if direction == "increase"
                else usable & (delta <= -t_value)
            )
            if not mask.any():
                neighbours[tag] = {
                    "threshold": t_value,
                    "component_pixels": 0,
                    "retained_fraction_of_region": 0.0,
                    "component_growth_factor": 0.0,
                }
                shrink = min(shrink, 0.0)
                continue
            labels, _ = ndimage.label(mask, structure=CONNECTIVITY_STRUCTURE)
            overlap_ids = labels[region_mask]
            overlap_ids = overlap_ids[overlap_ids > 0]
            if overlap_ids.size == 0:
                neighbours[tag] = {
                    "threshold": t_value,
                    "component_pixels": 0,
                    "retained_fraction_of_region": 0.0,
                    "component_growth_factor": 0.0,
                }
                shrink = min(shrink, 0.0)
                continue
            component_id = np.bincount(overlap_ids).argmax()
            component_px = int((labels == component_id).sum())
            retained = float(overlap_ids.size) / float(region_mask.sum())
            growth_factor = component_px / max(1, int(region_mask.sum()))
            neighbours[tag] = {
                "threshold": t_value,
                "component_pixels": component_px,
                "retained_fraction_of_region": round(retained, 4),
                "component_growth_factor": round(growth_factor, 4),
            }
            if tag.startswith("t_minus"):
                growth = max(growth, growth_factor)
            else:
                retention_hi = retained
                shrink = min(shrink, growth_factor)
    if retention_hi >= 0.8 and growth <= 2.0 and shrink >= 0.5:
        label = "spatially persistent across tested thresholds"
    elif retention_hi < 0.5 or growth > 3.0 or shrink < 1 / 3.0:
        label = "threshold-sensitive"
    else:
        label = "moderately threshold-sensitive"
    return {
        "status": "computed",
        "method": (
            "candidate mask relabelled at t ± 0.05; the containing component "
            "of the recorded region is tracked (max-overlap component)"
        ),
        "neighbour_delta": SENSITIVITY_NEIGHBOURS[0],
        "neighbours": neighbours,
        "label": label,
        "label_rules": label_rules,
    }


def _polygon_wgs84(ring_utm: list[tuple[float, float]], transformer) -> list[list[float]]:
    return [
        [round(lon, 6), round(lat, 6)]
        for lon, lat in (transformer.transform(x, y) for x, y in ring_utm)
    ]


def _ring_area_m2(ring: list[tuple[float, float]]) -> float:
    """Shoelace area of a UTM ring (projected grid; orientation-agnostic)."""
    acc = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        acc += x1 * y2 - x2 * y1
    return abs(acc) / 2.0


def _region_findings(
    *,
    experiment_id: str,
    processed_dir: Path,
    index: str,
    block: dict[str, Any],
    periods: list[dict[str, Any]],
    summary: dict[str, Any],
    counter,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract findings for one index from its frozen delta raster."""
    threshold = float(block["primary_threshold"])
    common_valid_pixels = int(block["common_valid_pixels"])
    pixel_area_m2 = float(block.get("pixel_area_m2", 100.0))
    earlier, later = periods[0], periods[1]
    tag_e = f"{earlier['period_id']}_{earlier['anchor_date']}"
    tag_l = f"{later['period_id']}_{later['anchor_date']}"
    # Delta rasters are named after the LATER period tag in the engine layout
    # (one difference raster per index); fall back to the plain name.
    delta_candidates = [
        processed_dir / f"delta_{index}.tif",
        processed_dir / f"{tag_l}_delta_{index}.tif",
    ]
    delta_path = next((p for p in delta_candidates if p.exists()), None)
    common_path = processed_dir / f"common_valid_{index}.tif"
    if delta_path is None or not common_path.exists():
        LOGGER.warning("%s: missing delta/common rasters for %s", experiment_id, index)
        return [], {}

    with rasterio.open(delta_path) as src:
        delta = src.read(1).astype(np.float64)
        transform = src.transform
        crs = src.crs
    with rasterio.open(common_path) as src:
        common = src.read(1).astype(bool)

    usable = common & np.isfinite(delta)
    decrease_mask = usable & (delta <= -threshold)
    increase_mask = usable & (delta >= threshold)

    from pyproj import CRS as PyCRS, Transformer

    to_wgs84 = Transformer.from_crs(crs, PyCRS.from_epsg(4326), always_xy=True)

    findings: list[dict[str, Any]] = []
    totals: dict[str, int] = {}
    for direction, mask in (("decrease", decrease_mask), ("increase", increase_mask)):
        total = int(mask.sum())
        totals[direction] = total
        if total == 0:
            continue
        labels, n = ndimage.label(mask, structure=CONNECTIVITY_STRUCTURE)
        if n == 0:
            continue
        counts = np.bincount(labels.ravel())[1:]
        ids = np.arange(1, n + 1)
        keep = ids[counts >= MINIMUM_MAPPING_UNIT_PX]
        # Deterministic order: area descending, then centroid row/col.
        regions = []
        for region_id in keep:
            region_mask = labels == region_id
            rows, cols = np.nonzero(region_mask)
            mean_delta = float(delta[region_mask].mean())
            median_delta = float(np.median(delta[region_mask]))
            regions.append(
                (int(region_mask.sum()), float(rows.mean()), float(cols.mean()), region_mask, mean_delta, median_delta)
            )
        regions.sort(key=lambda item: (-item[0], item[1], item[2]))
        for pixel_count, _, _, region_mask, mean_delta, median_delta in regions[
            :MAX_REGIONS_PER_INDEX_DIRECTION
        ]:
            polys = [
                geom
                for geom, value in rio_shapes(
                    region_mask.astype(np.uint8), mask=region_mask, transform=transform
                )
                if value == 1
            ]
            if not polys:
                continue
            geometry = polys[0]  # one connected component → one polygon
            # Ring 0 is the exterior; any further rings are interior holes
            # (masked pixels fully enclosed by the candidate component). They
            # are preserved in the geometry and counted explicitly.
            rings_utm = geometry["coordinates"]
            utm_ring = rings_utm[0]
            hole_pixel_count = int(
                round((_ring_area_m2(utm_ring) - pixel_count * pixel_area_m2) / pixel_area_m2)
            )
            hole_rings_wgs84 = [
                _polygon_wgs84(ring, to_wgs84) for ring in rings_utm[1:]
            ]
            xs = [point[0] for point in utm_ring]
            ys = [point[1] for point in utm_ring]
            centroid_x, centroid_y = float(np.mean(xs)), float(np.mean(ys))
            centroid_lon, centroid_lat = to_wgs84.transform(centroid_x, centroid_y)
            wgs_ring = _polygon_wgs84(utm_ring, to_wgs84)
            display_id = f"Region {next(counter):02d}"
            # Content-derived stable ID, computed from the ROUNDED centroid
            # that is recorded on the finding, so the ID is reproducible from
            # the record itself.
            centroid_utm = [round(centroid_x, 2), round(centroid_y, 2)]
            evidence_id = (
                f"ev-{experiment_id}-{index}-{direction[:3]}"
                f"-{round(centroid_utm[0])}-{round(centroid_utm[1])}"
            )
            findings.append(
                {
                    "id": display_id.lower().replace(" ", "_"),
                    "display_id": display_id,
                    "evidence_id": evidence_id,
                    "index": index,
                    "direction": direction,
                    "threshold": threshold,
                    "pixel_count": int(pixel_count),
                    "area_ha": round(pixel_count * pixel_area_m2 / 1e4, 4),
                    "share_of_common_valid_percent": round(
                        pixel_count / common_valid_pixels * 100, 4
                    ),
                    "mean_delta": round(mean_delta, 6),
                    "median_delta": round(median_delta, 6),
                    "common_valid_pixels": common_valid_pixels,
                    "hole_pixel_count": hole_pixel_count,
                    "centroid_utm": centroid_utm,
                    "centroid_lonlat": [round(centroid_lon, 6), round(centroid_lat, 6)],
                    "geometry_wgs84": {
                        "type": "Polygon",
                        "coordinates": [wgs_ring] + hole_rings_wgs84,
                    },
                    "input_raster": str(delta_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                    "valid_mask": str(common_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                    # M4-R2 G6: threshold-sensitivity evaluation (moved into
                    # the evidence record by generate(); the flat key is
                    # removed before serialisation).
                    "_threshold_sensitivity": _threshold_sensitivity(
                        delta=delta,
                        usable=usable,
                        region_mask=region_mask,
                        threshold=threshold,
                        direction=direction,
                        pixel_area_m2=pixel_area_m2,
                    ),
                }
            )

    index_stats = {
        "threshold": threshold,
        "common_valid_pixels": common_valid_pixels,
        "decrease_pixels_total": totals.get("decrease", 0),
        "increase_pixels_total": totals.get("increase", 0),
    }
    return findings, index_stats


def _git_commit() -> str | None:
    """Commit of record at generation time; None when git is unavailable."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=PROJECT_ROOT,
        ).stdout.strip()
    except Exception:  # pragma: no cover - provenance is best-effort
        return None


def _software_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for dist in ("numpy", "rasterio", "scipy", "pyproj"):
        try:
            versions[dist] = metadata.version(dist)
        except Exception:  # pragma: no cover
            versions[dist] = "unavailable"
    return versions


def _finding_checksum(finding: dict[str, Any]) -> str:
    payload = json.loads(json.dumps(finding))  # deep copy
    payload["evidence"]["method_provenance"]["output_checksum"] = None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _evidence_record(
    finding: dict[str, Any],
    *,
    summary: dict[str, Any],
    method: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the versioned Evidence Record for one finding (G4).

    Structured measurements only — the explanatory interpretation stays in
    ``finding['interpretation']`` and is part of the record by reference.
    Fields the pipeline cannot supply are recorded as null, never invented.
    """
    study = summary["study"]
    earlier, later = summary["periods"][0], summary["periods"][1]
    grid = summary["grid"]
    aoi = summary["aoi"]
    outputs = summary.get("outputs", {})
    index = finding["index"]
    block = summary["change"][index]
    spec = summary.get("indices", {}).get(index, {})
    catalog = summary.get("catalog", {})

    def output_hash(*registry_keys: str) -> str | None:
        for key in registry_keys:
            entry = outputs.get(key)
            if entry and entry.get("sha256"):
                return entry["sha256"]
        return None

    delta_hash = output_hash(f"delta_{index}_tif", f"{later['period_id']}_{later['anchor_date']}_delta_{index}_tif")
    common_hash = output_hash(f"common_valid_{index}_tif")

    # Validity: the shared-valid footprint is the intersection of both
    # periods' valid masks; the per-period fractions are recorded per period.
    quality_limitations = list(summary.get("limitations", []))

    return {
        "schema": "habitatshift-evidence-record/1",
        "identification": {
            "evidence_id": finding["evidence_id"],
            "finding_id": finding["id"],
            "display_id": finding["display_id"],
            "schema_version": 1,
            "study_id": study["study_id"],
            "experiment_id": summary["experiment_id"],
            "finding_type": "threshold-connected-region",
            "candidate_direction": finding["direction"],
            "evidence_status": ctx["evidence_status"],
        },
        "source_observations": {
            "earlier": {
                "item_ids": earlier.get("item_ids"),
                "observation_dates": earlier.get("observation_dates"),
                "anchor_date": earlier["anchor_date"],
                "composite_method": earlier["composite_method"],
                "observation_count": earlier.get("observation_count"),
                "valid_pixels": earlier.get("valid_pixels"),
                "aoi_pixels": earlier.get("aoi_pixels"),
                "valid_fraction": earlier.get("valid_fraction"),
            },
            "later": {
                "item_ids": later.get("item_ids"),
                "observation_dates": later.get("observation_dates"),
                "anchor_date": later["anchor_date"],
                "composite_method": later["composite_method"],
                "observation_count": later.get("observation_count"),
                "valid_pixels": later.get("valid_pixels"),
                "aoi_pixels": later.get("aoi_pixels"),
                "valid_fraction": later.get("valid_fraction"),
            },
            "dataset": {
                "collection": catalog.get("collection"),
                "provider": catalog.get("provider"),
                "license": catalog.get("license"),
                "processing_level": "Sentinel-2 L2A surface reflectance",
                "attribution": summary.get("attribution"),
            },
            "study_aoi": {
                "bounds_lonlat": aoi.get("bounds_4326"),
                "area_km2": aoi.get("area_km2"),
                "aoi_pixels": aoi.get("aoi_pixels"),
            },
        },
        "input_measurements": {
            "index": index,
            "index_label": block.get("label") or index.upper(),
            "formula": spec.get("formula"),
            "bands": spec.get("bands"),
            "native_band_resolution_m": spec.get("native_resolution_m"),
            "band_resolution_note": spec.get("resolution_note"),
            "delta_definition": "I_later(p) - I_earlier(p) on the shared analysis grid",
            "threshold": finding["threshold"],
            "threshold_rule": "|ΔI| ≥ t, inclusive; sign selects the candidate direction",
            "input_raster": finding["input_raster"],
            "input_raster_sha256": delta_hash,
            "valid_mask": finding["valid_mask"],
            "valid_mask_sha256": common_hash,
            "analysis_grid": {
                "crs": grid["crs"],
                "resolution_m": grid["resolution_m"],
                "width": grid["width"],
                "height": grid["height"],
                "transform": grid["transform"],
                "pixel_area_m2": grid["pixel_area_m2"],
            },
        },
        "spatial_measurements": {
            "pixel_count": finding["pixel_count"],
            "area_ha": finding["area_ha"],
            "area_units": "ha (projected analysis grid, pixel count × pixel area)",
            "mean_delta": finding["mean_delta"],
            "median_delta": finding["median_delta"],
            "valid_pixel_denominator": finding["common_valid_pixels"],
            "share_of_common_valid_percent": finding["share_of_common_valid_percent"],
            "hole_pixel_count": finding["hole_pixel_count"],
            "centroid_utm": finding["centroid_utm"],
            "centroid_lonlat": finding["centroid_lonlat"],
            "geometry_wgs84_ref": "finding.geometry_wgs84",
        },
        "evidence_quality": {
            "earlier_valid_fraction": earlier.get("valid_fraction"),
            "later_valid_fraction": later.get("valid_fraction"),
            "shared_valid_fraction_of_aoi": ctx["common_valid_fraction_of_aoi"],
            "observation_support": {
                "earlier_observations": earlier.get("observation_count"),
                "later_observations": later.get("observation_count"),
                "min_observations_required": earlier.get("min_observations"),
            },
            "masking_and_cloud_limitations": quality_limitations,
            # Replaced by the computed G6 evaluation in generate().
            "threshold_sensitivity": {"status": "computed in generate()", "result": None},
            "confounding_factors": finding["interpretation"]["explanations"],
        },
        # Replaced by the computed overlap links in generate().
        "relationships": {
            "overlap_rule": "equal-area UTM intersection ≥ 10 % of the smaller region",
            "links": [],
        },
        "method_provenance": {
            "algorithm": "threshold candidate mask → 4-connected components (scipy.ndimage.label) → MMU filter → top-K selection",
            "algorithm_version": summary.get("pipeline_version"),
            "parameters": {
                "threshold": finding["threshold"],
                "minimum_mapping_unit_px": method["minimum_mapping_unit_px"],
                "minimum_mapping_unit_ha": method["minimum_mapping_unit_ha"],
                "max_regions_per_index_direction": method["max_regions_per_index_direction"],
                "connectivity": 4,
            },
            "input_hashes": {
                "delta_raster": delta_hash,
                "common_valid_mask": common_hash,
            },
            "source_experiment_run": {
                "experiment_id": summary["experiment_id"],
                "run_generated_utc": summary.get("generated_utc"),
                "pipeline_verification": summary.get("verification"),
            },
            "git_commit": _git_commit(),
            "software": _software_versions(),
            "generated_utc": ctx["generated_utc"],
            "output_checksum": None,  # filled by _finding_checksum below
        },
    }


MAX_RELATIONSHIPS_PER_FINDING = 8


def _attach_relationships(payload: dict[str, Any], summary: dict[str, Any]) -> None:
    """Link overlapping findings within one experiment (M4-R2 G6).

    Measurements of the same geography stay separate records — the links
    exist so overlapping candidate regions are never presented as
    independent environmental events. Relationship kinds:

    - ``same-direction-overlap``: two indices flag the same candidate change
      in the same area (multiple measurements of one region);
    - ``opposite-direction-overlap``: different candidate signals overlap
      (e.g. an NDVI decrease inside an NDWI increase area — typically the
      water/sub vegetation contrast).

    Cross-index only: components of one index-direction mask are disjoint by
    construction, so same-index links cannot exist.
    """
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.ops import transform as shp_transform
    from pyproj import CRS as PyCRS, Transformer

    findings = payload["findings"]
    if len(findings) < 2:
        return
    to_utm = Transformer.from_crs(
        PyCRS.from_epsg(4326), PyCRS.from_string(summary["grid"]["crs"]), always_xy=True
    )
    polygons = []
    for finding in findings:
        rings = finding["geometry_wgs84"]["coordinates"]
        shp = ShapelyPolygon(rings[0], rings[1:])
        polygons.append(shp_transform(lambda x, y, t=to_utm: t.transform(x, y), shp))

    for i, finding in enumerate(findings):
        links = []
        for j, other in enumerate(findings):
            if i == j or finding["index"] == other["index"]:
                continue
            inter = polygons[i].intersection(polygons[j]).area
            smaller = min(polygons[i].area, polygons[j].area)
            if smaller <= 0:
                continue
            overlap = inter / smaller
            if overlap < 0.10:
                continue
            links.append(
                {
                    "with_evidence_id": other["evidence_id"],
                    "relation": (
                        "same-direction-overlap"
                        if finding["direction"] == other["direction"]
                        else "opposite-direction-overlap"
                    ),
                    "indices": sorted({finding["index"], other["index"]}),
                    "overlap_percent_of_smaller": round(overlap * 100, 2),
                }
            )
        links.sort(key=lambda item: (-item["overlap_percent_of_smaller"], item["with_evidence_id"]))
        finding["evidence"]["relationships"]["links"] = links[:MAX_RELATIONSHIPS_PER_FINDING]

    overview = payload["overview"]
    overview["related_findings"] = sum(
        1 for f in findings if f["evidence"]["relationships"]["links"]
    )
    overview["relationship_kinds"] = sorted(
        {
            link["relation"]
            for f in findings
            for link in f["evidence"]["relationships"]["links"]
        }
    )


def generate(experiment_id: str, processed_rel: str) -> int:
    processed_dir = PROJECT_ROOT / processed_rel
    summary_path = processed_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    study_id = summary["study"]["study_id"]
    periods = summary["periods"]
    change = summary.get("change", {})

    all_findings: list[dict[str, Any]] = []
    indices: dict[str, Any] = {}
    counter = iter(range(1, 1000))
    for index, block in change.items():
        found, stats = _region_findings(
            experiment_id=experiment_id,
            processed_dir=processed_dir,
            index=index,
            block=block,
            periods=periods,
            summary=summary,
            counter=counter,
        )
        indices[index] = stats
        all_findings.extend(found)

    method = {
        "source": "frozen M1 difference rasters + common-valid masks",
        "threshold_rule": "recorded primary threshold of each index (|Δ| ≥ t)",
        "connected_components": "scipy.ndimage.label, 4-connectivity",
        "minimum_mapping_unit_px": MINIMUM_MAPPING_UNIT_PX,
        "minimum_mapping_unit_ha": round(
            MINIMUM_MAPPING_UNIT_PX * float(next(iter(change.values())).get("pixel_area_m2", 100.0)) / 1e4, 4
        ) if change else None,
        "max_regions_per_index_direction": MAX_REGIONS_PER_INDEX_DIRECTION,
        "geometry": "rasterio.features.shapes on the native UTM grid, projected to WGS84 (pyproj); no hand-drawn geometry",
        "area_convention": "pixel count × pixel area on the projected analysis grid",
    }

    first_block = next(iter(change.values()), None)
    generated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "schema": "habitatshift-findings/2",
        "study_id": study_id,
        "experiment_id": experiment_id,
        "generated_utc": generated_utc,
        # Same evidence verdict as the bundle builder: "partial" marks the
        # study the feasibility review restricted (docs/M4_FEASIBILITY.md).
        "evidence_status": (
            "partial" if study_id == "himalaya_purepu_2025" else summary.get("evidence_status", "processed")
        ),
        "method": method,
        "periods": {
            "earlier": {
                "anchor_date": periods[0]["anchor_date"],
                "composite_method": periods[0]["composite_method"],
            },
            "later": {
                "anchor_date": periods[1]["anchor_date"],
                "composite_method": periods[1]["composite_method"],
            },
        },
        "common_valid_pixels": first_block["common_valid_pixels"] if first_block else 0,
        "common_valid_fraction_of_aoi": first_block["common_valid_fraction_of_aoi"] if first_block else 0,
        "indices": indices,
        "findings": [
            {**finding, "interpretation": None} for finding in all_findings
        ],
        "overview": {
            "findings_total": len(all_findings),
            "by_direction": {
                "decrease": sum(1 for f in all_findings if f["direction"] == "decrease"),
                "increase": sum(1 for f in all_findings if f["direction"] == "increase"),
            },
            "signal_types": sorted({f["index"].upper() for f in all_findings}),
            "no_finding_statement": (
                "No connected candidate region met the documented minimum "
                "mapping unit at the recorded thresholds for this comparison."
                if not all_findings
                else None
            ),
        },
        "limitations": summary.get("limitations", []),
    }

    # Attach per-finding deterministic interpretation templates.
    ctx = {
        "experiment_id": experiment_id,
        "earlier_date": periods[0]["anchor_date"],
        "later_date": periods[1]["anchor_date"],
        "composite_method": periods[0]["composite_method"],
        "common_valid_fraction_of_aoi": payload["common_valid_fraction_of_aoi"],
        "evidence_status": payload["evidence_status"],
        "method": method["source"],
        "generated_utc": generated_utc,
    }
    for finding in payload["findings"]:
        finding["interpretation"] = _interpretation(study_id, finding, ctx)

    # Attach the versioned Evidence Record (structured measurements; the
    # explanatory interpretation stays at finding level and belongs to the
    # record by reference). Then seal each record with a checksum.
    for finding in payload["findings"]:
        sensitivity = finding.pop("_threshold_sensitivity")
        record = _evidence_record(finding, summary=summary, method=method, ctx=ctx)
        record["evidence_quality"]["threshold_sensitivity"] = sensitivity
        finding["evidence"] = record
        record["method_provenance"]["output_checksum"] = _finding_checksum(finding)

    # M4-R2 G6: overlap relationships within the experiment. Overlapping
    # measurements are recorded as related - never merged, never discarded -
    # so overlapping candidate regions are not misrepresented as independent
    # events. Rule: an equal-area UTM intersection ≥ 10 % of the smaller
    # region's area creates a link, strongest first (bounded per finding).
    _attach_relationships(payload, summary)
    for finding in payload["findings"]:
        finding["evidence"]["method_provenance"]["output_checksum"] = _finding_checksum(finding)

    out_dir = PROJECT_ROOT / "data" / "findings"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{experiment_id}.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    LOGGER.info(
        "%s: %d findings (%s) → %s",
        experiment_id,
        len(all_findings),
        ", ".join(
            f"{f['display_id']} Δ{f['index'].upper()} {f['direction']}"
            for f in all_findings
        ) or "none",
        out_path.relative_to(PROJECT_ROOT),
    )
    return len(all_findings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", action="append", choices=sorted(EXPERIMENTS))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    targets = (
        {name: EXPERIMENTS[name] for name in args.experiment}
        if args.experiment
        else EXPERIMENTS
    )
    total = 0
    for experiment_id, processed_rel in targets.items():
        total += generate(experiment_id, processed_rel)
    print(f"Generated {total} findings across {len(targets)} experiments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
