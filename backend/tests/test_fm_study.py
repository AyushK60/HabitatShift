"""Offline tests for study loading and per-method feature building (uses a fake embedder, no GPU)."""
from __future__ import annotations

import json

import numpy as np

from backend.app.foundation import study as S


class FakeEmbedder:
    def embed(self, refl):
        _, h, w = refl.shape
        rng = np.random.default_rng(int(np.nansum(refl) * 1000) % (2**32))
        return rng.normal(size=((h + 15) // 16, (w + 15) // 16, 8)).astype("float32")


def _scene(rng, h=40, w=40):
    refl = rng.uniform(0.05, 0.4, size=(6, h, w)).astype("float32")
    return {"period": "earlier", "date": "2021-02-01"}, refl, np.ones((h, w), bool)


def test_features_cover_base_and_embedding_methods():
    rng = np.random.default_rng(0)
    scenes = [_scene(rng) for _ in range(3)]
    feats, oks = S.features_for(scenes, {"prithvi": FakeEmbedder(), "ssl4eo_rgb": FakeEmbedder()})
    assert set(feats) == set(S.BASE_METHODS) | {"prithvi", "ssl4eo_rgb"}
    assert len(oks) == 3 and oks[0].shape == (3, 3)
    assert feats["raw6"][0].shape == (3, 3, 6) and feats["prithvi"][0].shape == (3, 3, 8)
    assert np.allclose(np.linalg.norm(feats["prithvi"][0], axis=-1), 1.0)


def test_features_without_embedders_skip_them():
    rng = np.random.default_rng(1)
    feats, _ = S.features_for([_scene(rng), _scene(rng)], {})
    assert "prithvi" not in feats and "ndvi" in feats


def test_load_scenes_orders_earlier_before_later(tmp_path):
    for name, period, date in (("b", "later", "2025-02-01"), ("a", "earlier", "2021-03-01"), ("c", "earlier", "2021-02-01")):
        np.savez(tmp_path / f"{name}.npz", refl=np.zeros((6, 4, 4), "float32"), valid=np.ones((4, 4), bool))
        (tmp_path / f"{name}.json").write_text(json.dumps({"period": period, "date": date}))
    order = [(m["period"], m["date"]) for m, _, _ in S.load_scenes(tmp_path)]
    assert order == [("earlier", "2021-02-01"), ("earlier", "2021-03-01"), ("later", "2025-02-01")]
