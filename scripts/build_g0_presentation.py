"""Build presentation-only validity assets for the M2-G0 comparison repair.

The M1 bundle already contains the authoritative valid-mask, observation-count
and common-valid rasters.  This script derives neutral, non-copper previews and
transparent invalid-pixel overlays from those rasters for the proof viewer.

It never writes into ``data/processed/m1`` or ``data/previews/m1``, never edits
the M1 summary or manifest, and never fills a masked pixel as if an observation
existed.  Every reported count is read back from the exported rasters and
cross-checked against the frozen M1 summary before anything is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.warp import transform_geom

if __package__ in (None, ""):  # direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import config  # noqa: E402

PRESENTATION_VERSION = "g0-1.0"

#: Neutral validity palette.  Copper is deliberately absent: copper already
#: means "higher later index" on the change maps.
VALID_RGB = (143, 176, 170)
INVALID_RGB = (24, 39, 45)
BOUNDARY_RGB = (95, 112, 108)
PAPER_RGB = (236, 233, 225)
HATCH_BASE = (176, 188, 183, 90)
HATCH_LINE = (224, 230, 226, 205)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_mask(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1) > 0


def _grid_from(path: Path) -> dict[str, object]:
    with rasterio.open(path) as src:
        return {
            "crs": src.crs.to_string() if src.crs else None,
            "width": src.width,
            "height": src.height,
            "transform": list(src.transform)[:6],
        }


def _aoi_mask(summary: dict, shape: tuple[int, int]) -> np.ndarray:
    grid = summary["grid"]
    geometry = summary["aoi"]["geojson"]
    if geometry.get("type") == "Feature":
        geometry = geometry["geometry"]
    projected = transform_geom("EPSG:4326", grid["crs"], geometry)
    mask = rasterize(
        [(projected, 1)],
        out_shape=shape,
        transform=Affine(*grid["transform"]),
        fill=0,
        all_touched=False,
        dtype="uint8",
    ).astype(bool)
    expected = int(summary["aoi"]["aoi_pixels"])
    actual = int(mask.sum())
    if actual != expected:
        raise RuntimeError(
            f"AOI rasterisation mismatch: rasterised {actual} px, summary says {expected} px"
        )
    return mask


def _boundary(mask: np.ndarray) -> np.ndarray:
    border = np.zeros(mask.shape, dtype=bool)
    border[:, 1:] |= mask[:, 1:] & ~mask[:, :-1]
    border[1:, :] |= mask[1:, :] & ~mask[:-1, :]
    return border


def _neutral_mask(valid: np.ndarray, aoi: np.ndarray) -> Image.Image:
    rgb = np.empty((*valid.shape, 3), dtype=np.uint8)
    rgb[:, :] = np.array(INVALID_RGB, dtype=np.uint8)
    rgb[valid] = np.array(VALID_RGB, dtype=np.uint8)
    rgb[_boundary(aoi)] = np.array(BOUNDARY_RGB, dtype=np.uint8)
    return Image.fromarray(rgb, mode="RGB")


def _masked_preview(valid: np.ndarray, aoi: np.ndarray) -> Image.Image:
    """Light canvas with masked pixels in neutral charcoal plus a hatch."""
    invalid = ~valid
    yy, xx = np.indices(valid.shape)
    hatch = ((xx + yy) % 8) < 2
    rgb = np.empty((*valid.shape, 3), dtype=np.uint8)
    rgb[:, :] = np.array(PAPER_RGB, dtype=np.uint8)
    rgb[invalid] = np.array(INVALID_RGB, dtype=np.uint8)
    rgb[invalid & hatch] = np.array((196, 206, 201), dtype=np.uint8)
    rgb[_boundary(aoi)] = np.array(BOUNDARY_RGB, dtype=np.uint8)
    return Image.fromarray(rgb, mode="RGB")


def _invalid_overlay(valid: np.ndarray) -> Image.Image:
    """Transparent where valid; a neutral hatch over unavailable pixels."""
    invalid = ~valid
    yy, xx = np.indices(valid.shape)
    hatch = ((xx + yy) % 8) < 2
    rgba = np.zeros((*valid.shape, 4), dtype=np.uint8)
    rgba[invalid] = np.array(HATCH_BASE, dtype=np.uint8)
    rgba[invalid & hatch] = np.array(HATCH_LINE, dtype=np.uint8)
    return Image.fromarray(rgba, mode="RGBA")


def _histogram(counts: np.ndarray) -> dict[str, int]:
    """Full-grid observation-count distribution, including 0 for masked pixels."""
    values, frequencies = np.unique(counts, return_counts=True)
    return {str(int(value)): int(frequency) for value, frequency in zip(values, frequencies)}


def _write(image: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    return path


def _resolve(study_id: str, processed_dir: Path | None) -> tuple[Path, Path]:
    processed = processed_dir or (config.PROCESSED_M1_DIR / study_id)
    summary_path = processed / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(
            f"M1 summary not found at {config.relative(summary_path)}; run the M1 study first"
        )
    return processed, summary_path


def build_presentation(
    study_id: str,
    *,
    processed_dir: Path | None = None,
    out_dir: Path | None = None,
    force: bool = False,
) -> dict[str, object]:
    """Derive neutral validity previews and report the measured coverage."""
    processed, summary_path = _resolve(study_id, processed_dir)
    summary = json.loads(summary_path.read_text("utf-8"))
    output = out_dir or (config.PREVIEW_G0_DIR / study_id)

    expected_names = {
        "earlier_valid.png",
        "later_valid.png",
        "common_valid.png",
        "masked_common.png",
        "earlier_invalid.png",
        "later_invalid.png",
        "common_invalid.png",
        "quality.json",
    }
    existing = {path.name for path in output.iterdir()} if output.is_dir() else set()
    if existing & expected_names and not force:
        raise FileExistsError(
            f"presentation assets already exist in {config.relative(output)}; "
            "pass --force to regenerate them"
        )

    periods = summary.get("periods") or []
    if len(periods) < 2:
        raise RuntimeError("M1 summary must contain two periods")
    earlier, later = periods[0], periods[1]

    earlier_path = processed / f"{earlier['period_id']}_{earlier['anchor_date']}_valid_mask.tif"
    later_path = processed / f"{later['period_id']}_{later['anchor_date']}_valid_mask.tif"
    block = (summary.get("change") or {}).get("ndvi") or next(
        iter((summary.get("change") or {}).values()), None
    )
    if not block:
        raise RuntimeError("M1 summary has no change block")
    common_path = config.PROJECT_ROOT / block["common_valid_tif"]
    earlier_count_path = (
        processed / f"{earlier['period_id']}_{earlier['anchor_date']}_observation_count.tif"
    )
    later_count_path = (
        processed / f"{later['period_id']}_{later['anchor_date']}_observation_count.tif"
    )

    for path in (earlier_path, later_path, common_path):
        if not path.exists():
            raise FileNotFoundError(f"required raster missing: {config.relative(path)}")

    earlier_valid = _read_mask(earlier_path)
    later_valid = _read_mask(later_path)
    common_valid = _read_mask(common_path)
    shape = earlier_valid.shape
    if later_valid.shape != shape or common_valid.shape != shape:
        raise RuntimeError("valid-mask rasters do not share one grid")
    grid = _grid_from(earlier_path)
    if (grid["height"], grid["width"]) != shape:
        raise RuntimeError("raster shape disagrees with its own GeoTIFF header")
    if grid["crs"] != summary["grid"]["crs"]:
        raise RuntimeError("valid-mask CRS disagrees with the M1 summary grid")
    if not np.allclose(grid["transform"], summary["grid"]["transform"], atol=1e-6, rtol=0):
        raise RuntimeError("valid-mask transform disagrees with the M1 summary grid")

    aoi = _aoi_mask(summary, shape)
    common_expected = earlier_valid & later_valid
    if not np.array_equal(common_valid, common_expected):
        raise RuntimeError("common-valid raster is not the intersection of the two period masks")

    measured = {
        "aoi_pixels": int(aoi.sum()),
        "grid_pixels": int(shape[0] * shape[1]),
        "earlier_valid_pixels": int(earlier_valid.sum()),
        "later_valid_pixels": int(later_valid.sum()),
        "common_valid_pixels": int(common_valid.sum()),
        "masked_pixels": int((~common_valid).sum()),
    }
    checks = {
        "earlier_valid": (measured["earlier_valid_pixels"], int(earlier.get("valid_pixels", -1))),
        "later_valid": (measured["later_valid_pixels"], int(later.get("valid_pixels", -1))),
        "common_valid": (
            measured["common_valid_pixels"],
            int(block.get("common_valid_pixels", -1)),
        ),
        "aoi": (measured["aoi_pixels"], int(summary["aoi"]["aoi_pixels"])),
    }
    mismatches = {
        name: {"raster": actual, "summary": expected}
        for name, (actual, expected) in checks.items()
        if actual != expected
    }
    if mismatches:
        raise RuntimeError(f"raster/summary count mismatch: {mismatches}")

    observation_counts: dict[str, dict[str, int]] = {}
    source_paths = {
        "earlier_valid_mask": earlier_path,
        "later_valid_mask": later_path,
        "common_valid_mask": common_path,
    }
    for key, count_path in (
        ("earlier", earlier_count_path),
        ("later", later_count_path),
    ):
        if count_path.exists():
            with rasterio.open(count_path) as src:
                counts = src.read(1)
            if counts.shape != shape:
                raise RuntimeError(f"{key} observation-count raster does not share the grid")
            observation_counts[key] = _histogram(counts)
            source_paths[f"{key}_observation_count"] = count_path

    written: dict[str, Path] = {}
    written["earlier_valid.png"] = _write(
        _neutral_mask(earlier_valid, aoi), output / "earlier_valid.png"
    )
    written["later_valid.png"] = _write(
        _neutral_mask(later_valid, aoi), output / "later_valid.png"
    )
    written["common_valid.png"] = _write(
        _neutral_mask(common_valid, aoi), output / "common_valid.png"
    )
    written["masked_common.png"] = _write(
        _masked_preview(common_valid, aoi), output / "masked_common.png"
    )
    written["earlier_invalid.png"] = _write(
        _invalid_overlay(earlier_valid), output / "earlier_invalid.png"
    )
    written["later_invalid.png"] = _write(
        _invalid_overlay(later_valid), output / "later_invalid.png"
    )
    written["common_invalid.png"] = _write(
        _invalid_overlay(common_valid), output / "common_invalid.png"
    )

    coverage = {
        **measured,
        "earlier_valid_fraction_of_aoi": measured["earlier_valid_pixels"] / measured["aoi_pixels"],
        "later_valid_fraction_of_aoi": measured["later_valid_pixels"] / measured["aoi_pixels"],
        "common_valid_fraction_of_aoi": measured["common_valid_pixels"] / measured["aoi_pixels"],
        "uniform_common": bool(
            measured["earlier_valid_pixels"]
            == measured["later_valid_pixels"]
            == measured["common_valid_pixels"]
            == measured["aoi_pixels"]
        ),
        "uniform_note": (
            "All AOI pixels are valid in both periods; a uniform common-valid "
            "footprint is mathematically expected, not a rendering defect."
            if measured["earlier_valid_pixels"]
            == measured["later_valid_pixels"]
            == measured["common_valid_pixels"]
            == measured["aoi_pixels"]
            else "At least one AOI pixel is unavailable in one or both periods."
        ),
    }

    quality = {
        "presentation_version": PRESENTATION_VERSION,
        "study_id": study_id,
        "source_summary_generated_utc": summary.get("generated_utc"),
        "grid": summary["grid"],
        "coverage": coverage,
        "observation_counts": observation_counts,
        "mask_previews": {
            name: config.relative(path)
            for name, path in written.items()
            if name.endswith("_valid.png") or name == "masked_common.png"
        },
        "overlay_previews": {
            name: config.relative(path)
            for name, path in written.items()
            if name.endswith("_invalid.png")
        },
        "sources": {name: config.relative(path) for name, path in source_paths.items()},
        "source_sha256": {name: _sha256(path) for name, path in source_paths.items()},
    }
    quality_path = output / "quality.json"
    quality["artifact_sha256"] = {
        name: _sha256(path) for name, path in written.items()
    }
    quality_path.write_text(
        json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return quality


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", default="coringa_coastal", help="M1 study id")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=None,
        help="override the processed M1 study directory",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="override the presentation output directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="regenerate assets that already exist (never silent)",
    )
    args = parser.parse_args(argv)

    try:
        result = build_presentation(
            args.study,
            processed_dir=args.processed_dir,
            out_dir=args.out,
            force=args.force,
        )
    except (FileExistsError, FileNotFoundError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    coverage = result["coverage"]
    print(
        f"Wrote presentation assets for {args.study}: "
        f"{coverage['common_valid_pixels']} common-valid px "
        f"({coverage['common_valid_fraction_of_aoi']:.1%} of AOI), "
        f"{coverage['masked_pixels']} masked px"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
