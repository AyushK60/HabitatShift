"""Grid-resolution sensitivity (completes the item M5-G5 deferred).

Reprocesses one study end-to-end at a coarser analysis grid (default 20 m) through the same
audited engine, in a sandbox (separate cache, outputs redirected), and compares
the primary-threshold change fractions with the recorded 10 m run. Frozen
outputs are only read. Result: data/experiments/m5_resolution/<experiment>/result.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def primary_row(block: dict) -> dict:
    return next(r for r in block["thresholds"] if abs(float(r["threshold"]) - float(block["primary_threshold"])) < 1e-9)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--experiment", default="kathmandu_m4")
    ap.add_argument("--resolution", type=float, default=20.0)
    args = ap.parse_args()
    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.app.pipeline import engine as engine_mod
    from backend.app.pipeline.config import load_study_config

    work = Path(tempfile.mkdtemp(prefix="hs_res_"))
    base = load_study_config(PROJECT_ROOT / "studies" / "experiments" / f"{args.experiment}.yaml")
    cfg = replace(
        base,
        experiment_id=f"{args.experiment}_res{int(args.resolution)}",
        resolution_m=args.resolution,
        processed_dir=work / "processed",
        preview_dir=work / "previews",
        manifest_path=work / "manifest.json",
        status_path=work / "processed" / "status.json",
    )
    started = dt.datetime.now(dt.timezone.utc)
    engine = engine_mod.M1Engine(cfg, cache_dir=work / "cache", observation_cache_dir=work / "cache" / "observations")
    summary = engine.run()
    recorded = json.loads((PROJECT_ROOT / "data" / "manifests" / f"m4_{args.experiment}.json").read_text())

    rows = {}
    for index, block in recorded["change"].items():
        fresh = summary["change"].get(index)
        if not fresh:
            continue
        r10, rc = primary_row(block), primary_row(fresh)
        n10, nc = int(block["common_valid_pixels"]), int(fresh["common_valid_pixels"])
        rows[index] = {
            "primary_threshold": block["primary_threshold"],
            "decrease_percent_10m": 100 * r10["decrease_pixels"] / n10,
            f"decrease_percent_{int(args.resolution)}m": 100 * rc["decrease_pixels"] / nc,
            "increase_percent_10m": 100 * r10["increase_pixels"] / n10,
            f"increase_percent_{int(args.resolution)}m": 100 * rc["increase_pixels"] / nc,
            "common_valid_pixels_10m": n10,
            f"common_valid_pixels_{int(args.resolution)}m": nc,
        }
        rows[index]["decrease_difference_pp"] = rows[index][f"decrease_percent_{int(args.resolution)}m"] - rows[index]["decrease_percent_10m"]
        rows[index]["increase_difference_pp"] = rows[index][f"increase_percent_{int(args.resolution)}m"] - rows[index]["increase_percent_10m"]
    out = {
        "schema": "habitatshift-m5-resolution-sensitivity/1",
        "experiment": args.experiment,
        "generated_utc": started.isoformat(),
        "resolution_m": args.resolution,
        "recorded_resolution_m": 10.0,
        "framing": "sensitivity of the recorded change fractions to analysis-grid resolution; the 10 m run remains the recorded result",
        "per_index": rows,
        "sandbox": str(work),
    }
    dest = PROJECT_ROOT / "data" / "experiments" / "m5_resolution" / args.experiment
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
