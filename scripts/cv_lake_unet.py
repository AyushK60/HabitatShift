"""Leave-lakes-out cross-validation of the radar water U-Net, with conformal area intervals checked across lakes.

Why: the single split in train_lake_unet.py calibrated intervals on 4 lakes and they under-covered 6 other lakes.
Here all 30 lakes are split into 5 folds of whole lakes (hash order). For each fold a model is trained on the other
4 folds (10% of its pairs held out to pick the epoch) and predicts the held-out lakes on the whole tile, so every
lake gets predictions from a model that never saw it. Conformal intervals for lake area are then calibrated on the
out-of-fold errors of the other 4 folds and checked on the fold left out.

Lake area = water patches touching the lake seed (same rule as the lake time series), pixels with a usable optical
label only. Truth is the optical water mask, so this is agreement with that rule, not accuracy.

    python scripts/cv_lake_unet.py --epochs 30
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.radar import lakes as L  # noqa: E402
from backend.app.segmentation import conformal as C  # noqa: E402
from backend.app.segmentation import data as D  # noqa: E402
from backend.app.segmentation.train import fit, predict_tile  # noqa: E402

TRAIN_DIR = config.DATA_DIR / "lakes_train"
OUT_DIR = config.DATA_DIR / "models" / "lake_unet"
RESULT = config.DATA_DIR / "experiments" / "v3_unet" / "cv.json"
FOLDS = 5


def fold_of(lake_ids: list[str]) -> dict[str, int]:
    ranked = sorted(lake_ids, key=lambda i: hashlib.sha256(f"cv:{i}".encode()).hexdigest())
    return {lake: k % FOLDS for k, lake in enumerate(ranked)}


def stack(parts: list[dict]) -> dict:
    return {k: np.concatenate([p[k] for p in parts]) for k in ("x", "y", "ok")} | {"meta": sum((p["meta"] for p in parts), [])}


def tile_areas(net, lake: str, meta: list[dict], static: dict, device: str) -> list[dict]:
    seed, slope = static["seed"], static["slope"]
    out = []
    for m in meta:
        z = np.load(TRAIN_DIR / lake / "pairs" / f"{m['pair']}.npz")
        vv, vh = z["vv_db"].astype("float32"), z["vh_db"].astype("float32")
        ok = z["valid"] & np.isfinite(vv)
        prob = predict_tile(net, D.make_input(vv, vh, slope), device)
        pred_km2, _ = L.lake_patch_area((prob > 0.5) & ok, seed, 10.0)
        true_km2, _ = L.lake_patch_area(z["water"] & ok, seed, 10.0)
        out.append({"lake": lake, "pair": m["pair"], "year": m["year"], "pred_km2": pred_km2, "true_km2": true_km2,
                    "tile_iou": C.iou(prob > 0.5, z["water"], ok)})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=30)
    args = parser.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rng = np.random.default_rng(0)
    lake_ids = sorted(p.parent.name for p in TRAIN_DIR.glob("*/pairs.jsonl"))
    folds = fold_of(lake_ids)
    per_lake, statics = {}, {}
    for lake in lake_ids:
        loaded = D.load_lake_pairs(TRAIN_DIR, config.DATA_DIR / "lakes", lake)
        if loaded is not None:
            per_lake[lake] = loaded
            statics[lake] = dict(np.load(config.DATA_DIR / "lakes" / lake / "static.npz"))
    print(len(per_lake), "lakes loaded", flush=True)
    rows, fold_info = [], {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for k in range(FOLDS):
        held = [l for l in per_lake if folds[l] == k]
        train = stack([per_lake[l] for l in per_lake if folds[l] != k])
        idx = rng.permutation(len(train["y"]))
        n_val = len(idx) // 10
        is_val = np.isin(np.arange(len(idx)), idx[:n_val])
        pick = lambda m: {"x": train["x"][m], "y": train["y"][m], "ok": train["ok"][m]}
        net, best, history = fit(pick(~is_val), pick(is_val), device, epochs=args.epochs, seed=k, verbose=False)
        torch.save({"state": {a: b.cpu() for a, b in net.state_dict().items()}, "base": 16, "fold": k, "lakes_held_out": held},
                   OUT_DIR / f"unet_fold{k}.pt")
        for lake in held:
            rows += [dict(r, fold=k) for r in tile_areas(net, lake, per_lake[lake]["meta"], statics[lake], device)]
        fold_info[k] = {"lakes": held, "best_val_iou": best, "n_train_pairs": int((~is_val).sum())}
        print(f"fold {k}: held-out lakes {len(held)}, val IoU {best:.3f}", flush=True)

    pred = np.array([r["pred_km2"] for r in rows])
    true = np.array([r["true_km2"] for r in rows])
    fold = np.array([r["fold"] for r in rows])
    lake_arr = np.array([r["lake"] for r in rows])
    result = {"folds": fold_info, "epochs": args.epochs, "n_pairs": len(rows),
              "tile_mean_iou": float(np.nanmean([r["tile_iou"] for r in rows])),
              "median_relative_area_error": float(np.median(np.abs(true - pred) / np.maximum(true, 0.1)))}
    result["conformal"] = {}
    for alpha in (0.2, 0.1, 0.05):
        cover, per_lake_cov, per_fold = np.zeros(len(rows), bool), {}, {}
        widths = np.zeros(len(rows))
        for k in range(FOLDS):
            q = C.conformal_quantile(C.conformal_scores(pred[fold != k], true[fold != k]), alpha)
            lo, hi = C.interval(pred[fold == k], q)
            cover[fold == k] = (true[fold == k] >= lo) & (true[fold == k] <= hi)
            widths[fold == k] = hi - lo
            per_fold[k] = {"q": q, "coverage": float(cover[fold == k].mean())}
        for lake in per_lake:
            per_lake_cov[lake] = float(cover[lake_arr == lake].mean())
        result["conformal"][f"alpha_{alpha}"] = {
            "coverage_overall": float(cover.mean()), "per_fold": per_fold,
            "lake_coverage_min": min(per_lake_cov.values()), "lake_coverage_median": float(np.median(list(per_lake_cov.values()))),
            "lakes_below_target": int(sum(v < 1 - alpha - 0.1 for v in per_lake_cov.values())),
            "median_interval_width_km2": float(np.median(widths)), "per_lake": per_lake_cov}
        # Full-sample quantile, used for the monthly series of lakes
        result["conformal"][f"alpha_{alpha}"]["q_all_folds"] = C.conformal_quantile(C.conformal_scores(pred, true), alpha)
    result["rows"] = rows
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    for a, e in result["conformal"].items():
        print(a, "coverage", round(e["coverage_overall"], 3), "worst lake", round(e["lake_coverage_min"], 2),
              "median lake", round(e["lake_coverage_median"], 2), "lakes below", e["lakes_below_target"])


if __name__ == "__main__":
    main()
