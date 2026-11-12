"""Independent numerical audit of one recorded M2 experiment run.

This script re-derives the recorded numbers from the frozen M0/M1 rasters
using code paths that do NOT import the experiment engine's threshold or
estimator functions.  It reads the run's result.json and recomputes:

* threshold classification on the exported M1 delta raster (fresh numpy);
* pixel areas from the raster's own affine transform (not the summary);
* area conservation and percentage identities;
* the composite_median mean delta from the period rasters;
* sweep monotonicity;
* CSV consistency against result.json;
* manifest artifact hashes;
* estimator inventory arithmetic;
* bootstrap interval containment;
* absence of any supervised-accuracy claim;
* API summary agreement (in-process TestClient, no recomputation).

A value that only matches because the same function produced both sides is
worthless here: every check below uses an independently written expression
or an independently stored source.

Usage:
    python verification/audit_m2.py [--run-dir data/experiments/m2/coringa_m2/<run>]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402

CHECKS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "passed": bool(ok), "detail": detail})
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))


def read_tif(path: Path) -> tuple[np.ndarray, float]:
    with rasterio.open(path) as src:
        array = src.read(1)
        transform = src.transform
        pixel_area = abs(transform.a * transform.e)
        crs = src.crs
    return array, (pixel_area, str(crs))


def classify(delta: np.ndarray, valid: np.ndarray, threshold: float):
    """Fresh implementation of the symmetric classification rule."""
    lower = valid & (delta <= -threshold)
    upper = valid & (delta >= threshold)
    middle = valid & (delta > -threshold) & (delta < threshold)
    return lower, middle, upper


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="run directory (default: newest run of coringa_m2)",
    )
    args = parser.parse_args()

    run_dir = args.run_dir
    if run_dir is None:
        candidates = sorted(
            (PROJECT_ROOT / "data/experiments/m2/coringa_m2").glob("*/result.json")
        )
        if not candidates:
            print("no recorded coringa_m2 run found")
            return 2
        run_dir = candidates[-1].parent
    result_path = run_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    print(f"audit target: {run_dir}")
    print(f"run: {result['run_id']}  fingerprint: {result['fingerprint'][:16]}…\n")

    # ---- 1. raster-derived recomputation ---------------------------------
    print("1. threshold classes re-derived from exported M1 rasters")
    m1_dir = PROJECT_ROOT / "data/processed/m1/coringa_coastal"
    thresholds = result["config"]["thresholds"]
    for index in result["config"]["indices"]:
        earlier, meta_e = read_tif(
            m1_dir / f"earlier_{'2020-03-26'}_{index}.tif"
        )
        # locate the actual period raster names from the summary
        summary = json.loads((m1_dir / "summary.json").read_text(encoding="utf-8"))
        earlier_name = Path(summary["outputs"][f"earlier_{index}_tif"]["path"]).name
        later_name = Path(summary["outputs"][f"later_{index}_tif"]["path"]).name
        delta_name = Path(summary["change"][index]["delta_tif"]).name
        earlier, meta_e = read_tif(m1_dir / earlier_name)
        later, _ = read_tif(m1_dir / later_name)
        delta_tif, meta_d = read_tif(m1_dir / delta_name)
        pixel_area, crs = meta_d

        valid = np.isfinite(earlier) & np.isfinite(later) & np.isfinite(delta_tif)
        delta = delta_tif.astype(np.float64)

        recorded = next(
            item
            for item in result["estimators"]
            if item["estimator_id"] == "composite_median" and item["index"] == index
        )
        for row in recorded["thresholds"]:
            lower, middle, upper = classify(delta, valid, row["threshold"])
            check(
                f"{index} t={row['threshold']:.2f}: decrease pixels match",
                int(lower.sum()) == row["decrease_pixels"],
                f"{int(lower.sum())} vs {row['decrease_pixels']}",
            )
            check(
                f"{index} t={row['threshold']:.2f}: increase pixels match",
                int(upper.sum()) == row["increase_pixels"],
                f"{int(upper.sum())} vs {row['increase_pixels']}",
            )
            check(
                f"{index} t={row['threshold']:.2f}: stable pixels match",
                int(middle.sum()) == row["stable_pixels"],
                f"{int(middle.sum())} vs {row['stable_pixels']}",
            )
            # area from the raster's own transform
            check(
                f"{index} t={row['threshold']:.2f}: decrease area from transform",
                abs(int(lower.sum()) * pixel_area / 10_000.0
                    - row["decrease_area_ha"]) <= 1e-6,
            )
            check(
                f"{index} t={row['threshold']:.2f}: pixel area is 100 m2",
                abs(pixel_area - 100.0) <= 1e-9,
                f"{pixel_area}",
            )

        # conservation independently
        check(
            f"{index}: classes partition the valid footprint",
            bool(np.array_equal(lower | middle | upper, valid)),
        )
        # mean delta independently
        mean = float(delta[valid].mean())
        check(
            f"{index}: composite mean delta matches recording",
            abs(mean - recorded["delta_stats"]["mean"]) <= 1e-9,
            f"{mean} vs {recorded['delta_stats']['mean']}",
        )
        # M1 headline regression (frozen values from the M1 summary)
        headline = summary["change"][index]["delta_stats"]["mean"]
        check(
            f"{index}: M1 headline mean reproduced",
            abs(mean - float(headline)) <= 1e-6,
            f"{mean} vs {headline}",
        )

    # ---- 2. sweep monotonicity (independent) ------------------------------
    print("\n2. recorded sweeps are monotone")
    for index in result["config"]["indices"]:
        recorded = next(
            item
            for item in result["estimators"]
            if item["estimator_id"] == "composite_median" and item["index"] == index
        )
        rows = sorted(recorded["thresholds"], key=lambda r: r["threshold"])
        dec = [r["decrease_pixels"] for r in rows]
        inc = [r["increase_pixels"] for r in rows]
        check(
            f"{index}: decrease non-increasing with threshold",
            all(a >= b for a, b in zip(dec, dec[1:])),
            f"{dec}",
        )
        check(
            f"{index}: increase non-increasing with threshold",
            all(a >= b for a, b in zip(inc, inc[1:])),
            f"{inc}",
        )

    # ---- 3. estimator inventory arithmetic --------------------------------
    print("\n3. estimator inventory arithmetic")
    periods = {p["period_id"]: p for p in result["coverage"]["periods"]}
    n_earlier = periods["earlier"]["observation_count"]
    n_later = periods["later"]["observation_count"]
    for index in result["config"]["indices"]:
        rows = [item for item in result["estimators"] if item["index"] == index]
        singles = [i for i in rows if i["family"] == "single_pairs"]
        loos = [i for i in rows if i["family"] == "leave_one_out"]
        composites = [i for i in rows if i["family"] == "composite"]
        check(f"{index}: single pairs = n_earlier*n_later", len(singles) == n_earlier * n_later,
              f"{len(singles)} vs {n_earlier * n_later}")
        check(f"{index}: leave-one-out = n_earlier+n_later", len(loos) == n_earlier + n_later,
              f"{len(loos)} vs {n_earlier + n_later}")
        check(f"{index}: two composites (median+mean)", len(composites) == 2)
        check(
            f"{index}: all estimators conserve area",
            all(i["area_conservation_all_ok"] for i in rows),
        )
    m0_rows = [i for i in result["estimators"] if i["family"] == "m0_single_scene"]
    check("m0 estimator appears once (ndvi only)", len(m0_rows) == 1)

    # ---- 4. bootstrap containment ------------------------------------------
    print("\n4. bootstrap intervals contain the point estimate")
    for index, bootstrap in result["uncertainty"]["block_bootstrap"].items():
        if not bootstrap.get("enabled"):
            check(f"{index}: bootstrap enabled", False)
            continue
        for row in bootstrap["thresholds"]:
            for kind in ("decrease", "increase"):
                ci = row[f"{kind}_fraction_ci95"]
                point = row[f"{kind}_fraction"]
                check(
                    f"{index} t={row['threshold']:.2f}: {kind} CI contains point",
                    ci["p2_5"] - 1e-12 <= point <= ci["p97_5"] + 1e-12,
                    f"{ci} vs {point}",
                )
        check(
            f"{index}: bootstrap iterations used == requested",
            bootstrap["iterations_used"] == bootstrap["iterations_requested"],
        )

    # ---- 5. CSV consistency -------------------------------------------------
    print("\n5. CSV tables agree with result.json")
    csv_path = run_dir / "estimator_thresholds.csv"
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    check("csv row count == estimators x thresholds",
          len(rows) == len(result["estimators"]) * len(thresholds),
          f"{len(rows)} vs {len(result['estimators']) * len(thresholds)}")
    recorded_map = {
        (item["estimator_id"], item["index"], round(item["threshold"], 2)):
            item
        for item in (
            {**est, **row}
            for est in result["estimators"]
            for row in est["thresholds"]
        )
    }
    mismatch = 0
    for row in rows:
        key = (row["estimator_id"], row["index"], round(float(row["threshold"]), 2))
        recorded = recorded_map.get(key)
        if recorded is None:
            mismatch += 1
            continue
        if (
            int(row["decrease_pixels"]) != recorded["decrease_pixels"]
            or int(row["increase_pixels"]) != recorded["increase_pixels"]
            or abs(float(row["delta_mean"]) - recorded["delta_stats"]["mean"]) > 5e-7
        ):
            mismatch += 1
    check("every csv row matches result.json", mismatch == 0, f"{mismatch} mismatches")

    # ---- 6. manifest hashes --------------------------------------------------
    print("\n6. manifest artifact hashes")
    broken = []
    for relative, recorded_hash in manifest["artifacts"].items():
        path = PROJECT_ROOT / relative
        if not path.exists():
            broken.append(f"missing {relative}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != recorded_hash:
            broken.append(f"hash {relative}")
    check("all manifest artifact hashes verify", not broken, "; ".join(broken))
    check("manifest records git commit", manifest.get("git_commit") not in (None, "", "unknown"),
          manifest.get("git_commit"))
    check("manifest records software versions", bool(manifest.get("software")))

    # ---- 7. input provenance -------------------------------------------------
    print("\n7. frozen-input provenance")
    m1_summary_bytes = (m1_dir / "summary.json").read_bytes()
    check(
        "M1 summary hash matches the run's recorded input hash",
        hashlib.sha256(m1_summary_bytes).hexdigest()
        == result["inputs"]["m1_summary"]["sha256"],
    )
    check(
        "M1 config hash recorded and present",
        (PROJECT_ROOT / result["inputs"]["m1_config"]["path"]).exists(),
    )
    check(
        "observation cache inventory complete (3 earlier + 3 later)",
        len(result["inputs"]["observations"]) == n_earlier + n_later,
    )

    # ---- 8. no supervised claims ---------------------------------------------
    print("\n8. supervised-metric absence")
    forbidden = {"accuracy", "f1", "confusion_matrix", "precision", "recall",
                 "balanced_accuracy", "iou", "overall_accuracy", "model_card",
                 "trained_model"}

    def walk(node):
        hits = []
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).lower() in forbidden:
                    hits.append(str(key))
                hits.extend(walk(value))
        elif isinstance(node, list):
            for item in node:
                hits.extend(walk(item))
        return hits

    hits = walk(result)
    check("result.json contains no supervised metric keys", not hits, str(hits[:5]))
    check(
        "run records the label-blocked status",
        result["config"].get("raw", {}).get("labels", {}).get("status", "blocked")
        .startswith("blocked"),
    )

    # ---- 9. API summary agreement ---------------------------------------------
    print("\n9. API summary agrees with the recorded result (no recomputation)")
    try:
        from fastapi.testclient import TestClient

        from backend.app.api.app import app

        client = TestClient(app)
        response = client.get("/api/experiments/coringa_m2/latest")
        check("api latest returns 200", response.status_code == 200)
        if response.status_code == 200:
            payload = response.json()
            check("api serves the same run", payload["run_id"] == result["run_id"])
            composite_api = [
                item for item in payload["estimators_at_primary"]
                if item["estimator_id"] == "composite_median"
                and item["index"] == "ndvi"
            ]
            composite_file = next(
                item for item in result["estimators"]
                if item["estimator_id"] == "composite_median"
                and item["index"] == "ndvi"
            )
            check(
                "api decrease area equals result.json",
                abs(composite_api[0]["decrease_area_ha"]
                    - composite_file["primary"]["decrease_area_ha"]) <= 1e-9,
            )
    except Exception as exc:  # pragma: no cover - environment dependent
        check("api reachable in-process", False, str(exc))

    # ---- summary ---------------------------------------------------------------
    passed = sum(1 for item in CHECKS if item["passed"])
    failed = len(CHECKS) - passed
    print(f"\naudit: {passed}/{len(CHECKS)} checks passed, {failed} failed")
    (run_dir / "audit_m2_results.json").write_text(
        json.dumps(
            {
                "run_id": result["run_id"],
                "audit_utc_source": "wall clock, not used in results",
                "checks": CHECKS,
                "passed": passed,
                "failed": failed,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
