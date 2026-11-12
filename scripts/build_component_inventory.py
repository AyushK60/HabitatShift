"""Complete-component inventory (the M4-R3 follow-up: 'complete-component inventory mode').

The sealed findings are a curated top-five-per-index/direction selection. This
script lists EVERY connected component at or above the minimum mapping unit
from the frozen delta rasters, using the same rule as the findings generator
(4-connectivity, common-valid footprint, symmetric inclusive threshold, MMU
25 px), and cross-checks its totals against the audited selection policy
(frontend/public/studies/selection_policy.json). Frozen outputs are only read.

Output: data/experiments/m5_inventory/<experiment>/components.csv + summary.json
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
MMU_PX = 25
STRUCT = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])
EXPERIMENTS = {
    "coringa_m1": "data/processed/m1/coringa_coastal",
    "chilika_m4_dry": "data/processed/m4/chilika_m4_dry",
    "chilika_m4_postmonsoon": "data/processed/m4/chilika_m4_postmonsoon",
    "western_ghats_m4": "data/processed/m4/western_ghats_m4",
    "himalaya_purepu_2025_m4": "data/processed/m4/himalaya_purepu_2025_m4",
    "himalaya_langtang_2026_m4": "data/processed/m4/himalaya_langtang_2026_m4",
    "kathmandu_m4": "data/processed/m4/kathmandu_m4",
}
THRESHOLD = 0.15


def main() -> int:
    policy = json.loads((ROOT / "frontend/public/studies/selection_policy.json").read_text(encoding="utf-8"))
    expected = {e["experiment_id"]: e for e in policy["experiments"]}
    all_ok = True
    for exp, rel in EXPERIMENTS.items():
        d = ROOT / rel
        out = ROOT / "data" / "experiments" / "m5_inventory" / exp
        out.mkdir(parents=True, exist_ok=True)
        rows, summary = [], {}
        for delta_path in sorted(d.glob("delta_*.tif")):
            index = delta_path.stem[len("delta_"):]
            with rasterio.open(delta_path) as src:
                delta = src.read(1).astype(np.float64)
                tf, crs = src.transform, src.crs
            with rasterio.open(d / f"common_valid_{index}.tif") as c:
                common = c.read(1) == 1
            to4326 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
            px_ha = abs(tf.a * tf.e) / 10_000.0
            for sign, direction in ((-1, "decrease"), (1, "increase")):
                mask = common & ((delta <= -THRESHOLD) if sign < 0 else (delta >= THRESHOLD))
                labels, n = ndimage.label(mask, structure=STRUCT)
                sizes = np.bincount(labels.ravel())[1:]
                keep = np.flatnonzero(sizes >= MMU_PX) + 1
                order = sorted(keep.tolist(), key=lambda k: (-int(sizes[k - 1]), k))
                coms = ndimage.center_of_mass(mask, labels, order) if order else []
                means = ndimage.mean(delta, labels, order) if order else []
                for rank, (lab, (r, c_)) in enumerate(zip(order, coms), start=1):
                    x, y = tf * (c_ + 0.5, r + 0.5)
                    lon, lat = to4326.transform(x, y)
                    rows.append({
                        "experiment": exp, "index": index, "direction": direction, "rank_by_size": rank,
                        "pixels": int(sizes[lab - 1]), "area_ha": round(float(sizes[lab - 1] * px_ha), 3),
                        "mean_delta": round(float(means[rank - 1]), 4),
                        "centroid_lon": round(lon, 6), "centroid_lat": round(lat, 6),
                    })
                summary.setdefault(index, {})[direction] = {
                    "components_total": int(n), "components_at_or_above_mmu": int(len(order)),
                    "area_ha_at_or_above_mmu": round(float(sum(sizes[k - 1] for k in order) * px_ha), 2),
                }
        total = sum(v["components_at_or_above_mmu"] for idx in summary.values() for v in idx.values())
        exp_policy = expected.get(exp)
        match = exp_policy is not None and int(exp_policy["components_at_or_above_mmu_total"]) == total
        all_ok &= match
        with open(out / "components.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["experiment"])
            w.writeheader()
            w.writerows(rows)
        (out / "summary.json").write_text(json.dumps({
            "schema": "habitatshift-m5-component-inventory/1", "experiment": exp,
            "rule": f"4-connected components on the common-valid footprint at |delta| >= {THRESHOLD}, MMU {MMU_PX} px",
            "components_at_or_above_mmu_total": total,
            "selection_policy_total": None if exp_policy is None else exp_policy["components_at_or_above_mmu_total"],
            "matches_selection_policy": match, "by_index": summary,
            "note": "complete inventory; the sealed findings remain the curated top-five selection",
        }, indent=2), encoding="utf-8")
        print(f"{exp}: inventory total {total} vs selection_policy "
              f"{None if exp_policy is None else exp_policy['components_at_or_above_mmu_total']} -> {'MATCH' if match else 'MISMATCH'}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
