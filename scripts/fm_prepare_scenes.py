"""Fetch the six Prithvi bands for the scenes a version 2 study used, on the same 10 m grid.

For each selected observation in data/manifests/<manifest>.json this writes
data/fm/<experiment>/scenes/<item_id>.npz with
    refl   (6, H, W) float32 surface reflectance: blue, green, red, nir08 (B8A), swir16, swir22
    valid  (H, W) bool, from the Sentinel-2 scene classification (same policy as version 2)
and a small .json with period, date and radiometry notes. Existing files are skipped.

    python scripts/fm_prepare_scenes.py m4_western_ghats_m4
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import requests
from rasterio.enums import Resampling
from rasterio.transform import Affine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import config  # noqa: E402
from backend.app.acquisition.assets import (  # noqa: E402
    empirical_offset_rejection, to_reflectance, verify_radiometry, with_scale_only_offset,
)
from backend.app.acquisition.cog import WindowRequest, read_window  # noqa: E402
from backend.app.catalog.models import SceneCandidate  # noqa: E402
from backend.app.foundation.prithvi import BANDS  # noqa: E402
from backend.app.preprocess import masks as mask_mod  # noqa: E402

KEYS = BANDS + (config.ASSET_SCL,)


def fetch_items(ids: list[str]) -> dict[str, dict]:
    response = requests.post(f"{config.CATALOG_URL.rstrip('/')}/search",
                             json={"collections": [config.COLLECTION], "ids": ids, "limit": len(ids)}, timeout=60)
    response.raise_for_status()
    return {item["id"]: item for item in response.json()["features"]}


def main(manifest_name: str) -> None:
    manifest = json.loads((config.MANIFEST_DIR / f"{manifest_name}.json").read_text(encoding="utf-8"))
    grid = manifest["grid"]
    experiment = manifest["experiment_id"]
    out_dir = config.DATA_DIR / "fm" / experiment / "scenes"
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = [(period, obs) for period, block in manifest["search"].items() for obs in block["selected_observations"]]
    items = fetch_items([obs["item_id"] for _, obs in wanted])

    def request(resampling, dtype):
        return WindowRequest(dst_crs=grid["crs"], dst_transform=Affine(*grid["transform"][:6]),
                             height=grid["height"], width=grid["width"], resampling=resampling, dtype=dtype)

    for period, obs in wanted:
        item_id = obs["item_id"]
        target = out_dir / f"{item_id}.npz"
        if target.exists():
            continue
        candidate = SceneCandidate.from_stac(items[item_id], catalog_url=config.CATALOG_URL, required_assets=KEYS)
        scl = read_window(candidate.asset(config.ASSET_SCL).href, request(Resampling.nearest, "int32"))
        valid, _ = mask_mod.build_valid_mask(scl)
        radiometry = verify_radiometry(candidate, BANDS)
        dn = {k: read_window(candidate.asset(k).href, request(Resampling.bilinear, "float32")) for k in BANDS}
        refl = {k: to_reflectance(dn[k], radiometry[k]) for k in BANDS}
        corrected = empirical_offset_rejection(refl) is not None
        if corrected:   # same empirical acceptance test as version 2 (2025 reprocessing)
            refl = {k: to_reflectance(dn[k], with_scale_only_offset(radiometry[k])) for k in BANDS}
        stack = np.stack([refl[k] for k in BANDS]).astype("float32")
        np.savez_compressed(target, refl=stack, valid=valid & np.isfinite(stack).all(axis=0))
        (out_dir / f"{item_id}.json").write_text(json.dumps({
            "item_id": item_id, "period": period, "date": obs["date"], "bands": list(BANDS),
            "offset_corrected_empirically": corrected, "valid_fraction": round(float(valid.mean()), 4)}, indent=1))
        print(f"{period} {obs['date']} {item_id} valid={valid.mean():.2f} corrected={corrected}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
