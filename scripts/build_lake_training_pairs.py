"""Build paired radar / optical tiles for training a radar water-segmentation model (Phase 3).

For each lake, every clear Sentinel-2 scene (2020-2022) that has a Sentinel-1 scene within +/-3 days gives a pair:
  input  Sentinel-1 VV and VH backscatter in dB on the lake grid (float16)
  label  the Sentinel-2 water mask (MNDWI + NIR, cloud and snow masked)
  valid  where the optical scene is usable (labels are ignored elsewhere)
Terrain slope and DEM come from data/lakes/<lake>/static.npz.

The labels are weak: they come from a spectral rule, not from hand mapping, and that rule is known to fail on
turbid, icy water (Imja Tsho). Each pair stores what is needed to judge label quality later: optical cloud cover,
share of the lake seed flagged ice, and the radar contrast between the optical water and its surroundings.

Output: data/lakes_train/<lake>/pairs/<s2 item>__<s1 item>.npz, plus pairs.jsonl. Resumable.
    python scripts/build_lake_training_pairs.py --workers 10
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")
os.environ.setdefault("GDAL_HTTP_CONNECTTIMEOUT", "20")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.catalog.search import SearchRequest  # noqa: E402
from backend.app.catalog.stac_client import CatalogClient  # noqa: E402
from backend.app.http import HttpSession  # noqa: E402
from backend.app.preprocess.aoi import aoi_from_bounds  # noqa: E402
from backend.app.radar import lakes as L  # noqa: E402
from backend.app.radar import sar  # noqa: E402
from backend.app.radar.planetary import S1_COLLECTION, PlanetaryClient  # noqa: E402

TRAIN_DIR = config.DATA_DIR / "lakes_train"
MAX_DAYS = 3
MAX_S1_PER_S2 = 2
MAX_S2_CLOUD = 0.4


def date_of(iso: str) -> dt.date:
    return dt.date.fromisoformat(iso[:10])


def s2_candidates(lake, start, end):
    west, south, east, north = lake.bbox
    aoi = aoi_from_bounds(study_id=lake.id, west=west, south=south, east=east, north=north,
                          description=lake.name, source="studies/lakes.yaml")
    catalog = CatalogClient(HttpSession(cache_dir=config.CACHE_DIR), probe_assets=False,
                            required_assets=(config.ASSET_GREEN, config.ASSET_NIR, config.ASSET_SWIR1, config.ASSET_SCL))
    found, cursor = {}, start
    while cursor < end:
        stop = min(cursor + dt.timedelta(days=360), end)
        request = SearchRequest(aoi=aoi, start=dt.datetime.combine(cursor, dt.time.min),
                                end=dt.datetime.combine(stop, dt.time.max), max_cloud_cover=60.0, limit=100)
        for c in catalog.search(request).items:
            found[c.item_id] = c
        cursor = stop + dt.timedelta(days=1)
    return list(found.values())


def partners(candidate, s1_items):
    day = date_of(candidate.acquisition_iso)
    near = [(abs((date_of(i["properties"]["datetime"]) - day).days), i) for i in s1_items]
    near = sorted([n for n in near if n[0] <= MAX_DAYS], key=lambda n: n[0])
    chosen, orbits = [], set()
    for gap, item in near:
        key = (item["properties"].get("sat:orbit_state"), item["properties"].get("sat:relative_orbit"))
        if key not in orbits:
            chosen.append((gap, item))
            orbits.add(key)
        if len(chosen) == MAX_S1_PER_S2:
            break
    return chosen


def process_lake(client, lake, start, end, workers):
    folder = TRAIN_DIR / lake.id
    (folder / "pairs").mkdir(parents=True, exist_ok=True)
    log = folder / "pairs.jsonl"
    done = {json.loads(line)["pair"] for line in log.read_text().splitlines()} if log.exists() else set()
    prep = L.prepare_lake(client, lake)
    s1_items = client.search(S1_COLLECTION, lake.bbox, start - dt.timedelta(days=MAX_DAYS), end + dt.timedelta(days=MAX_DAYS))
    todo = []
    for candidate in s2_candidates(lake, start, end):
        if (candidate.cloud_fraction() or 0) > MAX_S2_CLOUD:
            continue
        match = partners(candidate, s1_items)
        if match:
            todo.append((candidate, match))
    print(f"  {len(todo)} optical scenes with a radar scene within {MAX_DAYS} days", flush=True)

    def work(candidate, match):
        mask, valid, rec = L.s2_water_mask(candidate, prep)
        results = []
        if mask is None or rec.get("seed_ice_fraction", 0) > L.ICE_MAX_FRACTION:
            return [{"pair": f"{candidate.item_id}__{i['id']}", "status": "skipped_" + rec.get("status", "ice")} for _, i in match]
        for gap, item in match:
            name = f"{candidate.item_id}__{item['id']}"
            if name in done:
                continue
            try:
                vv = client.read_to_grid(item, "vv", S1_COLLECTION, prep["grid"])
                vh = client.read_to_grid(item, "vh", S1_COLLECTION, prep["grid"])
            except Exception as exc:
                results.append({"pair": name, "status": "error", "error": str(exc)[:150]})
                continue
            vv_db = sar.to_db(vv)
            seed_cover = float(np.isfinite(vv[prep["seed"]]).mean())
            if seed_cover < 0.9:
                results.append({"pair": name, "status": "skipped_lake_not_covered"})
                continue
            inside, outside = mask & np.isfinite(vv_db), valid & ~mask & np.isfinite(vv_db)
            contrast = (float(np.nanmedian(vv_db[inside]) - np.nanmedian(vv_db[outside]))
                        if inside.sum() > 20 and outside.sum() > 20 else None)
            np.savez_compressed(folder / "pairs" / f"{name}.npz", vv_db=vv_db.astype("float16"),
                                vh_db=sar.to_db(vh).astype("float16"), water=mask, valid=valid)
            props = item["properties"]
            results.append({"pair": name, "status": "ok", "s2_date": candidate.date_str,
                            "s1_datetime": props["datetime"], "gap_days": gap,
                            "orbit": f"{(props.get('sat:orbit_state') or '')[:3]}{props.get('sat:relative_orbit')}",
                            "s2_cloud": candidate.cloud_fraction(), "seed_ice_fraction": rec["seed_ice_fraction"],
                            "water_pixels": int(mask.sum()), "water_km2": rec["area_km2"],
                            "radar_contrast_db": None if contrast is None else round(contrast, 2)})
        return results

    n_ok = 0
    with ThreadPoolExecutor(workers) as pool, log.open("a", encoding="utf-8") as handle:
        for future in as_completed([pool.submit(work, c, m) for c, m in todo]):
            try:
                for record in future.result():
                    handle.write(json.dumps(record) + "\n")
                    n_ok += record["status"] == "ok"
            except Exception as exc:
                handle.write(json.dumps({"pair": "?", "status": "error", "error": str(exc)[:150]}) + "\n")
            handle.flush()
    print(f"  pairs written this run: {n_ok}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", action="append")
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2020, 1, 1))
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.date(2022, 12, 31))
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()
    lakes = L.load_lakes()
    client = PlanetaryClient()
    for lake_id in args.lake or list(lakes):
        print(lakes[lake_id].name, flush=True)
        process_lake(client, lakes[lake_id], args.start, args.end, args.workers)


if __name__ == "__main__":
    main()
