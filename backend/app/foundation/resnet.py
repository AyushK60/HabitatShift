"""SSL4EO-S12 ResNet-50 (RGB, MoCo) patch embeddings: a small second foundation model for comparison.

Weights: torchgeo/resnet50_sentinel2_rgb_moco on Hugging Face (SSL4EO-S12, Wang et al. 2022, CC-BY 4.0).
File lives in data/models/ssl4eo_resnet50_rgb (downloaded, not committed).

It sees only red, green and blue, with no near- or short-wave infrared, so it is a deliberately light baseline.
Features come from layer 3 (stride 16), which gives one 1024-number vector per 16 x 16 pixel patch, the same grid
as Prithvi. Input is reflectance (DN / 10000), as the weights were trained.
"""
from __future__ import annotations

import hashlib

import numpy as np
import torch
import torchvision

from .. import config as project_config

WEIGHTS = project_config.DATA_DIR / "models" / "ssl4eo_resnet50_rgb" / "resnet50_sentinel2_rgb_moco.pth"
PATCH = 16
RGB_INDEX = (2, 1, 0)  # red, green, blue within (blue, green, red, nir08, swir16, swir22)


def weights_sha256() -> str:
    digest = hashlib.sha256()
    with WEIGHTS.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


class SSL4EOResNetEmbedder:
    def __init__(self, device: str | None = None, half: bool = True) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.half = half and self.device == "cuda"
        net = torchvision.models.resnet50()
        state = torch.load(WEIGHTS, map_location="cpu", weights_only=True)
        report = net.load_state_dict(state, strict=False)
        self.load_report = {"missing": list(report.missing_keys)[:5], "unexpected": list(report.unexpected_keys)[:5]}
        trunk = torch.nn.Sequential(net.conv1, net.bn1, net.relu, net.maxpool, net.layer1, net.layer2, net.layer3)
        self.trunk = trunk.eval().to(self.device)
        if self.half:
            self.trunk = self.trunk.half()

    @torch.no_grad()
    def embed(self, reflectance: np.ndarray) -> np.ndarray:
        """(6, H, W) reflectance -> (ceil(H/16), ceil(W/16), 1024) patch embeddings."""
        rgb = reflectance[list(RGB_INDEX)].astype("float32")
        rgb = np.where(np.isfinite(rgb), rgb, 0.0)
        _, height, width = rgb.shape
        pad_h, pad_w = (-height) % PATCH, (-width) % PATCH
        rgb = np.pad(rgb, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")
        tensor = torch.from_numpy(rgb).unsqueeze(0).to(self.device)
        if self.half:
            tensor = tensor.half()
        features = self.trunk(tensor)[0].float().cpu().numpy()          # (1024, h, w)
        return np.moveaxis(features, 0, -1)
