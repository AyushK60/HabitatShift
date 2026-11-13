"""Bundle the lake results into one static file for the app: frontend/public/lakes/lakes.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.radar import lakes as L  # noqa: E402

OUT = L.config.PROJECT_ROOT / "frontend" / "public" / "lakes" / "lakes.json"


def main() -> None:
    reference_path = L.LAKES_DIR / "reference_himag.json"
    reference = json.loads(reference_path.read_text()) if reference_path.exists() else {"lakes": {}}
    bundle = {"schema": "habitatshift-lakes/1", "reference": reference.get("reference"), "lakes": []}
    for lake_id, lake in L.load_lakes().items():
        path = lake.directory / "monthly.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        static = json.loads(str(__import__("numpy").load(lake.directory / "static.npz")["seed_info"]))
        unet_path = lake.directory / "monthly_unet.json"
        unet = None
        if unet_path.exists():
            u = json.loads(unet_path.read_text())
            unet = {"interval": u["interval"], "months": u["s1_unet_monthly"]}
        bundle["lakes"].append({
            "id": lake_id, "name": lake.name, "note": lake.note, "lon": lake.lon, "lat": lake.lat,
            "seed": static, "s1_orbits": data["s1_orbits"], "scene_counts": data["scene_counts"],
            "s1_monthly": data["s1_monthly"], "s2_monthly": data["s2_monthly"], "unet": unet,
            "reference": reference["lakes"].get(lake_id, {}).get("years"),
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(bundle['lakes'])} lakes)")


if __name__ == "__main__":
    main()
