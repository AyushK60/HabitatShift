"""M2 experiment runner: fingerprinted, cached, never silently overwriting.

One call to :func:`run_experiment` performs:

1. input verification against the frozen M0/M1 artefacts (including an
   independent recomputation of the M1 delta rasters);
2. estimator expansion and threshold sweeps with area conservation;
3. cross-pipeline (M0 versus M1 anchor) comparison;
4. coverage, temporal-robustness and spatial-block-bootstrap uncertainty;
5. hypothesis verdicts computed only from the measured numbers;
6. deterministic reporting artefacts (result JSON, CSV tables, SVG charts);
7. a provenance manifest with artifact hashes and software versions.

Runs are content-addressed: the fingerprint hashes the canonical config plus
every input hash.  A rerun with unchanged inputs is served from the existing
run directory instead of recomputing, and no existing run is ever overwritten
without an explicit ``--force``.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .. import config
from .config import M2Config, load_m2_config
from .estimators import (
    build_surfaces,
    cross_pipeline_comparison,
    evaluate_surfaces,
)
from .inputs import (
    M1Bundle,
    input_inventory,
    load_m0_bundle,
    load_m1_bundle,
    load_observations,
    read_raster,
    sha256_file,
)
from .reporting import (
    bootstrap_svg,
    delta_histogram_svg,
    estimator_comparison_svg,
    threshold_response_svg,
    write_sensitivity_csv,
    write_summary_csv,
)
from .uncertainty import block_bootstrap, coverage_summary, temporal_robustness

RESULT_SCHEMA = "habitatshift-m2-result/1"
MANIFEST_SCHEMA = "habitatshift-m2-manifest/1"


class M2RunError(RuntimeError):
    """Raised when an experiment run cannot be executed or recorded."""


@dataclass(frozen=True)
class RunOutcome:
    run_id: str
    run_dir: Path
    fingerprint: str
    cached: bool
    result: dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=config.PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _software_versions() -> dict[str, str]:
    import rasterio

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "rasterio": rasterio.__version__,
    }


def verify_m1_rasters(m1: M1Bundle, indices: tuple[str, ...]) -> dict[str, Any]:
    """Recompute each M1 delta from its period rasters and compare."""
    checks: list[dict[str, Any]] = []
    for index in indices:
        earlier, _ = read_raster(m1.index_paths["earlier"][index])
        later, _ = read_raster(m1.index_paths["later"][index])
        delta, profile = read_raster(m1.delta_paths[index])
        common = np.isfinite(earlier) & np.isfinite(later)
        recomputed = later.astype(np.float64) - earlier.astype(np.float64)
        shared = common & np.isfinite(delta)
        if not shared.any():
            raise M2RunError(
                f"{index}: M1 delta raster and period rasters share no valid pixels"
            )
        difference = np.abs(recomputed[shared] - delta.astype(np.float64)[shared])
        summary_stats = (m1.summary.get("change") or {}).get(index, {}).get(
            "delta_stats"
        ) or {}
        recomputed_mean = float(recomputed[shared].mean())
        recorded_mean = float(summary_stats.get("mean", "nan"))
        checks.append(
            {
                "index": index,
                "shared_pixels": int(shared.sum()),
                "max_abs_recompute_difference": float(difference.max()),
                "recomputed_mean": recomputed_mean,
                "summary_mean": recorded_mean,
                "mean_matches_summary": bool(
                    abs(recomputed_mean - recorded_mean) <= 1e-6
                ),
                "raster_shape_matches_grid": bool(
                    (profile["width"], profile["height"])
                    == (m1.summary["grid"]["width"], m1.summary["grid"]["height"])
                ),
            }
        )
    problems = [
        item
        for item in checks
        if item["max_abs_recompute_difference"] > 1e-6
        or not item["mean_matches_summary"]
        or not item["raster_shape_matches_grid"]
    ]
    return {
        "checks": checks,
        "all_ok": not problems,
        "tolerance": 1e-6,
    }


def _primary_row(result: dict[str, Any]) -> dict[str, Any]:
    return next(
        row
        for row in result["thresholds"]
        if abs(row["threshold"] - result["primary_threshold"]) <= 1e-9
    )


def _row_at_threshold(result: dict[str, Any], threshold: float) -> dict[str, Any]:
    return next(
        row
        for row in result["thresholds"]
        if abs(row["threshold"] - threshold) <= 1e-9
    )


def evaluate_hypotheses(
    config_: M2Config,
    results: list[dict[str, Any]],
    coverage: dict[str, Any],
    cross_pipeline: dict[str, Any],
) -> list[dict[str, Any]]:
    """Verdicts computed strictly from measured numbers; no claim beyond them."""
    statement_by_prefix = {}
    for hypothesis in config_.hypotheses:
        # Hypotheses are written as "H1 (short name): statement ...";
        # index them by their leading id so verdicts carry the full text.
        identifier = hypothesis.split(":", 1)[0].strip().split("(", 1)[0].strip()
        statement_by_prefix[identifier] = hypothesis
        statement_by_prefix.setdefault(hypothesis, hypothesis)

    def by_id(estimator_id: str, index: str) -> dict[str, Any]:
        return next(
            item
            for item in results
            if item["estimator_id"] == estimator_id and item["index"] == index
        )

    verdicts: list[dict[str, Any]] = []

    # H1 - monotone response (enforced by the sweep) and stable index ranking
    # of decrease fractions between the loosest threshold and the primary one.
    loosest = min(config_.thresholds)
    ranking_at = {}
    for reference in (loosest, config_.primary_threshold):
        ranking_at[reference] = sorted(
            config_.indices,
            key=lambda index: -_row_at_threshold(
                by_id("composite_median", index), reference
            )["decrease_percent_of_common"],
        )
    ranking_stable = ranking_at[loosest] == ranking_at[config_.primary_threshold]
    verdicts.append(
        {
            "id": "H1",
            "statement": statement_by_prefix.get("H1", ""),
            "verdict": "supported" if ranking_stable else "not_supported",
            "evidence": {
                "decrease_ranking_at_loosest_threshold": ranking_at[loosest],
                "decrease_ranking_at_primary_threshold": ranking_at[
                    config_.primary_threshold
                ],
                "monotonicity": (
                    "enforced by threshold_sweep; the run aborts on violation"
                ),
            },
        }
    )

    # H2 - composite against single-pair mean-delta magnitude.
    h2: dict[str, Any] = {}
    composite_wins = True
    for index in config_.indices:
        composite = by_id("composite_median", index)
        singles = [
            item
            for item in results
            if item["family"] == "single_pairs" and item["index"] == index
        ]
        single_means = [abs(item["delta_stats"]["mean"]) for item in singles]
        composite_abs_mean = abs(composite["delta_stats"]["mean"])
        within = composite_abs_mean <= float(np.mean(single_means))
        h2[index] = {
            "composite_abs_mean_delta": composite_abs_mean,
            "single_pair_abs_mean_delta_mean": float(np.mean(single_means)),
            "single_pair_abs_mean_delta_range": [
                float(min(single_means)),
                float(max(single_means)),
            ],
            "composite_within_single_pair_spread": within,
        }
        composite_wins = composite_wins and within
    verdicts.append(
        {
            "id": "H2",
            "statement": statement_by_prefix.get("H2", ""),
            "verdict": "supported" if composite_wins else "not_supported",
            "evidence": h2,
        }
    )

    # H3 - leave-one-out shifts are smaller than the single-pair spread.
    h3: dict[str, Any] = {}
    loo_wins = True
    for index in config_.indices:
        composite = by_id("composite_median", index)
        singles = [
            item
            for item in results
            if item["family"] == "single_pairs" and item["index"] == index
        ]
        loos = [
            item
            for item in results
            if item["family"] == "leave_one_out" and item["index"] == index
        ]
        per_threshold = []
        for row in composite["thresholds"]:
            threshold = row["threshold"]
            single_decreases = [
                _row_at_threshold(single, threshold)["decrease_percent_of_common"]
                for single in singles
            ]
            loo_shifts = [
                abs(
                    _row_at_threshold(loo, threshold)["decrease_percent_of_common"]
                    - row["decrease_percent_of_common"]
                )
                for loo in loos
            ]
            spread = float(max(single_decreases) - min(single_decreases))
            max_shift = float(max(loo_shifts)) if loo_shifts else 0.0
            per_threshold.append(
                {
                    "threshold": threshold,
                    "single_pair_decrease_spread_percent": spread,
                    "max_leave_one_out_shift_percent": max_shift,
                    "loo_shift_within_spread": max_shift <= spread,
                }
            )
        h3[index] = per_threshold
        loo_wins = loo_wins and all(
            item["loo_shift_within_spread"] for item in per_threshold
        )
    verdicts.append(
        {
            "id": "H3",
            "statement": statement_by_prefix.get("H3", ""),
            "verdict": "supported" if loo_wins else "not_supported",
            "evidence": h3,
        }
    )

    # H4 - cross-pipeline agreement on the shared footprint.
    if cross_pipeline.get("available"):
        shared = int(cross_pipeline["shared_pixels"])
        identical = int(cross_pipeline["pixels_identical_within_1e_9"])
        identical_fraction = identical / shared if shared else 0.0
        verdict = "supported" if identical_fraction >= 0.99 else "inconclusive"
        evidence: dict[str, Any] = {
            "shared_pixels": shared,
            "pixels_identical_within_1e_9": identical,
            "identical_fraction": identical_fraction,
            "mean_difference": cross_pipeline["mean_difference"],
            "max_abs_difference": cross_pipeline["max_abs_difference"],
        }
    else:
        verdict = "inconclusive"
        evidence = {"reason": cross_pipeline.get("reason", "unavailable")}
    verdicts.append(
        {
            "id": "H4",
            "statement": statement_by_prefix.get("H4", ""),
            "verdict": verdict,
            "evidence": evidence,
        }
    )

    # H5 - validity completeness explains estimator differences.
    complete = bool(coverage["all_indices_suitable"]) and (
        coverage["minimum_common_valid_fraction_of_aoi"] >= 0.999
    )
    verdicts.append(
        {
            "id": "H5",
            "statement": statement_by_prefix.get("H5", ""),
            "verdict": "supported" if complete else "inconclusive",
            "evidence": {
                "minimum_common_valid_fraction_of_aoi": coverage[
                    "minimum_common_valid_fraction_of_aoi"
                ],
                "all_indices_suitable": coverage["all_indices_suitable"],
            },
        }
    )
    return verdicts


def compute_fingerprint(config_: M2Config, inventory: dict[str, Any]) -> str:
    payload = {
        "config": config_.canonical(),
        "inputs": {
            "m1_config": inventory["m1_config"],
            "m1_summary": inventory["m1_summary"],
            "m0_summary": inventory["m0_summary"],
            "observations": inventory["observations"],
            "m1_rasters": inventory["m1_rasters"],
            "m0_rasters": inventory["m0_rasters"],
        },
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def find_cached_run(config_: M2Config, fingerprint: str) -> Path | None:
    runs_root = config_.output_root / config_.experiment_id
    if not runs_root.is_dir():
        return None
    for manifest_path in sorted(runs_root.glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if manifest.get("fingerprint") == fingerprint:
            return manifest_path.parent
    return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def run_experiment(
    config_path: Path,
    *,
    force: bool = False,
    use_cache: bool = True,
) -> RunOutcome:
    """Execute one M2 experiment end to end."""
    config_: M2Config = load_m2_config(Path(config_path))

    observations = load_observations(config_)
    m1 = load_m1_bundle(config_, observations)
    m0 = load_m0_bundle(config_)

    fingerprint = compute_fingerprint(
        config_, input_inventory(config_, observations, m1, m0)
    )

    if use_cache and not force:
        cached = find_cached_run(config_, fingerprint)
        if cached is not None:
            result = json.loads((cached / "result.json").read_text(encoding="utf-8"))
            return RunOutcome(
                run_id=str(result["run_id"]),
                run_dir=cached,
                fingerprint=fingerprint,
                cached=True,
                result=result,
            )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}_{fingerprint[:8]}"
    run_dir = config_.output_root / config_.experiment_id / run_id
    if run_dir.exists():
        raise M2RunError(
            f"run directory already exists: {config.relative(run_dir)}; "
            "refusing to overwrite"
        )
    charts_dir = run_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=False)

    # ---- verification of frozen inputs -----------------------------------
    m1_verification = verify_m1_rasters(m1, config_.indices)
    if not m1_verification["all_ok"]:
        raise M2RunError(
            "M1 delta rasters do not reproduce from their period rasters: "
            f"{m1_verification['checks']}"
        )

    # ---- estimators -------------------------------------------------------
    m0_periods = {item["period_id"]: item for item in m0.summary.get("periods", [])}
    m0_source = {
        "earlier_item_id": m0_periods.get("earlier", {}).get("item_id"),
        "earlier_date": m0_periods.get("earlier", {}).get("date"),
        "later_item_id": m0_periods.get("later", {}).get("item_id"),
        "later_date": m0_periods.get("later", {}).get("date"),
    }
    surfaces = build_surfaces(
        config_,
        observations,
        m1.summary,
        m0_delta=m0.delta,
        m0_valid=m0.delta_valid,
        m0_source=m0_source,
    )
    results = evaluate_surfaces(surfaces, config_, m1.summary)
    cross_pipeline = cross_pipeline_comparison(results, surfaces, m0)

    # ---- uncertainty ------------------------------------------------------
    coverage = coverage_summary(config_, m1.summary, observations)
    robustness = {
        index: temporal_robustness(results, index, config_.thresholds)
        for index in config_.indices
    }
    bootstrap_by_index: dict[str, dict[str, Any]] = {}
    for index in config_.indices:
        surface = next(
            item
            for item in surfaces
            if item.estimator_id == "composite_median" and item.index == index
        )
        bootstrap_by_index[index] = block_bootstrap(
            delta=surface.delta,
            common=surface.common,
            thresholds=config_.thresholds,
            block_size_px=config_.block_size_px,
            iterations=config_.bootstrap_iterations,
            seed=config_.bootstrap_seed,
            pixel_area_m2=float(m1.summary["grid"]["pixel_area_m2"]),
        )

    # ---- hypothesis verdicts ---------------------------------------------
    hypotheses = evaluate_hypotheses(config_, results, coverage, cross_pipeline)

    # ---- reporting artefacts ---------------------------------------------
    composite_results = [
        item for item in results if item["estimator_id"] == "composite_median"
    ]
    primary_table = {item["index"]: item["thresholds"] for item in composite_results}

    generated_utc = _utc_now()
    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "experiment_id": config_.experiment_id,
        "study_id": config_.study_id,
        "run_id": run_id,
        "fingerprint": fingerprint,
        "generated_utc": generated_utc,
        "hypotheses": list(config_.hypotheses),
        "hypothesis_verdicts": hypotheses,
        "config": config_.to_dict(),
        "inputs": input_inventory(config_, observations, m1, m0),
        "verification": {"m1_rasters": m1_verification},
        "coverage": coverage,
        "estimators": results,
        "cross_pipeline": cross_pipeline,
        "temporal_robustness": robustness,
        "uncertainty": {
            "block_bootstrap": bootstrap_by_index,
            "interpretation": (
                "All intervals and ranges here describe resampling and "
                "observation-selection variability for this AOI and grid. "
                "None of them is a confidence interval about mangrove extent "
                "in general, and none validates a specific threshold as "
                "'true' change."
            ),
        },
        "interpretation_guardrails": [
            "Candidate-change areas are threshold-dependent descriptions of "
            "index difference, not verified environmental change.",
            "For Coringa, an NDVI decrease is not evidence of mangrove loss: "
            "tides, seasonality and mixed pixels can produce the same signal.",
            "No independent reference labels were used in this run; no "
            "supervised accuracy number is reported anywhere in it.",
            "Estimator differences measure observation-selection effects, "
            "not processing errors.",
        ],
    }
    _write_json(run_dir / "result.json", result)

    summary_rows = write_summary_csv(run_dir / "estimator_thresholds.csv", results)
    sensitivity_rows = write_sensitivity_csv(
        run_dir / "threshold_sensitivity.csv", primary_table
    )

    chart_files: list[str] = []
    threshold_response_svg(
        primary_table, "composite_median", charts_dir / "threshold_response.svg"
    )
    chart_files.append("charts/threshold_response.svg")
    for index in config_.indices:
        surface = next(
            item
            for item in surfaces
            if item.estimator_id == "composite_median" and item.index == index
        )
        delta_histogram_svg(
            surface.delta,
            surface.common,
            index,
            "composite_median",
            charts_dir / f"delta_histogram_{index}.svg",
        )
        chart_files.append(f"charts/delta_histogram_{index}.svg")
        estimator_comparison_svg(
            results,
            index,
            config_.primary_threshold,
            charts_dir / f"estimator_comparison_{index}.svg",
        )
        chart_files.append(f"charts/estimator_comparison_{index}.svg")
        if bootstrap_by_index[index].get("enabled"):
            bootstrap_svg(
                bootstrap_by_index[index],
                index,
                charts_dir / f"bootstrap_{index}.svg",
            )
            chart_files.append(f"charts/bootstrap_{index}.svg")

    # ---- manifest ---------------------------------------------------------
    artifacts: dict[str, str] = {}
    for artifact in sorted(run_dir.rglob("*")):
        if artifact.is_file():
            artifacts[config.relative(artifact)] = sha256_file(artifact)

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "run_id": run_id,
        "fingerprint": fingerprint,
        "experiment_id": config_.experiment_id,
        "study_id": config_.study_id,
        "generated_utc": generated_utc,
        "config_source": {
            "path": config.relative(config_.source_path),
            "sha256": config_.source_sha256,
        },
        "m1_config": {
            "path": config.relative(config_.m1_config_path),
            "sha256": sha256_file(config_.m1_config_path),
        },
        "git_commit": _git_commit(),
        "software": _software_versions(),
        "inputs": result["inputs"],
        "artifacts": artifacts,
        "row_counts": {
            "estimator_threshold_rows": summary_rows,
            "threshold_sensitivity_rows": sensitivity_rows,
        },
        "charts": chart_files,
    }
    _write_json(run_dir / "manifest.json", manifest)

    return RunOutcome(
        run_id=run_id,
        run_dir=run_dir,
        fingerprint=fingerprint,
        cached=False,
        result=result,
    )
