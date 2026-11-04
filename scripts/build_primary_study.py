"""M0 primary study pipeline: real Sentinel-2 acquisition, masking and NDVI.

Usage (from the repository root, inside the project venv):

    python scripts/build_primary_study.py

The script is fully deterministic given the catalogue: it writes
``data/manifests/m0_primary_study.json`` from the values it actually used, and
``scripts/reproduce_primary_study.py`` re-runs the same configuration from that
manifest.

Stages
  1. read the study + AOI from ``studies/registry.yaml``
  2. verify catalogue capability (asset keys, native GSD, scaling)
  3. search both periods, score candidates by *in-AOI* valid coverage
  4. window-read B02/B03/B04/B08/SCL on one common UTM grid
  5. mask with SCL, convert DN -> reflectance, compute NDVI
  6. intersect both masks for the comparison, write GeoTIFFs + PNG previews
  7. independently re-check sampled NDVI values against the bands
  8. write and validate the provenance manifest
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio
import yaml
from rasterio.enums import Resampling

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import config                                   # noqa: E402
from backend.app.acquisition.assets import (                     # noqa: E402
    Radiometry,
    to_reflectance,
    verify_radiometry,
)
from backend.app.acquisition.cog import (                         # noqa: E402
    WindowRequest,
    read_window,
)
from backend.app.catalog.models import SceneCandidate            # noqa: E402
from backend.app.catalog.search import SearchRequest             # noqa: E402
from backend.app.catalog.stac_client import CatalogClient        # noqa: E402
from backend.app.http import HttpSession                         # noqa: E402
from backend.app.indices import ndvi as ndvi_mod                 # noqa: E402
from backend.app.preprocess import masks as mask_mod             # noqa: E402
from backend.app.preprocess import preview                       # noqa: E402
from backend.app.preprocess.aoi import AOI, aoi_from_bounds      # noqa: E402
from backend.app.preprocess.grid import (                        # noqa: E402
    AnalysisWindow,
    analysis_window,
    aoi_raster_mask,
    assert_same_grid,
    write_geotiff,
)
from backend.app.preprocess.scoring import score_candidates      # noqa: E402
from backend.app.provenance import manifest as manifest_mod      # noqa: E402

LOGGER = logging.getLogger("build_primary_study")

STUDY_ID = "coringa_coastal"
MANIFEST_PATH = config.MANIFEST_DIR / "m0_primary_study.json"
EVIDENCE_DIR = config.DOCS_DIR / "evidence" / "m0"
OUT_PROCESSED = config.PROCESSED_DIR / STUDY_ID
OUT_PREVIEW = config.PREVIEW_DIR / STUDY_ID

#: Threshold used for the preliminary thresholded-area summary (NDVI units).
DELTA_THRESHOLD = 0.15

#: Sampling used by the independent NDVI re-check.
VERIFY_SAMPLE_SIZE = 400


@dataclass
class PeriodResult:
    """Everything measured for one observation date."""

    period_id: str
    candidate: SceneCandidate
    radiometry: dict[str, Radiometry]
    reflectance: dict[str, np.ndarray]
    valid_mask: np.ndarray
    mask_report: mask_mod.MaskReport
    ndvi: np.ndarray
    ndvi_stats: ndvi_mod.IndexStats
    outputs: dict[str, dict] = field(default_factory=dict)
    windows: dict[str, dict] = field(default_factory=dict)


def load_study(path: Path, study_id: str) -> dict:
    registry = yaml.safe_load(path.read_text(encoding="utf-8"))
    for study in registry["studies"]:
        if study["study_id"] == study_id:
            return study
    raise SystemExit(f"study {study_id!r} not found in {path}")


def make_aoi(study: dict) -> AOI:
    bounds = study["aoi"]["bounds"]
    return aoi_from_bounds(
        study_id=study["study_id"],
        west=bounds["west"],
        south=bounds["south"],
        east=bounds["east"],
        north=bounds["north"],
        description=study["aoi"].get("kind", ""),
        source=study["aoi"].get("boundary_source", ""),
    )


def pick_scene(
    client: CatalogClient,
    aoi: AOI,
    period_id: str,
    window: dict,
    *,
    search_manifest: dict,
) -> SceneCandidate:
    """Search one period and return the best AOI-valid scene."""
    start = dt.datetime.fromisoformat(window["start"] + "T00:00:00+00:00")
    end = dt.datetime.fromisoformat(window["end"] + "T23:59:59+00:00")
    request = SearchRequest(
        aoi=aoi,
        start=start,
        end=end,
        max_cloud_cover=60.0,
        limit=100,
        label=f"{period_id}:{window['start']}..{window['end']}",
    )
    result = client.search(request)
    scores = score_candidates(result.items, aoi)
    search_manifest[period_id] = {
        **result.to_dict(),
        "scores": [s.to_dict() for s in scores],
    }
    usable = [s for s in scores if s.usable]
    LOGGER.info(
        "%s: %d candidates, %d usable in-AOI", period_id, len(scores), len(usable)
    )
    if not usable:
        best = scores[0] if scores else None
        detail = best.to_dict() if best else "no candidates returned"
        raise SystemExit(
            f"no usable scene for {period_id}; best candidate: {detail}"
        )
    chosen = usable[0].item_id
    for candidate in result.items:
        if candidate.item_id == chosen:
            return candidate
    raise SystemExit(f"internal: chosen item {chosen} vanished")  # pragma: no cover


def process_period(
    candidate: SceneCandidate,
    window: AnalysisWindow,
    aoi_mask: np.ndarray,
    period_id: str,
) -> PeriodResult:
    """Read, validate, mask and index one genuinely acquired scene."""
    radiometry = verify_radiometry(candidate)
    LOGGER.info("%s: %s (%s)", period_id, candidate.item_id, candidate.date_str)

    scl_request = WindowRequest(
        dst_crs=window.crs,
        dst_transform=window.transform,
        height=window.height,
        width=window.width,
        resampling=Resampling.nearest,   # categorical: never smoothed
        dtype="int32",
    )
    scl = read_window(candidate.asset(config.ASSET_SCL).href, scl_request)
    scl_valid, scl_report = mask_mod.build_valid_mask(scl)

    reflectance: dict[str, np.ndarray] = {}
    for key in (
        config.ASSET_BLUE,
        config.ASSET_GREEN,
        config.ASSET_RED,
        config.ASSET_NIR,
    ):
        request = WindowRequest(
            dst_crs=window.crs,
            dst_transform=window.transform,
            height=window.height,
            width=window.width,
            resampling=Resampling.bilinear,   # continuous reflectance
            dtype="float32",
        )
        dn = read_window(candidate.asset(key).href, request)
        reflectance[key] = to_reflectance(dn, radiometry[key])

    finite = mask_mod.reflectance_valid_mask(
        reflectance[config.ASSET_RED], reflectance[config.ASSET_NIR]
    )
    # AOI footprint AND usable radiometry at SCL level.
    valid_mask = mask_mod.combine_masks(aoi_mask, scl_valid, finite)
    report = mask_mod.MaskReport(
        total_pixels=int(aoi_mask.sum()),
        valid_pixels=int(valid_mask.sum()),
        class_counts=scl_report.class_counts,
    )

    masked = {
        key: mask_mod.apply_mask(band, valid_mask) for key, band in reflectance.items()
    }
    index = ndvi_mod.ndvi(masked[config.ASSET_NIR], masked[config.ASSET_RED])
    index[~valid_mask] = np.nan
    stats = ndvi_mod.summarise(index, valid_mask)

    return PeriodResult(
        period_id=period_id,
        candidate=candidate,
        radiometry=radiometry,
        reflectance=masked,
        valid_mask=valid_mask,
        mask_report=report,
        ndvi=index,
        ndvi_stats=stats,
    )


def write_period_outputs(
    result: PeriodResult, window: AnalysisWindow, aoi_mask: np.ndarray
) -> dict[str, dict]:
    """Write rasters and previews for one period; return the output records."""
    stem = result.period_id
    tag = f"{stem}_{result.candidate.date_str}"
    outputs: dict[str, dict] = {}

    bands = np.stack(
        [
            result.reflectance[config.ASSET_RED],
            result.reflectance[config.ASSET_GREEN],
            result.reflectance[config.ASSET_BLUE],
            result.reflectance[config.ASSET_NIR],
        ]
    )
    band_path = write_geotiff(
        OUT_PROCESSED / f"{tag}_reflectance.tif",
        bands,
        window,
        descriptions=("red_B04", "green_B03", "blue_B02", "nir_B08"),
    )
    outputs["reflectance_tif"] = manifest_mod.describe_output(band_path, "raster")

    ndvi_path = write_geotiff(
        OUT_PROCESSED / f"{tag}_ndvi.tif",
        result.ndvi,
        window,
        descriptions=("ndvi",),
    )
    outputs["ndvi_tif"] = manifest_mod.describe_output(ndvi_path, "raster")

    mask_path = write_geotiff(
        OUT_PROCESSED / f"{tag}_valid_mask.tif",
        result.valid_mask.astype(np.uint8),
        window,
        dtype="uint8",
        nodata=0,
        descriptions=("valid",),
    )
    outputs["valid_mask_tif"] = manifest_mod.describe_output(mask_path, "raster")

    stretch = preview.stretch_bounds(
        (
            result.reflectance[config.ASSET_RED],
            result.reflectance[config.ASSET_GREEN],
            result.reflectance[config.ASSET_BLUE],
        )
    )
    result.windows["true_colour_stretch"] = stretch.to_dict()

    rgb = preview.rgb_to_png(
        result.reflectance[config.ASSET_RED],
        result.reflectance[config.ASSET_GREEN],
        result.reflectance[config.ASSET_BLUE],
        result.valid_mask,
        stretch,
        gamma=1.35,
    )
    rgb = preview.draw_aoi(rgb, aoi_mask)
    rgb_path = preview.save(rgb, OUT_PREVIEW / f"{tag}_true_colour.png")
    outputs["true_colour_png"] = manifest_mod.describe_output(rgb_path, "preview")

    ndvi_img = preview.draw_aoi(
        preview.ndvi_to_png(result.ndvi, result.valid_mask), aoi_mask
    )
    ndvi_png = preview.save(ndvi_img, OUT_PREVIEW / f"{tag}_ndvi.png")
    outputs["ndvi_png"] = manifest_mod.describe_output(ndvi_png, "preview")

    coverage = preview.draw_aoi(
        preview.coverage_to_png(result.valid_mask), aoi_mask
    )
    coverage_png = preview.save(coverage, OUT_PREVIEW / f"{tag}_valid_mask.png")
    outputs["valid_mask_png"] = manifest_mod.describe_output(coverage_png, "preview")

    return outputs


def verify_ndvi_independently(
    result: PeriodResult, window: AnalysisWindow, tag: str
) -> dict:
    """Re-derive sampled NDVI from the written band file and compare."""
    band_path = OUT_PROCESSED / f"{tag}_reflectance.tif"
    ndvi_path = OUT_PROCESSED / f"{tag}_ndvi.tif"

    with rasterio.open(band_path) as src:
        assert src.crs is not None
        red = src.read(1)
        nir = src.read(4)
    with rasterio.open(ndvi_path) as src:
        stored = src.read(1)
        stored_transform = src.transform
        stored_shape = (src.height, src.width)
        stored_crs = src.crs

    valid = result.valid_mask
    flat_valid = np.flatnonzero(valid.ravel())
    if flat_valid.size == 0:
        raise SystemExit(f"{result.period_id}: no valid pixels to verify")
    rng = np.random.default_rng(20260804)   # deterministic sample
    sample = rng.choice(
        flat_valid, size=min(VERIFY_SAMPLE_SIZE, flat_valid.size), replace=False
    )

    red_sample = red.ravel()[sample]
    nir_sample = nir.ravel()[sample]
    recomputed = (nir_sample - red_sample) / (nir_sample + red_sample)
    stored_sample = stored.ravel()[sample]
    diff = np.abs(recomputed - stored_sample)

    georef_ok = (
        stored_crs == window.crs
        and stored_shape == window.shape
        and np.allclose(np.array(stored_transform)[:6], np.array(window.transform)[:6])
    )
    masked_ok = bool(np.all(np.isnan(stored[~valid])))

    return {
        "period_id": result.period_id,
        "sample_size": int(sample.size),
        "max_abs_difference": float(diff.max()),
        "mean_abs_difference": float(diff.mean()),
        "within_tolerance": bool(diff.max() <= 1e-5),
        "georeferencing_matches_grid": georef_ok,
        "masked_pixels_are_nan": masked_ok,
    }


def write_delta(
    earlier: PeriodResult,
    later: PeriodResult,
    window: AnalysisWindow,
    aoi_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, dict], dict]:
    """Compute the common-valid delta raster, its stats and its previews."""
    common = mask_mod.combine_masks(earlier.valid_mask, later.valid_mask)
    delta = ndvi_mod.difference(later.ndvi, earlier.ndvi)
    delta[~common] = np.nan

    comparable_fraction = float(common.sum() / max(int(aoi_mask.sum()), 1))
    suitable = comparable_fraction >= config.MIN_COMPARABLE_VALID_FRACTION
    stats = ndvi_mod.summarise(delta, common)
    areas = ndvi_mod.thresholded_area(
        delta,
        common,
        threshold=DELTA_THRESHOLD,
        pixel_area_m2=window.pixel_area_m2,
    )

    outputs: dict[str, dict] = {}
    if suitable:
        delta_path = write_geotiff(
            OUT_PROCESSED / "delta_ndvi.tif", delta, window,
            descriptions=("delta_ndvi",),
        )
        outputs["delta_tif"] = manifest_mod.describe_output(delta_path, "raster")
        delta_png = preview.save(
            preview.draw_aoi(preview.ndvi_to_png(delta, common), aoi_mask),
            OUT_PREVIEW / "delta_ndvi.png",
        )
        outputs["delta_png"] = manifest_mod.describe_output(delta_png, "preview")
    common_png = preview.save(
        preview.draw_aoi(preview.coverage_to_png(common, common), aoi_mask),
        OUT_PREVIEW / "common_valid_mask.png",
    )
    outputs["common_mask_png"] = manifest_mod.describe_output(common_png, "preview")

    detail = {
        "comparable_valid_fraction": round(comparable_fraction, 6),
        "suitable_for_comparison": suitable,
        "threshold": DELTA_THRESHOLD,
        "thresholded_areas": areas,
        "delta_stats": stats.to_dict(),
        "valid_common_pixels": int(common.sum()),
        "aoi_pixels": int(aoi_mask.sum()),
        "valid_common_area_ha": round(
            common.sum() * window.pixel_area_m2 / 10_000.0, 4
        ),
        "label": "observed spectral change (NDVI difference); not a land-cover verdict",
    }
    return delta, common, outputs, detail

def build_manifest_sections(
    study: dict,
    aoi: AOI,
    window: AnalysisWindow,
    client: CatalogClient,
    search_manifest: dict,
    delta_detail: dict,
    delta_outputs: dict[str, dict],
    verifications: list[dict],
    http: HttpSession,
) -> manifest_mod.ManifestBuilder:
    """Assemble every manifest section except the per-period blocks."""
    manifest = manifest_mod.ManifestBuilder()
    manifest.update(
        {
            "study": {
                "study_id": study["study_id"],
                "title": study["title"],
                "study_type": study["study_type"],
                "question": " ".join(study["question"].split()),
                "phenomena": study["phenomena"],
                "limitations": study["limitations"],
            },
            "aoi": {
                "geojson": aoi.to_geojson(),
                "bounds_4326": list(aoi.bounds_4326),
                "crs": "EPSG:4326",
                "analysis_crs": window.crs,
                "area_km2": round(aoi.area_km2(), 6),
                "grid": {
                    "resolution_m": window.resolution,
                    "transform": list(window.transform)[:6],
                    "width": window.width,
                    "height": window.height,
                    "signature": window.signature(),
                },
            },
            "catalog": {
                "endpoint": client.catalog_url,
                "collection": client.collection,
                "provider": config.PROVIDER_NAME,
                "license": config.DATA_LICENSE,
            },
            "processing": {
                "pipeline_version": config.PIPELINE_VERSION,
                "profile": config.PROCESSING_PROFILE,
                "operations": [
                    "STAC search with AOI polygon and date range",
                    "in-AOI SCL valid-fraction scoring and selection",
                    "windowed COG read via WarpedVRT (bilinear reflectance,"
                    " nearest SCL)",
                    "radiometry verification and DN->reflectance scaling (x0.0001)",
                    "SCL masking (classes 0,1,3,8,9,10 rejected)",
                    "NDVI = (B08-B04)/(B08+B04) in float32",
                    "common-valid mask intersection across both dates",
                    "delta NDVI with thresholded area summary",
                ],
                "parameters": {
                    "analysis_profile": config.PROCESSING_PROFILE,
                    "grid_resolution_m": window.resolution,
                    "resampling_continuous": "bilinear",
                    "resampling_categorical": "nearest",
                    "scale": config.EXPECTED_SCALE,
                    "offset": config.EXPECTED_OFFSET,
                    "nodata": config.EXPECTED_NODATA,
                    "scl_accepted": list(config.SCL_VALID_CLASSES),
                    "scl_rejected": list(config.SCL_ALWAYS_INVALID),
                    "delta_threshold": DELTA_THRESHOLD,
                    "ndvi_formula": "(NIR - RED) / (NIR + RED)",
                },
            },
            "software": config.software_versions(),
            "attribution": {
                "text": config.ATTRIBUTION,
                "license": config.DATA_LICENSE,
                "access_date_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
            "validity": {
                "comparable_valid_fraction": delta_detail["comparable_valid_fraction"],
                "suitable_for_comparison": delta_detail["suitable_for_comparison"],
            },
            "delta": delta_detail,
            "search": search_manifest,
            "verification": verifications,
            "outputs": dict(delta_outputs),
            "http_requests": http.request_count,
            "bytes_downloaded": http.bytes_downloaded,
        }
    )
    return manifest



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the M0 primary study")
    parser.add_argument(
        "--registry", type=Path, default=config.STUDIES_DIR / "registry.yaml"
    )
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.force_refresh:
        for path in config.CACHE_DIR.glob("*.json"):
            path.unlink()

    study = load_study(args.registry, STUDY_ID)
    aoi = make_aoi(study)
    window = analysis_window(aoi)
    aoi_mask = aoi_raster_mask(aoi, window)
    LOGGER.info(
        "AOI %s: %.3f km2, grid %dx%d px at %.0f m, CRS %s",
        STUDY_ID, aoi.area_km2(), window.width, window.height,
        window.resolution, window.crs,
    )

    http = HttpSession(cache_dir=config.CACHE_DIR)
    client = CatalogClient(http)
    collection_meta = client.load_collection()
    LOGGER.info("collection %s verified on %s", client.collection, client.catalog_url)

    search_manifest: dict = {
        "catalog_endpoint": client.catalog_url,
        "collection": client.collection,
        "collection_license": collection_meta.get("license"),
        "usable_thresholds": {
            "min_scene_valid_fraction": config.MIN_SCENE_VALID_FRACTION,
            "min_comparable_valid_fraction": config.MIN_COMPARABLE_VALID_FRACTION,
        },
    }

    periods = study["target_periods"]
    earlier_scene = pick_scene(
        client, aoi, "earlier", periods["earlier"], search_manifest=search_manifest
    )
    later_scene = pick_scene(
        client, aoi, "later", periods["later"], search_manifest=search_manifest
    )
    if earlier_scene.item_id == later_scene.item_id:
        raise SystemExit("both periods resolved to the same STAC item")

    earlier = process_period(earlier_scene, window, aoi_mask, "earlier")
    later = process_period(later_scene, window, aoi_mask, "later")

    earlier.outputs = write_period_outputs(earlier, window, aoi_mask)
    later.outputs = write_period_outputs(later, window, aoi_mask)
    _, _common, delta_outputs, delta_detail = write_delta(
        earlier, later, window, aoi_mask
    )

    verifications = [
        verify_ndvi_independently(earlier, window, f"earlier_{earlier_scene.date_str}"),
        verify_ndvi_independently(later, window, f"later_{later_scene.date_str}"),
    ]
    LOGGER.info("NDVI re-check: %s", json.dumps(verifications))

    manifest = build_manifest_sections(
        study, aoi, window, client, search_manifest,
        delta_detail, delta_outputs, verifications, http,
    )
    for result in (earlier, later):
        manifest.data.setdefault("periods", []).append(
            {
                "period_id": result.period_id,
                "acquisition_date": result.candidate.date_str,
                "acquisition_utc": result.candidate.acquisition_iso,
                "scene": result.candidate.to_provenance(),
                "valid_fraction": round(result.mask_report.valid_fraction, 6),
                "mask_policy": result.mask_report.to_dict(),
                "radiometry": {k: v.to_dict() for k, v in result.radiometry.items()},
                "window_rendering": result.windows,
                "index_stats": result.ndvi_stats.to_dict(),
                "outputs": result.outputs,
            }
        )

    manifest.write(MANIFEST_PATH)
    LOGGER.info("manifest written to %s", config.relative(MANIFEST_PATH))

    summary = {
        "study_id": study["study_id"],
        "title": study["title"],
        "study_type": study["study_type"],
        "periods": [
            {
                "period_id": r.period_id,
                "date": r.candidate.date_str,
                "item_id": r.candidate.item_id,
                "valid_fraction": round(r.mask_report.valid_fraction, 6),
                "cloud_cover_percent": r.candidate.cloud_cover,
                "ndvi_stats": r.ndvi_stats.to_dict(),
                "png": r.outputs["true_colour_png"]["path"],
                "ndvi_png": r.outputs["ndvi_png"]["path"],
                "mask_png": r.outputs["valid_mask_png"]["path"],
                "reflectance_tif": r.outputs["reflectance_tif"]["path"],
            }
            for r in (earlier, later)
        ],
        "delta": delta_detail,
        "grid": window.to_dict(),
        "attribution": config.ATTRIBUTION,
        "verification": verifications,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    summary_path = OUT_PROCESSED / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    LOGGER.info("summary written to %s", config.relative(summary_path))

    ok = all(
        v["within_tolerance"] and v["georeferencing_matches_grid"]
        and v["masked_pixels_are_nan"]
        for v in verifications
    )
    LOGGER.info("scientific re-check: %s", "PASS" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
