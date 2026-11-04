"""Ad-hoc catalogue probe: list raw hits for an AOI/window without processing.

Usage:
    python scripts/probe_catalog.py --study coringa_coastal --start 2020-01-01 \
        --end 2020-05-31 [--measure]

``--measure`` additionally reads the real SCL to report in-AOI valid coverage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml                                                       # noqa: E402

from backend.app import config                                    # noqa: E402
from backend.app.catalog.search import SearchRequest               # noqa: E402
from backend.app.catalog.stac_client import CatalogClient, CatalogUnavailable  # noqa: E402
from backend.app.http import HttpSession                          # noqa: E402
from backend.app.preprocess.aoi import aoi_from_bounds            # noqa: E402
from backend.app.preprocess.scoring import score_candidates       # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--max-cloud", type=float, default=60.0)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--measure", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    registry = yaml.safe_load(
        (config.STUDIES_DIR / "registry.yaml").read_text(encoding="utf-8")
    )
    study = next(s for s in registry["studies"] if s["study_id"] == args.study)
    b = study["aoi"]["bounds"]
    aoi = aoi_from_bounds(
        study_id=args.study, west=b["west"], south=b["south"],
        east=b["east"], north=b["north"],
        description="", source="",
    )
    print(f"AOI {args.study}: {aoi.area_km2():.3f} km2 bounds={aoi.bbox}")

    http = HttpSession(cache_dir=config.CACHE_DIR)
    client = CatalogClient(http)
    try:
        client.load_collection()
    except CatalogUnavailable as exc:
        print(f"CATALOG UNAVAILABLE: {exc}")
        return 1

    request = SearchRequest(
        aoi=aoi,
        start=dt.datetime.fromisoformat(args.start + "T00:00:00+00:00"),
        end=dt.datetime.fromisoformat(args.end + "T23:59:59+00:00"),
        max_cloud_cover=args.max_cloud,
        limit=args.limit,
        label=f"probe:{args.study}",
    )
    result = client.search(request)
    print(f"accepted={len(result.items)} rejected={len(result.rejected)} "
          f"matched={result.matched_count}")
    for candidate in sorted(result.items, key=lambda c: c.acquired):
        print(f"  {candidate.acquisition_iso}  {candidate.item_id}  "
              f"cloud={candidate.cloud_cover}")

    if args.measure:
        for score in score_candidates(result.items, aoi):
            print(f"  score {score.item_id}: valid={score.aoi_valid_fraction} "
                  f"inter={score.aoi_intersection_fraction:.3f} "
                  f"usable={score.usable} {score.notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
