"""Create a new foundation-model comparison study: grid, matched-season scenes, six-band stacks.

    python scripts/fm_make_study.py bastar_forest 81.134 19.184 81.206 19.256 \
        --earlier 2021-01-20 2021-03-20 --later 2025-01-20 2025-03-20
Writes data/fm/<id>/study.json and data/fm/<id>/scenes/*.npz
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.foundation import scenes as S  # noqa: E402
from backend.app.radar.planetary import make_grid  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("study_id")
    p.add_argument("bbox", nargs="*", type=float, help="west south east north (or use --lake)")
    p.add_argument("--lake", help="use the exact analysis box of a lake in studies/lakes.yaml")
    p.add_argument("--earlier", nargs=2, type=dt.date.fromisoformat, required=True)
    p.add_argument("--later", nargs=2, type=dt.date.fromisoformat, required=True)
    p.add_argument("--n", type=int, default=3)
    args = p.parse_args()
    if args.lake:
        from backend.app.radar.lakes import load_lakes
        bbox = load_lakes()[args.lake].bbox
    else:
        bbox = tuple(args.bbox)
        assert len(bbox) == 4, "give west south east north or --lake"
    g = make_grid(bbox)
    grid = {"crs": g.crs, "transform": list(g.transform)[:6], "width": g.width, "height": g.height, "resolution_m": g.res}
    out = config.DATA_DIR / "fm" / args.study_id
    (out / "scenes").mkdir(parents=True, exist_ok=True)
    study = {"study_id": args.study_id, "bbox": bbox, "grid": grid, "periods": {}}
    for name, (start, end) in (("earlier", args.earlier), ("later", args.later)):
        chosen = S.choose_scenes(bbox, grid, start, end, n=args.n)
        print(name, chosen, flush=True)
        study["periods"][name] = {"window": [str(start), str(end)], "scenes": chosen}
        items = {i["id"]: i for i in S.search_items(None, None, None, ids=[c["item_id"] for c in chosen])}
        for c in chosen:
            S.fetch_scene(items[c["item_id"]], grid, name, out / "scenes")
    (out / "study.json").write_text(json.dumps(study, indent=1), encoding="utf-8")
    print("wrote", out / "study.json")


if __name__ == "__main__":
    main()
