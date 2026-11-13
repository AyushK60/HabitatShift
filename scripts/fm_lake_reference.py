"""Radar water-frequency reference for the lake foundation-model comparison.

For each period of data/fm/<study>/study.json, the Sentinel-1 scenes of usable orbits within +/-20 days of the
optical window give a water mask each; the share of scenes calling a pixel water is its water frequency. Radar is a
different sensor from the optical data under test, so it is a fair, independent check, but it has its own errors
(it underestimates some lakes, see the Hi-MAG comparison). Output: radar_water_<period>.npy in the study folder.

    python scripts/fm_lake_reference.py lake_imja_tsho imja_tsho
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.radar import lakes as L  # noqa: E402
from backend.app.radar.planetary import S1_COLLECTION, PlanetaryClient  # noqa: E402

MARGIN_DAYS = 20


def main(study_id: str, lake_id: str) -> None:
    folder = config.DATA_DIR / "fm" / study_id
    study = json.loads((folder / "study.json").read_text())
    lake = L.load_lakes()[lake_id]
    client = PlanetaryClient()
    prep = L.prepare_lake(client, lake)
    grid = study["grid"]
    assert (prep["grid"].height, prep["grid"].width) == (grid["height"], grid["width"]), "study grid != lake grid"
    orbits = json.loads((lake.directory / "monthly.json").read_text())["s1_orbits"]
    summary = {}
    for period, block in study["periods"].items():
        start = dt.date.fromisoformat(block["window"][0]) - dt.timedelta(days=MARGIN_DAYS)
        end = dt.date.fromisoformat(block["window"][1]) + dt.timedelta(days=MARGIN_DAYS)
        items = client.search(S1_COLLECTION, lake.bbox, start, end)

        def work(item):
            return L.scene_water_mask(client, item, prep)

        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(work, items))
        masks, valids, kept = [], [], []
        for mask, record in results:
            key = f"{(record.get('orbit_state') or '')[:3]}{record.get('relative_orbit')}"
            if mask is None or not orbits.get(key, {}).get("usable") or record["contrast_db"] > L.DARK_CONTRAST_DB:
                continue
            masks.append(mask)
            valids.append(record["_valid"])
            kept.append({"item": record["item"], "date": record["datetime"][:10], "area_km2": record["area_km2"]})
        if masks:
            wet = np.sum(masks, axis=0).astype("float32")
            seen = np.sum(valids, axis=0).astype("float32")
            freq = np.where(seen > 0, wet / np.maximum(seen, 1), np.nan).astype("float32")
        else:
            freq = np.full(prep["seed"].shape, np.nan, dtype="float32")
        np.save(folder / f"radar_water_{period}.npy", freq)
        summary[period] = {"scenes_found": len(items), "scenes_used": len(kept), "used": kept}
        print(period, "found", len(items), "used", len(kept), "mean area", round(float(np.mean([k["area_km2"] for k in kept])), 3) if kept else None, flush=True)
    (folder / "radar_reference.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
