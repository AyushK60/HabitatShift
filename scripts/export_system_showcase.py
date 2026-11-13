"""Collect what the system has actually done into frontend/public/system/system.json for the System page.

Counts come from files on disk (scene logs, pair logs, registry, test collection); nothing is estimated.
    python scripts/export_system_showcase.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402

ROOT = config.PROJECT_ROOT
OUT = ROOT / "frontend" / "public" / "system" / "system.json"


def lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def loc(patterns: list[str]) -> int:
    total = 0
    for pattern in patterns:
        for f in ROOT.glob(pattern):
            if f.is_file() and "node_modules" not in f.parts and ".venv" not in f.parts and "dist" not in f.parts:
                total += sum(1 for _ in f.open(encoding="utf-8", errors="ignore"))
    return total


def dir_gb(path: Path) -> float:
    return round(sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e9, 2) if path.exists() else 0.0


def main() -> None:
    lakes = yaml.safe_load((config.STUDIES_DIR / "lakes.yaml").read_text(encoding="utf-8"))["lakes"]
    s1 = s2 = 0
    for lake in lakes:
        d = config.DATA_DIR / "lakes" / lake["id"]
        s1 += sum(r.get("status") == "ok" for r in lines(d / "s1_scenes.jsonl"))
        s2 += sum(r.get("status") == "ok" for r in lines(d / "s2_scenes.jsonl"))
    pair_ok = pair_all = 0
    for lake in lakes:
        recs = lines(config.DATA_DIR / "lakes_train" / lake["id"] / "pairs.jsonl")
        pair_all += len(recs)
        pair_ok += sum(r.get("status") == "ok" for r in recs)
    registry = json.loads((ROOT / "frontend" / "public" / "studies" / "registry.json").read_text(encoding="utf-8"))
    studies = len(registry.get("studies", []))
    collect = subprocess.run([sys.executable, "-m", "pytest", "backend/tests", "--collect-only", "-q", "-p", "no:warnings"],
                             cwd=ROOT, capture_output=True, text=True)
    tests = sum(int(l.rsplit(': ', 1)[1]) for l in collect.stdout.splitlines() if '.py: ' in l)
    unet = config.DATA_DIR / "models" / "lake_unet"
    cv = config.DATA_DIR / "experiments" / "v3_unet" / "cv.json"
    cv_pairs = json.loads(cv.read_text())["n_pairs"] if cv.exists() else None
    bundle = {
        "schema": "habitatshift-system/1",
        "counts": {
            "lakes": len(lakes), "radar_scenes": s1, "optical_scenes": s2, "training_pairs": pair_ok, "pairs_examined": pair_all,
            "study_areas": studies, "tests": tests, "unet_fold_models": len(list(unet.glob("unet_fold*.pt"))) if unet.exists() else 0,
            "cv_scored_pairs": cv_pairs,
        },
        "size": {"training_tiles_gb": dir_gb(config.DATA_DIR / "lakes_train"), "foundation_weights_gb": dir_gb(config.DATA_DIR / "models" / "prithvi_eo_2_300m")},
        "code": {"python_lines": loc(["backend/**/*.py", "scripts/*.py"]), "frontend_lines": loc(["frontend/src/**/*.ts", "frontend/src/**/*.tsx", "frontend/src/**/*.css"]),
                 "doc_pages": len(list((ROOT / "docs").glob("*.md")))},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, indent=1), encoding="utf-8")
    print(json.dumps(bundle["counts"]))


if __name__ == "__main__":
    main()
