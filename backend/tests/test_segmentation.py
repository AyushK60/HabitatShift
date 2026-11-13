"""Offline tests for the radar water model pieces."""
from __future__ import annotations

import numpy as np
import torch

from backend.app.segmentation import conformal as C
from backend.app.segmentation import data as D
from backend.app.segmentation.unet import UNet, bce_dice_loss


def test_crop_window_centres_on_seed_and_stays_inside():
    seed = np.zeros((600, 600), bool)
    seed[300:310, 300:310] = True
    r0, c0 = D.crop_window(seed)
    assert 0 <= r0 <= 600 - D.CROP
    assert r0 <= 304 < r0 + D.CROP
    edge = np.zeros((600, 600), bool)
    edge[0:5, 0:5] = True
    assert D.crop_window(edge) == (0, 0)


def test_make_input_flags_missing_radar():
    vv = np.full((4, 4), -10.0, "float32")
    vh = np.full((4, 4), -18.0, "float32")
    vv[0, 0] = np.nan
    x = D.make_input(vv, vh, np.zeros((4, 4), "float32"))
    assert x.shape == (4, 4, 4) and x[3, 0, 0] == 0 and x[3, 1, 1] == 1 and np.isfinite(x).all()


def test_keep_pair_drops_weak_labels():
    good = {"status": "ok", "radar_contrast_db": -6.0, "water_pixels": 500}
    assert D.keep_pair(good)
    assert not D.keep_pair({**good, "radar_contrast_db": -1.0})
    assert not D.keep_pair({**good, "radar_contrast_db": None})
    assert not D.keep_pair({**good, "water_pixels": 3})


def test_split_is_by_lake_deterministic_and_sized():
    ids = [f"lake{i}" for i in range(30)]
    a, b = D.assign_split(ids), D.assign_split(list(reversed(ids)))
    assert a == b
    counts = {s: list(a.values()).count(s) for s in ("train", "cal", "test")}
    assert counts == {"train": 20, "cal": 4, "test": 6}


def test_unet_output_shape_and_loss_ignores_unusable_pixels():
    net = UNet(base=4, depth=3)
    x = torch.randn(2, 4, 64, 64)
    out = net(x)
    assert out.shape == (2, 64, 64)
    target = torch.zeros(2, 64, 64, dtype=torch.bool)
    ok_none = torch.zeros_like(target)
    assert torch.isfinite(bce_dice_loss(out, target, ok_none))
    ok = torch.ones_like(target)
    loss = bce_dice_loss(out, target, ok)
    loss.backward()
    assert loss.item() > 0


def test_conformal_quantile_and_coverage_on_synthetic_errors():
    rng = np.random.default_rng(0)
    pred = rng.uniform(0.3, 2.0, 5000)
    truth = pred * (1 + rng.normal(0, 0.05, 5000))
    cal, test = slice(0, 2500), slice(2500, None)
    q = C.conformal_quantile(C.conformal_scores(pred[cal], truth[cal]), 0.1)
    lo, hi = C.interval(pred[test], q)
    assert 0.87 <= C.coverage(truth[test], lo, hi) <= 0.93


def test_conformal_quantile_infinite_when_too_few_points():
    assert C.conformal_quantile(np.array([0.1, 0.2]), 0.1) == float("inf")


def test_iou_ignores_unusable_pixels():
    t = np.array([[1, 1, 0, 0]], bool)
    p = np.array([[1, 0, 1, 1]], bool)
    ok = np.array([[1, 1, 1, 0]], bool)
    assert abs(C.iou(p, t, ok) - 1 / 3) < 1e-9


def test_predict_tile_handles_sizes_not_divisible_by_16():
    from backend.app.segmentation.train import predict_tile
    net = UNet(base=4, depth=4)
    prob = predict_tile(net, np.zeros((4, 101, 77), "float32"), "cpu")
    assert prob.shape == (101, 77) and ((prob >= 0) & (prob <= 1)).all()
