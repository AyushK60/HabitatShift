"""AOI-relative scene scoring.

Global scene cloud percentage says little about a 3-5 km window: a scene that is
95 % cloud-free overall can be entirely covered inside the AOI.  Selection
therefore measures valid-data coverage *within the AOI* with the real SCL raster.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rasterio.enums import Resampling
from shapely.geometry import shape

from .. import config
from ..acquisition.cog import WindowRequest, read_window
from ..catalog.models import SceneCandidate
from ..preprocess import masks as mask_mod
from ..preprocess.aoi import AOI
from ..preprocess.grid import analysis_window

LOGGER = logging.getLogger(__name__)


@dataclass
class SceneScore:
    """Selection evidence for one candidate."""

    item_id: str
    acquired: str
    cloud_cover_percent: float | None
    aoi_intersection_fraction: float
    aoi_valid_fraction: float | None
    usable: bool
    notes: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Rank by in-AOI validity, with a mild global-cloud tiebreak."""
        base = self.aoi_valid_fraction or 0.0
        penalty = (self.cloud_cover_percent or 0.0) / 1000.0
        return base - penalty

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "acquired_utc": self.acquired,
            "cloud_cover_percent": self.cloud_cover_percent,
            "aoi_intersection_fraction": round(self.aoi_intersection_fraction, 6),
            "aoi_valid_fraction": None
            if self.aoi_valid_fraction is None
            else round(self.aoi_valid_fraction, 6),
            "usable": self.usable,
            "score": round(self.score, 6),
            "notes": self.notes,
        }


def aoi_intersection_fraction(candidate: SceneCandidate, aoi: AOI) -> float:
    """Fraction of the AOI covered by the scene footprint."""
    footprint = candidate.footprint
    if not footprint:
        return 0.0
    try:
        scene_geom = shape(footprint)
    except Exception:
        return 0.0
    if not scene_geom.is_valid:
        scene_geom = scene_geom.buffer(0)
    aoi_area = aoi.polygon.area
    if aoi_area <= 0:
        return 0.0
    return float(scene_geom.intersection(aoi.polygon).area / aoi_area)


def _measurement_cache_path(
    cache_dir: Path, candidate: SceneCandidate, aoi: AOI, resolution: float
) -> Path:
    """Name the memo file for one (item, AOI grid, resolution) measurement.

    The key includes the analysis-grid signature, so a different AOI or grid
    resolution can never reuse an unrelated valid fraction.
    """
    signature = ";".join(
        (
            candidate.item_id,
            candidate.asset(config.ASSET_SCL).href,
            aoi.study_id,
            f"{resolution:g}",
            analysis_window(aoi, resolution).signature(),
        )
    )
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:40]
    return cache_dir / f"{digest}.json"


def measure_aoi_valid_fraction(
    candidate: SceneCandidate,
    aoi: AOI,
    *,
    resolution: float = config.GRID_RESOLUTION,
    cache_dir: Path | None = None,
    offline: bool = False,
) -> tuple[float, dict[str, Any]]:
    """Read the real SCL over the AOI and return its valid fraction.

    When ``cache_dir`` is given the result is memoised for
    :data:`backend.app.config.CACHE_TTL` seconds, so re-running the pipeline
    does not re-download the same SCL window.  The memo stores the measured
    fraction together with the mask report, never a fabricated value.  In
    ``offline`` mode a stale-but-present memo is accepted and a missing memo is
    not read remotely.
    """
    cache_path: Path | None = None
    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = _measurement_cache_path(cache_dir, candidate, aoi, resolution)
        if cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if offline or age <= config.CACHE_TTL:
                try:
                    memo = json.loads(cache_path.read_text(encoding="utf-8"))
                    LOGGER.debug("valid-fraction cache hit %s", candidate.item_id)
                    return float(memo["valid_fraction"]), memo["report"]
                except (KeyError, ValueError, TypeError):     # pragma: no cover
                    LOGGER.warning("discarding unreadable cache %s", cache_path)

    if offline:
        raise RuntimeError(
            f"offline mode: no cached SCL measurement for {candidate.item_id}"
        )

    window = analysis_window(aoi, resolution)
    request = WindowRequest(
        dst_crs=window.crs,
        dst_transform=window.transform,
        height=window.height,
        width=window.width,
        resampling=Resampling.nearest,
        dtype="int32",
    )
    scl = read_window(candidate.asset(config.ASSET_SCL).href, request)
    _, report = mask_mod.build_valid_mask(scl)
    if cache_path is not None:
        cache_path.write_text(
            json.dumps(
                {"valid_fraction": report.valid_fraction, "report": report.to_dict()},
                indent=2,
            ),
            encoding="utf-8",
        )
    return report.valid_fraction, report.to_dict()


