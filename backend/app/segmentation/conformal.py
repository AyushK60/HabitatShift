"""Split conformal intervals for lake area, and metrics for masks."""
from __future__ import annotations

import numpy as np

PIXEL_KM2 = 1e-4  # 10 m x 10 m


def iou(pred: np.ndarray, truth: np.ndarray, ok: np.ndarray) -> float:
    p, t = pred & ok, truth & ok
    union = (p | t).sum()
    return float((p & t).sum() / union) if union else float("nan")


def area_km2(mask: np.ndarray, ok: np.ndarray | None = None) -> float:
    return float((mask & ok).sum() if ok is not None else mask.sum()) * PIXEL_KM2


def conformal_scores(predicted: np.ndarray, truth: np.ndarray, floor: float = 0.1) -> np.ndarray:
    """Relative error |truth - predicted| / max(predicted, floor): intervals scale with lake size."""
    return np.abs(truth - predicted) / np.maximum(predicted, floor)


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """The ceil((n+1)(1-alpha))/n quantile, which gives >= 1-alpha coverage for exchangeable data."""
    n = len(scores)
    k = int(np.ceil((n + 1) * (1 - alpha)))
    if k > n:
        return float("inf")
    return float(np.sort(scores)[k - 1])


def interval(predicted: np.ndarray, q: float, floor: float = 0.1) -> tuple[np.ndarray, np.ndarray]:
    half = q * np.maximum(predicted, floor)
    return np.maximum(predicted - half, 0.0), predicted + half


def coverage(truth: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    return float(np.mean((truth >= lo) & (truth <= hi)))
