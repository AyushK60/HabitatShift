"""A small U-Net (about 1.9 M weights) and the training loss."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def _block(cin: int, cout: int) -> nn.Sequential:
    return nn.Sequential(nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                         nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True))


class UNet(nn.Module):
    def __init__(self, in_channels: int = 4, base: int = 16, depth: int = 4):
        super().__init__()
        widths = [base * 2 ** i for i in range(depth + 1)]
        self.down = nn.ModuleList([_block(in_channels, widths[0])] + [_block(widths[i], widths[i + 1]) for i in range(depth)])
        self.up = nn.ModuleList([nn.ConvTranspose2d(widths[i + 1], widths[i], 2, stride=2) for i in reversed(range(depth))])
        self.dec = nn.ModuleList([_block(widths[i] * 2, widths[i]) for i in reversed(range(depth))])
        self.head = nn.Conv2d(widths[0], 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skips = []
        for i, block in enumerate(self.down):
            x = block(x)
            if i < len(self.down) - 1:
                skips.append(x)
                x = F.max_pool2d(x, 2)
        for up, dec in zip(self.up, self.dec):
            x = up(x)
            x = dec(torch.cat([x, skips.pop()], dim=1))
        return self.head(x).squeeze(1)


def bce_dice_loss(logits: torch.Tensor, target: torch.Tensor, ok: torch.Tensor) -> torch.Tensor:
    """Binary cross-entropy plus Dice, both computed only where the label is usable (``ok``)."""
    w = ok.float()
    bce = (F.binary_cross_entropy_with_logits(logits, target.float(), reduction="none") * w).sum() / w.sum().clamp(min=1)
    p = torch.sigmoid(logits) * w
    t = target.float() * w
    dice = 1 - (2 * (p * t).sum() + 1) / (p.sum() + t.sum() + 1)
    return bce + dice
