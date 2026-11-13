"""Linear-probe baseline on frozen embeddings, leave-one-area-out. Design: studies/probe_design.yaml.

    python scripts/run_fm_probe.py
Writes data/experiments/v3_fm/probe/evaluation.json.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy import ndimage
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from backend.app import config  # noqa: E402
from backend.app.foundation import compare as C  # noqa: E402
from backend.app.foundation import evaluate as E  # noqa: E402
from backend.app.foundation.prithvi import PrithviEmbedder  # noqa: E402
from backend.app.foundation.resnet import SSL4EOResNetEmbedder  # noqa: E402
from backend.app.foundation.study import features_for, load_scenes  # noqa: E402
from backend.app.radar import lakes as L  # noqa: E402
import run_fm_evaluation as FE  # noqa: E402
import run_fm_lake_evaluation as LK  # noqa: E402

FOREST = {"bastar_forest": "20N_080E", "odisha_forest": "20N_080E", "kodagu_wayanad_forest": "20N_070E",
          "garo_hills_forest": "30N_090E", "uttarakhand_shivalik_forest": "30N_070E"}
LAKES = ["lake_tsho_rolpa", "lake_imja_tsho", "lake_thulagi", "lake_himag_gl087092e27798n"]
METHODS = ["prithvi", "ssl4eo_rgb", "raw6", "indices5"]
WIDE = "--wide" in sys.argv
CS = [0.00001, 0.0001, 0.001, 0.01, 0.1, 1.0] if WIDE else [0.001, 0.01, 0.1, 1.0]


def study_vectors(study_id: str, embedders: dict):
    """Change vectors u per method (h, w, d), the main-evaluation scores, and the all-scenes validity mask."""
    folder = config.DATA_DIR / "fm" / study_id
    scenes = load_scenes(folder / "scenes")
    earlier = [i for i, s in enumerate(scenes) if s[0]["period"] == "earlier"]
    later = [i for i, s in enumerate(scenes) if s[0]["period"] == "later"]
    feats, oks = features_for(scenes, embedders)
    scores, vectors = {}, {}
    for method in feats:
        res = C.change_scores(feats[method], oks, earlier, later)
        scores[f"{method}:D"], scores[f"{method}:z"] = res["D"], res["z"]
        if method == "ndvi":
            scores["ndvi_decrease:D"], scores["ndvi_decrease:z"] = -res["D_signed"], -res["z_signed"]
        if method in METHODS:
            sigma2 = C.noise_variance(feats[method], oks, [earlier, later])
            n_a = np.stack([oks[i] for i in earlier]).sum(0)
            n_b = np.stack([oks[i] for i in later]).sum(0)

            def mean_of(idx, method=method):
                stack = np.stack([np.where(oks[i][..., None], feats[method][i], np.nan) for i in idx])
                return np.nanmean(stack, axis=0)

            with np.errstate(invalid="ignore", divide="ignore"):
                scale = np.sqrt(sigma2 * (1 / n_a + 1 / n_b))[..., None]
                vectors[method] = ((mean_of(later) - mean_of(earlier)) / scale).astype("float32")
    return folder, scores, vectors, np.logical_and.reduce(oks)


def pack(use, positive, vectors, scores, blocks, reference):
    return {"y": positive[use].astype(int), "blocks": blocks[use],
            "X": {m: vectors[m][use] for m in METHODS}, "ref": scores[reference][use],
            "main": {m: scores[f"{m}:z"][use] for m in METHODS}}


def forest_dataset(study_id: str, tile: str, embedders):
    folder, scores, vectors, ok_all = study_vectors(study_id, embedders)
    grid = json.loads((folder / "study.json").read_text())["grid"]
    lossyear = FE.hansen_layer("lossyear", tile, grid, folder / "hansen_lossyear.npy")
    forest = FE.hansen_layer("treecover2000", tile, grid, folder / "hansen_treecover2000.npy") >= 30
    frac = FE.patch_fraction(forest)

    def loss(a, b):
        return FE.patch_fraction(forest & (lossyear >= a) & (lossyear <= b))

    finite = np.logical_and.reduce([np.isfinite(s) for s in scores.values()])
    eligible = (frac >= 0.5) & ok_all & finite
    positive, negative = eligible & (loss(22, 24) >= 0.10), eligible & (loss(21, 24) < 0.02)
    rows, cols = np.indices(positive.shape)
    return pack(positive | negative, positive, vectors, scores, E.block_ids(rows, cols, 8), "ndvi_decrease:z")


def lake_dataset(study_id: str, n: int, embedders):
    folder, scores, vectors, ok_all = study_vectors(study_id, embedders)
    lake = L.load_lakes()[study_id.removeprefix("lake_")]
    seed = np.load(lake.directory / "static.npz")["seed"]
    f0, f1 = np.load(folder / "radar_water_earlier.npy"), np.load(folder / "radar_water_later.npy")
    delta = np.abs(LK.patch_mean(f1) - LK.patch_mean(f0))
    both = LK.patch_mean(np.where(np.isfinite(f0) & np.isfinite(f1), 1.0, np.nan))
    near = ndimage.binary_dilation(LK.patch_mean(seed.astype("float32")) > 0, iterations=LK.DOMAIN_PATCHES)
    finite = np.logical_and.reduce([np.isfinite(s) for s in scores.values()])
    eligible = near & ok_all & np.isfinite(delta) & (both > 0.9) & finite
    positive, negative = eligible & (delta >= LK.POSITIVE), eligible & (delta < LK.NEGATIVE)
    rows, cols = np.indices(positive.shape)
    return pack(positive | negative, positive, vectors, scores, E.block_ids(rows, cols, 8) + n * 10_000_000, "mndwi:z")


def fit_predict(c: float, x_tr, y_tr, x_te):
    mu, sd = x_tr.mean(0), x_tr.std(0)
    sd[sd == 0] = 1.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clf = LogisticRegression(C=c, max_iter=3000, class_weight="balanced").fit((x_tr - mu) / sd, y_tr)
    return clf.decision_function((x_te - mu) / sd)


def choose_c(data: dict, train: list[str], method: str) -> float:
    best, best_ap = CS[0], -1.0
    for c in CS:
        aps = []
        for inner in train:
            fit = [k for k in train if k != inner]
            y_in = data[inner]["y"]
            if y_in.min() == y_in.max() or sum(data[k]["y"].sum() for k in fit) == 0:
                continue
            s = fit_predict(c, np.concatenate([data[k]["X"][method] for k in fit]),
                            np.concatenate([data[k]["y"] for k in fit]), data[inner]["X"][method])
            aps.append(average_precision_score(y_in, s))
        if aps and np.mean(aps) > best_ap:
            best, best_ap = c, float(np.mean(aps))
    return best


def leave_one_out(data: dict, pooled: bool):
    names = list(data)
    out_scores = {k: {} for k in names}
    chosen = {k: {} for k in names}
    for held in names:
        train = [k for k in names if k != held]
        for m in METHODS:
            c = choose_c(data, train, m)
            chosen[held][m] = c
            out_scores[held][m] = fit_predict(c, np.concatenate([data[k]["X"][m] for k in train]),
                                              np.concatenate([data[k]["y"] for k in train]), data[held]["X"][m])
        print("held out", held, flush=True)
    result = {"chosen_C": chosen, "groups": {}}
    groups = {"pooled": names} if pooled else {k: [k] for k in names}
    for label, members in groups.items():
        y = np.concatenate([data[k]["y"] for k in members])
        blocks = np.concatenate([data[k]["blocks"] for k in members])
        sc = {f"{m}:probe": np.concatenate([out_scores[k][m] for k in members]) for m in METHODS}
        sc.update({f"{m}:z": np.concatenate([data[k]["main"][m] for k in members]) for m in ("prithvi", "ssl4eo_rgb", "raw6")})
        sc["reference"] = np.concatenate([data[k]["ref"] for k in members])
        point = {n: E.metrics(y, s) for n, s in sc.items()}
        boot = E.block_bootstrap(y, sc, blocks, reference="reference", n_boot=500)
        boot_raw = E.block_bootstrap(y, sc, blocks, reference="raw6:probe", n_boot=500)
        result["groups"][label] = {
            "positives": int(y.sum()), "negatives": int((1 - y).sum()), "metrics": point,
            "ap_ci95": {n: boot[n]["average_precision"]["ci95"] for n in sc},
            "diff_vs_reference_ap_ci95": {n: boot[n]["average_precision"]["diff_vs_reference_ci95"] for n in sc},
            "diff_vs_raw6_probe_ap_ci95": {n: boot_raw[n]["average_precision"]["diff_vs_reference_ci95"] for n in sc}}
        print(label, {n: round(v["average_precision"], 3) for n, v in point.items()}, flush=True)
    return result


def main() -> None:
    embedders = {"prithvi": PrithviEmbedder(), "ssl4eo_rgb": SSL4EOResNetEmbedder()}
    forest = {s: forest_dataset(s, t, embedders) for s, t in FOREST.items()}
    lakes = {s: lake_dataset(s, n, embedders) for n, s in enumerate(LAKES)}
    result = {"design": "studies/probe_design.yaml", "Cs": CS, "methods": METHODS,
              "forest_reference": "ndvi_decrease:z", "lake_reference": "mndwi:z",
              "forest": leave_one_out(forest, pooled=False), "lakes": leave_one_out(lakes, pooled=True)}
    out = config.DATA_DIR / "experiments" / "v3_fm" / "probe"
    out.mkdir(parents=True, exist_ok=True)
    (out / ("evaluation_wider_C.json" if WIDE else "evaluation.json")).write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
