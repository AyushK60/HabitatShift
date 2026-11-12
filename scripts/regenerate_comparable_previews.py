"""Regenerate colour-composite previews with a joint two-period stretch (M4-R1 §8).

The M1 engine stretched each period's colour composites independently
(per-band 2–98 percentile on that period's valid pixels). For a direct
earlier/later visual comparison that is misleading: identical reflectance maps
to different brightness in the two images, so the later period can read as
darker (or lighter) for purely presentational reasons. Kathmandu's recorded
stretch windows differ by ~15 % between its 2020 and 2025 composites — a
verified presentation problem, not a scientific one.

This script re-renders ONLY the true-colour and false-colour preview PNGs from
the frozen reflectance composites, using ONE joint per-band 2–98 percentile
stretch computed over both periods' valid pixels. Every analytical raster
(indices, delta rasters, masks, counts) is untouched, and the rendering code,
gamma values and AOI outline are exactly the engine's own. The joint bounds
replace the per-period bounds in the run summary and run manifest so the
recorded provenance keeps describing the displayed artefacts.

Coringa is deliberately excluded: its M0–M2 evidence is the frozen reference
case verified by verification/audit_m2.py.

After running, rebuild the showcase bundles
(``python scripts/build_showcase_bundles.py``) so the bundled copies and their
SHA-256 checksums refresh.

Usage:
    python scripts/regenerate_comparable_previews.py            # all M4 studies
    python scripts/regenerate_comparable_previews.py --experiment kathmandu_m4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rasterio                                                      # noqa: E402
from rasterio.features import geometry_mask                          # noqa: E402

from backend.app.preprocess import preview as preview_mod            # noqa: E402

LOGGER = logging.getLogger("regenerate_comparable_previews")

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: M4 experiment directories (Coringa's frozen reference case is excluded).
M4_EXPERIMENTS = [
    "chilika_m4_dry",
    "chilika_m4_postmonsoon",
    "western_ghats_m4",
    "himalaya_purepu_2025_m4",
    "himalaya_langtang_2026_m4",
    "kathmandu_m4",
]

JOINT_METHOD = (
    "joint per-band 2-98 percentile linear stretch over both periods' valid "
    "pixels (M4-R1 §8: consistent stretch for direct visual comparison)"
)


def load_band(src: rasterio.DatasetReader, description: str) -> np.ndarray:
    for index, name in enumerate(src.descriptions, start=1):
        if name == description:
            return src.read(index).astype(np.float64)
    raise KeyError(f"band {description!r} not in {src.description}")


def load_valid(processed_dir: Path, tag: str) -> np.ndarray:
    with rasterio.open(processed_dir / f"{tag}_valid_mask.tif") as src:
        return src.read(1).astype(bool)


def aoi_mask_for(summary: dict[str, Any]) -> np.ndarray:
    """Rasterise the summary's AOI polygon onto the analysis grid."""
    from pyproj import CRS, Transformer
    from shapely.geometry import shape
    from shapely.ops import transform as shapely_transform

    grid = summary["grid"]
    aoi = summary["aoi"]["geojson"]
    feature = (
        aoi["features"][0] if aoi.get("type") == "FeatureCollection" else aoi
    )
    utm_epsg = int(grid["crs"].removeprefix("EPSG:"))
    transformer = Transformer.from_crs(
        CRS.from_epsg(4326), CRS.from_epsg(utm_epsg), always_xy=True
    )
    projected = shapely_transform(transformer.transform, shape(feature["geometry"]))
    return geometry_mask(
        [projected],
        out_shape=(grid["height"], grid["width"]),
        transform=tuple(grid["transform"]),
        invert=True,
    )


