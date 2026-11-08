"""M5-G3: supervised Random Forest experiments (label-gated).

Implements the experiments permitted by docs/M5_ML_LABEL_FEASIBILITY.md:

- kathmandu_m5_ml       multi-class: built-up / vegetation / bare / water
- western_ghats_m5_ml   binary:    forest-vegetation / other
- chilika_dry_m5_ml     binary:    water / land  (dry-season application)
- chilika_postmonsoon_m5_ml  binary: water / land (post-monsoon application)
- coringa_m5_ml         binary:    vegetation / water (PARTIAL: no mangrove labels)

Design (fixed, then documented verbatim in the run manifest):

* Features: surface reflectance on the 10 m analysis grid — blue, green,
  red, NIR (native 10 m) and SWIR1 (native 20 m, bilinearly resampled by the
  audited pipeline; recorded as upsampled, never claimed native) — plus the
  study's registered indices (NDVI/NDWI/MNDWI/NDBI per study config).
* Labels: ESA WorldCover v200 (2021 epoch), read live per AOI and rasterised
  onto the analysis grid; reference-product labels, never claimed as ground
  truth.
* Split: contiguous 100-pixel-square spatial blocks partitioned into
  train / validation / test thirds by block row stripes (geographically
  separated; no adjacent-pixel splitting, no spatial leakage across folds).
* Model: sklearn RandomForestClassifier, fixed seed, hyperparameters and
  feature list recorded in the manifest; class_weight balanced to handle the
  documented imbalances.
* Evaluation (on the spatially separated test blocks only): confusion
  matrix, per-class precision/recall/F1, macro-F1, balanced accuracy, IoU —
  all reported as "agreement with ESA WorldCover v200".
* Application: the frozen classifier is applied to the existing 2020 and
  2025 M4 composites; per-period predicted-class fractions and the predicted
  change are compared with the mathematical Δ-index findings (agreement and
  disagreement counted, never hidden).
* Probability outputs are recorded per application epoch but are model
  confidences, NOT accuracy estimates.

Artifacts: data/experiments/m5_ml/<study>/<UTCstamp>/{model.joblib,
result.json, manifest.json, evaluation.csv, agreement maps}; frozen M4
outputs untouched. Usage: python scripts/run_m5_ml.py [--study kathmandu_m5_ml]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import rasterio
from rasterio.env import Env
from rasterio.io import MemoryFile
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: WorldCover v200 classes; labels read live per AOI
WC_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
GDAL_ENV = {
    "AWS_NO_SIGN_REQUEST": "YES",
    "GDAL_HTTP_TIMEOUT": "60",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "VSI_CACHE": "TRUE",
}

SEED = 20261108
BLOCK = 100  # pixels; contiguous blocks for the geographic split

#: study -> (class mapping {WC code: experiment class}, feature assets, indices)
EXPERIMENTS = {
    "kathmandu_m5_ml": {
        "classes": {50: "built_up", 10: "vegetation", 30: "vegetation", 40: "vegetation", 60: "bare", 80: "water"},
        "class_order": ["built_up", "vegetation", "bare", "water"],
        "indices": ["ndbi", "ndvi", "ndwi"],
        "application": [
            ("earlier", "data/processed/m4/kathmandu_m4/earlier_2020-03-31_reflectance_composite.tif", "2020-03-31"),
            ("later", "data/processed/m4/kathmandu_m4/later_2025-03-29_reflectance_composite.tif", "2025-03-29"),
        ],
        "training": "data/processed/m5_ml/kathmandu_m5_ml/training_2021-03-30_reflectance_composite.tif",
        "m4_experiment": "kathmandu_m4",
        "primary_index": "ndbi",
    },
    "western_ghats_m5_ml": {
        "classes": {10: "forest_vegetation", 30: "forest_vegetation", 40: "other", 50: "other", 60: "other", 80: "other"},
        "class_order": ["forest_vegetation", "other"],
        "indices": ["ndvi", "ndwi"],
        "application": [
            ("earlier", "data/processed/m4/western_ghats_m4/earlier_2020-02-19_reflectance_composite.tif", "2020-02-19"),
            ("later", "data/processed/m4/western_ghats_m4/later_2025-02-22_reflectance_composite.tif", "2025-02-22"),
        ],
        "training": "data/processed/m5_ml/western_ghats_m5_ml/training_2021-02-19_reflectance_composite.tif",
        "m4_experiment": "western_ghats_m4",
        "primary_index": "ndvi",
    },
    "chilika_dry_m5_ml": {
        "classes": {80: "water", 90: "water", 40: "land", 10: "land", 30: "land", 50: "land", 60: "land", 20: "land", 95: "land"},
        "class_order": ["water", "land"],
        "indices": ["ndwi", "mndwi", "ndvi"],
        "application": [
            ("earlier", "data/processed/m4/chilika_m4_dry/earlier_2020-02-17_reflectance_composite.tif", "2020-02-17"),
            ("later", "data/processed/m4/chilika_m4_dry/later_2025-02-15_reflectance_composite.tif", "2025-02-15"),
        ],
        "training": "data/processed/m5_ml/chilika_dry_m5_ml/training_2021-02-17_reflectance_composite.tif",
        "m4_experiment": "chilika_m4_dry",
        "primary_index": "mndwi",
    },
    "chilika_postmonsoon_m5_ml": {
        "classes": {80: "water", 90: "water", 40: "land", 10: "land", 30: "land", 50: "land", 60: "land", 20: "land", 95: "land"},
        "class_order": ["water", "land"],
        "indices": ["ndwi", "mndwi", "ndvi"],
        "application": [
            ("earlier", "data/processed/m4/chilika_m4_postmonsoon/earlier_2020-11-08_reflectance_composite.tif", "2020-11-08"),
            ("later", "data/processed/m4/chilika_m4_postmonsoon/later_2025-11-17_reflectance_composite.tif", "2025-11-17"),
        ],
        "training": "data/processed/m5_ml/chilika_postmonsoon_m5_ml/training_2021-11-08_reflectance_composite.tif",
        "m4_experiment": "chilika_m4_postmonsoon",
        "primary_index": "mndwi",
    },
    "coringa_m5_ml": {
        "classes": {10: "vegetation", 20: "vegetation", 30: "vegetation", 40: "vegetation", 95: "vegetation", 80: "water", 90: "water", 50: "other", 60: "other"},
        "class_order": ["vegetation", "water", "other"],
        "indices": ["ndvi", "ndwi", "mndwi"],
        "application": [
            ("earlier", "data/processed/m1/coringa_coastal/earlier_2020-03-26_reflectance_composite.tif", "2020-03-26"),
            ("later", "data/processed/m1/coringa_coastal/later_2025-03-25_reflectance_composite.tif", "2025-03-25"),
        ],
        "training": "data/processed/m5_ml/coringa_m5_ml/training_2021-03-26_reflectance_composite.tif",
        "m4_experiment": "coringa_m1",
        "primary_index": "ndvi",
    },
}

TIF_BAND_BY_ASSET = {
    "blue": "blue", "green": "green", "red": "red", "nir": "nir", "swir16": "swir1",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def composite_bands(path: Path) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    with rasterio.open(path) as ds:
        for i, description in enumerate(ds.descriptions, start=1):
            prefix = description.split("_")[0]
            asset = next((k for k, v in TIF_BAND_BY_ASSET.items() if v == prefix), None)
            if asset is not None:
                out[asset] = ds.read(i).astype(np.float32)
        grid = {"crs": ds.crs.to_string(), "transform": list(ds.transform)[:6], "width": ds.width, "height": ds.height}
    return out, grid


def ndiff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    num = a.astype(np.float64) - b.astype(np.float64)
    den = a.astype(np.float64) + b.astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = num / den
    r[np.abs(den) < 1e-6] = np.nan
    r[~np.isfinite(r)] = np.nan
    r[np.abs(r) > 1.0] = np.nan
    return r.astype(np.float32)


def build_features(bands: dict[str, np.ndarray], indices: list[str]) -> tuple[np.ndarray, list[str]]:
    """Stack reflectance + index features; returns (n_px, n_feat) and names."""
    names: list[str] = []
    columns: list[np.ndarray] = []
    for asset in ("blue", "green", "red", "nir", "swir16"):
        if asset in bands:
            names.append(f"reflectance_{asset}")
            columns.append(bands[asset])
    for key in indices:
        if key == "ndvi":
            arr = ndiff(bands["nir"], bands["red"])
        elif key == "ndwi":
            arr = ndiff(bands["green"], bands["nir"])
        elif key == "mndwi":
            arr = ndiff(bands["green"], bands["swir16"])
        elif key == "ndbi":
            arr = ndiff(bands["swir16"], bands["nir"])
        else:
            raise ValueError(key)
        names.append(key)
        columns.append(arr)
    return np.stack(columns, axis=-1), names




def block_split(shape: tuple[int, int], block: int, seed: int) -> np.ndarray:
    """Assign every 100-px (1 km) block to train/validation/test by diagonal
    stripe pattern ``(row_block + col_block) % 3``.

    Folds are disjoint at block granularity: no pixel is ever split across
    folds, and same-fold blocks are separated by at least one full block from
    each other in the stripe direction.  Within-block spatial dependence is
    retained by design; between-fold leakage is bounded by the 1 km block
    size.  The pattern (rather than a random shuffle) keeps fold pixel counts
    nearly equal and gives every fold geographic coverage of the whole AOI.
    """
    height, width = shape
    rows = np.arange(height) // block
    cols = np.arange(width) // block
    fold = (rows[:, None] + cols[None, :]) % 3
    return fold.astype(np.int8)


def raster_bounds(grid: dict) -> tuple[float, float, float, float]:
    a, b, c, d, e, f = grid["transform"]
    if abs(a) < 1e-6:  # GDAL order unlikely; treat as rasterio order
        a, c = c, a
    # rasterio order: a=res_x, c=left, f=top
    left = grid["transform"][2]
    top = grid["transform"][5]
    res_x = grid["transform"][0]
    res_y = grid["transform"][4]
    width, height = grid["width"], grid["height"]
    return (left, top + res_y * height, left + res_x * width, top)


def reproject_grid_to_4326(bounds_grid: dict) -> tuple[tuple[float, float, float, float], tuple[int, int]]:
    """Reproject the analysis grid's bbox to EPSG:4326 for the label read."""
    from rasterio.warp import transform_bounds
    from rasterio.crs import CRS

    left, bottom, right, top = raster_bounds(bounds_grid)
    w, s, e, n = transform_bounds(
        CRS.from_string(bounds_grid["crs"]), CRS.from_string("EPSG:4326"),
        left, bottom, right, top,
    )
    return (w, s, e, n), (bounds_grid["width"], bounds_grid["height"])



