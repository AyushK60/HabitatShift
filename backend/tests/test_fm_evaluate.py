"""Offline tests for the ranking metrics and the spatial block bootstrap."""
from __future__ import annotations

import numpy as np
import pytest

from backend.app.foundation import evaluate as E


def test_perfect_score_has_perfect_metrics():
    y = np.array([0] * 90 + [1] * 10)
    score = y.astype(float) + np.linspace(0, 0.01, 100)
    m = E.metrics(y, score)
    assert m["average_precision"] == pytest.approx(1.0) and m["roc_auc"] == pytest.approx(1.0)
    assert m["tpr_at_fpr_1pct"] == pytest.approx(1.0)


def test_random_score_is_near_the_base_rate():
    rng = np.random.default_rng(0)
    y = (rng.random(4000) < 0.2).astype(int)
    m = E.metrics(y, rng.random(4000))
    assert abs(m["average_precision"] - 0.2) < 0.04 and abs(m["roc_auc"] - 0.5) < 0.04


def test_block_ids_group_neighbours():
    rows, cols = np.indices((16, 16))
    ids = E.block_ids(rows.ravel(), cols.ravel(), 8)
    assert len(np.unique(ids)) == 4
    assert ids[0] == ids[1] and ids[0] != ids[8 + 8 * 16 - 8]


def test_bootstrap_separates_a_good_score_from_a_random_one():
    rng = np.random.default_rng(1)
    n = 3000
    rows, cols = np.indices((50, 60))
    blocks = E.block_ids(rows.ravel(), cols.ravel(), 8)
    y = (rng.random(n) < 0.25).astype(int)
    scores = {"good": y + rng.normal(0, 0.7, n), "random": rng.random(n)}
    out = E.block_bootstrap(y, scores, blocks, reference="random", n_boot=60)
    lo, hi = out["good"]["roc_auc"]["diff_vs_reference_ci95"]
    assert lo > 0.1
    assert out["n_boot_used"] > 50
    assert out["random"]["roc_auc"]["diff_vs_reference_ci95"] == [0.0, 0.0]
