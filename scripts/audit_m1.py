"""Independent numerical audit of an M1 study bundle.

This script re-derives every headline number from the exported GeoTIFFs and
checks it against ``summary.json`` and the reproducibility manifest.  It does
not import the processing engine, so a bug in the engine cannot validate
itself here.

Usage (from the repository root, inside the project venv):

    python scripts/audit_m1.py --study coringa_coastal
    python scripts/audit_m1.py --study coringa_coastal --json

Exit codes: 0 all checks pass, 2 at least one check fails, 1 the bundle is
missing or unreadable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import config  # noqa: E402

PIXEL_AREA_M2 = 100.0
M2_PER_HA = 10_000.0
M2_PER_KM2 = 1_000_000.0

#: Band description -> role, exactly as the engine exported them.
ROLE_BY_DESCRIPTION = {
    "blue_B02": "blue",
    "green_B03": "green",
    "red_B04": "red",
    "nir_B08": "nir",
    "swir1_B11": "swir16",
}

#: Independent formulas, repeated here so the audit does not share registry
#: code with the engine.
FORMULAS = {
    "ndvi": ("nir", "red"),
    "ndwi": ("green", "nir"),
    "mndwi": ("green", "swir16"),
}


def _read(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    with rasterio.open(path) as src:
        return src.read(1), {
            "crs": src.crs.to_string() if src.crs else None,
            "transform": tuple(src.transform)[:6],
            "shape": (src.height, src.width),
            "dtype": src.dtypes[0],
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(results: list[dict], name: str, passed: bool, details: dict | None = None):
    results.append({"check": name, "passed": bool(passed), "details": details or {}})
    return passed


def audit(study_id: str) -> dict[str, Any]:
    processed = config.PROCESSED_M1_DIR / study_id
    summary_path = processed / "summary.json"
    manifest_path = config.MANIFEST_DIR / f"m1_{study_id}.json"
    if not summary_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(
            f"missing bundle for {study_id!r}: run scripts/run_study.py first"
        )
    summary = json.loads(summary_path.read_text("utf-8"))
    manifest = json.loads(manifest_path.read_text("utf-8"))
    results: list[dict] = []

    # -- manifest hashes ---------------------------------------------------- #
    hash_failures = []
    for name, record in (manifest.get("outputs") or {}).items():
        path = config.PROJECT_ROOT / record["path"]
        if not path.exists():
            hash_failures.append(f"{name}:missing")
            continue
        if _sha256(path) != record["sha256"]:
            hash_failures.append(f"{name}:hash")
        elif path.stat().st_size != record["bytes"]:
            hash_failures.append(f"{name}:bytes")
    _check(
        results,
        "manifest_output_hashes",
        not hash_failures,
        {"outputs": len(manifest.get("outputs") or {}), "failures": hash_failures},
    )

    # -- grid consistency --------------------------------------------------- #
    rasters = sorted(processed.glob("*.tif"))
    grids = {path.name: _read(path)[1] for path in rasters}
    reference = grids[rasters[0].name]
    mismatched = [
        name
        for name, grid in grids.items()
        if grid["crs"] != reference["crs"]
        or grid["shape"] != reference["shape"]
        or not np.allclose(grid["transform"], reference["transform"], atol=1e-9)
    ]
    _check(
        results,
        "grid_consistency",
        not mismatched,
        {
            "rasters": len(rasters),
            "crs": reference["crs"],
            "shape": list(reference["shape"]),
            "mismatched": mismatched,
        },
    )
    _check(
        results,
        "grid_matches_summary",
        reference["crs"] == summary["grid"]["crs"]
        and list(reference["shape"])
        == [summary["grid"]["height"], summary["grid"]["width"]],
        {"summary_signature": summary["grid"]["signature"]},
    )

    # -- period index recomputation ---------------------------------------- #
    for period in summary["periods"]:
        period_id = period["period_id"]
        tag = f"{period_id}_{period['anchor_date']}"
        band_path = processed / f"{tag}_reflectance_composite.tif"
        with rasterio.open(band_path) as src:
            roles = {
                ROLE_BY_DESCRIPTION[description]: src.read(index)
                for index, description in enumerate(src.descriptions, start=1)
            }
        valid = roles["nir"] == roles["nir"]  # finite check below
        valid = np.isfinite(roles["red"]) & np.isfinite(roles["green"])
        valid &= np.isfinite(roles["nir"]) & np.isfinite(roles["swir16"])

        for key, (first, second) in FORMULAS.items():
            with np.errstate(divide="ignore", invalid="ignore"):
                recomputed = (roles[first] - roles[second]) / (
                    roles[first] + roles[second]
                )
            recomputed = np.where(valid & np.isfinite(recomputed), recomputed, np.nan)
            exported, _ = _read(processed / f"{tag}_{key}.tif")
            common = np.isfinite(recomputed) & np.isfinite(exported)
            max_diff = float(np.nanmax(np.abs(recomputed[common] - exported[common])))
            stats = period["indices"][key]["stats"]
            mean_diff = abs(float(np.nanmean(recomputed)) - stats["mean"])
            _check(
                results,
                f"index_recompute_{period_id}_{key}",
                max_diff <= 2e-5 and mean_diff <= 2e-5,
                {
                    "pixels": int(common.sum()),
                    "max_abs_pixel_difference": round(max_diff, 9),
                    "mean_difference": round(mean_diff, 9),
                },
            )

        # -- observation accounting ----------------------------------------- #
        counts, _ = _read(processed / f"{tag}_observation_count.tif")
        valid_mask, _ = _read(processed / f"{tag}_valid_mask.tif")
        _check(
            results,
            f"observation_count_{period_id}",
            bool(np.array_equal(counts > 0, valid_mask.astype(bool))),
            {
                "valid_pixels": int(valid_mask.sum()),
                "count_min": int(counts[valid_mask.astype(bool)].min()),
                "count_max": int(counts.max()),
                "mean_count": round(float(counts[valid_mask.astype(bool)].mean()), 6),
            },
        )
        _check(
            results,
            f"valid_fraction_{period_id}",
            abs(
                period["valid_fraction"]
                - int(valid_mask.sum()) / int(summary["aoi"]["aoi_pixels"])
            )
            <= 1e-9,
            {
                "valid_fraction": period["valid_fraction"],
                "valid_fraction_of_grid": period["valid_fraction_of_grid"],
            },
        )

    # -- change recomputation ---------------------------------------------- #
    earlier = summary["periods"][0]
    later = summary["periods"][1]
    for key, block in (summary["change"] or {}).items():
        early, _ = _read(
            processed / f"{earlier['period_id']}_{earlier['anchor_date']}_{key}.tif"
        )
        late, _ = _read(
            processed / f"{later['period_id']}_{later['anchor_date']}_{key}.tif"
        )
        delta, _ = _read(processed / f"delta_{key}.tif")
        common = np.isfinite(early) & np.isfinite(late)
        recomputed = late - early
        diff = np.abs(recomputed[common] - delta[common])
        _check(
            results,
            f"delta_recompute_{key}",
            float(np.nanmax(diff)) <= 1e-6 and int(common.sum()) == block["common_valid_pixels"],
            {
                "common_valid_pixels": int(common.sum()),
                "max_abs_pixel_difference": round(float(np.nanmax(diff)), 9),
            },
        )

        values = delta[np.isfinite(delta)]
        threshold = float(block["primary_threshold"])
        decrease = int(np.count_nonzero(values <= -threshold))
        increase = int(np.count_nonzero(values >= threshold))
        primary = block["primary"]
        areas_ok = (
            abs(decrease * PIXEL_AREA_M2 / M2_PER_HA - primary["decrease_area_ha"]) <= 1e-4
            and abs(increase * PIXEL_AREA_M2 / M2_PER_HA - primary["increase_area_ha"]) <= 1e-4
            and abs(
                values.size * PIXEL_AREA_M2 / M2_PER_HA - block["common_valid_area_ha"]
            )
            <= 1e-4
        )
        conservation = (
            int(primary["decrease_pixels"])
            + int(primary["increase_pixels"])
            + int(primary["stable_pixels"])
            == int(primary["valid_pixels"])
            == values.size
        )
        percent_ok = (
            abs(
                primary["increase_percent_of_common"]
                - 100.0 * increase / values.size
            )
            <= 1e-5
            and abs(
                primary["decrease_percent_of_common"]
                - 100.0 * decrease / values.size
            )
            <= 1e-5
        )
        _check(
            results,
            f"threshold_counts_and_areas_{key}",
            decrease == primary["decrease_pixels"]
            and increase == primary["increase_pixels"]
            and areas_ok
            and conservation
            and percent_ok,
            {
                "threshold": threshold,
                "valid_pixels": int(values.size),
                "decrease_pixels": decrease,
                "increase_pixels": increase,
                "decrease_ha": round(decrease * PIXEL_AREA_M2 / M2_PER_HA, 4),
                "increase_ha": round(increase * PIXEL_AREA_M2 / M2_PER_HA, 4),
                "common_valid_area_ha": block["common_valid_area_ha"],
            },
        )

    # -- area cross-check --------------------------------------------------- #
    areas = summary["area_cross_check"]
    _check(
        results,
        "area_cross_check",
        areas["raster_vs_projected_relative_difference"] < 1e-3
        and areas["geodesic_vs_projected_relative_difference"] < 1e-3
        and abs(
            areas["aoi_raster_km2"]
            - summary["aoi"]["aoi_pixels"] * PIXEL_AREA_M2 / M2_PER_KM2
        )
        <= 1e-6,
        {
            "projected_km2": areas["aoi_polygon_projected_km2"],
            "geodesic_km2": areas["aoi_polygon_geodesic_km2"],
            "raster_km2": areas["aoi_raster_km2"],
        },
    )

    # -- provenance agreement ---------------------------------------------- #
    manifest_periods = {p["period_id"]: p for p in manifest["periods"]}
    provenance_ok = all(
        period["item_ids"] == manifest_periods[period["period_id"]]["item_ids"]
        and period["observation_dates"]
        == manifest_periods[period["period_id"]]["observation_dates"]
        for period in summary["periods"]
    )
    _check(
        results,
        "summary_manifest_scene_agreement",
        provenance_ok and manifest["grid"]["signature"] == summary["grid"]["signature"],
        {
            "periods": {
                period["period_id"]: period["item_ids"] for period in summary["periods"]
            }
        },
    )
    _check(
        results,
        "engine_verification_passed",
        summary["verification"]["all_passed"]
        and manifest["verification"]["all_passed"],
        {
            "check_count": summary["verification"]["check_count"],
            "failed": summary["verification"]["failed_checks"],
        },
    )

    return {
        "study_id": study_id,
        "summary_path": config.relative(summary_path),
        "manifest_path": config.relative(manifest_path),
        "checks": results,
        "all_passed": all(check["passed"] for check in results),
        "check_count": len(results),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independently audit an M1 bundle")
    parser.add_argument("--study", default="coringa_coastal")
    parser.add_argument("--json", action="store_true", help="print the full report")
    args = parser.parse_args(argv)

    try:
        report = audit(args.study)
    except FileNotFoundError as exc:
        print(f"audit failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for check in report["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"{mark}  {check['check']}")
            if not check["passed"]:
                print(f"      {json.dumps(check['details'])}")
        print(
            f"\n{report['check_count']} checks, "
            f"{'all passed' if report['all_passed'] else 'FAILURES PRESENT'}"
        )
    return 0 if report["all_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
