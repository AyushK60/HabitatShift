"""Glacial-lake area from Sentinel-1 radar and Sentinel-2 optical scenes.

Per scene we measure the lake area; per month we combine the scenes and use their spread as the
uncertainty (the version 2 noise idea). A lake is located with a DEM-derived "seed": the flat area of the
Copernicus 30 m DEM nearest the lake point. The seed is used to
  * pick the lake out from other dark patches (only water touching the seed is counted), and
  * judge whether a radar orbit can see the lake at all (layover hides it from some orbits).
The seed is NOT used to set the water threshold, so a lake that drains still shows as shrinking.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy import ndimage

from .. import config
from . import sar
from .planetary import S1_COLLECTION, Grid, PlanetaryClient, make_grid

LAKES_FILE = config.STUDIES_DIR / "lakes.yaml"
LAKES_DIR = config.DATA_DIR / "lakes"

#: Contrast (lake minus surroundings, dB) at or below which a radar scene "sees" the lake as dark water.
DARK_CONTRAST_DB = -4.0
#: Seed must be at least this large (pixels) and within this distance of the lake point (metres).
SEED_MIN_PIXELS = 300
SEED_MAX_DISTANCE_M = 400.0
#: Optical scenes with more than this share of the lake flagged snow/ice are excluded: a partly frozen lake
#: gives a partial area that looks like shrinkage.
ICE_MAX_FRACTION = 0.1
#: Optical scenes with more scene-wide cloud than this are skipped (cloud shadow and haze near the lake).
MAX_SCENE_CLOUD = 0.4
#: Smallest water patch counted (pixels).
MIN_PATCH_PIXELS = 5


@dataclass(frozen=True)
class Lake:
    id: str
    name: str
    lon: float
    lat: float
    half_deg: float
    note: str = ""

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        h = self.half_deg
        return (self.lon - h, self.lat - 0.9 * h, self.lon + h, self.lat + 0.9 * h)

    @property
    def directory(self) -> Path:
        return LAKES_DIR / self.id


def load_lakes(path: Path = LAKES_FILE) -> dict[str, Lake]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {entry["id"]: Lake(**entry) for entry in data["lakes"]}


# --------------------------------------------------------------------------- seed
def find_seed(slope: np.ndarray, grid: Grid, lon: float, lat: float) -> tuple[np.ndarray, dict]:
    """Flat DEM component nearest the lake point (the lake's footprint in the DEM)."""
    from pyproj import Transformer

    x, y = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True).transform(lon, lat)
    col, row = ~grid.transform * (x, y)
    flat = ndimage.binary_opening(slope < 1.5, iterations=2)
    labels, n = ndimage.label(flat)
    if n == 0:
        raise ValueError("no flat terrain found; cannot place the lake seed")
    sizes = ndimage.sum(flat, labels, range(1, n + 1))
    rows, cols = np.indices(slope.shape)
    dist = np.hypot(rows - row, cols - col) * grid.res
    best, best_d = None, math.inf
    for index, size in enumerate(sizes, start=1):
        if size < SEED_MIN_PIXELS:
            continue
        d = float(dist[labels == index].min())
        if d < best_d:
            best, best_d = index, d
    if best is None or best_d > SEED_MAX_DISTANCE_M:
        raise ValueError(f"no flat DEM area within {SEED_MAX_DISTANCE_M:.0f} m of the lake point")
    seed = labels == best
    return seed, {"seed_pixels": int(seed.sum()), "seed_area_km2": round(seed.sum() * grid.res**2 / 1e6, 3),
                  "seed_distance_m": round(best_d, 1)}


def prepare_lake(client: PlanetaryClient, lake: Lake) -> dict[str, Any]:
    """Grid, DEM slope and seed for one lake, cached on disk."""
    lake.directory.mkdir(parents=True, exist_ok=True)
    cache = lake.directory / "static.npz"
    grid = make_grid(lake.bbox)
    if cache.exists():
        with np.load(cache) as data:
            return {"grid": grid, "slope": data["slope"], "seed": data["seed"], "dem": data["dem"],
                    "seed_info": json.loads(str(data["seed_info"]))}
    dem = client.read_dem(lake.bbox, grid)
    slope = sar.slope_degrees(dem, grid.res)
    seed, info = find_seed(slope, grid, lake.lon, lake.lat)
    info["seed_elevation_m"] = round(float(np.nanmedian(dem[seed])), 1)
    np.savez_compressed(cache, dem=dem, slope=slope, seed=seed, seed_info=json.dumps(info))
    return {"grid": grid, "slope": slope, "seed": seed, "dem": dem, "seed_info": info}


