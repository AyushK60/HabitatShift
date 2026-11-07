"""CLI entry point for one M2 experiment.

Usage:
    python scripts/run_experiment.py --config studies/experiments/coringa_m2.yaml
    python scripts/run_experiment.py --config ... --force   # recompute, new run
    python scripts/run_experiment.py --config ... --no-cache

An unchanged rerun is served from the cached run directory (same content
fingerprint) unless ``--no-cache`` or ``--force`` is given.  ``--force``
recomputes into a NEW timestamped run directory; it never overwrites an
existing one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.experiments.runner import M2RunError, run_experiment  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="path to an M2 experiment YAML configuration",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="recompute even if a cached run with the same fingerprint exists",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="skip the cache lookup entirely",
    )
    args = parser.parse_args()

    try:
        outcome = run_experiment(
            PROJECT_ROOT / args.config if not args.config.is_absolute() else args.config,
            force=args.force,
            use_cache=not args.no_cache,
        )
    except (M2RunError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if outcome.cached:
        print(f"cache hit (fingerprint {outcome.fingerprint[:12]}...)")
        print(f"run: {outcome.run_dir}")

    result = outcome.result
    print(f"experiment : {result['experiment_id']}  (study {result['study_id']})")
    print(f"run        : {outcome.run_id}{'  [cached]' if outcome.cached else ''}")
    print(f"run dir    : {outcome.run_dir}")
    print("")

    coverage = result["coverage"]
    print(
        f"coverage   : {coverage['aoi_pixels']:,} AOI px, "
        f"min common-valid fraction {coverage['minimum_common_valid_fraction_of_aoi']:.3f}"
    )
    print("")
    print("primary composite (median) at the configured primary threshold:")
    for estimator in result["estimators"]:
        if estimator["estimator_id"] != "composite_median":
            continue
        row = estimator["primary"]
        print(
            f"  {estimator['index']:>6}: mean delta {estimator['delta_stats']['mean']:+.4f} | "
            f"decrease {row['decrease_area_ha']:.2f} ha ({row['decrease_percent_of_common']:.2f}%) | "
            f"increase {row['increase_area_ha']:.2f} ha ({row['increase_percent_of_common']:.2f}%)"
        )
    print("")
    print("hypothesis verdicts:")
    for verdict in result["hypothesis_verdicts"]:
        print(f"  {verdict['id']}: {verdict['verdict']}")
    print("")
    print(f"artifacts  : {len(outcome.result['inputs']['m1_rasters'])} input hashes, "
          f"manifest.json, result.json, 2 CSV tables, charts/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
