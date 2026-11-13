"""Offline tests for the noise-calibrated change scores (no GPU, no network)."""
from __future__ import annotations

import numpy as np

from backend.app.foundation import compare as C


def _scenes(n_a=3, n_b=3, h=20, w=20, d=4, noise=0.1, shift=None, seed=0):
    rng = np.random.default_rng(seed)
    base = rng.normal(size=(h, w, d))
    feats, periods = [], []
    for k in range(n_a + n_b):
        later = k >= n_a
        f = base + rng.normal(scale=noise, size=base.shape)
        if later and shift is not None:
            f = f + shift
        feats.append(f)
        periods.append(later)
    ok = [np.ones((h, w), bool) for _ in feats]
    return feats, ok, list(range(n_a)), list(range(n_a, n_a + n_b))


def test_z_is_about_one_when_nothing_changes():
    feats, ok, a, b = _scenes(n_a=4, n_b=4, h=40, w=40, d=8)
    z = C.change_scores(feats, ok, a, b)["z"]
    assert 0.8 < np.nanmedian(z ** 2) ** 0.5 < 1.4


def test_z_is_large_where_a_real_change_is_added():
    shift = np.zeros((20, 20, 4))
    shift[:10, :10] = 1.0          # change in one quadrant, 10x the noise scale
    feats, ok, a, b = _scenes(shift=shift)
    z = C.change_scores(feats, ok, a, b)["z"]
    assert np.nanmedian(z[:10, :10]) > 5 * np.nanmedian(z[10:, 10:])


def test_placebo_false_alarm_rate_is_low_for_gaussian_noise():
    feats, ok, a, b = _scenes(n_a=3, n_b=3, h=40, w=40, d=8)
    runs = C.placebo_scores(feats, ok, a, b)
    assert len(runs) == 6
    z = np.concatenate([r["z"][np.isfinite(r["z"])] for r in runs])
    assert (z > 3).mean() < 0.05


def test_placebo_needs_three_scenes_in_a_period():
    feats, ok, a, b = _scenes(n_a=2, n_b=2)
    assert C.placebo_scores(feats, ok, a, b) == []


def test_invalid_patches_give_nan_not_zero():
    feats, ok, a, b = _scenes()
    for mask in ok:
        mask[0, 0] = False
    z = C.change_scores(feats, ok, a, b)["z"]
    assert np.isnan(z[0, 0]) and np.isfinite(z[5, 5])


def test_patch_mean_ignores_invalid_pixels():
    stack = np.ones((1, 32, 32), dtype="float32")
    stack[0, :16, :16] = 5.0
    valid = np.ones((32, 32), bool)
    valid[:8, :16] = False        # half of the first patch is invalid
    mean, frac = C.patch_mean(stack, valid)
    assert mean.shape == (2, 2, 1)
    assert mean[0, 0, 0] == 5.0 and frac[0, 0] == 0.5 and mean[1, 1, 0] == 1.0


def test_scene_features_shapes_and_range():
    rng = np.random.default_rng(1)
    refl = rng.uniform(0.05, 0.4, size=(6, 40, 40)).astype("float32")
    out = C.scene_features(refl, np.ones((40, 40), bool))
    assert out["raw6"][0].shape == (3, 3, 6) and out["indices5"][0].shape == (3, 3, 5)
    assert np.all(np.abs(out["ndvi"][0]) <= 1)


def test_l2_normalise_unit_length():
    v = C.l2_normalise(np.random.default_rng(2).normal(size=(4, 4, 16)))
    assert np.allclose(np.linalg.norm(v, axis=-1), 1.0)
