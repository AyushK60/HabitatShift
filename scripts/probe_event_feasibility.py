"""M0 feasibility probe: what imagery actually exists for the Nepal studies?

This script answers the M0 data-reality questions for the studies that are *not*
processed yet (roadmap items M0.11 and M0.13):

  * D1 - Purepu supraglacial-lake drainage, 8 July 2025
  * D2 - Langtang Lirung rock-ice collapse, 26 August 2026
  * E  - Kathmandu Valley urban pilot, matched 2020 / 2025 windows

For every target window it records the real STAC item IDs and acquisition
dates, the catalogue's cloud figure, the footprint coverage of the AOI and -
for a bounded subset - the *measured* in-AOI SCL valid fraction.  Nothing is
inferred: a window with no usable observation is reported as such, and an AOI
that is mostly cloud inside is never described as observed.

Usage (from the repository root, inside the project venv):

    python scripts/probe_event_feasibility.py
    python scripts/probe_event_feasibility.py --studies himalaya_purepu_2025
    python scripts/probe_event_feasibility.py --max-measure 4 --force-refresh

Output: ``data/cache/event_feasibility.json`` (git-ignored cache) plus a plain
text table on stdout.  The published document derived from it is
``docs/M0_HIMALAYAN_DATA_FEASIBILITY.md``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import config                                    # noqa: E402
from backend.app.catalog.search import SearchRequest              # noqa: E402
from backend.app.catalog.stac_client import CatalogClient         # noqa: E402
from backend.app.http import HttpSession                          # noqa: E402
from backend.app.preprocess.aoi import AOI, aoi_from_bounds       # noqa: E402
from backend.app.preprocess.scoring import score_candidates       # noqa: E402

LOGGER = logging.getLogger("probe_event_feasibility")

DEFAULT_STUDIES = (
    "himalaya_purepu_2025",
    "himalaya_langtang_2026",
    "kathmandu_urban",
)
DEFAULT_OUT = config.CACHE_DIR / "event_feasibility.json"


def load_registry(path: Path) -> dict[str, dict]:
    registry = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {study["study_id"]: study for study in registry["studies"]}


def make_aoi(study: dict) -> AOI:
    bounds = study["aoi"]["bounds"]
    return aoi_from_bounds(
        study_id=study["study_id"],
        west=bounds["west"],
        south=bounds["south"],
        east=bounds["east"],
        north=bounds["north"],
        description=study["aoi"].get("kind", ""),
        source=study["aoi"].get("boundary_source", ""),
    )


def probe_window(
    client: CatalogClient,
    study: dict,
    aoi: AOI,
    period_key: str,
    window: dict,
    *,
    max_measure: int,
) -> dict:
    """Search one window and record the real candidates it returns."""
    start = dt.datetime.fromisoformat(window["start"] + "T00:00:00+00:00")
    end = dt.datetime.fromisoformat(window["end"] + "T23:59:59+00:00")
    request = SearchRequest(
        aoi=aoi,
        start=start,
        end=end,
        max_cloud_cover=100.0,      # feasibility: see everything, then judge
        limit=100,
        label=f"{study['study_id']}:{period_key}:{window['start']}..{window['end']}",
    )
    result = client.search(request)
    scores = score_candidates(
        result.items,
        aoi,
        max_measured=max_measure,
        cache_dir=config.SCL_MEASUREMENT_CACHE_DIR,
    )
    usable = [s for s in scores if s.usable]
    measured = sum(1 for s in scores if s.aoi_valid_fraction is not None)
    LOGGER.info(
        "%s/%s: %d accepted, %d usable in-AOI, %d measured",
        study["study_id"], period_key, len(result.items), len(usable), measured,
    )
    return {
        "period_key": period_key,
        "labelled_window": window,
        "window_utc": {
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
        },
        "search": result.to_dict(),
        "selection_policy": {
            "measurement_budget": max_measure,
            "measured_candidate_count": measured,
            "decision_metric": "measured in-AOI SCL valid fraction",
            "usable_threshold": config.MIN_SCENE_VALID_FRACTION,
            "unmeasured_candidates_are_unusable": True,
        },
        "usable_candidate_count": len(usable),
        "best_valid_fraction": (
            max((s.aoi_valid_fraction or 0.0) for s in scores) if scores else None
        ),
        "candidates": [s.to_dict() for s in scores],
    }


def study_verdict(periods: dict[str, dict]) -> dict:
    """State honestly what the catalogue can and cannot support."""
    usable_periods = {
        key: block["usable_candidate_count"] > 0 for key, block in periods.items()
    }
    best = {key: block["best_valid_fraction"] for key, block in periods.items()}
    any_usable = any(usable_periods.values())
    return {
        "usable_periods": usable_periods,
        "best_in_aoi_valid_fraction": best,
        "any_usable_observation": any_usable,
        "suitable_for_pairwise_change": (
            sum(1 for flag in usable_periods.values() if flag) >= 2
        ),
        "statement": (
            "at least one window contains an in-AOI usable observation"
            if any_usable
            else "no window contains an observation passing the in-AOI "
                 "validity threshold at this AOI; treat as blocked, not faked"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe Nepal study feasibility")
    parser.add_argument(
        "--registry", type=Path, default=config.STUDIES_DIR / "registry.yaml"
    )
    parser.add_argument(
        "--studies", default=",".join(DEFAULT_STUDIES),
        help="comma-separated study_id values",
    )
    parser.add_argument("--max-measure", type=int, default=6)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="ignore cached catalogue responses and valid-fraction memos",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    if args.force_refresh:
        for path in config.CACHE_DIR.glob("*.json"):
            path.unlink()
        for path in config.SCL_MEASUREMENT_CACHE_DIR.glob("*.json"):
            path.unlink()

    registry = load_registry(args.registry)
    http = HttpSession(cache_dir=config.CACHE_DIR)
    client = CatalogClient(http)
    meta = client.load_collection()
    LOGGER.info("collection %s verified on %s", client.collection, client.catalog_url)

    payload: dict = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "catalog": {
            "endpoint": client.catalog_url,
            "collection": client.collection,
            "collection_license": meta.get("license"),
        },
        "thresholds": {
            "min_scene_valid_fraction": config.MIN_SCENE_VALID_FRACTION,
            "min_comparable_valid_fraction": config.MIN_COMPARABLE_VALID_FRACTION,
            "max_cloud_cover_filter": 100.0,
            "measurement_budget": args.max_measure,
        },
        "attribution": config.ATTRIBUTION,
        "studies": {},
    }

    for study_id in [s.strip() for s in args.studies.split(",") if s.strip()]:
        study = registry.get(study_id)
        if study is None:
            raise SystemExit(f"study_id {study_id!r} not present in the registry")
        aoi = make_aoi(study)
        periods = {
            key: probe_window(
                client, study, aoi, key, window, max_measure=args.max_measure
            )
            for key, window in study["target_periods"].items()
        }
        block = {
            "study_id": study_id,
            "portfolio_id": study.get("id"),
            "title": study.get("title"),
            "study_type": study.get("study_type"),
            "status_in_registry": study.get("status"),
            "event_date": study.get("event_date"),
            "event_mechanism": " ".join(
                str(study.get("event_mechanism", "")).split()
            ),
            "question": " ".join(str(study.get("question", "")).split()),
            "aoi": {
                "bounds_4326": list(aoi.bounds_4326),
                "area_km2": round(aoi.area_km2(), 6),
                "kind": study["aoi"].get("kind"),
                "boundary_source": " ".join(
                    str(study["aoi"].get("boundary_source", "")).split()
                ),
            },
            "limitations": study.get("limitations", []),
            "periods": periods,
        }
        block["verdict"] = study_verdict(periods)
        payload["studies"][study_id] = block

        print(f"\n=== {study_id} ({block['portfolio_id']}) {block['title']}")
        for key, period in periods.items():
            best = period["best_valid_fraction"]
            best_text = "n/a" if best is None else f"{best:.3f}"
            print(
                f"  {key:9s} {period['window_utc']['start_utc'][:10]}.."
                f"{period['window_utc']['end_utc'][:10]}  "
                f"accepted={period['search']['accepted_items']:3d}  "
                f"usable={period['usable_candidate_count']:3d}  "
                f"best_valid={best_text}"
            )
        print(f"  verdict: {block['verdict']['statement']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload["run_stats"] = {
        "catalogue_requests": http.request_count,
        "catalogue_bytes_downloaded": http.bytes_downloaded,
        "note": (
            "counts cover this invocation only; catalogue responses and SCL "
            "valid-fraction memos are reused from data/cache across runs"
        ),
        "measurement_budget": args.max_measure,
    }
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nfeasibility record written to {config.relative(args.out)}")
    print(
        f"catalogue requests: {http.request_count}, "
        f"bytes downloaded: {http.bytes_downloaded}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
