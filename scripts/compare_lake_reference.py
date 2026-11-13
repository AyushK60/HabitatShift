"""Compare our lake areas with the Hi-MAG annual glacial-lake outlines (agreement, not accuracy).

Hi-MAG: Annual 30 m glacial lake dataset for High Mountain Asia, 2008-2017 (Landsat based), CC-BY 4.0,
https://doi.org/10.5281/zenodo.4275164 . It is another satellite product with its own errors, so the
numbers below measure how closely we agree with it, not how close we are to the truth.

Download first (about 59 MB):
    mkdir -p data/reference/himag_extracted   and unzip "Hi-MAG database.zip" into it.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.radar import lakes as L  # noqa: E402

HIMAG_DIR = L.config.DATA_DIR / "reference" / "himag_extracted" / "Hi-MAG database"
YEARS = (2016, 2017)
OPEN_WATER_MONTHS = ("06", "07", "08", "09", "10")
SEARCH_RADIUS_M = 500.0


def himag_lake_area(year: int, lon: float, lat: float) -> dict | None:
    base = HIMAG_DIR / f"Hi_MAG_database_{year}"
    crs = CRS.from_wkt(base.with_suffix(".prj").read_text())
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(lon, lat)
    reader = shapefile.Reader(str(base))
    best = None
    for rec in reader.iterShapeRecords(bbox=(x - 3000, y - 3000, x + 3000, y + 3000)):
        geom = shape(rec.shape.__geo_interface__)
        distance = geom.distance(Point(x, y))
        if distance <= SEARCH_RADIUS_M and (best is None or distance < best[0]):
            best = (distance, geom, rec.record.as_dict())
    if best is None:
        return None
    distance, geom, attrs = best
    return {"year": year, "area_km2": round(geom.area / 1e6, 4), "distance_m": round(distance, 1),
            "attributes": {k: v for k, v in attrs.items() if not isinstance(v, bytes)}}


def our_open_water_area(monthly: list[dict], year: int) -> dict:
    values = [r["area_km2"] for r in monthly
              if r["month"].startswith(str(year)) and r["month"][5:7] in OPEN_WATER_MONTHS and "area_km2" in r]
    if not values:
        return {"months": 0}
    return {"months": len(values), "median_km2": round(statistics.median(values), 4),
            "min_km2": round(min(values), 4), "max_km2": round(max(values), 4)}


def main() -> None:
    out = {"reference": "Hi-MAG v3.0 (Zenodo 4275164, CC-BY 4.0)", "lakes": {}}
    for lake_id, lake in L.load_lakes().items():
        path = lake.directory / "monthly.json"
        if not path.exists():
            continue
        monthly = json.loads(path.read_text())
        entry = {"name": lake.name, "years": {}}
        for year in YEARS:
            ref = himag_lake_area(year, lake.lon, lake.lat)
            row = {"himag": ref, "s1": our_open_water_area(monthly["s1_monthly"], year),
                   "s2": our_open_water_area(monthly["s2_monthly"], year)}
            if ref:
                for sensor in ("s1", "s2"):
                    if row[sensor].get("median_km2") is not None:
                        row[sensor]["difference_vs_himag_pct"] = round(
                            100 * (row[sensor]["median_km2"] - ref["area_km2"]) / ref["area_km2"], 1)
            entry["years"][str(year)] = row
        out["lakes"][lake_id] = entry
    target = L.LAKES_DIR / "reference_himag.json"
    target.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
