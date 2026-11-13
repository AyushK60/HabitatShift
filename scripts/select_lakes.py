"""Add every Hi-MAG (2017) glacial lake of 0.3-6 km2 inside Nepal to studies/lakes.yaml.

Selection rule, fixed in advance and applied without sampling:
  * Hi-MAG v3.0 2017 outline (Zenodo 4275164, CC-BY 4.0), representative point inside the Nepal boundary
    (geoBoundaries gbOpen NPL ADM0, CC-BY 4.0)
  * outline area between 0.3 and 6 km2
Lakes within 500 m of a lake already in the registry are skipped (the three pilot lakes).
Each new lake needs a DEM-flat seed within 400 m of its point; lakes without one are not added and are written
to studies/lakes_rejected.json with the reason.

Download the inputs first (see compare_lake_reference.py and data/reference/nepal_boundary).
    python scripts/select_lakes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import shapefile
import yaml
from pyproj import CRS, Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.radar import lakes as L  # noqa: E402
from backend.app.radar.planetary import PlanetaryClient  # noqa: E402

HIMAG = config.DATA_DIR / "reference" / "himag_extracted" / "Hi-MAG database" / "Hi_MAG_database_2017"
BOUNDARY = config.DATA_DIR / "reference" / "nepal_boundary" / "geoBoundaries-NPL-ADM0_simplified.geojson"
MIN_KM2, MAX_KM2 = 0.3, 6.0
HALF_DEG = 0.04
REJECTED = config.STUDIES_DIR / "lakes_rejected.json"


def candidates() -> list[dict]:
    nepal = shape(json.loads(BOUNDARY.read_text())["features"][0]["geometry"])
    crs = CRS.from_wkt(HIMAG.with_suffix(".prj").read_text())
    to_lonlat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    out = []
    for sr in shapefile.Reader(str(HIMAG)).iterShapeRecords():
        rec = sr.record.as_dict()
        area = rec["GL_Area"] / 1e6
        if not MIN_KM2 <= area <= MAX_KM2:
            continue
        point = transform(to_lonlat, shape(sr.shape.__geo_interface__).representative_point())
        if nepal.contains(Point(point.x, point.y)):
            out.append({"himag_id": rec["GL_ID"], "type": rec["GL_Type"], "area_km2": round(area, 3),
                        "elevation_m": int(rec["GL_Elev"]), "lon": round(point.x, 4), "lat": round(point.y, 4)})
    return sorted(out, key=lambda c: c["himag_id"])


def main() -> None:
    registry = yaml.safe_load(L.LAKES_FILE.read_text(encoding="utf-8"))["lakes"]
    existing = [(e["lon"], e["lat"]) for e in registry]
    client = PlanetaryClient()
    added, rejected = [], []
    for c in candidates():
        if any(abs(c["lon"] - x) < 0.006 and abs(c["lat"] - y) < 0.006 for x, y in existing):
            print("skip (already in registry):", c["himag_id"])
            continue
        lake = L.Lake(id=f"himag_{c['himag_id'].lower()}", name=f"Lake {c['himag_id']}", lon=c["lon"], lat=c["lat"],
                      half_deg=HALF_DEG, note=f"Hi-MAG 2017: {c['type']}, {c['area_km2']} km2, {c['elevation_m']} m.")
        try:
            L.prepare_lake(client, lake)
        except Exception as exc:
            rejected.append({**c, "reason": str(exc)[:200]})
            print("rejected:", c["himag_id"], str(exc)[:100], flush=True)
            continue
        added.append(lake)
        print("ok:", lake.id, c["area_km2"], "km2", flush=True)
    text = L.LAKES_FILE.read_text(encoding="utf-8").rstrip() + "\n"
    for lake in added:
        text += (f"  - id: {lake.id}\n    name: {lake.name}\n    lon: {lake.lon}\n    lat: {lake.lat}\n"
                 f"    half_deg: {lake.half_deg}\n    note: {lake.note}\n")
    L.LAKES_FILE.write_text(text, encoding="utf-8")
    REJECTED.write_text(json.dumps(rejected, indent=1), encoding="utf-8")
    print(f"added {len(added)}, rejected {len(rejected)}")


if __name__ == "__main__":
    main()
