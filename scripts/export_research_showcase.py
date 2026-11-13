"""Bundle the version 3 research results into frontend/public/research/v3.json for the Research page.

Reads only recorded outputs (data/experiments/v3_fm, data/experiments/v3_unet); computes nothing new.
    python scripts/export_research_showcase.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402

EXP = config.DATA_DIR / "experiments"
OUT = config.PROJECT_ROOT / "frontend" / "public" / "research" / "v3.json"

LABELS = {
    "ndvi_decrease": "NDVI decrease (signed)", "raw6": "Six raw bands", "prithvi": "Prithvi foundation model",
    "ssl4eo_rgb": "SSL4EO ResNet-50 (RGB)", "ndvi": "NDVI", "ndwi": "NDWI", "mndwi": "MNDWI", "indices5": "Five indices",
}
KIND = {"ndvi_decrease": "index", "raw6": "bands", "prithvi": "model", "ssl4eo_rgb": "model", "ndvi": "index",
        "ndwi": "index", "mndwi": "index", "indices5": "index"}


def method_rows(evaluation: dict, keep: list[str], reference: str) -> list[dict]:
    rows = []
    for name in keep:
        key = f"{name}:z"
        if key not in evaluation["metrics"]:
            continue
        m = evaluation["metrics"][key]
        boot = evaluation["block_bootstrap"].get(key, {})
        ap = boot.get("average_precision", {})
        rows.append({"id": name, "label": LABELS[name], "kind": KIND[name],
                     "ap": round(m["average_precision"], 3), "auc": round(m["roc_auc"], 3),
                     "ap_ci": [round(x, 3) for x in ap.get("ci95", [None, None])] if ap.get("ci95") else None,
                     "vs_reference_ci": [round(x, 3) for x in ap["diff_vs_reference_ci95"]] if ap.get("diff_vs_reference_ci95") else None,
                     "is_reference": name == reference})
    return sorted(rows, key=lambda r: -r["ap"])


def main() -> None:
    forest = {}
    for study, title in (("bastar_forest", "Bastar, Chhattisgarh"), ("odisha_forest", "Odisha")):
        e = json.loads((EXP / "v3_fm" / study / "evaluation.json").read_text())
        forest[study] = {"title": title, "counts": e["counts"], "reference_method": "ndvi_decrease",
                         "scenes": e["scenes"], "rows": method_rows(
                             e, ["ndvi_decrease", "raw6", "prithvi", "ssl4eo_rgb", "ndvi", "ndwi", "indices5"], "ndvi_decrease")}
    lakes_eval = json.loads((EXP / "v3_fm" / "lakes" / "evaluation.json").read_text())
    lakes = {"counts": lakes_eval["pooled_counts"], "per_lake": lakes_eval["per_lake"],
             "rows": method_rows(lakes_eval, ["raw6", "prithvi", "ndvi", "mndwi", "indices5", "ssl4eo_rgb"], "mndwi")}

    seeds = {"seed0": "evaluation.json", "seed1": "evaluation_seed1.json", "seed2": "evaluation_seed2.json"}
    runs = {k: json.loads((EXP / "v3_unet" / v).read_text()) for k, v in seeds.items() if (EXP / "v3_unet" / v).exists()}
    unet = {"seeds": len(runs), "sets": {}}
    for key, label in (("time_holdout_2022_same_lakes", "Same lakes, new year"), ("test_lakes", "Unseen lakes")):
        ious = [r[key]["unet"]["mean_iou"] for r in runs.values()]
        unet["sets"][key] = {
            "label": label, "unet_mean": round(statistics.mean(ious), 3),
            "unet_sd": round(statistics.stdev(ious), 3) if len(ious) > 1 else None,
            "otsu": round(runs["seed0"][key]["otsu_radar_rule"]["mean_iou"], 3), "n_pairs": runs["seed0"][key]["unet"]["n_pairs"]}
    cv_path = EXP / "v3_unet" / "cv.json"
    if cv_path.exists():
        cv = json.loads(cv_path.read_text())
        unet["cv"] = {"n_pairs": cv["n_pairs"], "median_relative_area_error": round(cv["median_relative_area_error"], 3),
                      "tile_mean_iou": round(cv["tile_mean_iou"], 3),
                      "coverage": {a: {"target": round(1 - float(a.split("_")[1]), 2), "achieved": round(e["coverage_overall"], 3),
                                       "worst_lake": round(e["lake_coverage_min"], 2), "lakes_below_target": e["lakes_below_target"]}
                                   for a, e in cv["conformal"].items()}}
    # Earlier single-split coverage, kept to show why the cross-validated check was needed
    unet["single_split_coverage_unseen_lakes"] = {
        a: [round(r["conformal_area"][a]["test_lakes"]["coverage"], 2) for r in runs.values()]
        for a in ("alpha_0.1",)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"schema": "habitatshift-v3/1", "forest": forest, "lakes": lakes, "unet": unet},
                              separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