def _pre_rank(candidates: list[SceneCandidate], aoi: AOI) -> list[SceneCandidate]:
    """Order candidates for *measurement* using metadata only.

    Full-footprint coverage first, then the catalogue's global cloud figure.
    This ordering only decides which candidates get their SCL measured under a
    budget; the ranking that selects the scene still uses the measured in-AOI
    valid fraction, and every unmeasured candidate is recorded as such.
    """
    return sorted(
        candidates,
        key=lambda c: (
            -aoi_intersection_fraction(c, aoi),
            c.cloud_cover if c.cloud_cover is not None else 100.0,
            c.item_id,
        ),
    )


def score_candidates(
    candidates: list[SceneCandidate],
    aoi: AOI,
    *,
    min_valid_fraction: float = config.MIN_SCENE_VALID_FRACTION,
    measure: bool = True,
    max_measured: int | None = None,
    cache_dir: Path | None = None,
    offline: bool = False,
) -> list[SceneScore]:
    """Score every candidate, ordered best first.

    ``max_measured`` bounds the number of remote SCL reads per search (the
    expensive step); ``None`` measures every candidate.  Candidates outside the
    budget are still returned, unmeasured and explicitly marked unusable.
    """
    order = _pre_rank(candidates, aoi) if max_measured is not None else list(candidates)
    budget = len(order) if max_measured is None else max(int(max_measured), 0)
    measured_ids = {c.item_id for c in order[:budget]}

    scores: list[SceneScore] = []
    for candidate in order:
        intersection = aoi_intersection_fraction(candidate, aoi)
        notes: list[str] = []
        valid: float | None = None
        if intersection < 0.999:
            notes.append(f"AOI only {intersection:.3f} covered by scene footprint")
        if candidate.item_id not in measured_ids:
            notes.append(
                "in-AOI validity not measured: outside the measurement budget"
            )
        elif measure and intersection > 0.05:
            memo_available = (
                cache_dir is not None
                and _measurement_cache_path(
                    Path(cache_dir), candidate, aoi, config.GRID_RESOLUTION
                ).exists()
            )
            if offline and not memo_available:
                notes.append("offline: no cached in-AOI SCL measurement")
            else:
                try:
                    if cache_dir is None:
                        valid, _ = measure_aoi_valid_fraction(
                            candidate, aoi, offline=offline
                        )
                    else:
                        valid, _ = measure_aoi_valid_fraction(
                            candidate, aoi, cache_dir=cache_dir, offline=offline
                        )
                except Exception as exc:                      # pragma: no cover - net
                    notes.append(f"valid-fraction read failed: {exc}")
        usable = (
            intersection >= 0.999
            and valid is not None
            and valid >= min_valid_fraction
        )
        if valid is not None and valid < min_valid_fraction:
            notes.append(
                f"in-AOI valid fraction {valid:.3f} below {min_valid_fraction}"
            )
        scores.append(
            SceneScore(
                item_id=candidate.item_id,
                acquired=candidate.acquisition_iso,
                cloud_cover_percent=candidate.cloud_cover,
                aoi_intersection_fraction=intersection,
                aoi_valid_fraction=valid,
                usable=usable,
                notes=notes,
            )
        )
    scores.sort(key=lambda s: s.score, reverse=True)
    return scores
