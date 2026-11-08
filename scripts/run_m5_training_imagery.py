"""M5-G3: acquire 2021-epoch training imagery through the audited M1 chain.

Every supervised M5 experiment (docs/M5_ML_LABEL_FEASIBILITY.md) needs
Sentinel-2 imagery whose epoch matches its reference labels (ESA WorldCover
v200 = the 2021 epoch).  This script reuses the production engine internals
— catalogue search, in-AOI SCL scoring, observation selection, radiometry
with the empirical acceptance test, masking, median compositing, index
computation — to build one training composite per study per application
season, and records a full provenance manifest for each.

Nothing in data/processed/m4, data/manifests/m4_*, or the M4 findings is
touched: new artifacts go to data/processed/m5_ml/<study>/ with manifests
data/manifests/m5ml_<study>.json (schema habitatshift-m5ml-training/1).

Usage:
    python scripts/run_m5_training_imagery.py               # all five
    python scripts/run_m5_training_imagery.py --study kathmandu_m5_ml
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import config  # noqa: E402
from backend.app.catalog.search import SearchRequest  # noqa: E402
from backend.app.catalog.stac_client import CatalogClient  # noqa: E402
from backend.app.http import HttpSession  # noqa: E402
from backend.app.pipeline import engine as engine_mod  # noqa: E402
from backend.app.pipeline.config import PeriodSpec, load_study_config  # noqa: E402
from backend.app.preprocess.grid import write_geotiff  # noqa: E402
from backend.app.provenance.manifest import describe_output  # noqa: E402

MANIFEST_SCHEMA = "habitatshift-m5ml-training/1"

#: study_id -> (m4 config to inherit, anchor, search window, season tag)
TRAINING_RUNS = {
    "kathmandu_m5_ml": ("kathmandu_m4", "2021-03-30", "2021-02-28", "2021-04-30"),
    "western_ghats_m5_ml": ("western_ghats_m4", "2021-02-19", "2021-01-20", "2021-03-10"),
    "coringa_m5_ml": ("coringa_m1", "2021-03-26", "2021-02-26", "2021-04-25"),
    "chilika_dry_m5_ml": ("chilika_m4_dry", "2021-02-17", "2021-01-18", "2021-03-09"),
    "chilika_postmonsoon_m5_ml": ("chilika_m4_postmonsoon", "2021-11-08", "2021-10-09", "2021-11-29"),
}


def build_manifest(
    study: str,
    cfg,
    period_spec: PeriodSpec,
    selection_report: dict,
    observations,
    period_study,
    outputs: dict,
    started: dt.datetime,
) -> dict:
    generated = dt.datetime.now(dt.timezone.utc).isoformat()
    return {
        "manifest_schema": MANIFEST_SCHEMA,
        "generated_utc": generated,
        "study": study,
        "purpose": (
            "2021-epoch training imagery for the M5 supervised experiments; "
            "label epoch = ESA WorldCover v200 (2021). NOT a change study."
        ),
        "inherited_config": {
            "from_experiment": cfg.experiment_id,
            "aoi": cfg.aoi().to_dict() if hasattr(cfg.aoi(), "to_dict") else str(cfg.aoi()),
            "resolution_m": cfg.resolution_m,
            "indices": list(cfg.indices),
            "composite_method": cfg.composite_method,
            "max_observations": cfg.max_observations,
            "min_observations": cfg.min_observations,
            "max_cloud_cover": cfg.max_cloud_cover,
            "min_scene_valid_fraction": cfg.min_scene_valid_fraction,
        },
        "training_period": period_spec.to_dict(),
        "grid": {
            "crs": period_study.window.crs if hasattr(period_study, "window") else None,
        },
        "selection": selection_report,
        "observations": [obs.to_provenance() for obs in observations],
        "reference_labels": {
            "dataset": "ESA WorldCover v200",
            "epoch": 2021,
            "license": "CC-BY 4.0 (© ESA WorldCover project 2022)",
            "note": "reference-product labels, not independent ground truth",
        },
        "software": {
            "m1_pipeline_version": config.M1_PIPELINE_VERSION,
            "radiometry_policy_version": engine_mod.RADIOMETRY_POLICY_VERSION
            if hasattr(engine_mod, "RADIOMETRY_POLICY_VERSION")
            else "see composite module",
        },
        "outputs": outputs,
        "started_utc": started.isoformat(),
    }


def run_study(study: str, base_experiment: str, anchor: str, start: str, end: str, dry_run: bool = False) -> int:
    import numpy as np  # local import keeps module import light

    from backend.app.preprocess.composite import RADIOMETRY_POLICY_VERSION

    cfg = load_study_config(PROJECT_ROOT / "studies" / "experiments" / f"{base_experiment}.yaml")
    period_spec = PeriodSpec(
        period_id="training",
        anchor=dt.date.fromisoformat(anchor),
        search_start=dt.date.fromisoformat(start),
        search_end=dt.date.fromisoformat(end),
        max_offset_days=max(
            abs((dt.date.fromisoformat(start) - dt.date.fromisoformat(anchor)).days),
            abs((dt.date.fromisoformat(end) - dt.date.fromisoformat(anchor)).days),
        ),
    )

    engine = engine_mod.M1Engine(cfg)
    started = dt.datetime.now(dt.timezone.utc)
    print(f"[{study}] searching {start}..{end} (anchor {anchor})")

    scores, candidates_by_id, search_report = engine._search_period(period_spec)
    selected, selection_report = engine_mod.select_period_observations(
        scores,
        candidates_by_id,
        period_spec,
        max_observations=cfg.max_observations,
        min_observations=cfg.min_observations,
    )
    usable = [s for s in selected if s.usable]
    print(f"[{study}] {len(usable)} usable observation(s): {[s.item_id for s in usable]}")
    if len(usable) < cfg.min_observations:
        print(f"[{study}] FAILED: insufficient usable observations in the 2021 window")
        return 2

    observations = [
        engine_mod.read_observation(
            candidates_by_id[s.item_id],
            engine.window,
            engine.aoi_mask,
            engine.band_keys,
            period_id="training",
            cache=engine.observation_cache,
        )
        for s in usable
    ]
    period_study = engine_mod.compose_period(
        observations,
        period_spec,
        cfg.indices,
        method=cfg.composite_method,
        min_observations=cfg.min_observations,
    )
    if dry_run:
        print(f"[{study}] dry run: composite valid px {int(period_study.composite.valid.sum())}")
        return 0

    processed_dir = PROJECT_ROOT / "data" / "processed" / "m5_ml" / study
    processed_dir.mkdir(parents=True, exist_ok=True)
    anchor_iso = period_spec.anchor.isoformat()

    outputs: dict[str, dict] = {}
    export_keys = tuple(
        key for key in engine_mod.BAND_EXPORT_ORDER if key in period_study.composite.bands
    )

    def record(path: Path, kind: str) -> dict:
        outputs[path.stem] = describe_output(path, kind)
        return path

    # one multiband reflectance export in the engine's canonical band order,
    # with the engine's own band descriptions
    stack_path = write_geotiff(
        processed_dir / f"training_{anchor_iso}_reflectance_composite.tif",
        np.stack([period_study.composite.bands[k] for k in export_keys]),
        engine.window,
        descriptions=tuple(engine_mod.BAND_DESCRIPTIONS[k] for k in export_keys),
        producer="HabitatShift M5-ML",
    )
    record(stack_path, "raster")
    record(
        write_geotiff(
            processed_dir / f"training_{anchor_iso}_valid_mask.tif",
            period_study.composite.valid.astype(np.uint8),
            engine.window,
            dtype="uint8",
            nodata=0,
            descriptions=("valid",),
            producer="HabitatShift M5-ML",
        ),
        "mask",
    )
    record(
        write_geotiff(
            processed_dir / f"training_{anchor_iso}_observation_count.tif",
            period_study.composite.counts.astype(np.int16),
            engine.window,
            dtype="int16",
            nodata=0,
            descriptions=("valid_observation_count",),
            producer="HabitatShift M5-ML",
        ),
        "mask",
    )
    for key in cfg.indices:
        record(
            write_geotiff(
                processed_dir / f"training_{anchor_iso}_{key}.tif",
                period_study.indices[key],
                engine.window,
                descriptions=(key,),
                producer="HabitatShift M5-ML",
            ),
            "raster",
        )

    manifest = build_manifest(
        study, cfg, period_spec, selection_report, observations, period_study,
        outputs, started,
    )
    manifest["grid"] = {
        "crs": engine.window.crs,
        "resolution_m": engine.window.resolution,
        "width": engine.window.width,
        "height": engine.window.height,
        "transform": list(engine.window.transform)[:6],
        "signature": engine.window.signature(),
        "pixel_area_m2": engine.window.pixel_area_m2,
    }
    manifest["radiometry_policy_version"] = RADIOMETRY_POLICY_VERSION
    manifest_path = PROJECT_ROOT / "data" / "manifests" / f"m5ml_{study}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    valid_px = int(period_study.composite.valid.sum())
    print(f"[{study}] wrote {stack_path.name} ({valid_px} valid px) + manifest {manifest_path.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", choices=sorted(TRAINING_RUNS))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    studies = [args.study] if args.study else sorted(TRAINING_RUNS)
    failures = 0
    for study in studies:
        base, anchor, start, end = TRAINING_RUNS[study]
        failures += run_study(study, base, anchor, start, end, dry_run=args.dry_run)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
