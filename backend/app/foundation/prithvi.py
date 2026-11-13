"""Prithvi-EO-2.0 (300M) patch embeddings for single Sentinel-2 scenes.

Model: IBM/NASA Prithvi-EO-2.0-300M, Apache-2.0, https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M
Files live in data/models/prithvi_eo_2_300m (code, config, weights); they are downloaded, not committed.

Input: six bands in this order, as surface reflectance (0-1): blue, green, red, NIR (B8A), SWIR1, SWIR2.
Output: one 1024-number vector per 16 x 16 pixel patch (160 m at 10 m pixels). One scene at a time
(a single time step), so every scene of a period gets its own embedding and the scene-to-scene spread
can be measured in embedding space.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import torch

from .. import config as project_config

MODEL_DIR = project_config.DATA_DIR / "models" / "prithvi_eo_2_300m"
WEIGHTS = MODEL_DIR / "Prithvi_EO_V2_300M.pt"
PATCH = 16
BANDS = ("blue", "green", "red", "nir08", "swir16", "swir22")


def _load_module():
    spec = importlib.util.spec_from_file_location("prithvi_mae_local", MODEL_DIR / "prithvi_mae.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def weights_sha256() -> str:
    digest = hashlib.sha256()
    with WEIGHTS.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


class PrithviEmbedder:
    def __init__(self, device: str | None = None, half: bool = True) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.half = half and self.device == "cuda"
        cfg = json.loads((MODEL_DIR / "config.json").read_text())["pretrained_cfg"]
        self.mean = np.asarray(cfg["mean"], dtype="float32")[:, None, None]
        self.std = np.asarray(cfg["std"], dtype="float32")[:, None, None]
        cfg.update(coords_encoding=[], num_frames=1, in_chans=len(BANDS))
        for key in ("bands", "mean", "std", "origin_url", "paper_ids"):
            cfg.pop(key, None)
        module = _load_module()
        model = module.PrithviMAE(**cfg)
        state = torch.load(WEIGHTS, map_location="cpu", weights_only=True)
        for key in [k for k in state if "pos_embed" in k]:
            del state[key]   # fixed sin-cos table is rebuilt for any input size
        missing = model.load_state_dict(state, strict=False)
        self.load_report = {"missing": list(missing.missing_keys)[:5], "unexpected": list(missing.unexpected_keys)[:5]}
        self.encoder = model.encoder.eval().to(self.device)
        if self.half:
            self.encoder = self.encoder.half()

    @torch.no_grad()
    def embed(self, reflectance: np.ndarray) -> np.ndarray:
        """(6, H, W) reflectance -> (ceil(H/16), ceil(W/16), 1024) float32 patch embeddings.

        NaN pixels are replaced by the band mean (after normalisation that is 0) so they carry no signal;
        the image is reflect-padded up to a multiple of 16 pixels.
        """
        bands, height, width = reflectance.shape
        if bands != len(BANDS):
            raise ValueError(f"expected {len(BANDS)} bands, got {bands}")
        dn = reflectance.astype("float32") * 10000.0
        x = (dn - self.mean) / self.std
        x = np.where(np.isfinite(x), x, 0.0)
        pad_h, pad_w = (-height) % PATCH, (-width) % PATCH
        x = np.pad(x, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")
        tensor = torch.from_numpy(x).unsqueeze(0).to(self.device)
        if self.half:
            tensor = tensor.half()
        tokens = self.encoder.forward_features(tensor)[-1][0, 1:, :].float().cpu().numpy()
        return tokens.reshape(x.shape[1] // PATCH, x.shape[2] // PATCH, -1)
