"""Per-scene index time series from the cached observations (read-only).

For every recorded study this reads each scene that fed the earlier/later composites
(matched by item id AND the study's grid signature, so a 20 m sandbox run can never be
mixed in), and reports the mean of each index over that scene's own valid pixels.

This is a per-scene description, not a trend test: with 3 scenes per period and two
periods five years apart it shows scene-to-scene spread within a period against the
between-period difference. Output: frontend/public/studies/m5_timeseries.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "observations"
OUT = ROOT / "frontend" / "public" / "studies" / "m5_timeseries.json"
MANIFESTS = {
    "coringa_coastal": "m1_coringa_coastal.json",
    "chilika_wetland_dry": "m4_chilika_m4_dry.json",
    "chilika_wetland_postmonsoon": "m4_chilika_m4_postmonsoon.json",
    "western_ghats_forest": "m4_western_ghats_m4.json",
    "himalaya_purepu_2025": "m4_himalaya_purepu_2025_m4.json",
    "himalaya_langtang_2026": "m4_himalaya_langtang_2026_m4.json",
    "kathmandu_urban": "m4_kathmandu_m4.json",
}
STUDY_ID = {k: k.split("_dry")[0].split("_postmonsoon")[0] for k in MANIFESTS}


sys.path.insert(0, str(ROOT))
from backend.app.indices.ndvi import normalised_difference as nd  # noqa: E402  the audited engine function


def index_values(z: np.lib.npyio.NpzFile) -> dict[str, np.ndarray]:
    r = {k.replace("reflectance_", ""): z[k].astype("float32") for k in z.files if k.startswith("reflectance_")}
    out: dict[str, np.ndarray] = {}
    if {"nir", "red"} <= r.keys():
        out["ndvi"] = nd(r["nir"], r["red"])
    if {"green", "nir"} <= r.keys():
        out["ndwi"] = nd(r["green"], r["nir"])
    if {"swir16", "nir"} <= r.keys():
        out["ndbi"] = nd(r["swir16"], r["nir"])
    if {"green", "swir16"} <= r.keys():
        out["mndwi"] = nd(r["green"], r["swir16"])
    return out


def main() -> int:
    metas = {}
    for meta_path in CACHE.glob("*.json"):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        metas.setdefault((meta["item_id"], meta["grid_signature"]), []).append((meta_path, meta))

    studies = []
    for key, manifest_name in MANIFESTS.items():
        manifest = json.loads((ROOT / "data" / "manifests" / manifest_name).read_text(encoding="utf-8"))
        signature = manifest["grid"].get("signature")
        scenes = []
        for period in manifest["periods"]:
            for item_id, date in zip(period["item_ids"], period["observation_dates"]):
                entries = metas.get((item_id, signature), [])
                if not entries:
                    continue
                # Some 2025 scenes have two cache entries: the declared-offset reading and the
                # empirically corrected one (radiometry_evidence present) that the engine
                # actually used. Use only the corrected group when it exists.
                corrected = [path for path, meta in entries if "radiometry_evidence" in meta]
                paths = corrected or [path for path, _ in entries]
                merged: dict[str, float] = {}
                valid_px = 0
                for path in paths:  # several cache entries may carry different band sets
                    z = np.load(path.with_suffix(".npz"))
                    valid = z["valid"].astype(bool)
                    valid_px = max(valid_px, int(valid.sum()))
                    for name, arr in index_values(z).items():
                        ok = valid & np.isfinite(arr)
                        if ok.any() and name not in merged:
                            merged[name] = round(float(arr[ok].mean()), 4)
                scenes.append(
                    {
                        "date": date,
                        "item_id": item_id,
                        "period": period["period_id"],
                        "valid_pixels": valid_px,
                        "mean": merged,
                    }
                )
        scenes.sort(key=lambda s: s["date"])
        studies.append(
            {
                "key": key,
                "study_id": STUDY_ID[key],
                "experiment": manifest["experiment_id"],
                "scenes_expected": sum(len(p["item_ids"]) for p in manifest["periods"]),
                "scenes_found": len(scenes),
                "scenes": scenes,
            }
        )
    doc = {
        "schema": "habitatshift-m5-scene-timeseries/1",
        "note": "Mean index value over each scene's own valid pixels, from cached observations on the study grid. "
        "A per-scene description with 3 scenes per period; it is not a trend test.",
        "studies": studies,
    }
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    for s in studies:
        print(s["key"], s["scenes_found"], "/", s["scenes_expected"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
