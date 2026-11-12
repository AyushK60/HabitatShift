"""Bundle the complete-component inventory for the UI (read-only over recorded outputs).

Reads data/experiments/m5_inventory/<experiment>/{summary.json,components.csv} and writes
frontend/public/studies/m5_inventory.json (summaries + the ten largest components per
experiment) plus a downloadable CSV copy per experiment. Nothing is recomputed.
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "experiments" / "m5_inventory"
OUT = ROOT / "frontend" / "public" / "studies"
TOP = 10

STUDY_OF = {
    "coringa_m1": "coringa_coastal",
    "chilika_m4_dry": "chilika_wetland",
    "chilika_m4_postmonsoon": "chilika_wetland",
    "western_ghats_m4": "western_ghats_forest",
    "himalaya_purepu_2025_m4": "himalaya_purepu_2025",
    "himalaya_langtang_2026_m4": "himalaya_langtang_2026",
    "kathmandu_m4": "kathmandu_urban",
}


def main() -> int:
    (OUT / "m5_inventory").mkdir(parents=True, exist_ok=True)
    experiments = []
    for exp_dir in sorted(p for p in SRC.iterdir() if p.is_dir()):
        summary = json.loads((exp_dir / "summary.json").read_text(encoding="utf-8"))
        with (exp_dir / "components.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows.sort(key=lambda r: -int(r["pixels"]))
        top = [
            {
                "index": r["index"],
                "direction": r["direction"],
                "pixels": int(r["pixels"]),
                "area_ha": float(r["area_ha"]),
                "mean_delta": float(r["mean_delta"]),
                "lon": float(r["centroid_lon"]),
                "lat": float(r["centroid_lat"]),
            }
            for r in rows[:TOP]
        ]
        shutil.copyfile(exp_dir / "components.csv", OUT / "m5_inventory" / f"{exp_dir.name}.csv")
        experiments.append(
            {
                "experiment": exp_dir.name,
                "study_id": STUDY_OF[exp_dir.name],
                "rule": summary["rule"],
                "total": summary["components_at_or_above_mmu_total"],
                "matches_selection_policy": summary["matches_selection_policy"],
                "by_index": summary["by_index"],
                "largest": top,
                "csv": f"studies/m5_inventory/{exp_dir.name}.csv",
            }
        )
    doc = {
        "schema": "habitatshift-m5-inventory-bundle/1",
        "note": "Complete inventory of every component at or above the minimum mapping unit. "
        "The sealed findings remain the curated top-five selection; this view is additive.",
        "experiments": experiments,
    }
    (OUT / "m5_inventory.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"bundled {len(experiments)} experiments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
