"""Noise-calibration check of change scores from indices, raw bands and Prithvi embeddings.

Placebo test: compare one scene of a period with the rest of the same period (nothing changed, so every
flagged patch is a false alarm). Then compare the real earlier and later periods. No reference data is
used here, so this measures how the scores behave against noise, not how well they find real change.

    python scripts/run_fm_noise_check.py kathmandu_m4 western_ghats_m4 ...
Writes data/experiments/v3_fm/<experiment>/noise_check.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.foundation import compare as C  # noqa: E402
from backend.app.foundation.prithvi import PrithviEmbedder
from backend.app.foundation.resnet import SSL4EOResNetEmbedder  # noqa: E402

THRESHOLDS = (2.0, 3.0)
from backend.app.foundation.study import features_for, load_scenes  # noqa: E402


def summarise(experiment: str, embedders: dict) -> dict:
    scenes = load_scenes(config.DATA_DIR / "fm" / experiment / "scenes")
    earlier = [i for i, s in enumerate(scenes) if s[0]["period"] == "earlier"]
    later = [i for i, s in enumerate(scenes) if s[0]["period"] == "later"]
    features, oks = features_for(scenes, embedders)
    METHODS = tuple(features)
    out = {"experiment": experiment, "scenes": {"earlier": len(earlier), "later": len(later)},
           "patches": int(oks[0].size), "methods": {}}
    between = {}
    for method in METHODS:
        real = C.change_scores(features[method], oks, earlier, later)
        placebo = C.placebo_scores(features[method], oks, earlier, later)
        z_real = real["z"][np.isfinite(real["z"])]
        entry = {"between_period_flagged": {str(t): round(float((z_real > t).mean()), 4) for t in THRESHOLDS},
                 "between_period_median_z": round(float(np.median(z_real)), 3) if z_real.size else None,
                 "evaluated_patches": int(z_real.size)}
        if placebo:
            z_null = np.concatenate([p["z"][np.isfinite(p["z"])] for p in placebo])
            entry["placebo_false_alarm"] = {str(t): round(float((z_null > t).mean()), 4) for t in THRESHOLDS}
            entry["placebo_median_z"] = round(float(np.median(z_null)), 3)
            entry["placebo_comparisons"] = len(placebo)
        else:
            entry["placebo_false_alarm"] = None
        out["methods"][method] = entry
        between[method] = real["z"]
    agreement = {}
    for a in METHODS:
        for b in METHODS:
            if a < b:
                ok = np.isfinite(between[a]) & np.isfinite(between[b])
                if ok.sum() > 10:
                    agreement[f"{a}~{b}"] = round(float(spearmanr(between[a][ok], between[b][ok])[0]), 3)
    out["rank_correlation_of_z"] = agreement
    return out


def main(experiments: list[str]) -> None:
    embedder = {"prithvi": PrithviEmbedder(), "ssl4eo_rgb": SSL4EOResNetEmbedder()}
    for experiment in experiments:
        result = summarise(experiment, embedder)
        target = config.DATA_DIR / "experiments" / "v3_fm" / experiment
        target.mkdir(parents=True, exist_ok=True)
        (target / "noise_check.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"== {experiment}  scenes={result['scenes']}  patches={result['patches']}")
        for m, e in result["methods"].items():
            fa = e["placebo_false_alarm"]
            print(f"  {m:9s} placebo FAR z>3: {fa['3.0'] if fa else 'n/a':>7}  | between flagged z>3: {e['between_period_flagged']['3.0']:.3f}  median z {e['between_period_median_z']}")


if __name__ == "__main__":
    main(sys.argv[1:])
