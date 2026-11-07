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
(schema ``habitatshift-findings/1``). The bundle builder embeds this file per
experiment so map overlays and descriptions use exactly these measurements.

Usage:
    python scripts/generate_findings.py               # all experiments
    python scripts/generate_findings.py --experiment kathmandu_m4
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
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


def _polygon_wgs84(ring_utm: list[tuple[float, float]], transformer) -> list[list[float]]:
    return [
        [round(lon, 6), round(lat, 6)]
        for lon, lat in (transformer.transform(x, y) for x, y in ring_utm)
    ]


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
            utm_ring = geometry["coordinates"][0]
            xs = [point[0] for point in utm_ring]
            ys = [point[1] for point in utm_ring]
            centroid_x, centroid_y = float(np.mean(xs)), float(np.mean(ys))
            centroid_lon, centroid_lat = to_wgs84.transform(centroid_x, centroid_y)
            wgs_ring = _polygon_wgs84(utm_ring, to_wgs84)
            display_id = f"Region {next(counter):02d}"
            findings.append(
                {
                    "id": display_id.lower().replace(" ", "_"),
                    "display_id": display_id,
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
                    "centroid_utm": [round(centroid_x, 2), round(centroid_y, 2)],
                    "centroid_lonlat": [round(centroid_lon, 6), round(centroid_lat, 6)],
                    "geometry_wgs84": {
                        "type": "Polygon",
                        "coordinates": [wgs_ring],
                    },
                    "input_raster": str(delta_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                    "valid_mask": str(common_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                }
            )

    index_stats = {
        "threshold": threshold,
        "common_valid_pixels": common_valid_pixels,
        "decrease_pixels_total": totals.get("decrease", 0),
        "increase_pixels_total": totals.get("increase", 0),
    }
    return findings, index_stats


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
    payload = {
        "schema": "habitatshift-findings/1",
        "study_id": study_id,
        "experiment_id": experiment_id,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence_status": summary.get("evidence_status", "processed"),
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
    }
    for finding in payload["findings"]:
        finding["interpretation"] = _interpretation(study_id, finding, ctx)

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
