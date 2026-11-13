"""Do foundation-model change scores find real forest loss better than indices, judged by the same noise?

Study: data/fm/<id>/ (see scripts/fm_make_study.py). Reference: Hansen Global Forest Change v1.12 (2000-2024),
CC-BY 4.0, Hansen et al. 2013 Science 342:850. This is agreement with another satellite product, not accuracy.

Design, fixed before any score was looked at
  unit         16 x 16 pixel patch (160 m)
  eligible     at least 50 % of the patch has treecover2000 >= 30 %, and the patch is valid in every scene
  positive     at least 10 % of the patch lost forest in 2022-2024 (between the two imaging dates)
  negative     under 2 % of the patch lost forest in 2021-2024; patches in between are set aside
  methods      ndvi, ndwi, mndwi, ndbi, indices5, raw6, prithvi, plus ndvi_decrease (signed: loss lowers NDVI)
  scores       raw change D, and noise-calibrated change z (D over the noise expected for that many scenes)
  metrics      average precision, ROC-AUC, recall at 1 % and 5 % false-positive rate
  uncertainty  spatial block bootstrap (blocks of 8 x 8 patches = 1.28 km), paired differences vs ndvi_decrease
Sensitivities: positives from 2021-2024, positive cut-off 5 % and 20 %.

    python scripts/run_fm_evaluation.py bastar_forest 20N_080E
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.foundation import compare as C  # noqa: E402
from backend.app.foundation import evaluate as E  # noqa: E402
from backend.app.foundation.prithvi import PrithviEmbedder, weights_sha256  # noqa: E402
from backend.app.foundation.resnet import SSL4EOResNetEmbedder  # noqa: E402
from backend.app.foundation.resnet import weights_sha256 as resnet_sha256  # noqa: E402
from backend.app.foundation.study import features_for, load_scenes  # noqa: E402

HANSEN = "https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12"
BLOCK = 8
REFERENCE_METHOD = "ndvi_decrease"


def hansen_layer(layer: str, tile: str, grid: dict, cache: Path) -> np.ndarray:
    if cache.exists():
        return np.load(cache)
    url = f"/vsicurl/{HANSEN}/Hansen_GFC-2024-v1.12_{layer}_{tile}.tif"
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_TIMEOUT="120"):
        with rasterio.open(url) as src, WarpedVRT(
            src, crs=CRS.from_string(grid["crs"]), transform=Affine(*grid["transform"][:6]),
            width=grid["width"], height=grid["height"], resampling=Resampling.nearest, nodata=src.nodata,
        ) as vrt:
            data = vrt.read(1)
    np.save(cache, data)
    return data


def patch_fraction(mask: np.ndarray) -> np.ndarray:
    return C.patch_mean(mask[None].astype("float32"), np.ones(mask.shape, bool))[0][..., 0]


def main(study_id: str, tile: str) -> None:
    folder = config.DATA_DIR / "fm" / study_id
    study = json.loads((folder / "study.json").read_text())
    grid = study["grid"]
    lossyear = hansen_layer("lossyear", tile, grid, folder / "hansen_lossyear.npy")
    cover = hansen_layer("treecover2000", tile, grid, folder / "hansen_treecover2000.npy")
    forest = cover >= 30

    scenes = load_scenes(folder / "scenes")
    earlier = [i for i, s in enumerate(scenes) if s[0]["period"] == "earlier"]
    later = [i for i, s in enumerate(scenes) if s[0]["period"] == "later"]
    embedder = PrithviEmbedder()
    embedders = {"prithvi": embedder, "ssl4eo_rgb": SSL4EOResNetEmbedder()}
    feats, oks = features_for(scenes, embedders)
    ok_all = np.logical_and.reduce(oks)

    scores: dict[str, np.ndarray] = {}
    for method in feats:
        res = C.change_scores(feats[method], oks, earlier, later)
        scores[f"{method}:D"], scores[f"{method}:z"] = res["D"], res["z"]
        if method == "ndvi":
            scores[f"{REFERENCE_METHOD}:D"], scores[f"{REFERENCE_METHOD}:z"] = -res["D_signed"], -res["z_signed"]

    forest_frac = patch_fraction(forest)

    def loss_frac(years):
        return patch_fraction(forest & (lossyear >= years[0]) & (lossyear <= years[1]))

    rows, cols = np.indices(forest_frac.shape)
    blocks_all = E.block_ids(rows, cols, BLOCK)

    def evaluate(pos_years, pos_cut, neg_years=(21, 24), neg_cut=0.02):
        pos_frac, neg_frac = loss_frac(pos_years), loss_frac(neg_years)
        finite = np.logical_and.reduce([np.isfinite(s) for s in scores.values()])
        eligible = (forest_frac >= 0.5) & ok_all & finite
        positive = eligible & (pos_frac >= pos_cut)
        negative = eligible & (neg_frac < neg_cut)
        use = positive | negative
        y = positive[use].astype(int)
        sc = {name: s[use] for name, s in scores.items()}
        base = {"eligible_patches": int(eligible.sum()), "positives": int(positive.sum()),
                "negatives": int(negative.sum()), "set_aside": int((eligible & ~use).sum()),
                "base_rate": round(float(y.mean()), 4)}
        point = {name: E.metrics(y, s) for name, s in sc.items()}
        return base, point, y, sc, blocks_all[use]

    base, point, y, sc, blocks = evaluate((22, 24), 0.10)
    boot = E.block_bootstrap(y, sc, blocks, reference=f"{REFERENCE_METHOD}:z", n_boot=500)
    sensitivities = {}
    variants = {"positives_2021_2024": ((21, 24), 0.10), "cutoff_5pct": ((22, 24), 0.05), "cutoff_20pct": ((22, 24), 0.20)}
    for label, args in variants.items():
        b, p, *_ = evaluate(*args)
        sensitivities[label] = {"counts": b, "average_precision": {k: round(v["average_precision"], 4) for k, v in p.items()}}

    operating = {}
    for name, s_ in sc.items():
        if name.endswith(":z"):
            operating[name] = {}
            for t in (2.0, 3.0):
                flagged = s_ > t
                tp, fp = int((flagged & (y == 1)).sum()), int((flagged & (y == 0)).sum())
                operating[name][str(t)] = {"false_positive_rate": round(fp / max(int((y == 0).sum()), 1), 4),
                                           "recall": round(tp / max(int((y == 1).sum()), 1), 4),
                                           "precision": round(tp / max(tp + fp, 1), 4)}

    result = {        "study_id": study_id, "reference": "Hansen GFC v1.12 (2000-2024), CC-BY 4.0", "tile": tile,
        "scenes": {"earlier": [scenes[i][0]["date"] for i in earlier], "later": [scenes[i][0]["date"] for i in later]},
        "models": {"prithvi": {"name": "Prithvi-EO-2.0-300M", "weights_sha256": weights_sha256(), "fp16": embedder.half},
                   "ssl4eo_rgb": {"name": "SSL4EO-S12 ResNet-50 RGB MoCo, layer3", "weights_sha256": resnet_sha256()}},
        "design": {"unit_px": 16, "positive": "loss 2022-2024 >= 10% of patch", "negative": "loss 2021-2024 < 2% of patch",
                   "eligible": "forest (treecover2000 >= 30%) >= 50% of patch, valid in all scenes",
                   "block_patches": BLOCK, "reference_method": f"{REFERENCE_METHOD}:z"},
        "counts": base, "metrics": point, "operating_points_z": operating, "block_bootstrap": boot, "sensitivity": sensitivities,
    }
    out = config.DATA_DIR / "experiments" / "v3_fm" / study_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(base))
    print("fixed rule z > 3 on clean negatives / real loss:")
    for name, o in operating.items():
        print(f"  {name:18s} FPR {o['3.0']['false_positive_rate']:.3f}  recall {o['3.0']['recall']:.3f}  precision {o['3.0']['precision']:.3f}")
    print(f"{'score':22s} {'AP':>6s} {'AUC':>6s} {'TPR@1%':>7s} {'TPR@5%':>7s}   AP 95% CI")
    for name in sorted(point, key=lambda n: -point[n]["average_precision"]):
        m, ci = point[name], boot[name]["average_precision"]["ci95"]
        print(f"{name:22s} {m['average_precision']:6.3f} {m['roc_auc']:6.3f} {m['tpr_at_fpr_1pct']:7.3f} {m['tpr_at_fpr_5pct']:7.3f}   [{ci[0]:.3f}, {ci[1]:.3f}]")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
