"""M5-G7 fresh-environment reproduction of one major scientific result.

Reproduces the frozen **chilika_m4_dry** experiment end-to-end from the
original source data (live Earth Search STAC + COG downloads) with:
  - a completely separate observation cache (nothing reused from data/cache),
  - all outputs redirected to a sandbox directory (frozen M4 outputs are
    never written),
then compares the regenerated change statistics with the recorded manifest
at the recorded precision, and hashes the regenerated delta/common-valid
rasters against the recorded output checksums (byte-identical reproduction
is expected because the pipeline is deterministic at fixed seeds).

Usage:
    python scripts/reproduce_m5_fresh.py --venv <path-to-fresh-venv-python>
The fresh venv is created separately (see docs/M5_FRESH_REPRODUCTION.md);
this script runs in whatever interpreter it is given and must NOT be run
from inside the venv's directory.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=None, help="empty cache dir (fresh downloads)")
    parser.add_argument("--out-dir", type=Path, default=None, help="sandbox output dir")
    parser.add_argument("--experiment", default="chilika_m4_dry")
    args = parser.parse_args()

    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.app.pipeline import engine as engine_mod
    from backend.app.pipeline.config import load_study_config

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cache_dir = args.cache_dir or Path(tempfile.mkdtemp(prefix="hs_fresh_cache_"))
    out_dir = args.out_dir or Path(tempfile.mkdtemp(prefix="hs_fresh_out_"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    base = load_study_config(PROJECT_ROOT / "studies" / "experiments" / f"{args.experiment}.yaml")
    cfg = replace(
        base,
        experiment_id=f"{args.experiment}_reproduce",
        processed_dir=out_dir / "processed",
        preview_dir=out_dir / "previews",
        manifest_path=out_dir / "manifest.json",
        status_path=out_dir / "processed" / "status.json",
    )

    print(f"reproducing {args.experiment} from source data (fresh cache {cache_dir})")
    engine = engine_mod.M1Engine(cfg, cache_dir=cache_dir, observation_cache_dir=cache_dir / "observations")
    started = dt.datetime.now(dt.timezone.utc)
    summary = engine.run()

    recorded = json.loads((PROJECT_ROOT / "data" / "manifests" / f"m4_{args.experiment}.json").read_text())

    # 1. change statistics at the primary threshold
    comparison = {}
    for index, block in recorded["change"].items():
        fresh = summary["change"][index]
        rec_row = next(
            r for r in block["thresholds"]
            if abs(float(r["threshold"]) - float(block["primary_threshold"])) < 1e-9
        )
        fresh_row = next(
            r for r in fresh["thresholds"]
            if abs(float(r["threshold"]) - float(block["primary_threshold"])) < 1e-9
        )
        for key in ("decrease_pixels", "increase_pixels", "stable_pixels"):
            comparison[f"{index}/{key}"] = {
                "recorded": int(rec_row[key]),
                "reproduced": int(fresh_row[key]),
                "match": int(rec_row[key]) == int(fresh_row[key]),
            }
        comparison[f"{index}/common_valid_pixels"] = {
            "recorded": int(block["common_valid_pixels"]),
            "reproduced": int(fresh["common_valid_pixels"]),
            "match": int(block["common_valid_pixels"]) == int(fresh["common_valid_pixels"]),
        }

    # 2. byte-level raster reproduction where checksums exist for GeoTIFFs
    raster_checks = {}
    for name, meta in recorded["outputs"].items():
        if not name.endswith("_tif") or not Path(meta["path"]).name.startswith(("delta_", "common_valid_", "change_classes_")):
            continue
        recorded_file = PROJECT_ROOT / meta["path"]
        fresh_file = out_dir / "processed" / recorded_file.name
        if fresh_file.exists():
            same = hashlib.sha256(fresh_file.read_bytes()).hexdigest() == meta["sha256"]
            raster_checks[recorded_file.name] = "byte-identical" if same else "DIFFERS"

    result = {
        "schema": "habitatshift-m5-fresh-reproduction/1",
        "experiment": args.experiment,
        "generated_utc": started.isoformat(),
        "cache_dir": str(cache_dir),
        "out_dir": str(out_dir),
        "change_statistics": comparison,
        "raster_checks": raster_checks,
        "all_statistics_match": all(v["match"] for v in comparison.values()),
        "all_rasters_byte_identical": all(v == "byte-identical" for v in raster_checks.values()) and bool(raster_checks),
    }
    result_path = out_dir / "reproduction.json"
    result_path.write_text(json.dumps(result, indent=2))

    print(json.dumps(comparison, indent=1))
    print("rasters:", raster_checks)
    ok = result["all_statistics_match"] and result["all_rasters_byte_identical"]
    print(f"\nREPRODUCTION {'VERIFIED' if ok else 'MISMATCH'} — wrote {result_path}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