def joint_stretch(
    band_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> preview_mod.Stretch:
    """Per-band 2–98 percentile bounds over BOTH periods' valid pixels."""
    lows, highs = [], []
    for earlier, later in band_pairs:
        finite = np.concatenate(
            (earlier[np.isfinite(earlier)], later[np.isfinite(later)])
        )
        if finite.size == 0:
            lows.append(0.0)
            highs.append(0.15)
            continue
        lows.append(float(np.percentile(finite, 2.0)))
        highs.append(float(np.percentile(finite, 98.0)))
    return preview_mod.Stretch(low=tuple(lows), high=tuple(highs), gamma=1.0)


def regenerate_experiment(experiment_id: str) -> bool:
    processed_dir = PROJECT_ROOT / "data" / "processed" / "m4" / experiment_id
    summary_path = processed_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    preview_dir = PROJECT_ROOT / "data" / "previews" / "m4" / experiment_id
    mask = aoi_mask_for(summary)
    periods = summary["periods"]
    if len(periods) != 2:
        LOGGER.warning("%s: expected 2 periods, found %s", experiment_id, len(periods))
        return False

    def read_reflectance(tag: str) -> dict[str, np.ndarray]:
        path = processed_dir / f"{tag}_reflectance_composite.tif"
        with rasterio.open(path) as src:
            return {name: load_band(src, name) for name in src.descriptions}

    earlier = periods[0]
    later = periods[1]
    tag_e = f"{earlier['period_id']}_{earlier['anchor_date']}"
    tag_l = f"{later['period_id']}_{later['anchor_date']}"
    bands_e = read_reflectance(tag_e)
    bands_l = read_reflectance(tag_l)
    valid_e = load_valid(processed_dir, tag_e)
    valid_l = load_valid(processed_dir, tag_l)

    # Joint bounds: one stretch per composite, computed over both periods.
    true_stretch = joint_stretch(
        [
            (bands_e["red_B04"][valid_e], bands_l["red_B04"][valid_l]),
            (bands_e["green_B03"][valid_e], bands_l["green_B03"][valid_l]),
            (bands_e["blue_B02"][valid_e], bands_l["blue_B02"][valid_l]),
        ]
    )
    false_stretch = joint_stretch(
        [
            (bands_e["nir_B08"][valid_e], bands_l["nir_B08"][valid_l]),
            (bands_e["red_B04"][valid_e], bands_l["red_B04"][valid_l]),
            (bands_e["green_B03"][valid_e], bands_l["green_B03"][valid_l]),
        ]
    )

    rendered = 0
    for period, tag, valid, band_set in (
        (earlier, tag_e, valid_e, bands_e),
        (later, tag_l, valid_l, bands_l),
    ):
        for key, image, stretch in (
            (
                "true_colour",
                preview_mod.rgb_to_png(
                    band_set["red_B04"],
                    band_set["green_B03"],
                    band_set["blue_B02"],
                    valid,
                    true_stretch,
                    gamma=1.35,
                ),
                true_stretch,
            ),
            (
                "false_colour",
                preview_mod.false_colour_png(
                    band_set["nir_B08"],
                    band_set["red_B04"],
                    band_set["green_B03"],
                    valid,
                    false_stretch,
                    gamma=1.2,
                ),
                false_stretch,
            ),
        ):
            outlined = preview_mod.draw_aoi(image, mask)
            out_path = preview_dir / f"{tag}_{key}.png"
            preview_mod.save(outlined, out_path)
            period["stretch"][key] = {**stretch.to_dict(), "method": JOINT_METHOD}
            rendered += 1

    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    # Keep the run manifest's recorded stretch consistent with the artefacts.
    manifest_path = PROJECT_ROOT / "data" / "manifests" / f"m4_{experiment_id}.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for manifest_period, summary_period in zip(
            manifest.get("periods", []), periods
        ):
            if manifest_period.get("period_id") == summary_period["period_id"]:
                manifest_period["stretch"] = summary_period["stretch"]
        # Every artefact rewritten above must also have its recorded bytes and
        # SHA-256 refreshed, so the manifest's outputs section keeps matching
        # the files on disk (the M5 audit verifies this).
        rewritten = {
            "summary_json": summary_path,
        }
        for manifest_period, summary_period in zip(manifest.get("periods", []), periods):
            tag = manifest_period.get("period_id")
            if tag != summary_period["period_id"]:
                continue
            for key in ("true_colour", "false_colour"):
                preview_path = preview_dir / f"{tag}_{key}.png"
                if preview_path.exists():
                    rewritten[f"{tag}_{key}_png"] = preview_path
        refreshed = 0
        for name, meta in manifest.get("outputs", {}).items():
            source = rewritten.get(name)
            if source is None:
                continue
            payload = source.read_bytes()
            meta["bytes"] = len(payload)
            meta["sha256"] = hashlib.sha256(payload).hexdigest()
            refreshed += 1
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        if refreshed != len(rewritten):
            LOGGER.warning(
                "%s: refreshed %d/%d output checksums (manifest output names may differ)",
                experiment_id,
                refreshed,
                len(rewritten),
            )

    LOGGER.info(
        "%s: re-rendered %d composites with joint stretch "
        "(true high=%s, false high=%s)",
        experiment_id,
        rendered,
        [round(v, 4) for v in true_stretch.high],
        [round(v, 4) for v in false_stretch.high],
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--experiment",
        action="append",
        choices=M4_EXPERIMENTS,
        help="limit to one experiment (default: all M4 experiments)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    experiments = args.experiment or M4_EXPERIMENTS
    ok = all(regenerate_experiment(experiment) for experiment in experiments)
    if not ok:
        LOGGER.error("some experiments could not be processed")
        return 1
    print(
        "Now rebuild the showcase bundles: python scripts/build_showcase_bundles.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
