"""AOI-relative scene scoring.

Global scene cloud percentage says little about a 3-5 km window: a scene that is
95 % cloud-free overall can be entirely covered inside the AOI.  Selection
therefore measures valid-data coverage *within the AOI* with the real SCL raster.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rasterio.enums import Resampling
from shapely.geometry import shape

from .. import config
from ..acquisition.cog import WindowRequest, read_window
from ..catalog.models import SceneCandidate
from ..preprocess import masks as mask_mod
from ..preprocess.aoi import AOI
from ..preprocess.grid import analysis_window


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


def measure_aoi_valid_fraction(
    candidate: SceneCandidate,
    aoi: AOI,
    *,
    resolution: float = config.GRID_RESOLUTION,
) -> tuple[float, dict[str, Any]]:
    """Read the real SCL over the AOI and return its valid fraction."""
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
    return report.valid_fraction, report.to_dict()


def score_candidates(
    candidates: list[SceneCandidate],
    aoi: AOI,
    *,
    min_valid_fraction: float = config.MIN_SCENE_VALID_FRACTION,
    measure: bool = True,
) -> list[SceneScore]:
    """Score every candidate, ordered best first."""
    scores: list[SceneScore] = []
    for candidate in candidates:
        intersection = aoi_intersection_fraction(candidate, aoi)
        notes: list[str] = []
        valid: float | None = None
        if intersection < 0.999:
            notes.append(f"AOI only {intersection:.3f} covered by scene footprint")
        if measure and intersection > 0.05:
            try:
                valid, _ = measure_aoi_valid_fraction(candidate, aoi)
            except Exception as exc:                          # pragma: no cover - net
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
