"""Shared configuration for the HabitatShift M0 pipeline.

Every value here is either a physical constant of the Sentinel-2 L2A product
family (verified against live STAC item metadata before use) or an explicit,
documented operating parameter.  Nothing environment-specific is hardcoded
outside :data:`PROJECT_ROOT`.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PREVIEW_DIR = DATA_DIR / "previews"
MANIFEST_DIR = DATA_DIR / "manifests"
CACHE_DIR = DATA_DIR / "cache"
SCL_MEASUREMENT_CACHE_DIR = CACHE_DIR / "scl_valid"
OBSERVATION_CACHE_DIR = CACHE_DIR / "observations"
PROCESSED_M1_DIR = PROCESSED_DIR / "m1"
PREVIEW_M1_DIR = PREVIEW_DIR / "m1"

STUDIES_DIR = PROJECT_ROOT / "studies"
DOCS_DIR = PROJECT_ROOT / "docs"

for _p in (
    RAW_DIR,
    PROCESSED_DIR,
    PREVIEW_DIR,
    MANIFEST_DIR,
    CACHE_DIR,
    SCL_MEASUREMENT_CACHE_DIR,
    OBSERVATION_CACHE_DIR,
    PROCESSED_M1_DIR,
    PREVIEW_M1_DIR,
):
    _p.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# STAC catalogue
# --------------------------------------------------------------------------- #
#: Primary discovery endpoint mandated by the roadmap (Element 84 Earth Search).
CATALOG_URL = "https://earth-search.aws.element84.com/v1"

#: Verified Sentinel-2 Level-2A collection on that endpoint.
#: Fallbacks are only used when the primary endpoint is proven unavailable and
#: the switch is recorded in the study document.
COLLECTION = "sentinel-2-l2a"
FALLBACK_COLLECTIONS = ("sentinel-2-c1-l2a",)

#: Asset keys verified against the live collection ``item_assets`` definition
#: and re-checked on every selected item.  Never assume asset filenames.
ASSET_BLUE = "blue"
ASSET_GREEN = "green"
ASSET_RED = "red"
ASSET_NIR = "nir"
ASSET_SWIR1 = "swir16"          # B11, native 20 m
ASSET_SWIR2 = "swir22"          # B12, native 20 m
ASSET_SCL = "scl"

#: Required assets for the M0 pipeline (NDVI + true colour + quality mask).
REQUIRED_ASSETS = (ASSET_BLUE, ASSET_GREEN, ASSET_RED, ASSET_NIR, ASSET_SCL)

#: Every reflectance asset the M1 engine may read.  Only the bands an index
#: actually needs are fetched; nothing reads all six for a single-index run.
SPECTRAL_ASSETS = (
    ASSET_BLUE,
    ASSET_GREEN,
    ASSET_RED,
    ASSET_NIR,
    ASSET_SWIR1,
    ASSET_SWIR2,
)

#: Native ground sample distances in metres, taken from the collection
#: ``raster:bands[].spatial_resolution`` metadata.  Used to validate that the
#: catalog still describes the grid we think it does.
EXPECTED_GSD = {
    ASSET_BLUE: 10.0,
    ASSET_GREEN: 10.0,
    ASSET_RED: 10.0,
    ASSET_NIR: 10.0,
    ASSET_SWIR1: 20.0,
    ASSET_SWIR2: 20.0,
    ASSET_SCL: 20.0,
}

#: Digital-number to surface-reflectance transform for Sentinel-2 L2A.
#: ``reflectance = DN * SCALE + OFFSET``.
#:
#: Baseline 04.00 (25 Jan 2022) introduced ``BOA_ADD_OFFSET = -1000``, i.e. an
#: offset of -0.1; earlier products carry no offset.  Earth Search baked that
#: offset into some COGs and records this with
#: ``earthsearch:boa_offset_applied``; :mod:`backend.app.acquisition.assets`
#: resolves the offset actually to apply per item and never double-corrects.
EXPECTED_SCALE = 0.0001
BOA_ADD_OFFSET = -0.1
NO_OFFSET = 0.0

#: Baseline at which the BOA offset was introduced.
BASELINE_OFFSET_THRESHOLD = 4.0

EXPECTED_NODATA = 0


# --------------------------------------------------------------------------- #
# SCL (Scene Classification Layer) policy
# --------------------------------------------------------------------------- #
#: Class labels retained as *valid* observations for the coastal/vegetation
#: profile.  Note the two policies differ: class 1 is listed as valid-looking
#: in SCL but always removed here because its radiometry is unusable.
SCL_VALID_CLASSES = (
    2,   # dark area pixels
    4,   # vegetation
    5,   # not vegetated
    6,   # water
    7,   # unclassified
    11,  # snow / ice (absent at Coringa, a target class in the Himalaya)
)

#: Classes always removed for the coastal profile.
SCL_ALWAYS_INVALID = (
    0,   # no data
    1,   # saturated or defective  (unusable radiometry)
    3,   # cloud shadow
    8,   # cloud medium probability
    9,   # cloud high probability
    10,  # thin cirrus
)

#: Human-readable semantics, written verbatim into provenance manifests so a
#: later reviewer can audit the masking policy without reading code.
SCL_SEMANTICS = {
    0: "no_data",
    1: "saturated_or_defective",
    2: "dark_area_pixels",
    3: "cloud_shadow",
    4: "vegetation",
    5: "not_vegetated",
    6: "water",
    7: "unclassified",
    8: "cloud_medium_probability",
    9: "cloud_high_probability",
    10: "thin_cirrus",
    11: "snow_ice",
}

# --------------------------------------------------------------------------- #
# HTTP behaviour
# --------------------------------------------------------------------------- #
HTTP_TIMEOUT = 30
HTTP_CONNECT_TIMEOUT = 10
HTTP_MAX_RETRIES = 4
HTTP_BACKOFF_BASE = 1.5
HTTP_BACKOFF_MAX = 20.0
HTTP_MIN_INTERVAL = 0.25          # seconds between catalogue calls (rate limit)
USER_AGENT = "HabitatShift/0.1 (M0 feasibility; reproducible research client)"
MAX_ITEMS_PER_SEARCH = 200        # bounded pagination


# --------------------------------------------------------------------------- #
# Provenance / attribution
# --------------------------------------------------------------------------- #
ATTRIBUTION = (
    "Contains modified Copernicus Sentinel data, processed by ESA; "
    "L2A products distributed by the Element 84 Earth Search STAC catalogue "
    "(AWS Open Data)."
)
PROVIDER_NAME = "Element 84 Earth Search (AWS Open Data)"
DATA_LICENSE = (
    "Copernicus Sentinel data: free, open and unrestricted use with attribution "
    "(ESA Copernicus data policy). Catalogue: Element 84 Earth Search, AWS Open Data."
)

#: Pipeline identity recorded in every manifest.
PIPELINE_VERSION = "0.1.0-m0"
PROCESSING_PROFILE = "coastal_ndvi_m0"


def software_versions() -> dict[str, str]:
    """Return runtime versions for provenance records."""
    versions = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    for module_name in ("numpy", "rasterio", "pyproj", "shapely", "pystac_client"):
        try:
            module = __import__(module_name)
            versions[module_name] = getattr(module, "__version__", "unknown")
        except ImportError:                                  # pragma: no cover
            versions[module_name] = "not-installed"
    try:                                                     # pragma: no cover
        import rasterio
        versions["gdal"] = rasterio.__gdal_version__
    except Exception:                                        # pragma: no cover
        pass
    return versions


def relative(path: Path) -> str:
    """Render a path relative to the project root for portable manifests."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:                                       # pragma: no cover
        return str(path)


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

