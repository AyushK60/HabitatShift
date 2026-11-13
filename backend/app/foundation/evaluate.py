"""Ranking metrics and a spatial block bootstrap for patch-level change scores."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve


def tpr_at_fpr(y: np.ndarray, score: np.ndarray, fpr: float) -> float:
    fprs, tprs, _ = roc_curve(y, score)
    return float(np.interp(fpr, fprs, tprs))


def metrics(y: np.ndarray, score: np.ndarray) -> dict[str, float]:
    return {"average_precision": float(average_precision_score(y, score)), "roc_auc": float(roc_auc_score(y, score)),
            "tpr_at_fpr_1pct": tpr_at_fpr(y, score, 0.01), "tpr_at_fpr_5pct": tpr_at_fpr(y, score, 0.05)}


def block_ids(rows: np.ndarray, cols: np.ndarray, size: int) -> np.ndarray:
    """Spatial block id per patch (size x size patches); nearby patches share a block."""
    return (rows // size) * 100000 + (cols // size)


def block_bootstrap(y: np.ndarray, scores: dict[str, np.ndarray], blocks: np.ndarray, reference: str,
                    n_boot: int = 500, seed: int = 0) -> dict:
    """Percentile intervals for each score's metrics and for its difference from ``reference`` (paired).

    Whole spatial blocks are resampled with replacement, so neighbouring patches (which are alike) stay
    together and the intervals are not too narrow.
    """
    rng = np.random.default_rng(seed)
    unique = np.unique(blocks)
    members = {b: np.flatnonzero(blocks == b) for b in unique}
    keys = list(metrics(y, scores[reference]).keys())
    draws = {name: {k: [] for k in keys} for name in scores}
    for _ in range(n_boot):
        pick = rng.choice(unique, size=unique.size, replace=True)
        idx = np.concatenate([members[b] for b in pick])
        yb = y[idx]
        if yb.min() == yb.max():
            continue
        for name, s in scores.items():
            m = metrics(yb, s[idx])
            for k in keys:
                draws[name][k].append(m[k])
    out: dict = {}
    for name in scores:
        out[name] = {}
        for k in keys:
            d = np.array(draws[name][k])
            ref = np.array(draws[reference][k])
            diff = d - ref
            out[name][k] = {"ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                            "diff_vs_reference_ci95": [float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5))]}
    out["n_boot_used"] = int(len(draws[reference][keys[0]]))
    return out
