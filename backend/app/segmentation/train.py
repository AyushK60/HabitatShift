"""Training loop and prediction helpers for the radar water U-Net."""
from __future__ import annotations

import time

import numpy as np
import torch

from .conformal import iou
from .unet import UNet, bce_dice_loss


@torch.no_grad()
def predict(net: UNet, x: np.ndarray, device: str, batch: int = 32) -> np.ndarray:
    net.eval()
    return np.concatenate([torch.sigmoid(net(torch.from_numpy(x[i:i + batch]).to(device))).cpu().numpy()
                           for i in range(0, len(x), batch)])


@torch.no_grad()
def predict_tile(net: UNet, x: np.ndarray, device: str) -> np.ndarray:
    """Water probability for one whole tile (4, H, W): padded with 'no radar' to a multiple of 16, then cropped back."""
    h, w = x.shape[1:]
    ph, pw = (-h) % 16, (-w) % 16
    padded = np.pad(x, ((0, 0), (0, ph), (0, pw)))
    return predict(net, padded[None], device)[0, :h, :w]


def mean_iou(prob: np.ndarray, d: dict) -> float:
    return float(np.nanmean([iou(p > 0.5, t, o) for p, t, o in zip(prob, d["y"], d["ok"])]))


def fit(fit_d: dict, val_d: dict, device: str, *, epochs: int, batch: int = 16, lr: float = 2e-3, seed: int = 0,
        base: int = 16, verbose: bool = True):
    """Train from scratch; return the network with the best validation IoU, that IoU, and the per-epoch history."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = UNet(base=base).to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    steps = epochs * (len(fit_d["y"]) // batch + 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps)
    best, best_state, history = -1.0, None, []
    for epoch in range(epochs):
        net.train()
        t0, order, total = time.time(), rng.permutation(len(fit_d["y"])), 0.0
        for i in range(0, len(order), batch):
            b = order[i:i + batch]
            x, y, ok = fit_d["x"][b], fit_d["y"][b], fit_d["ok"][b]
            if rng.random() < 0.5:
                x, y, ok = x[..., ::-1], y[..., ::-1], ok[..., ::-1]
            if rng.random() < 0.5:
                x, y, ok = x[..., ::-1, :], y[..., ::-1, :], ok[..., ::-1, :]
            x, y, ok = (torch.from_numpy(np.ascontiguousarray(a)).to(device) for a in (x, y, ok))
            loss = bce_dice_loss(net(x), y, ok)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            total += loss.item() * len(b)
        v = mean_iou(predict(net, val_d["x"], device), val_d)
        history.append({"epoch": epoch + 1, "train_loss": total / len(order), "val_iou": v})
        if verbose:
            print(f"epoch {epoch + 1:2d} loss {total / len(order):.4f} val IoU {v:.4f} ({time.time() - t0:.0f}s)", flush=True)
        if v > best:
            best, best_state = v, {k: t.detach().cpu().clone() for k, t in net.state_dict().items()}
    net.load_state_dict(best_state)
    return net, best, history
