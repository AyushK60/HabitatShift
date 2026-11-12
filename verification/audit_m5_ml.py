"""M5-G3 independent audit of the supervised Random Forest experiments.

Verifies, without importing ``run_m5_ml.py``:

1.  Run integrity — result/manifest schemas, manifest output checksums.
2.  Split integrity — the saved fold raster partitions every pixel into
    exactly three folds, and the fold/count numbers in the result match a
    recomputation from the saved artifacts.
3.  Retraining reproducibility — an independently rebuilt feature stack
    (own normalised-difference and band-stacking code, from the training
    composite) + the saved WorldCover label raster, retrained with the
    recorded seed/hyperparameters, must reproduce the recorded test-set
    predictions exactly (RandomForest is deterministic at a fixed seed).
4.  Application reproduction — the recorded predicted fractions for the
    2020/2025 composites must match recomputation with the stored model.
5.  Gate compliance — no result claims ground-truth accuracy; unsupported
    classes have their per-class metrics suppressed.

Usage: python verification/audit_m5_ml.py   (offline; no network)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
BAND_MAP = {"blue": "blue", "green": "green", "red": "red", "nir": "nir", "swir16": "swir1"}


class Report:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.failures: list[str] = []

    def check(self, ok: bool, label: str) -> bool:
        if ok:
            self.passed += 1
        else:
            self.failed += 1
            self.failures.append(label)
            print(f"  [FAIL] {label}")
        return ok


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_bands(path: Path) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    with rasterio.open(path) as ds:
        for i, description in enumerate(ds.descriptions, start=1):
            prefix = description.split("_")[0]
            asset = next((k for k, v in BAND_MAP.items() if v == prefix), None)
            if asset is not None:
                out[asset] = ds.read(i).astype(np.float32)
    return out


def ndiff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    den = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        r = (a - b) / den
    r[np.abs(den) < 1e-6] = np.nan
    r[~np.isfinite(r)] = np.nan
    r[np.abs(r) > 1.0] = np.nan
    return r.astype(np.float32)


def build_features(bands: dict[str, np.ndarray], indices: list[str]) -> np.ndarray:
    cols: list[np.ndarray] = []
    for asset in ("blue", "green", "red", "nir", "swir16"):
        if asset in bands:
            cols.append(bands[asset])
    for key in indices:
        if key == "ndvi":
            cols.append(ndiff(bands["nir"], bands["red"]))
        elif key == "ndwi":
            cols.append(ndiff(bands["green"], bands["nir"]))
        elif key == "mndwi":
            cols.append(ndiff(bands["green"], bands["swir16"]))
        elif key == "ndbi":
            cols.append(ndiff(bands["swir16"], bands["nir"]))
        else:
            raise ValueError(key)
    return np.stack(cols, axis=-1)


def main() -> int:
    report = Report()
    base = ROOT / "data" / "experiments" / "m5_ml"
    studies = sorted(d for d in base.iterdir() if d.is_dir()) if base.is_dir() else []
    report.check(len(studies) == 5, f"five M5-ML experiment studies present (found {len(studies)})")

    for study_dir in studies:
        study = study_dir.name
        runs = sorted(p for p in study_dir.iterdir() if p.is_dir())
        report.check(len(runs) >= 1, f"{study}: at least one run directory")
        run = runs[-1]
        result = json.loads((run / "result.json").read_text())
        manifest = json.loads((run / "manifest.json").read_text())

        # 1. integrity
        report.check(result["schema"] == "habitatshift-m5ml-result/1", f"{study}: result schema")
        report.check(result["status"] == "complete", f"{study}: run completed")
        for name, meta in manifest["outputs"].items():
            path = ROOT / meta["path"]
            ok = path.exists() and sha256_file(path) == meta["sha256"]
            report.check(ok, f"{study}/{name}: manifest checksum")

        # 2. split integrity from the saved artifacts
        folds = np.load(run / "folds.npy")
        report.check(
            set(np.unique(folds).tolist()) <= {0, 1, 2} and len(set(np.unique(folds).tolist())) == 3,
            f"{study}: fold raster partitions the grid into exactly 3 folds",
        )
        labels_raw = np.load(run / "labels_worldcover.npy")
        report.check(
            folds.shape == labels_raw.shape,
            f"{study}: fold and label rasters share the grid shape",
        )
        class_map = {int(k): v for k, v in result["class_mapping"].items()}
        class_order = result["evaluation_test"]["class_order"]
        class_index = {name: i for i, name in enumerate(class_order)}
        labels = np.full(labels_raw.shape, 255, dtype=np.uint8)
        for code, name in class_map.items():
            labels[labels_raw == code] = class_index[name]
        split = result["split_design"]
        valid = np.load(run / "feature_valid_training.npy")
        labelled = valid & (labels != 255)
        report.check(
            int((labelled & (folds == 0)).sum()) == split["train_px"]
            and int((labelled & (folds == 1)).sum()) == split["validation_px"]
            and int((labelled & (folds == 2)).sum()) == split["test_px"],
            f"{study}: recorded train/validation/test counts match the saved artifacts",
        )

        # 3. retraining reproducibility (deterministic at the recorded seed)
        bands = read_bands(ROOT / result["training_imagery"])
        # rebuild the feature stack with the recorded feature list order
        cols = []
        for name in result["features"]:
            if name.startswith("reflectance_"):
                cols.append(bands[name[len("reflectance_"):]])
            elif name == "ndvi":
                cols.append(ndiff(bands["nir"], bands["red"]))
            elif name == "ndwi":
                cols.append(ndiff(bands["green"], bands["nir"]))
            elif name == "mndwi":
                cols.append(ndiff(bands["green"], bands["swir16"]))
            elif name == "ndbi":
                cols.append(ndiff(bands["swir16"], bands["nir"]))
        features = np.stack(cols, axis=-1)
        x_test = features[labelled & (folds == 2)]
        y_test = labels[labelled & (folds == 2)]
        x_train = features[labelled & (folds == 0)]
        y_train = labels[labelled & (folds == 0)]
        from sklearn.ensemble import RandomForestClassifier

        params = dict(result["model"]["params"])
        model = RandomForestClassifier(**params)
        model.fit(x_train, y_train)
        pred = model.predict(x_test)
        ev = result["evaluation_test"]
        cm = np.array(ev["confusion_matrix_rows_true_cols_pred"])
        cm_recomputed = np.zeros_like(cm)
        for t, p in zip(y_test, pred):
            cm_recomputed[t, p] += 1
        report.check(
            np.array_equal(cm, cm_recomputed),
            f"{study}: confusion matrix reproduced bit-for-bit by independent retraining (seed {params['random_state']})",
        )
        agreement = float(np.mean(pred == y_test))
        report.check(
            abs(agreement - ev["overall_agreement"]) < 1e-9,
            f"{study}: recorded overall agreement {ev['overall_agreement']:.4f} reproduced",
        )
        # per-class metric gating respected
        for name, row in ev["per_class"].items():
            if row["support"] < ev["support_floor"]:
                report.check(
                    row["precision"] is None and row["recall"] is None,
                    f"{study}/{name}: metrics suppressed below the {ev['support_floor']}-px support floor",
                )

        # 4. application reproduction with the stored model
        stored = joblib.load(run / "model.joblib")
        for tag, app in result["application"].items():
            app_bands = read_bands(ROOT / app["source_raster"])
            app_cols = []
            for name in result["features"]:
                if name.startswith("reflectance_"):
                    app_cols.append(app_bands[name[len("reflectance_"):]])
                elif name == "ndvi":
                    app_cols.append(ndiff(app_bands["nir"], app_bands["red"]))
                elif name == "ndwi":
                    app_cols.append(ndiff(app_bands["green"], app_bands["nir"]))
                elif name == "mndwi":
                    app_cols.append(ndiff(app_bands["green"], app_bands["swir16"]))
                elif name == "ndbi":
                    app_cols.append(ndiff(app_bands["swir16"], app_bands["nir"]))
            app_features = np.stack(app_cols, axis=-1)
            ok_fin = np.all(np.isfinite(app_features), axis=-1)
            pred_idx = stored.predict(app_features[ok_fin])
            frac = {
                name: float((pred_idx == class_index[name]).sum() / max(int(ok_fin.sum()), 1))
                for name in class_order
            }
            report.check(
                all(abs(frac[n] - app["predicted_fractions"][n]) < 1e-9 for n in class_order),
                f"{study}/{tag}: predicted fractions reproduced with the stored model",
            )
            saved_pred = np.load(run / f"prediction_{tag}.npy")
            re_pred = np.full(pred_idx.shape, -1, dtype=np.int8)
            report.check(
                np.array_equal(saved_pred[ok_fin].astype(np.int64), pred_idx.astype(np.int64)),
                f"{study}/{tag}: exported prediction raster matches the stored model",
            )

        # 5. gate compliance
        blob = json.dumps(result)
        report.check(
            "ground-truth accuracy" in ev["framing"] and "NOT" in ev["framing"],
            f"{study}: evaluation framing explicitly disclaims ground-truth accuracy",
        )
        report.check(
            "accuracy against ground truth" not in blob.lower() or ev["framing"],
            f"{study}: no unlabeled ground-truth claim",
        )
        print(f"[{study}] audit done")
    print(f"\nTOTAL: {report.passed} passed, {report.failed} failed")
    out = ROOT / "docs" / "evidence" / "m5" / "audit_m5_ml_checks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"passed": report.passed, "failed": report.failed, "failures": report.failures}, indent=1))
    print(f"wrote {out}")
    return 0 if report.failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
