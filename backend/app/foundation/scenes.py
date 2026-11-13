"""Scene selection and six-band fetching for the foundation-model comparison."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np
import requests
from rasterio.enums import Resampling
from rasterio.transform import Affine

from .. import config
from ..acquisition.assets import (
    empirical_offset_rejection, to_reflectance, verify_radiometry, with_scale_only_offset,
)
from ..acquisition.cog import WindowRequest, read_window
from ..catalog.models import SceneCandidate
from ..preprocess import masks as mask_mod
from .prithvi import BANDS

KEYS = BANDS + (config.ASSET_SCL,)


def window_request(grid: dict, resampling, dtype: str) -> WindowRequest:
    return WindowRequest(dst_crs=grid["crs"], dst_transform=Affine(*grid["transform"][:6]),
                         height=grid["height"], width=grid["width"], resampling=resampling, dtype=dtype)


def search_items(bbox, start: dt.date, end: dt.date, *, ids: list[str] | None = None, max_cloud: float = 40.0
                 ) -> list[dict[str, Any]]:
    body: dict[str, Any] = {"collections": [config.COLLECTION], "limit": 100}
    if ids:
        body.update(ids=ids, limit=len(ids))
    else:
        body.update(bbox=list(bbox), datetime=f"{start}T00:00:00Z/{end}T23:59:59Z",
                    query={"eo:cloud_cover": {"lt": max_cloud}})
    response = requests.post(f"{config.CATALOG_URL.rstrip('/')}/search", json=body, timeout=60)
    response.raise_for_status()
    return response.json()["features"]


def candidate_of(item: dict) -> SceneCandidate:
    return SceneCandidate.from_stac(item, catalog_url=config.CATALOG_URL, required_assets=KEYS)


def measure_valid_fraction(candidate: SceneCandidate, grid: dict) -> float:
    scl = read_window(candidate.asset(config.ASSET_SCL).href, window_request(grid, Resampling.nearest, "int32"))
    valid, _ = mask_mod.build_valid_mask(scl)
    return float(valid.mean())


def choose_scenes(bbox, grid: dict, start: dt.date, end: dt.date, n: int = 3, min_valid: float = 0.9,
                  max_measure: int = 30) -> list[dict]:
    """The n scenes with the highest measured valid fraction in the window (distinct dates)."""
    items = search_items(bbox, start, end)
    items.sort(key=lambda f: f["properties"].get("eo:cloud_cover", 100))
    scored = []
    for item in items[:max_measure]:
        try:
            scored.append((measure_valid_fraction(candidate_of(item), grid), item))
        except Exception:
            continue
    scored.sort(key=lambda s: -s[0])
    chosen, dates = [], set()
    for fraction, item in scored:
        day = item["properties"]["datetime"][:10]
        if fraction >= min_valid and day not in dates:
            chosen.append({"item_id": item["id"], "date": day, "valid_fraction": round(fraction, 4)})
            dates.add(day)
        if len(chosen) == n:
            break
    return chosen


def fetch_scene(item: dict, grid: dict, period: str, out_dir: Path) -> None:
    candidate = candidate_of(item)
    target = out_dir / f"{candidate.item_id}.npz"
    if target.exists():
        return
    scl = read_window(candidate.asset(config.ASSET_SCL).href, window_request(grid, Resampling.nearest, "int32"))
    valid, _ = mask_mod.build_valid_mask(scl)
    radiometry = verify_radiometry(candidate, BANDS)
    dn = {k: read_window(candidate.asset(k).href, window_request(grid, Resampling.bilinear, "float32")) for k in BANDS}
    refl = {k: to_reflectance(dn[k], radiometry[k]) for k in BANDS}
    corrected = empirical_offset_rejection(refl) is not None
    if corrected:
        refl = {k: to_reflectance(dn[k], with_scale_only_offset(radiometry[k])) for k in BANDS}
    stack = np.stack([refl[k] for k in BANDS]).astype("float32")
    np.savez_compressed(target, refl=stack, valid=valid & np.isfinite(stack).all(axis=0))
    (out_dir / f"{candidate.item_id}.json").write_text(json.dumps({
        "item_id": candidate.item_id, "period": period, "date": candidate.date_str, "bands": list(BANDS),
        "offset_corrected_empirically": corrected, "valid_fraction": round(float(valid.mean()), 4)}, indent=1))