# --------------------------------------------------------------------------- patches
def lake_patch_area(mask: np.ndarray, seed: np.ndarray, res: float) -> tuple[float, int]:
    """Area (km2) of water patches that touch the seed (dilated 3 px), and the patch count."""
    labels, n = ndimage.label(mask)
    if n == 0:
        return 0.0, 0
    touching = np.unique(labels[ndimage.binary_dilation(seed, iterations=3) & (labels > 0)])
    keep = np.zeros(n + 1, dtype=bool)
    sizes = ndimage.sum(mask, labels, range(n + 1))
    for label in touching:
        if sizes[label] >= MIN_PATCH_PIXELS:
            keep[label] = True
    pixels = int(keep[labels].sum())
    return pixels * res * res / 1e6, int(keep.sum())


# --------------------------------------------------------------------------- radar scene
def scene_water_mask(client: PlanetaryClient, item: dict, prep: dict) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Radar water mask for one scene on the lake grid, plus the per-scene record (mask is None if unusable)."""
    props = item["properties"]
    grid, seed, slope = prep["grid"], prep["seed"], prep["slope"]
    record: dict[str, Any] = {
        "sensor": "s1", "item": item["id"], "datetime": props["datetime"],
        "orbit_state": props.get("sat:orbit_state"), "relative_orbit": props.get("sat:relative_orbit"),
    }
    vv = client.read_to_grid(item, "vv", S1_COLLECTION, grid)
    record["valid_fraction"] = round(float(np.isfinite(vv).mean()), 4)
    if not np.isfinite(vv[seed]).mean() > 0.9:
        record["status"] = "lake_not_covered"
        return None, record
    mask, info = sar.water_mask(vv, slope)
    db = sar.to_db(sar.lee_filter(vv))
    outside = np.isfinite(db) & ~ndimage.binary_dilation(seed, iterations=10)
    record["contrast_db"] = round(float(np.nanmedian(db[seed]) - np.nanmedian(db[outside])), 2)
    area, patches = lake_patch_area(mask, seed, grid.res)
    record.update(info, area_km2=round(area, 4), patches=patches,
                  seed_water_fraction=round(float(mask[seed].mean()), 3))
    record.setdefault("status", "ok")
    mask = mask & np.isfinite(vv)
    mask[~np.isfinite(vv)] = False
    record["_valid"] = np.isfinite(vv)
    return mask, record


def process_s1_scene(client: PlanetaryClient, item: dict, prep: dict) -> dict[str, Any]:
    _, record = scene_water_mask(client, item, prep)
    record.pop("_valid", None)
    return record


# --------------------------------------------------------------------------- optical scene
MNDWI_WATER = 0.1
NIR_WATER_MAX = 0.12


def s2_water_mask(candidate, prep: dict) -> tuple[np.ndarray | None, np.ndarray | None, dict[str, Any]]:
    """Optical water mask, valid mask and record for one Sentinel-2 L2A scene (MNDWI + NIR, cloud and snow masked).

    The masks are None when the scene is unusable (cloud over the lake).
    """
    from rasterio.enums import Resampling

    from ..acquisition.assets import (
        empirical_offset_rejection, to_reflectance, verify_radiometry, with_scale_only_offset,
    )
    from ..acquisition.cog import WindowRequest, read_window
    from ..preprocess import masks as mask_mod

    grid, seed = prep["grid"], prep["seed"]
    keys = (config.ASSET_GREEN, config.ASSET_NIR, config.ASSET_SWIR1)
    record: dict[str, Any] = {"sensor": "s2", "item": candidate.item_id, "datetime": candidate.acquisition_iso,
                              "cloud_cover": candidate.cloud_fraction()}

    def request(resampling, dtype):
        return WindowRequest(dst_crs=grid.crs, dst_transform=grid.transform, height=grid.height,
                             width=grid.width, resampling=resampling, dtype=dtype)

    scl = read_window(candidate.asset(config.ASSET_SCL).href, request(Resampling.nearest, "int32"))
    valid, _ = mask_mod.build_valid_mask(scl)
    seed_valid = float(valid[seed].mean())
    record["seed_valid_fraction"] = round(seed_valid, 3)
    record["seed_ice_fraction"] = round(float((scl[seed] == 11).mean()), 3)
    if seed_valid < 0.9:
        record["status"] = "cloudy"
        return None, None, record
    radiometry = verify_radiometry(candidate, keys)
    dn = {k: read_window(candidate.asset(k).href, request(Resampling.bilinear, "float32")) for k in keys}
    refl = {k: to_reflectance(dn[k], radiometry[k]) for k in keys}
    if empirical_offset_rejection(refl) is not None:
        refl = {k: to_reflectance(dn[k], with_scale_only_offset(radiometry[k])) for k in keys}
    g, n, s = refl[config.ASSET_GREEN], refl[config.ASSET_NIR], refl[config.ASSET_SWIR1]
    with np.errstate(divide="ignore", invalid="ignore"):
        mndwi = (g - s) / (g + s)
    water = valid & (mndwi > MNDWI_WATER) & (n < NIR_WATER_MAX) & (scl != 11)
    area, patches = lake_patch_area(water, seed, grid.res)
    record.update(area_km2=round(area, 4), patches=patches,
                  seed_water_fraction=round(float(water[seed].mean()), 3), status="ok")
    return water, valid, record


def process_s2_scene(candidate, prep: dict) -> dict[str, Any]:
    _, _, record = s2_water_mask(candidate, prep)
    return record


# --------------------------------------------------------------------------- aggregation
def usable_orbits(records: list[dict], reference_years: tuple[int, int]) -> dict[str, dict]:
    """Which radar orbits can see this lake.

    Judged on the reference years when an orbit has at least 3 scenes there, otherwise on all of its
    scenes (and recorded as such). Geometry problems such as layover do not change from year to year,
    so a reference period is enough and a later drained or shrunken lake cannot hide its own orbit.
    """
    def key_of(r):
        return f"{r['orbit_state'][:3]}{r['relative_orbit']}"

    everything: dict[str, list[float]] = {}
    reference: dict[str, list[float]] = {}
    for r in records:
        if r.get("contrast_db") is None:
            continue
        everything.setdefault(key_of(r), []).append(r["contrast_db"])
        if reference_years[0] <= int(r["datetime"][:4]) <= reference_years[1]:
            reference.setdefault(key_of(r), []).append(r["contrast_db"])
    out = {}
    for key, values in everything.items():
        basis = "reference_years" if len(reference.get(key, [])) >= 3 else "all_years"
        used = reference[key] if basis == "reference_years" else values
        q25 = float(np.percentile(used, 25))
        out[key] = {"scenes": len(used), "basis": basis, "q25_contrast_db": round(q25, 2),
                    "usable": q25 <= DARK_CONTRAST_DB}
    return out


def not_dark_months(records: list[dict], orbits: dict[str, dict]) -> set[str]:
    """Months in which most radar scenes from usable orbits see the lake as not dark (frozen or melting)."""
    tally: dict[str, list[bool]] = {}
    for r in records:
        if r.get("status") != "ok" or r.get("contrast_db") is None:
            continue
        if not orbits.get(f"{r['orbit_state'][:3]}{r['relative_orbit']}", {}).get("usable"):
            continue
        tally.setdefault(r["datetime"][:7], []).append(r["contrast_db"] > DARK_CONTRAST_DB)
    return {m for m, flags in tally.items() if sum(flags) / len(flags) >= 0.5}


def monthly_series(records: list[dict], orbits: dict[str, dict] | None, frozen_months: set[str] | None = None) -> list[dict]:
    """Monthly lake area (median of scenes) with the scene-to-scene spread as uncertainty. Gaps are explicit."""
    months: dict[str, dict[str, Any]] = {}
    for r in records:
        month = r["datetime"][:7]
        slot = months.setdefault(month, {"area": [], "excluded": {}})
        if r.get("status") != "ok":
            why = r.get("status", "unknown")
        elif r["sensor"] == "s1" and orbits is not None and not orbits.get(
                f"{r['orbit_state'][:3]}{r['relative_orbit']}", {}).get("usable"):
            why = "orbit_cannot_see_lake"
        elif r["sensor"] == "s1" and r["contrast_db"] > DARK_CONTRAST_DB:
            why = "lake_not_dark"
        elif r["sensor"] == "s2" and (r.get("cloud_cover") or 0) > MAX_SCENE_CLOUD:
            why = "cloudy_scene"
        elif r["sensor"] == "s2" and frozen_months and month in frozen_months:
            why = "frozen_season"
        elif r["sensor"] == "s2" and r.get("seed_ice_fraction", 0) > ICE_MAX_FRACTION:
            why = "frozen"
        else:
            slot["area"].append(r["area_km2"])
            continue
        slot["excluded"][why] = slot["excluded"].get(why, 0) + 1
    series = []
    for month in sorted(months):
        a, ex = np.array(months[month]["area"], dtype=float), months[month]["excluded"]
        row: dict[str, Any] = {"month": month, "n": int(a.size), "excluded": ex}
        if a.size:
            row["area_km2"] = round(float(np.median(a)), 4)
            row["min_km2"], row["max_km2"] = round(float(a.min()), 4), round(float(a.max()), 4)
            if a.size >= 3:
                row["se_km2"] = round(float(a.std(ddof=1) / math.sqrt(a.size)), 4)
        series.append(row)
    return series


def flag_changes(series: list[dict], k: float = 3.0) -> list[dict]:
    """Mark month-to-month changes that exceed k times the combined standard error (version 2 rule)."""
    prev = None
    for row in series:
        row["change_vs_previous"] = None
        if prev and "se_km2" in row and "se_km2" in prev and row.get("area_km2") is not None:
            delta = row["area_km2"] - prev["area_km2"]
            threshold = k * math.hypot(row["se_km2"], prev["se_km2"])
            row["change_vs_previous"] = {"delta_km2": round(delta, 4), "threshold_km2": round(threshold, 4),
                                         "exceeds_noise": bool(abs(delta) > threshold)}
        if row.get("area_km2") is not None:
            prev = row
    return series


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