#: TTL for cached catalogue responses, in seconds (7 days).
CACHE_TTL = 7 * 24 * 3600

# --------------------------------------------------------------------------- #
# M1 science engine
# --------------------------------------------------------------------------- #
#: Pipeline identity for the M1 engine.  M0 keeps its own version string so the
#: two manifests never claim to be the same processing run.
M1_PIPELINE_VERSION = "0.2.0-m1"
M1_PROCESSING_PROFILE = "spectral_change_m1"

#: Candidate change thresholds in index units, and the primary threshold used
#: for the headline area table.  These are *candidate* thresholds, never
#: ecological verdicts.
M1_CHANGE_THRESHOLDS = (0.10, 0.15, 0.20)
M1_PRIMARY_THRESHOLD = 0.15

#: Difference-map previews saturate at +/- this many index units.
M1_CHANGE_RAMP_SCALE = 0.30

#: Default indices computed by an M1 run.
M1_INDICES = ("ndvi", "ndwi", "mndwi")

#: Default number of observations searched per period (not all need be used).
M1_MAX_OBSERVATIONS = 3
M1_MIN_OBSERVATIONS = 1

# --------------------------------------------------------------------------- #
# Analysis grid
# --------------------------------------------------------------------------- #
#: Working grid resolution in metres.  10 m is the native Sentinel-2 L2A
#: resolution of every band used for NDVI and true colour, so no upsample of
#: physical detail occurs.  The 20 m SCL is nearest-neighbour downsampled.
GRID_RESOLUTION = 10.0

#: Hard ceiling on processed window size (pixels), protecting RAM and credit.
MAX_WINDOW_PIXELS = 4_000_000

#: Valid-coverage thresholds for the two-date comparison to be considered
#: usable at all.  Below ``MIN_COMPARABLE_VALID_FRACTION`` the pair is flagged
#: unsuitable instead of producing a forced change estimate.
MIN_SCENE_VALID_FRACTION = 0.60
MIN_COMPARABLE_VALID_FRACTION = 0.50

# --------------------------------------------------------------------------- #
# Scene-selection budget
# --------------------------------------------------------------------------- #
#: Maximum number of candidate SCL windows actually downloaded per search.
#: Candidates are pre-ranked on metadata alone (footprint coverage, then global
#: cloud) and the best ``MAX_MEASURED_CANDIDATES`` get a real in-AOI
#: measurement.  Everything beyond the budget is returned *unmeasured* and
#: explicitly unusable, so a large search stays cheap without pretending the
#: unmeasured scenes were assessed.
MAX_MEASURED_CANDIDATES = 24