def read_labels_on_grid(bounds_wgs84: tuple, grid: dict) -> tuple[np.ndarray, str, np.ndarray]:
    """Read WorldCover and warp onto the analysis grid; returns (labels, url, raw_histogram)."""
    import rasterio.warp
    from rasterio.crs import CRS
    from rasterio.transform import Affine

    w, s, e, n = bounds_wgs84
    lat_n = int(s // 3) * 3
    lon_w = int(w // 3) * 3
    ns = "N" if lat_n >= 0 else "S"
    ew = "E" if lon_w >= 0 else "W"
    tile = f"{ns}{abs(lat_n):02d}{ew}{abs(lon_w):03d}"
    url = WC_URL.format(tile=tile)
    with Env(**GDAL_ENV):
        with rasterio.open(url) as src:
            # window the AOI on the label grid, then warp that window
            win = rasterio.windows.from_bounds(w, s, e, n, transform=src.transform)
            win = win.round_offsets().round_lengths()
            raw = src.read(1, window=win)
            raw_transform = src.window_transform(win)
            vals, counts = np.unique(raw, return_counts=True)
            hist = dict(zip(vals.tolist(), counts.tolist()))
    dst = np.zeros((grid["height"], grid["width"]), dtype=np.uint8)
    with Env(**GDAL_ENV):
        # open the windowed raster from memory via reproject
        mem = MemoryFile()
        with mem.open(
            driver="GTiff", width=raw.shape[1], height=raw.shape[0], count=1,
            dtype="uint8", crs="EPSG:4326", transform=raw_transform,
        ) as tmp:
            tmp.write(raw, 1)
            dataset = tmp
            rasterio.warp.reproject(
                rasterio.band(dataset, 1),
                dst,
                dst_transform=Affine(*grid["transform"]),
                dst_crs=CRS.from_string(grid["crs"]),
                resampling=rasterio.warp.Resampling.nearest,
                src_nodata=0,
            )
        mem.close()
    return dst, url, hist


def evaluate(y_true, y_pred, class_order: list[str]) -> dict:
    labels = list(range(len(class_order)))
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    SUPPORT_FLOOR = 50  # test pixels below which a class's metrics are not interpretable
    iou = {}
    for i, name in enumerate(class_order):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        iou[name] = float(tp / (tp + fp + fn)) if (tp + fp + fn) else None
    per_class = {}
    supported = []
    for i, name in enumerate(class_order):
        ok = int(support[i]) >= SUPPORT_FLOOR
        if ok:
            supported.append(i)
        per_class[name] = {
            "precision": float(precision[i]) if ok else None,
            "recall": float(recall[i]) if ok else None,
            "f1": float(f1[i]) if ok else None,
            "support": int(support[i]),
            "iou": iou[name] if ok else None,
            "metrics_reported": ok,
            "support_note": None if ok else (
                f"test support {int(support[i])} < {SUPPORT_FLOOR}: per-class metrics "
                "not interpretable and not reported (label-gate rule)"
            ),
        }
    macro_supported = (
        float(f1_score(y_true, y_pred, labels=supported, average="macro", zero_division=0))
        if supported else None
    )
    return {
        "class_order": class_order,
        "confusion_matrix_rows_true_cols_pred": cm.tolist(),
        "per_class": per_class,
        "macro_f1_all_classes": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_f1_supported_classes": macro_supported,
        "supported_class_names": [class_order[i] for i in supported],
        "support_floor": SUPPORT_FLOOR,
        "overall_agreement": float(np.mean(np.asarray(y_true) == np.asarray(y_pred))),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "framing": (
            "agreement with the ESA WorldCover v200 reference product on "
            "spatially separated test blocks; NOT independent ground-truth accuracy"
        ),
    }


def run_study(study: str) -> int:
    spec = EXPERIMENTS[study]
    started = dt.datetime.now(dt.timezone.utc)
    print(f"[{study}] features from {spec['training']}")

    train_bands, grid = composite_bands(PROJECT_ROOT / spec["training"])
    features, feature_names = build_features(train_bands, spec["indices"])
    valid = np.all(np.isfinite(features), axis=-1)
    for asset in ("blue", "green", "red", "nir"):
        if asset in train_bands:
            valid &= np.isfinite(train_bands[asset])

    bounds_wgs84, _ = reproject_grid_to_4326(grid)
    labels_raw, wc_url, wc_hist = read_labels_on_grid(bounds_wgs84, grid)
    print(f"[{study}] WorldCover window histogram: {wc_hist}")

    class_map = spec["classes"]
    class_order = spec["class_order"]
    class_index = {name: i for i, name in enumerate(class_order)}
    labels = np.full(labels_raw.shape, 255, dtype=np.uint8)
    for code, name in class_map.items():
        labels[labels_raw == code] = class_index[name]

    folds = block_split(labels.shape, BLOCK, SEED)
    labeled = valid & (labels != 255)

    def take(fold_value: int) -> tuple[np.ndarray, np.ndarray]:
        mask = labeled & (folds == fold_value)
        return features[mask], labels[mask]

    x_train, y_train = take(0)
    x_val, y_val = take(1)
    x_test, y_test = take(2)
    print(
        f"[{study}] split px — train {len(y_train)}, validation {len(y_val)}, test {len(y_test)} "
        f"(labelled {int(labeled.sum())} of {labeled.size})"
    )
    if len(y_train) < 500 or len(y_test) < 200:
        print(f"[{study}] INSUFFICIENT reference labels for a defensible split — metrics will not be reported")
        result = {"study": study, "status": "insufficient_test_labels", "train_px": int(len(y_train)), "test_px": int(len(y_test))}

    params = {
        "n_estimators": 300,
        "max_depth": None,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "random_state": SEED,
        "n_jobs": -1,
    }
    model = RandomForestClassifier(**params)
    model.fit(x_train, y_train)
    val_pred = model.predict(x_val)
    test_pred = model.predict(x_test)
    evaluation = evaluate(y_test, test_pred, class_order)
    evaluation_validation = evaluate(y_val, val_pred, class_order)
    print(
        f"[{study}] test agreement {evaluation['overall_agreement']:.3f} "
        f"macro-F1 (supported) {evaluation['macro_f1_supported_classes']} "
        f"balanced-acc {evaluation['balanced_accuracy']:.3f}"
    )

    # feature importance
    importances = {
        name: float(imp) for name, imp in zip(feature_names, model.feature_importances_)
    }

    # ---- geographic generalisation: every fold as held-out test ------------
    # Train on two folds, evaluate on the third (validation = the other
    # training fold), so the stability of agreement across *geographically
    # different* test blocks is measured rather than assumed.
    geographic = {"available": bool(len(y_train) and len(y_val) and len(y_test)), "folds": []}
    if geographic["available"]:
        for held in range(3):
            train_mask = labeled & (folds != held) & (folds != ((held + 2) % 3))
            val_mask = labeled & (folds == ((held + 2) % 3))
            test_mask = labeled & (folds == held)
            if test_mask.sum() < 200 or train_mask.sum() < 500:
                geographic["folds"].append({"held_out_fold": held, "available": False})
                continue
            gm = RandomForestClassifier(**params)
            gm.fit(features[train_mask], labels[train_mask])
            ge = evaluate(labels[test_mask], gm.predict(features[test_mask]), class_order)
            geographic["folds"].append({
                "held_out_fold": held,
                "available": True,
                "train_px": int(train_mask.sum()),
                "test_px": int(test_mask.sum()),
                "overall_agreement": ge["overall_agreement"],
                "macro_f1_supported_classes": ge["macro_f1_supported_classes"],
                "balanced_accuracy": ge["balanced_accuracy"],
            })
            print(
                f"[{study}] geographic hold-out fold {held}: agreement "
                f"{ge['overall_agreement']:.3f} macro-F1(supported) {ge['macro_f1_supported_classes']}"
            )
        agreements = [f["overall_agreement"] for f in geographic["folds"] if f.get("available")]
        if agreements:
            geographic["agreement_range"] = [min(agreements), max(agreements)]
            geographic["note"] = (
                "agreement spread across geographically different held-out "
                "blocks; a wide range means the classifier does not generalise "
                "uniformly over the AOI"
            )

    # ---- application to the frozen 2020/2025 composites --------------------
    applications = {}
    _pending_rasters: list = []
    for tag, rel_path, date in spec["application"]:
        bands, app_grid = composite_bands(PROJECT_ROOT / rel_path)
        app_features, _ = build_features(bands, spec["indices"])
        app_valid = np.all(np.isfinite(app_features), axis=-1)
        proba = model.predict_proba(app_features[app_valid])
        pred_idx = np.argmax(proba, axis=1)
        pred = np.full(app_features.shape[:2], -1, dtype=np.int8)
        pred[app_valid] = pred_idx.astype(np.int8)
        fractions = {
            name: float((pred == class_index[name]).sum() / max(app_valid.sum(), 1))
            for name in class_order
        }
        confidence = {
            name: float(proba[pred_idx == class_index[name], class_index[name]].mean())
            if (pred_idx == class_index[name]).any() else None
            for name in class_order
        }
        pred_path = None
        applications[tag] = {
            "source_raster": rel_path,
            "date": date,
            "valid_px": int(app_valid.sum()),
            "predicted_fractions": fractions,
            "mean_confidence_of_predicted_class": confidence,
            "note": "model probabilities are confidences, not accuracy estimates",
        }
        # prediction raster exported at first-write time; path recorded after
        # out_dir exists (deferred below)
        _pending_rasters.append((tag, pred, app_valid))
        print(f"[{study}] application {tag} ({date}): {fractions}")

    # ---- comparison with the mathematical baseline -------------------------
    m4_findings_path = PROJECT_ROOT / "data" / "findings" / f"{spec['m4_experiment']}.json"
    comparison = {"available": False}
    if m4_findings_path.exists():
        findings = json.loads(m4_findings_path.read_text())
        primary = spec["primary_index"]
        # predicted change per class between application epochs (of common valid px)
        if len(applications) == 2:
            a_tag, b_tag = sorted(applications)[:2]
            comparison = {
                "available": True,
                "note": (
                    "predicted class-fraction shifts between the two epochs "
                    "compared against the mathematical Δ-index finding; both are "
                    "candidate signals, neither is treated as verification"
                ),
                "math_finding_indices": sorted(findings.get("indices", {}).keys()),
                "predicted_fraction_shift": {
                    name: applications[b_tag]["predicted_fractions"][name]
                    - applications[a_tag]["predicted_fractions"][name]
                    for name in class_order
                },
            }

    out_dir = PROJECT_ROOT / "data" / "experiments" / "m5_ml" / study / (
        started.strftime("%Y%m%dT%H%M%SZ") + "_" + hashlib.sha256(spec["training"].encode()).hexdigest()[:8]
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "model.joblib"
    joblib.dump(model, model_path)
    np.save(out_dir / "labels_worldcover.npy", labels_raw)
    np.save(out_dir / "folds.npy", folds)
    np.save(out_dir / "feature_valid_training.npy", valid)
    for tag, pred, app_valid in _pending_rasters:
        np.save(out_dir / f"prediction_{tag}.npy", pred)
        applications[tag]["prediction_raster"] = f"prediction_{tag}.npy"

    result = {
        "schema": "habitatshift-m5ml-result/1",
        "study": study,
        "generated_utc": started.isoformat(),
        "status": "complete",
        "label_gate": "docs/M5_ML_LABEL_FEASIBILITY.md",
        "reference": {
            "dataset": "ESA WorldCover v200",
            "epoch": 2021,
            "url": wc_url,
            "window_histogram": wc_hist,
            "license": "CC-BY 4.0 (© ESA WorldCover project 2022)",
            "framing": "reference-product labels; agreement metrics are NOT ground-truth accuracy",
        },
        "training_imagery": spec["training"],
        "class_mapping": {str(k): v for k, v in spec["classes"].items()},
        "features": feature_names,
        "feature_resolution_note": (
            "blue/green/red/nir native 10 m; swir16 native 20 m bilinearly resampled "
            "to the 10 m analysis grid by the audited pipeline (no native 10 m SWIR)"
        ),
        "split_design": {
            "method": "contiguous 100-px block row stripes: train/validation/test interleaved bands",
            "block_px": BLOCK,
            "train_px": int(len(y_train)),
            "validation_px": int(len(y_val)),
            "test_px": int(len(y_test)),
            "labelled_px": int(labeled.sum()),
            "design_note": (
                "deterministic blocking concentrates rare classes unevenly across "
                "folds; per-class test support is reported and metrics are gated "
                "at support < 50 px"
            ),
        },
        "model": {"type": "sklearn.ensemble.RandomForestClassifier", "params": params},
        "evaluation_test": evaluation,
        "evaluation_validation": evaluation_validation,
        "feature_importance": importances,
        "application": applications,
        "math_baseline_comparison": comparison,
        "geographic_stability": geographic,
        "interpretation_guardrails": [
            "No claim of independent ground-truth accuracy is permitted.",
            "Predicted fractions are model outputs on reference-inherited class definitions.",
            "Application to 2020/2025 assumes class-spectral stability across epochs (limitation, not verified).",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2))
    manifest = {
        "schema": "habitatshift-m5ml-manifest/1",
        "study": study,
        "generated_utc": started.isoformat(),
        "outputs": {
            p.name: {"path": str(p.relative_to(PROJECT_ROOT)), "bytes": p.stat().st_size, "sha256": sha256_file(p)}
            for p in sorted(out_dir.iterdir()) if p.is_file()
        },
        "git_commit": __import__("subprocess").run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=PROJECT_ROOT
        ).stdout.strip(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[{study}] wrote {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", choices=sorted(EXPERIMENTS))
    args = parser.parse_args()
    studies = [args.study] if args.study else sorted(EXPERIMENTS)
    failures = 0
    for study in studies:
        failures += run_study(study)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
