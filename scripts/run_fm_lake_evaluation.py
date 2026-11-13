"""Do foundation-model change scores find glacial-lake water change better than indices?

Study folders: data/fm/lake_<id>/ (scripts/fm_make_study.py --lake, then scripts/fm_lake_reference.py).
Reference: Sentinel-1 water frequency per period (a different sensor from the optical data under test).
It is another satellite product with its own errors (radar underestimates some lakes), so this is agreement.

Design, fixed before any score was looked at
  unit         16 x 16 pixel patch (160 m)
  domain       patches within 6 patches (about 1 km) of the lake footprint; far-away land is trivially stable
  reference    change in mean radar water frequency between periods, absolute value
  positive     reference change >= 0.25 of the patch
  negative     reference change < 0.05 of the patch; patches in between are set aside
  methods      ndvi, ndwi, mndwi, ndbi, indices5, raw6, prithvi, ssl4eo_rgb (unsigned: water can grow or shrink)
  scores       raw change D and noise-calibrated change z
  metrics      average precision, ROC-AUC, recall at 1 % and 5 % false-positive rate
  uncertainty  spatial block bootstrap (8 x 8 patch blocks), paired difference vs mndwi z
  pooling      the lakes are pooled; if fewer than 30 positives result, the output says "underpowered"

    python scripts/run_fm_lake_evaluation.py lake_tsho_rolpa lake_imja_tsho lake_thulagi
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.foundation import compare as C  # noqa: E402
from backend.app.foundation import evaluate as E  # noqa: E402
from backend.app.foundation.prithvi import PrithviEmbedder  # noqa: E402
from backend.app.foundation.resnet import SSL4EOResNetEmbedder  # noqa: E402
from backend.app.foundation.study import features_for, load_scenes  # noqa: E402
from backend.app.radar import lakes as L  # noqa: E402

BLOCK = 8
DOMAIN_PATCHES = 6
POSITIVE, NEGATIVE = 0.25, 0.05
REFERENCE_METHOD = "mndwi:z"
MIN_POSITIVES = 30


def patch_mean(a: np.ndarray) -> np.ndarray:
    valid = np.isfinite(a)
    return C.patch_mean(np.where(valid, a, 0.0)[None].astype("float32"), valid)[0][..., 0]


def lake_inputs(study_id: str, embedders: dict) -> dict:
    folder = config.DATA_DIR / "fm" / study_id
    study = json.loads((folder / "study.json").read_text())
    lake = L.load_lakes()[study_id.removeprefix("lake_")]
    seed = np.load(lake.directory / "static.npz")["seed"]
    scenes = load_scenes(folder / "scenes")
    earlier = [i for i, s in enumerate(scenes) if s[0]["period"] == "earlier"]
    later = [i for i, s in enumerate(scenes) if s[0]["period"] == "later"]
    feats, oks = features_for(scenes, embedders)
    scores = {}
    for method in feats:
        res = C.change_scores(feats[method], oks, earlier, later)
        scores[f"{method}:D"], scores[f"{method}:z"] = res["D"], res["z"]
    f_early = np.load(folder / "radar_water_earlier.npy")
    f_late = np.load(folder / "radar_water_later.npy")
    delta = np.abs(patch_mean(f_late) - patch_mean(f_early))
    both = patch_mean(np.where(np.isfinite(f_early) & np.isfinite(f_late), 1.0, np.nan))
    seed_patches = patch_mean(seed.astype("float32")) > 0
    near = ndimage.binary_dilation(seed_patches, iterations=DOMAIN_PATCHES)
    return {"scores": scores, "delta": delta, "reference_ok": np.isfinite(delta) & (both > 0.9), "near": near,
            "ok": np.logical_and.reduce(oks), "scenes": (len(earlier), len(later))}


def main(study_ids: list[str]) -> None:
    embedders = {"prithvi": PrithviEmbedder(), "ssl4eo_rgb": SSL4EOResNetEmbedder()}
    ys, blocks, per_lake = [], [], {}
    pooled: dict[str, list] = {}
    for n, study_id in enumerate(study_ids):
        d = lake_inputs(study_id, embedders)
        finite = np.logical_and.reduce([np.isfinite(s) for s in d["scores"].values()])
        eligible = d["near"] & d["ok"] & d["reference_ok"] & finite
        positive, negative = eligible & (d["delta"] >= POSITIVE), eligible & (d["delta"] < NEGATIVE)
        use = positive | negative
        rows, cols = np.indices(use.shape)
        ys.append(positive[use].astype(int))
        blocks.append(E.block_ids(rows, cols, BLOCK)[use] + n * 10_000_000)
        for name, s in d["scores"].items():
            pooled.setdefault(name, []).append(s[use])
        per_lake[study_id] = {"scenes": {"earlier": d["scenes"][0], "later": d["scenes"][1]},
                              "domain_patches": int(eligible.sum()), "positives": int(positive.sum()),
                              "negatives": int(negative.sum()), "set_aside": int((eligible & ~use).sum())}
        print(study_id, per_lake[study_id], flush=True)
    y = np.concatenate(ys)
    sc = {name: np.concatenate(v) for name, v in pooled.items()}
    block = np.concatenate(blocks)
    counts = {"positives": int(y.sum()), "negatives": int((1 - y).sum()), "base_rate": round(float(y.mean()), 4)}
    underpowered = counts["positives"] < MIN_POSITIVES
    result = {"reference": "Sentinel-1 water-frequency change (Planetary Computer sentinel-1-rtc)", "per_lake": per_lake,
              "pooled_counts": counts, "underpowered": underpowered,
              "design": {"unit_px": 16, "domain_patches_from_lake": DOMAIN_PATCHES, "positive": f"|change| >= {POSITIVE}",
                         "negative": f"|change| < {NEGATIVE}", "block_patches": BLOCK, "reference_method": REFERENCE_METHOD}}
    if counts["positives"] >= 5 and counts["negatives"] >= 5:
        point = {name: E.metrics(y, s) for name, s in sc.items()}
        boot = E.block_bootstrap(y, sc, block, reference=REFERENCE_METHOD, n_boot=500)
        result.update(metrics=point, block_bootstrap=boot)
        print(json.dumps(counts), "UNDERPOWERED" if underpowered else "")
        print(f"{'score':16s} {'AP':>6s} {'AUC':>6s} {'TPR@5%':>7s}   AP 95% CI")
        for name in sorted(point, key=lambda k: -point[k]["average_precision"]):
            m, ci = point[name], boot[name]["average_precision"]["ci95"]
            print(f"{name:16s} {m['average_precision']:6.3f} {m['roc_auc']:6.3f} {m['tpr_at_fpr_5pct']:7.3f}   [{ci[0]:.3f}, {ci[1]:.3f}]")
    else:
        print("too few positives or negatives to evaluate:", counts)
    out = config.DATA_DIR / "experiments" / "v3_fm" / "lakes"
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation.json").write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
