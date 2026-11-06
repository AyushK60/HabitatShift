"""Run one M1 study from its YAML experiment configuration.

Usage (from the repository root, inside the project venv):

    python scripts/run_study.py --config studies/experiments/coringa_m1.yaml
    python scripts/run_study.py --config studies/experiments/coringa_m1.yaml --offline
    python scripts/run_study.py --config studies/experiments/coringa_m1.yaml --verbose

The script writes georeferenced rasters, previews, summary JSON/CSV and a
validated reproducibility manifest.  It exits 0 when every independent
verification passes, 2 when a check fails, and 1 when the run itself cannot be
completed honestly.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import config                                   # noqa: E402
from backend.app.pipeline.config import ConfigError, load_study_config  # noqa: E402
from backend.app.pipeline.engine import EngineError, M1Engine    # noqa: E402

LOGGER = logging.getLogger("run_study")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a configured M1 study")
    parser.add_argument(
        "--config",
        type=Path,
        default=config.STUDIES_DIR / "experiments" / "coringa_m1.yaml",
        help="experiment YAML file",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use only cached catalogue responses and cached observations",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("rasterio").setLevel(logging.WARNING)
    logging.getLogger("rasterio.session").setLevel(logging.WARNING)

    try:
        cfg = load_study_config(args.config)
        engine = M1Engine(cfg, offline=args.offline)
        summary = engine.run()
    except (ConfigError, EngineError) as exc:
        LOGGER.error("M1 run failed: %s", exc)
        return 1
    except Exception as exc:                                  # pragma: no cover - net
        LOGGER.exception("M1 run failed unexpectedly: %s", exc)
        return 1

    verification = summary.get("verification", {})
    LOGGER.info(
        "verification: %s (%d checks%s)",
        "PASS" if verification.get("all_passed") else "FAIL",
        verification.get("check_count", 0),
        ""
        if verification.get("all_passed")
        else "; failed: " + ", ".join(verification.get("failed_checks", [])),
    )
    print(
        json.dumps(
            {
                "experiment_id": summary["experiment_id"],
                "study_id": summary["study"]["study_id"],
                "grid": summary["grid"],
                "periods": [
                    {
                        "period_id": period["period_id"],
                        "observation_count": period["observation_count"],
                        "observation_dates": period["observation_dates"],
                        "item_ids": period["item_ids"],
                        "valid_fraction": period["valid_fraction"],
                        "indices": {
                            key: block["stats"]["mean"]
                            for key, block in period["indices"].items()
                        },
                    }
                    for period in summary["periods"]
                ],
                "change": {
                    key: {
                        "common_valid_fraction_of_aoi": block[
                            "common_valid_fraction_of_aoi"
                        ],
                        "primary_threshold": block["primary_threshold"],
                        "decrease_area_ha": block["primary"]["decrease_area_ha"],
                        "increase_area_ha": block["primary"]["increase_area_ha"],
                        "delta_mean": block["delta_stats"]["mean"],
                    }
                    for key, block in summary["change"].items()
                },
                "verification": verification,
            },
            indent=2,
        )
    )
    return 0 if verification.get("all_passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
