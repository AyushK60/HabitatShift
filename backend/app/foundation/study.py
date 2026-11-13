"""Loading a foundation-model study (scene stacks) and turning scenes into per-method patch features."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import compare as C

BASE_METHODS = ("ndvi", "ndwi", "mndwi", "ndbi", "indices5", "raw6")
EMBEDDING_METHODS = ("prithvi", "ssl4eo_rgb")
METHODS = BASE_METHODS + EMBEDDING_METHODS


def load_scenes(folder: Path):
    scenes = []
    for meta_path in sorted(Path(folder).glob("*.json")):
        meta = json.loads(meta_path.read_text())
        data = np.load(meta_path.with_suffix(".npz"))
        scenes.append((meta, data["refl"], data["valid"]))
    scenes.sort(key=lambda s: (s[0]["period"] != "earlier", s[0]["date"]))
    return scenes


def features_for(scenes, embedders: dict, methods=None):
    """Per-method list of (h, w, d) patch features per scene, and per-scene patch-validity masks.

    ``embedders`` maps a method name ("prithvi", "ssl4eo_rgb") to an object with ``embed(refl6)``.
    """
    methods = tuple(methods) if methods else BASE_METHODS + tuple(embedders)
    per_method: dict[str, list] = {m: [] for m in methods}
    oks = []
    for _, refl, valid in scenes:
        feats = C.scene_features(refl, valid)
        for m in methods:
            if m in embedders:
                per_method[m].append(C.l2_normalise(embedders[m].embed(refl)))
            else:
                per_method[m].append(feats[m][0])
        oks.append((feats["raw6"][1] >= C.MIN_VALID_FRACTION) & np.isfinite(feats["raw6"][0]).all(-1))
    for m in methods:
        if m not in embedders:
            per_method[m] = C.standardise(per_method[m])
    return per_method, oks
