"""Build monthly glacial-lake area series from Sentinel-1 radar and Sentinel-2 optical scenes.

Resumable: each processed scene is appended to data/lakes/<lake>/<sensor>_scenes.jsonl and skipped on the
next run. Example:
    python scripts/run_lake_series.py --lake tsho_rolpa --start 2019-01-01 --end 2020-12-31
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import config  # noqa: E402
from backend.app.catalog.search import SearchRequest  # noqa: E402
from backend.app.catalog.stac_client import CatalogClient  # noqa: E402
from backend.app.http import HttpSession  # noqa: E402
from backend.app.preprocess.aoi import aoi_from_bounds  # noqa: E402
from backend.app.radar import lakes as L  # noqa: E402
from backend.app.radar.planetary import S1_COLLECTION, PlanetaryClient  # noqa: E402

# A stalled remote read must fail and be retried rather than hang the whole run.
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")
os.environ.setdefault("GDAL_HTTP_CONNECTTIMEOUT", "20")

REFERENCE_YEARS = (2019, 2020)


def append(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def run_s1(client, lake, prep, start, end, workers):
    path = lake.directory / "s1_scenes.jsonl"
    done = {r["item"] for r in L.load_records(path) if r.get("status") != "error"}
    items = [i for i in client.search(S1_COLLECTION, lake.bbox, start, end) if i["id"] not in done]
    print(f"  S1: {len(items)} new scenes ({len(done)} already done)", flush=True)

    def work(item):
        try:
            return L.process_s1_scene(client, item, prep)
        except Exception as exc:  # recorded, not hidden
            return {"sensor": "s1", "item": item["id"], "datetime": item["properties"]["datetime"],
                    "status": "error", "error": str(exc)[:200]}

    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(work, i) for i in items]
        for n, future in enumerate(as_completed(futures), 1):
            append(path, future.result())
            if n % 25 == 0:
                print(f"    {n}/{len(items)}", flush=True)


def run_s2(lake, prep, start, end, workers):
    path = lake.directory / "s2_scenes.jsonl"
    done = {r["item"] for r in L.load_records(path) if r.get("status") != "error"}
    west, south, east, north = lake.bbox
    aoi = aoi_from_bounds(study_id=lake.id, west=west, south=south, east=east, north=north,
                          description=lake.name, source="studies/lakes.yaml")
    catalog = CatalogClient(HttpSession(cache_dir=config.CACHE_DIR), probe_assets=False,
                            required_assets=(config.ASSET_GREEN, config.ASSET_NIR, config.ASSET_SWIR1, config.ASSET_SCL))
    candidates = []
    year_start = start
    while year_start < end:
        year_end = min(year_start + dt.timedelta(days=360), end)
        request = SearchRequest(aoi=aoi, start=dt.datetime.combine(year_start, dt.time.min),
                                end=dt.datetime.combine(year_end, dt.time.max), max_cloud_cover=85.0, limit=100)
        candidates += [c for c in catalog.search(request).items if c.item_id not in done]
        year_start = year_end + dt.timedelta(days=1)
    candidates = list({c.item_id: c for c in candidates}.values())
    print(f"  S2: {len(candidates)} new scenes ({len(done)} already done)", flush=True)

    def work(candidate):
        try:
            return L.process_s2_scene(candidate, prep)
        except Exception as exc:
            return {"sensor": "s2", "item": candidate.item_id, "datetime": candidate.acquisition_iso,
                    "status": "error", "error": str(exc)[:200]}

    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(work, c) for c in candidates]
        for n, future in enumerate(as_completed(futures), 1):
            append(path, future.result())
            if n % 25 == 0:
                print(f"    {n}/{len(candidates)}", flush=True)


def write_monthly(lake):
    out = {"lake": lake.id, "name": lake.name, "reference_years_for_orbit_screening": list(REFERENCE_YEARS)}
    s1 = L.load_records(lake.directory / "s1_scenes.jsonl")
    orbits = L.usable_orbits(s1, REFERENCE_YEARS)
    out["s1_orbits"] = orbits
    out["s1_monthly"] = L.flag_changes(L.monthly_series(s1, orbits))
    s2 = L.load_records(lake.directory / "s2_scenes.jsonl")
    frozen = L.not_dark_months(s1, orbits)
    out["frozen_season_months"] = sorted(frozen)
    out["s2_monthly"] = L.flag_changes(L.monthly_series(s2, None, frozen))
    out["scene_counts"] = {"s1": len(s1), "s2": len(s2)}
    (lake.directory / "monthly.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", action="append", help="lake id (repeatable); default all")
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2017, 1, 1))
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.date(2026, 10, 31))
    parser.add_argument("--sensors", default="s1,s2")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    lakes = L.load_lakes()
    client = PlanetaryClient()
    for lake_id in args.lake or list(lakes):
        lake = lakes[lake_id]
        print(f"{lake.name}", flush=True)
        prep = L.prepare_lake(client, lake)
        print(f"  seed: {prep['seed_info']}", flush=True)
        if "s1" in args.sensors:
            run_s1(client, lake, prep, args.start, args.end, args.workers)
        if "s2" in args.sensors:
            run_s2(lake, prep, args.start, args.end, args.workers)
        write_monthly(lake)


if __name__ == "__main__":
    main()
