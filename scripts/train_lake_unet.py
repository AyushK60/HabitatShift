"""Train and evaluate the radar water U-Net (Phase 3).

Design, fixed before training:
  * Whole lakes are split into train / calibration / test (hash-ordered, see segmentation/data.py).
  * Time hold-out: for training lakes, 2020-2021 pairs train the model and 2022 pairs are a separate test.
  * Pairs with weak labels (radar contrast above -3 dB, under 20 water pixels) are dropped everywhere.
  * Baseline: the Otsu radar rule already used in the lake series (radar/sar.py), no training.
  * Split conformal prediction of lake area (90%): calibrated on the calibration lakes, checked on the test lakes.
The labels are optical water masks, so every score is agreement with that rule, not accuracy against the ground.

    python scripts/train_lake_unet.py --epochs 30
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.radar import lakes as L  # noqa: E402
from backend.app.radar import sar  # noqa: E402
from backend.app.segmentation import conformal as C  # noqa: E402
from backend.app.segmentation import data as D  # noqa: E402
from backend.app.segmentation.train import fit as fit_model, predict  # noqa: E402

TRAIN_DIR = config.DATA_DIR / "lakes_train"
OUT_DIR = config.DATA_DIR / "models" / "lake_unet"
RESULT_DIR = config.DATA_DIR / "experiments" / "v3_unet"


def stack(parts: list[dict]) -> dict:
    return {"x": np.concatenate([p["x"] for p in parts]), "y": np.concatenate([p["y"] for p in parts]),
            "ok": np.concatenate([p["ok"] for p in parts]), "meta": sum((p["meta"] for p in parts), [])}


def subset(d: dict, mask: np.ndarray) -> dict:
    return {"x": d["x"][mask], "y": d["y"][mask], "ok": d["ok"][mask], "meta": [m for m, k in zip(d["meta"], mask) if k]}


def otsu_baseline(d: dict, slopes: dict) -> np.ndarray:
    preds = []
    for x, m in zip(d["x"], d["meta"]):
        vv = np.where(x[3] > 0, x[0] * 8.0 - 15.0, np.nan)
        power = np.where(np.isfinite(vv), 10 ** (vv / 10.0), np.nan).astype("float32")
        mask, _ = sar.water_mask(power, slopes[m["lake"]])
        preds.append(mask)
    return np.stack(preds)


def scores(pred_masks: np.ndarray, d: dict) -> dict:
    ious = [C.iou(p, t, o) for p, t, o in zip(pred_masks, d["y"], d["ok"])]
    return {"n_pairs": len(ious), "mean_iou": float(np.nanmean(ious)), "median_iou": float(np.nanmedian(ious))}


def area_pairs(masks: np.ndarray, d: dict) -> tuple[np.ndarray, np.ndarray]:
    pred = np.array([C.area_km2(p, o) for p, o in zip(masks, d["ok"])])
    truth = np.array([C.area_km2(t, o) for t, o in zip(d["y"], d["ok"])])
    return pred, truth


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--base", type=int, default=16)
    parser.add_argument("--tag", default="", help="suffix for output files, e.g. _seed1")
    args = parser.parse_args()
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    lake_ids = sorted(p.parent.name for p in TRAIN_DIR.glob("*/pairs.jsonl"))
    split = D.assign_split(lake_ids)
    per_lake, slopes = {}, {}
    for lake in lake_ids:
        loaded = D.load_lake_pairs(TRAIN_DIR, config.DATA_DIR / "lakes", lake)
        if loaded is not None:
            per_lake[lake] = loaded
            static = np.load(config.DATA_DIR / "lakes" / lake / "static.npz")
            r0, c0 = D.crop_window(static["seed"])
            slopes[lake] = static["slope"][r0:r0 + D.CROP, c0:c0 + D.CROP]
    groups = {s: [per_lake[l] for l in per_lake if split[l] == s] for s in ("train", "cal", "test")}
    print({s: (sum(len(g["y"]) for g in v), len(v)) for s, v in groups.items()}, "pairs, lakes", flush=True)
    train_all, cal, test_lakes = stack(groups["train"]), stack(groups["cal"]), stack(groups["test"])
    years = np.array([m["year"] for m in train_all["meta"]])
    train, time_test = subset(train_all, years <= 2021), subset(train_all, years == 2022)
    # hold out 10% of training pairs (random) to choose the epoch
    idx = rng.permutation(len(train["y"]))
    n_val = max(1, len(idx) // 10)
    val, fit = subset(train, np.isin(np.arange(len(idx)), idx[:n_val])), subset(train, ~np.isin(np.arange(len(idx)), idx[:n_val]))
    print(f"fit {len(fit['y'])}, val {len(val['y'])}, time test {len(time_test['y'])}, "
          f"cal {len(cal['y'])}, lake test {len(test_lakes['y'])}", flush=True)

    net, best, history = fit_model(fit, val, device, epochs=args.epochs, batch=args.batch, lr=args.lr, seed=args.seed,
                                   base=args.base)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    best_state = {k: t.detach().cpu().clone() for k, t in net.state_dict().items()}
    torch.save({"state": best_state, "base": args.base, "channels": D.CHANNELS, "seed": args.seed}, OUT_DIR / f"unet{args.tag}.pt")

    result = {"design": {"split": split, "min_contrast_db": D.MIN_CONTRAST_DB, "crop_px": D.CROP, "epochs": args.epochs,
                         "seed": args.seed, "best_val_iou": best},
              "history": history}
    probs = {}
    for name, d in (("val_random_holdout", val), ("time_holdout_2022_same_lakes", time_test),
                    ("calibration_lakes", cal), ("test_lakes", test_lakes)):
        p = predict(net, d["x"], device)
        probs[name] = p > 0.5
        base = otsu_baseline(d, slopes)
        result[name] = {"unet": scores(probs[name], d), "otsu_radar_rule": scores(base, d)}
        print(name, result[name], flush=True)
        probs[name + "_otsu"] = base

    cal_pred, cal_true = area_pairs(probs["calibration_lakes"], cal)
    results_area = {}
    for alpha in (0.2, 0.1, 0.05):
        q = C.conformal_quantile(C.conformal_scores(cal_pred, cal_true), alpha)
        entry = {"relative_half_width_q": q}
        for name, d in (("test_lakes", test_lakes), ("time_holdout_2022_same_lakes", time_test)):
            tp, tt = area_pairs(probs[name], d)
            lo, hi = C.interval(tp, q)
            entry[name] = {"coverage": C.coverage(tt, lo, hi), "median_relative_error": float(np.median(np.abs(tt - tp) / np.maximum(tt, 0.1))),
                           "median_interval_width_km2": float(np.median(hi - lo)), "n": len(tt)}
            per_lake = {}
            for lake in sorted({m["lake"] for m in d["meta"]}):
                k = np.array([m["lake"] == lake for m in d["meta"]])
                per_lake[lake] = {"coverage": C.coverage(tt[k], lo[k], hi[k]), "n": int(k.sum())}
            entry[name]["per_lake"] = per_lake
        results_area[f"alpha_{alpha}"] = entry
    result["conformal_area"] = results_area
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    (RESULT_DIR / f"evaluation{args.tag}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: {n: results_area[k][n]["coverage"] for n in ("test_lakes", "time_holdout_2022_same_lakes")}
                      for k in results_area}, indent=1))


if __name__ == "__main__":
    main()
