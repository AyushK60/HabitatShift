"""Apply the radar water U-Net to the Sentinel-1 scenes of lakes and write a model monthly series.

Each lake uses the cross-validation model that never saw it in training (scripts/cv_lake_unet.py). Only scenes from
orbits already judged usable for that lake are processed, same as the Otsu radar series. Output per lake:
data/lakes/<id>/s1_unet.jsonl (scene areas, resumable) and data/lakes/<id>/monthly_unet.json (monthly series with a
conformal interval and a flag for months that have no optical value, i.e. gaps the model fills).

    python scripts/run_unet_lake_series.py --lake tsho_rolpa --lake imja_tsho --lake thulagi
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
import torch

os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")
os.environ.setdefault("GDAL_HTTP_CONNECTTIMEOUT", "20")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.radar import lakes as L  # noqa: E402
from backend.app.radar.planetary import S1_COLLECTION, PlanetaryClient  # noqa: E402
from backend.app.segmentation import conformal as C  # noqa: E402
from backend.app.segmentation import data as D  # noqa: E402
from backend.app.segmentation.train import predict_tile  # noqa: E402
from backend.app.segmentation.unet import UNet  # noqa: E402

CV = config.DATA_DIR / "experiments" / "v3_unet" / "cv.json"
MODELS = config.DATA_DIR / "models" / "lake_unet"
ALPHA = 0.1


def load_model(fold: int, device: str) -> UNet:
    ckpt = torch.load(MODELS / f"unet_fold{fold}.pt", map_location="cpu")
    net = UNet(base=ckpt["base"])
    net.load_state_dict(ckpt["state"])
    return net.to(device).eval()


def run_lake(client, lake, net, workers, device, q) -> None:
    prep = L.prepare_lake(client, lake)
    monthly = json.loads((lake.directory / "monthly.json").read_text())
    orbits = monthly["s1_orbits"]
    records = {r["item"]: r for r in L.load_records(lake.directory / "s1_scenes.jsonl")}
    todo = [r for r in records.values()
            if r.get("status") == "ok" and orbits.get(f"{r['orbit_state'][:3]}{r['relative_orbit']}", {}).get("usable")]
    out_path = lake.directory / "s1_unet.jsonl"
    done = {r["item"]: r for r in L.load_records(out_path)}
    todo = [r for r in todo if r["item"] not in done]
    print(f"{lake.name}: {len(done)} done, {len(todo)} to process", flush=True)
    if todo:
        years = [int(r["datetime"][:4]) for r in todo]
        items = {i["id"]: i for i in client.search(S1_COLLECTION, lake.bbox, dt.date(min(years), 1, 1), dt.date(max(years), 12, 31))}
        slope, seed = prep["slope"], prep["seed"]

        def read(rec):
            item = items[rec["item"]]
            return rec, client.read_to_grid(item, "vv", S1_COLLECTION, prep["grid"]), client.read_to_grid(item, "vh", S1_COLLECTION, prep["grid"])

        with ThreadPoolExecutor(workers) as pool, out_path.open("a", encoding="utf-8") as handle:
            for future in as_completed([pool.submit(read, r) for r in todo]):
                try:
                    rec, vv, vh = future.result()
                except Exception as exc:
                    print("  read failed:", str(exc)[:80], flush=True)
                    continue
                vv_db, vh_db = L.sar.to_db(vv), L.sar.to_db(vh)
                prob = predict_tile(net, D.make_input(vv_db, vh_db, slope), device)
                mask = (prob > 0.5) & np.isfinite(vv)
                area, patches = L.lake_patch_area(mask, seed, prep["grid"].res)
                row = {k: rec[k] for k in ("sensor", "item", "datetime", "orbit_state", "relative_orbit", "contrast_db")}
                row.update(status="ok", area_km2=round(area, 4), patches=patches)
                handle.write(json.dumps(row) + "\n")
                handle.flush()
                done[rec["item"]] = row
    series = L.flag_changes(L.monthly_series(list(done.values()), orbits))
    optical = {r["month"] for r in monthly["s2_monthly"] if r.get("area_km2") is not None}
    for row in series:
        if row.get("area_km2") is not None:
            lo, hi = C.interval(np.array([row["area_km2"]]), q)
            row["lo_km2"], row["hi_km2"] = round(float(lo[0]), 4), round(float(hi[0]), 4)
            row["fills_optical_gap"] = row["month"] not in optical
    (lake.directory / "monthly_unet.json").write_text(json.dumps({
        "lake": lake.id, "model": f"cross-validation fold model, lake held out in training",
        "interval": {"alpha": ALPHA, "relative_half_width_q": q,
                     "note": "calibrated on scene-level out-of-fold errors over 30 lakes; applied to monthly medians"},
        "s1_unet_monthly": series}, indent=1), encoding="utf-8")
    filled = sum(bool(r.get("fills_optical_gap")) for r in series if r.get("area_km2") is not None)
    print(f"  monthly series: {sum(r.get('area_km2') is not None for r in series)} months, {filled} fill an optical gap", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", action="append", required=True)
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cv = json.loads(CV.read_text())
    fold_of = {lake: int(k) for k, info in cv["folds"].items() for lake in info["lakes"]}
    q = cv["conformal"][f"alpha_{ALPHA}"]["q_all_folds"]
    lakes, client = L.load_lakes(), PlanetaryClient()
    for lake_id in args.lake:
        run_lake(client, lakes[lake_id], load_model(fold_of[lake_id], device), args.workers, device, q)


if __name__ == "__main__":
    main()
