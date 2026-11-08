"""M5-G4: exploratory K-means clustering (two studies only, by design).

K-means is applied where exploring spectral-similarity patterns adds
something the supervised and mathematical methods do not already show:

- kathmandu: does the inner-city scene contain spectrally coherent groups
  the built-up/vegetation classifier merges (construction sites, bare
  riverbed, industrial roofs)?
- coringa: how many spectrally distinct groups structure the mangrove/
  water/mudflat gradient, and how do they align with the classifier's
  vegetation/water split?

A cluster is a spectral-similarity group, never a named environmental class;
no cluster is interpreted as change.  Documented: features, scaling, k,
initialisation, seed, cluster statistics, spatial patterns, interpretation
limitations.  Usage: python scripts/run_m5_kmeans.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from scripts.run_m5_ml import build_features  # feature builder reused verbatim  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

RUNS = {
    "kathmandu": {
        "composite": "data/processed/m4/kathmandu_m4/later_2025-03-29_reflectance_composite.tif",
        "indices": ["ndbi", "ndvi", "ndwi"],
        "k": 8,
        "rf_prediction": ("kathmandu_m5_ml", "later"),
    },
    "coringa": {
        "composite": "data/processed/m1/coringa_coastal/later_2025-03-25_reflectance_composite.tif",
        "indices": ["ndvi", "ndwi", "mndwi"],
        "k": 6,
        "rf_prediction": ("coringa_m5_ml", "later"),
    },
}
SEED = 20261108


def main() -> int:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    failures = 0
    for name, spec in RUNS.items():
        started = dt.datetime.now(dt.timezone.utc)
        import rasterio

        bands = {}
        prefix_to_asset = {"blue": "blue", "green": "green", "red": "red", "nir": "nir", "swir1": "swir16"}
        with rasterio.open(ROOT / spec["composite"]) as ds:
            descriptions = ds.descriptions
            grid = {"crs": ds.crs.to_string(), "transform": list(ds.transform)[:6]}
            for i, d in enumerate(descriptions, start=1):
                asset = prefix_to_asset.get(d.split("_")[0])
                if asset:
                    bands[asset] = ds.read(i).astype(np.float32)
        features, feature_names = build_features(bands, spec["indices"])
        valid = np.all(np.isfinite(features), axis=-1)

        # z-score scaling on valid pixels (documented)
        scaler = StandardScaler()
        scaled = scaler.fit_transform(features[valid])

        km = KMeans(
            n_clusters=spec["k"], init="k-means++", n_init=10,
            random_state=SEED,
        )
        labels = km.fit_predict(scaled)
        cluster_map = np.full(valid.shape, -1, dtype=np.int8)
        cluster_map[valid] = labels.astype(np.int8)

        # cluster statistics on the raw (unscaled) features
        stats = []
        for c in range(spec["k"]):
            mask = cluster_map == c
            if not mask.any():
                continue
            means = {
                feature_names[j]: round(float(features[..., j][mask].mean()), 4)
                for j in range(features.shape[-1])
            }
            stats.append({
                "cluster": c,
                "pixels": int(mask.sum()),
                "fraction_of_valid": round(float(mask.sum() / max(valid.sum(), 1)), 4),
                "mean_raw_features": means,
            })
        stats.sort(key=lambda s: -s["pixels"])

        # crosstab with the RF prediction (exploratory alignment, not agreement)
        rf_study, rf_tag = spec["rf_prediction"]
        rf_runs = sorted((ROOT / "data" / "experiments" / "m5_ml" / rf_study).iterdir())
        rf_pred = np.load(rf_runs[-1] / f"prediction_{rf_tag}.npy")
        crosstab = {}
        if rf_pred.shape == cluster_map.shape:
            both = (cluster_map >= 0) & (rf_pred >= 0)
            for c in range(spec["k"]):
                row = {}
                for r in range(int(rf_pred.max()) + 1):
                    row[f"rf_class_{r}"] = int(((cluster_map == c) & (rf_pred == r) & both).sum())
                crosstab[str(c)] = row

        inertia = float(km.inertia_)
        out_dir = ROOT / "data" / "experiments" / "m5_kmeans" / name / (
            started.strftime("%Y%m%dT%H%M%SZ") + "_" + hashlib.sha256(spec["composite"].encode()).hexdigest()[:8]
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        np.save(out_dir / "cluster_map.npy", cluster_map)
        result = {
            "schema": "habitatshift-m5-kmeans/1",
            "study": name,
            "generated_utc": started.isoformat(),
            "source_composite": spec["composite"],
            "features": feature_names,
            "scaling": "z-score (sklearn StandardScaler) over valid pixels",
            "k": spec["k"],
            "init": "k-means++",
            "n_init": 10,
            "random_state": SEED,
            "inertia": inertia,
            "valid_pixels": int(valid.sum()),
            "cluster_statistics": stats,
            "rf_prediction_crosstab_exploratory": crosstab,
            "interpretation_limits": [
                "A cluster is a spectral-similarity group, not a named environmental class.",
                "Cluster membership is not evidence of change; no change claim is made from it.",
                "k was chosen for interpretability, not optimised; no cluster-quality metric is claimed as validation.",
            ],
        }
        (out_dir / "result.json").write_text(json.dumps(result, indent=2))
        manifest = {
            "schema": "habitatshift-m5-kmeans-manifest/1",
            "study": name,
            "outputs": {
                p.name: {"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size,
                         "sha256": __import__("hashlib").sha256(p.read_bytes()).hexdigest()}
                for p in sorted(out_dir.iterdir()) if p.is_file()
            },
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        print(f"[{name}] k={spec['k']} inertia={inertia:.1f} top clusters: "
              + ", ".join(f"c{s['cluster']} {s['fraction_of_valid']:.1%}" for s in stats[:4])
              + f" -> {out_dir}")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
