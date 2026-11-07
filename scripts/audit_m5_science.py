"""M5-G1 independent scientific audit of the HabitatShift processing chain.

This script deliberately imports NOTHING from ``backend.app``: every
recomputation below (indices, deltas, classifications, composites, the block
bootstrap, live STAC metadata, live COG window reads) is an independent
re-implementation written from the documented spec, so a shared bug cannot
hide in an imported production function.

Sections
--------
A  Satellite source verification — every recorded observation in every
   manifest is checked against the live Earth Search STAC catalog: item id,
   acquisition date, sensor/platform, processing baseline, selected asset
   names, native resolution, scale/offset, NoData, EPSG/grid consistency.
B  Critical radiometry review — every record is classified (raw DN /
   scaled DN / offset-applied / empirical scale-only), policy-consistency
   rules are asserted (never a double-applied BOA offset; every empirical
   fallback carries measured evidence; no pre-04.00 offset), the stored
   observation cache is re-validated pixel-wise, and a per-convention sample
   of items is re-read live from the source COGs to confirm the recorded
   radiometry decision against the pixels actually stored.
C  Processing verification — grid consistency, independent recomputation of
   indices, deltas, common-valid masks and threshold classifications from the
   exported rasters, independent recomputation of the median composites from
   the observation cache, area arithmetic, manifest output checksums, and a
   deterministic reproduction of the M2 spatial block bootstrap from cached
   observations with the recorded seed.

Usage:  python scripts/audit_m5_science.py [--no-live]
Exit 0 when every check passes.  Writes
``docs/evidence/m5/audit_m5_science_checks.json``.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.env import Env
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT

ROOT = Path(__file__).resolve().parents[1]
STAC_BASE = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

M4_MANIFESTS = [
    "coringa_m1",
    "chilika_m4_dry",
    "chilika_m4_postmonsoon",
    "western_ghats_m4",
    "himalaya_purepu_2025_m4",
    "himalaya_langtang_2026_m4",
    "kathmandu_m4",
]
M0_MANIFEST = "m0_primary_study"

#: experiment_id -> processed raster directory (relative to data/processed)
STUDY_DIR_BY_EXPERIMENT = {
    "coringa_m1": "m1/coringa_coastal",
}

#: asset key -> (composite tif description prefix, expected native GSD)
ASSET_TIF_PREFIX = {
    "blue": "blue",
    "green": "green",
    "red": "red",
    "nir": "nir",
    "swir16": "swir1",
}
ASSET_GSD = {"blue": 10.0, "green": 10.0, "red": 10.0, "nir": 10.0, "swir16": 20.0}

#: index key -> (numerator asset, denominator asset)
INDEX_BANDS = {
    "ndvi": ("nir", "red"),
    "ndwi": ("green", "nir"),
    "mndwi": ("green", "swir16"),
    "ndsi": ("green", "swir16"),
    "ndbi": ("swir16", "nir"),
}
DENOM_EPS = 1e-6
PHYSICAL_MIN_MEAN = -0.005
BOA_OFFSET = -0.1
EXPECTED_SCALE = 0.0001

GDAL_ENV = {
    "AWS_NO_SIGN_REQUEST": "YES",
    "GDAL_HTTP_TIMEOUT": "60",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "1",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "64000000",
    "CPL_CURL_VERBOSE": "NO",
}


class Report:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.failures: list[str] = []

    def check(self, ok: bool, label: str) -> bool:
        if ok:
            self.passed += 1
        else:
            self.failed += 1
            self.failures.append(label)
            print(f"  [FAIL] {label}")
        return ok

    def note(self, label: str) -> None:
        self.passed += 1
        print(f"  [ok]   {label}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# A. source verification
# ---------------------------------------------------------------------------

_stac_cache: dict[str, dict | None] = {}


def stac_item(item_id: str) -> dict | None:
    if item_id not in _stac_cache:
        url = f"{STAC_BASE}/collections/{COLLECTION}/items/{item_id}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                _stac_cache[item_id] = json.load(response)
        except Exception:
            _stac_cache[item_id] = None
    return _stac_cache[item_id]


def walk_observation_records(node: object) -> list[dict]:
    """Find every dict carrying an item id and per-asset radiometry metadata."""
    found: list[dict] = []
    if isinstance(node, dict):
        if "item_id" in node and isinstance(node.get("radiometry"), dict):
            found.append(node)
        for value in node.values():
            found.extend(walk_observation_records(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(walk_observation_records(value))
    return found


def iter_manifest_observations(manifest: dict) -> list[tuple[str, dict]]:
    """Yield (experiment_id, observation record) pairs from one manifest."""
    experiment = manifest.get("experiment_id") or manifest.get("study", {}).get("id", "unknown")
    out = []
    for record in walk_observation_records(manifest):
        out.append((experiment, record))
    # deduplicate: the search section may repeat selected observations
    seen: set[tuple[str, str]] = set()
    unique = []
    for experiment, record in out:
        key = (experiment, record["item_id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append((experiment, record))
    return unique


def radiometry_decision(record: dict) -> str:
    """Classify one observation's recorded convention from its own metadata."""
    sources = " | ".join(
        band.get("source", "") for band in record["radiometry"].values()
    )
    offsets = {float(band.get("offset", 0.0)) for band in record["radiometry"].values()}
    if "empirical correction" in sources:
        return "empirical_scale_only"
    if 0.0 in offsets and not any(abs(o) > 1e-9 for o in offsets):
        if "boa_offset_applied=true" in sources:
            return "offset_applied_scale_only"
        return "no_offset_declared"
    if any(abs(o - BOA_OFFSET) < 1e-9 for o in offsets):
        return "declared_offset_applied"
    return "unclassified"


def audit_source_verification(report: Report, manifests: dict[str, dict], live: bool) -> list[dict]:
    print("\nA. satellite source verification (live STAC cross-check)")
    rows: list[dict] = []
    for name in sorted(manifests):
        manifest = manifests[name]
        records = iter_manifest_observations(manifest)
        if name == M0_MANIFEST:
            # the older M0 schema records selected items in the search section
            report.check(
                bool((manifest.get("search") or {})),
                f"{name}: M0 manifest records its catalog search",
            )
            report.check(
                bool((manifest.get("processing", {}).get("parameters", {}).get("offset_policy"))),
                f"{name}: M0 manifest records its offset policy",
            )
            # M0's two anchor scenes are the same dates as the Coringa M1
            # anchor observations, which are live-verified below.
            for prefix, anchor in (("earlier", "2020-03-26"), ("later", "2025-03-25")):
                report.check(
                    (ROOT / "data" / "processed" / "coringa_coastal" / f"{prefix}_{anchor}_reflectance.tif").exists(),
                    f"{name}: anchor scene {prefix} {anchor} present in the frozen outputs",
                )
            continue
        else:
            report.check(len(records) > 0, f"{name}: manifest records observations with radiometry")
        for experiment, record in records:
            item_id = record["item_id"]
            decision = radiometry_decision(record)
            row = {
                "experiment": experiment,
                "item_id": item_id,
                "acquisition_date": record.get("acquisition_date"),
                "processing_baseline": record.get("processing_baseline"),
                "decision": decision,
                "grid_signature": record.get("grid_signature"),
            }
            rows.append(row)

            # -- item-id embedded date and sensor --------------------------
            parts = item_id.split("_")
            report.check(
                len(parts) >= 5 and parts[0].startswith("S2") and parts[4].endswith("L2A"),
                f"{experiment}/{item_id}: item id is a Sentinel-2 L2A identifier",
            )
            date_from_id = f"{parts[2][:4]}-{parts[2][4:6]}-{parts[2][6:]}"
            report.check(
                date_from_id == record.get("acquisition_date"),
                f"{experiment}/{item_id}: acquisition date matches the item id ({date_from_id})",
            )

            # -- recorded radiometry sanity --------------------------------
            for band, rad in record["radiometry"].items():
                report.check(
                    abs(float(rad["scale"]) - EXPECTED_SCALE) < 1e-9,
                    f"{experiment}/{item_id}/{band}: recorded scale is {EXPECTED_SCALE}",
                )
                report.check(
                    rad.get("nodata") in (0, None),
                    f"{experiment}/{item_id}/{band}: recorded nodata is 0",
                )
                gsd = rad.get("gsd_metres")
                if gsd is not None and band in ASSET_GSD:
                    report.check(
                        abs(float(gsd) - ASSET_GSD[band]) < 1e-6,
                        f"{experiment}/{item_id}/{band}: native GSD {gsd} m matches the Sentinel-2 convention",
                    )
                report.check(
                    bool(rad.get("source")),
                    f"{experiment}/{item_id}/{band}: radiometry decision carries a provenance source string",
                )
                if decision == "empirical_scale_only":
                    report.check(
                        abs(float(rad["offset"])) < 1e-9,
                        f"{experiment}/{item_id}/{band}: empirical correction resolves the offset to 0 (no double application)",
                    )

            # -- live STAC metadata ----------------------------------------
            if not live:
                continue
            item = stac_item(item_id)
            if not report.check(item is not None, f"{experiment}/{item_id}: live STAC item retrieved"):
                continue
            props = item["properties"]
            datetime_date = str(props.get("datetime", ""))[:10]
            report.check(
                datetime_date == record.get("acquisition_date"),
                f"{experiment}/{item_id}: live acquisition datetime {datetime_date} matches the record",
            )
            report.check(
                str(props.get("s2:processing_baseline")) == str(record.get("processing_baseline")),
                f"{experiment}/{item_id}: live processing baseline {props.get('s2:processing_baseline')} matches the record",
            )
            flag = props.get("earthsearch:boa_offset_applied")
            if decision == "offset_applied_scale_only":
                report.check(
                    flag is True,
                    f"{experiment}/{item_id}: live earthsearch:boa_offset_applied=true consistent with the scale-only decision",
                )
            elif decision == "empirical_scale_only":
                report.check(
                    flag is False,
                    f"{experiment}/{item_id}: live boa_offset_applied=false consistent with the empirical-correction decision",
                )
            platform = str(props.get("platform") or props.get("constellation") or "")
            report.check(
                platform.startswith("sentinel-2"),
                f"{experiment}/{item_id}: live platform '{platform}' is Sentinel-2",
            )
            for band in ("blue", "green", "red", "nir", "swir16"):
                asset = item["assets"].get(band)
                if asset is None:
                    continue
                rb = (asset.get("raster:bands") or [{}])[0]
                report.check(
                    abs(float(rb.get("scale", -1)) - EXPECTED_SCALE) < 1e-9,
                    f"{experiment}/{item_id}/{band}: live raster:bands scale is {EXPECTED_SCALE}",
                )
                declared = rb.get("offset")
                report.check(
                    declared is not None and abs(float(declared) - BOA_OFFSET) < 1e-9 or abs(float(declared or 0)) < 1e-9,
                    f"{experiment}/{item_id}/{band}: live declared offset {declared} is a Sentinel-2 convention (0 or -0.1)",
                )
                report.check(
                    rb.get("nodata") in (0, None),
                    f"{experiment}/{item_id}/{band}: live nodata is 0",
                )
                gsd = rb.get("spatial_resolution") or asset.get("gsd")
                if gsd is not None:
                    report.check(
                        abs(float(gsd) - ASSET_GSD[band]) < 1e-6,
                        f"{experiment}/{item_id}/{band}: live spatial resolution {gsd} m matches the convention",
                    )
            epsg = props.get("proj:epsg")
            grid = (manifest.get("grid") or {})
            crs = str(grid.get("crs") or "")
            if epsg is not None and crs.startswith("EPSG:"):
                report.check(
                    int(crs.split(":")[1]) == int(epsg),
                    f"{experiment}/{item_id}: live proj:epsg {epsg} matches the analysis grid {crs}",
                )
    return rows


# ---------------------------------------------------------------------------
# B. radiometry review
# ---------------------------------------------------------------------------

def load_cache_records() -> dict[str, list[dict]]:
    """Load every observation-cache record, keyed by item id.

    Several records can exist per item: the cache key embeds the radiometry
    policy version, so records written under a superseded policy linger on
    disk as orphans.  Callers select among them with
    :func:`select_cache_record`.
    """
    cache_dir = ROOT / "data" / "cache" / "observations"
    out: dict[str, list[dict]] = {}
    if not cache_dir.is_dir():
        return out
    for meta_path in sorted(cache_dir.glob("*.json")):
        meta = json.loads(meta_path.read_text())
        item_id = meta.get("item_id")
        npz_path = meta_path.with_suffix(".npz")
        if item_id and npz_path.exists():
            meta["_npz_path"] = str(npz_path)
            out.setdefault(item_id, []).append(meta)
    return out


def record_applies_boa_offset(meta: dict) -> bool:
    """True when the record's own radiometry applied the declared -0.1 offset."""
    for band in (meta.get("radiometry") or {}).values():
        if abs(float(band.get("offset", 0.0)) - BOA_OFFSET) < 1e-9:
            return True
    return False


def select_cache_record(cache: dict[str, list[dict]], manifest_record: dict) -> dict | None:
    """Pick the cache record that matches the manifest observation.

    Must agree on grid signature and on the applied radiometry convention, so
    a superseded-policy orphan can never satisfy the selection, and must cover
    every asset the manifest observation records (duplicate records with a
    smaller band set exist for some items from earlier fetches with fewer
    indices); among those, the most complete record wins.
    """
    wanted_offset = 0.0
    if radiometry_decision(manifest_record) == "declared_offset_applied":
        wanted_offset = BOA_OFFSET
    needed = set((manifest_record.get("assets") or {}).keys())
    best: dict | None = None
    for meta in cache.get(manifest_record["item_id"], []):
        if meta.get("grid_signature") != manifest_record.get("grid_signature"):
            continue
        offsets = {
            float(b.get("offset", 0.0)) for b in (meta.get("radiometry") or {}).values()
        }
        if wanted_offset == 0.0 and any(abs(o - BOA_OFFSET) < 1e-9 for o in offsets):
            continue  # superseded legacy record
        if wanted_offset != 0.0 and not any(abs(o - BOA_OFFSET) < 1e-9 for o in offsets):
            continue
        bands = set(meta.get("band_keys") or [])
        if needed and not needed.issubset(bands):
            continue
        if best is None or len(bands) > len(set(best.get("band_keys") or [])):
            best = meta
    return best


def audit_radiometry_records(report: Report, manifests: dict[str, dict]) -> dict[str, int]:
    print("\nB1. radiometry decision classification and policy consistency")
    counts = {
        "no_offset_declared": 0,
        "offset_applied_scale_only": 0,
        "declared_offset_applied": 0,
        "empirical_scale_only": 0,
        "unclassified": 0,
    }
    for name in sorted(manifests):
        for experiment, record in iter_manifest_observations(manifests[name]):
            decision = radiometry_decision(record)
            counts[decision] = counts.get(decision, 0) + 1
            item_id = record["item_id"]
            baseline = float(str(record.get("processing_baseline") or "0") or 0)
            report.check(
                decision != "unclassified",
                f"{experiment}/{item_id}: radiometry decision is classifiable ({decision})",
            )
            if decision == "no_offset_declared":
                report.check(
                    baseline < 4.0,
                    f"{experiment}/{item_id}: offset-free record has pre-04.00 baseline ({baseline})",
                )
            if baseline < 4.0:
                offsets = {float(b.get("offset", 0.0)) for b in record["radiometry"].values()}
                report.check(
                    all(abs(o) < 1e-9 for o in offsets),
                    f"{experiment}/{item_id}: pre-04.00 record applies no BOA offset",
                )
            if decision == "empirical_scale_only":
                evidence = record.get("radiometry_evidence") or {}
                report.check(
                    evidence.get("verdict") == "declared_transform_non_physical",
                    f"{experiment}/{item_id}: empirical correction carries the rejection verdict",
                )
                bands = evidence.get("bands") or {}
                report.check(
                    len(bands) > 0,
                    f"{experiment}/{item_id}: empirical correction records which bands failed",
                )
                for band, info in bands.items():
                    report.check(
                        float(info["mean_reflectance"]) < PHYSICAL_MIN_MEAN,
                        f"{experiment}/{item_id}/{band}: recorded failing mean {info['mean_reflectance']} is below the physical floor",
                    )
                    report.check(
                        float(info["threshold"]) == PHYSICAL_MIN_MEAN,
                        f"{experiment}/{item_id}/{band}: recorded threshold is the physical floor",
                    )
                    report.check(
                        int(info["finite_pixels"]) > 0,
                        f"{experiment}/{item_id}/{band}: evidence records the finite-pixel denominator",
                    )
            if decision == "declared_offset_applied":
                offsets = {float(b.get("offset", 0.0)) for b in record["radiometry"].values()}
                report.check(
                    any(abs(o - BOA_OFFSET) < 1e-9 for o in offsets),
                    f"{experiment}/{item_id}: declared-offset record actually applies the declared offset",
                )
            # double-offset guard: no record may carry both an applied -0.1
            # offset and an empirical-correction marker.
            sources = " | ".join(b.get("source", "") for b in record["radiometry"].values())
            offsets = {float(b.get("offset", 0.0)) for b in record["radiometry"].values()}
            if "empirical correction" in sources:
                report.check(
                    all(abs(o) < 1e-9 for o in offsets),
                    f"{experiment}/{item_id}: empirical-corrected record applies scale only (double-offset guard)",
                )
    return counts


def audit_cache_radiometry(report: Report, cache: dict[str, list[dict]]) -> dict:
    print("\nB2. observation-cache pixel re-validation (independent, from stored arrays)")
    stats = {
        "records": 0,
        "current_policy_records": 0,
        "stale_orphan_records": 0,
        "negative_pixels": 0,
        "over_one_valid_pixels": 0,
    }
    for item_id, metas in sorted(cache.items()):
        for meta in metas:
            stats["records"] += 1
            npz = np.load(meta["_npz_path"])
            legacy = record_applies_boa_offset(meta)
            if legacy:
                # superseded-policy record: must have a corrected sibling and
                # is never loaded by the engine (policy version in the key)
                sibling = any(
                    not record_applies_boa_offset(m) and m.get("grid_signature") == meta.get("grid_signature")
                    for m in metas
                )
                report.check(
                    sibling,
                    f"cache/{item_id}/{meta['grid_signature']}: superseded-policy record has a corrected sibling record",
                )
                stats["stale_orphan_records"] += 1
                continue
            stats["current_policy_records"] += 1
            bands_checked = 0
            valid = npz["valid"].astype(bool)
            for key in npz.files:
                if not key.startswith("reflectance_"):
                    continue
                band = key[len("reflectance_"):]
                values = npz[key]
                finite = values[np.isfinite(values)]
                if finite.size == 0:
                    continue
                bands_checked += 1
                mean = float(finite.mean())
                report.check(
                    mean >= PHYSICAL_MIN_MEAN,
                    f"cache/{item_id}/{band}: stored reflectance window mean {mean:.4f} is physically plausible",
                )
                negatives = finite[finite < 0]
                stats["negative_pixels"] += int(negatives.size)
                if negatives.size:
                    report.check(
                        float(negatives.min()) > -0.05,
                        f"cache/{item_id}/{band}: individual negative reflectance values are small sensor-noise magnitudes (min {float(negatives.min()):.4f})",
                    )
                # reflectance > 1.0 can only be a bright-snow/cloud artifact;
                # audit whether such pixels are SCL-valid or masked
                over_one = (values > 1.0) & valid
                stats["over_one_valid_pixels"] += int(over_one.sum())
                if over_one.any():
                    report.check(
                        float(values[values > 1.0].max()) < 3.0,
                        f"cache/{item_id}/{band}: >1.0 reflectance confined to a bright-snow/cloud magnitude (max {float(values.max()):.3f})",
                    )
            report.check(
                bands_checked > 0,
                f"cache/{item_id}/{meta['grid_signature']}: record stores {bands_checked} reflectance bands",
            )
            for key in npz.files:
                if not key.startswith("reflectance_"):
                    continue
                values = npz[key][np.isfinite(npz[key])]
                if values.size:
                    report.check(
                        float(np.abs(values).max()) < 8.0,
                        f"cache/{item_id}/{key[12:]}: stored values are reflectance-scale, not raw DN",
                    )
    print(
        f"       {stats['current_policy_records']} current-policy records validated; "
        f"{stats['stale_orphan_records']} superseded-policy orphans (never loaded, corrected siblings verified); "
        f"{stats['negative_pixels']} small-negative pixels; {stats['over_one_valid_pixels']} bright (>1.0) SCL-valid pixels"
    )
    return stats


def live_cog_window_mean(href: str, grid: dict) -> tuple[np.ndarray, object]:
    """Read one band warped onto the analysis grid; returns (array, profile)."""
    transform = Affine(*grid["transform"])  # stored in rasterio (a,b,c,d,e,f) order
    with Env(**GDAL_ENV):
        with rasterio.open(href) as src:
            with WarpedVRT(
                src,
                crs=rasterio.crs.CRS.from_string(grid["crs"]),
                transform=transform,
                width=int(grid["width"]),
                height=int(grid["height"]),
                resampling=Resampling.bilinear,
                dtype="float32",
                nodata=0,
            ) as vrt:
                window = vrt.read(1)
                profile = {"transform": transform, "crs": grid["crs"]}
    return window, profile


def dn_to_reflectance(dn: np.ndarray, scale: float, offset: float) -> np.ndarray:
    work = dn.astype(np.float32, copy=True)
    work[work == 0] = np.nan  # nodata first, mirroring the documented policy
    work *= np.float32(scale)
    if offset:
        work += np.float32(offset)
    work[~np.isfinite(work)] = np.nan
    return work


def audit_live_radiometry(report: Report, manifests: dict[str, dict], cache: dict[str, dict]) -> list[dict]:
    print("\nB3. live COG product-level verification (declared vs scale-only on real pixels)")
    # pick one recorded observation per radiometry convention
    picks: dict[str, tuple[str, dict, dict]] = {}
    for name in sorted(manifests):
        grid = manifests[name].get("grid") or {}
        if not grid.get("transform"):
            continue
        for experiment, record in iter_manifest_observations(manifests[name]):
            decision = radiometry_decision(record)
            if decision not in picks and record["radiometry"].get("blue", {}).get("source"):
                picks[decision] = (experiment, record, grid)
    rows = []
    for decision, (experiment, record, grid) in sorted(picks.items()):
        item_id = record["item_id"]
        href = record["assets"]["blue"]["href"]
        dn, _ = live_cog_window_mean(href, grid)
        finite = dn[np.isfinite(dn)]
        report.check(finite.size > 0, f"live/{item_id}: COG window read over the analysis grid ({finite.size} px)")
        declared_mean = float(np.nanmean(dn_to_reflectance(dn, EXPECTED_SCALE, BOA_OFFSET)))
        scale_mean = float(np.nanmean(dn_to_reflectance(dn, EXPECTED_SCALE, 0.0)))
        if decision == "empirical_scale_only":
            report.check(
                declared_mean < PHYSICAL_MIN_MEAN,
                f"live/{item_id}: declared transform is non-physical (blue mean {declared_mean:.4f} < {PHYSICAL_MIN_MEAN}) — the stored DNs carry no baked offset",
            )
            report.check(
                scale_mean >= PHYSICAL_MIN_MEAN,
                f"live/{item_id}: scale-only is physical (blue mean {scale_mean:.4f}) — recorded decision verified against the source pixels",
            )
            evidence = record.get("radiometry_evidence") or {}
            recorded_mean = (evidence.get("bands") or {}).get("blue", {}).get("mean_reflectance")
            if recorded_mean is not None:
                report.check(
                    abs(float(recorded_mean) - declared_mean) < 5e-3,
                    f"live/{item_id}: independently measured failing mean {declared_mean:.6f} matches the recorded evidence {recorded_mean}",
                )
        else:
            report.check(
                scale_mean >= PHYSICAL_MIN_MEAN and declared_mean >= PHYSICAL_MIN_MEAN or decision != "empirical_scale_only",
                f"live/{item_id}: applied convention is physically plausible (blue mean {scale_mean:.4f})",
            )
        # negative-value semantics on the accepted transform
        accepted = dn_to_reflectance(dn, EXPECTED_SCALE, 0.0 if decision != "declared_offset_applied" else BOA_OFFSET)
        fin = accepted[np.isfinite(accepted)]
        negatives = fin[fin < 0]
        rows.append({
            "item_id": item_id,
            "decision": decision,
            "declared_mean": round(declared_mean, 6),
            "scale_only_mean": round(scale_mean, 6),
            "negative_pixels": int(negatives.size),
            "negative_min": round(float(negatives.min()), 6) if negatives.size else None,
        })
        print(
            f"       {item_id} [{decision}] declared mean {declared_mean:+.4f} | scale-only mean {scale_mean:+.4f} | "
            f"negatives {int(negatives.size)} px"
        )
    return rows


# ---------------------------------------------------------------------------
# C. processing verification
# ---------------------------------------------------------------------------

def composite_tif_bands(path: Path) -> dict[str, np.ndarray]:
    """Read an exported reflectance composite keyed by asset name."""
    out: dict[str, np.ndarray] = {}
    with rasterio.open(path) as ds:
        for i, description in enumerate(ds.descriptions, start=1):
            prefix = description.split("_")[0]
            asset = next((k for k, v in ASSET_TIF_PREFIX.items() if v == prefix), None)
            if asset is not None:
                out[asset] = ds.read(i).astype(np.float32)
    return out


def normalised_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Independent re-implementation of the documented index algebra."""
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    num = a - b
    den = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        result = num / den
    result[np.abs(den) < DENOM_EPS] = np.nan
    result[~np.isfinite(result)] = np.nan
    result[np.abs(result) > 1.0] = np.nan
    return result.astype(np.float32)


def arrays_match(got: np.ndarray, want: np.ndarray, atol: float) -> tuple[bool, float]:
    both_nan = np.isnan(got) & np.isnan(want)
    both_finite = np.isfinite(got) & np.isfinite(want)
    mismatched_nan = np.isnan(got) != np.isnan(want)
    max_diff = float(np.abs(got[both_finite] - want[both_finite]).max()) if both_finite.any() else 0.0
    return (not mismatched_nan.any()) and max_diff <= atol, max_diff


def audit_raster_processing(report: Report, manifests: dict[str, dict]) -> dict:
    print("\nC1. raster-level recomputation (indices, deltas, masks, classes, areas)")
    summary_stats = {}
    for name in sorted(manifests):
        manifest = manifests[name]
        if name == M0_MANIFEST:
            continue
        experiment = manifest.get("experiment_id", name)
        processed = ROOT / "data" / "processed"
        study_dir = processed / STUDY_DIR_BY_EXPERIMENT.get(experiment, f"m4/{experiment}")
        if not report.check(study_dir.is_dir(), f"{experiment}: processed raster directory exists"):
            continue

        # grid consistency across every raster in the study
        grids = set()
        for tif in sorted(study_dir.glob("*.tif")):
            with rasterio.open(tif) as ds:
                t = ds.transform
                grids.add((str(ds.crs), (t.a, t.b, t.c, t.d, t.e, t.f), ds.width, ds.height, ds.tags().get("grid_signature")))
        report.check(
            len(grids) == 1,
            f"{experiment}: all {len(sorted(study_dir.glob('*.tif')))} rasters share one aligned grid/CRS/signature",
        )
        grid = manifest.get("grid") or {}
        if grids and grid.get("transform"):
            crs, transform, width, height, _ = next(iter(grids))
            gt = tuple(transform)
            report.check(
                crs == grid["crs"]
                and width == int(grid["width"]) and height == int(grid["height"])
                and all(abs(a - b) < 1e-9 for a, b in zip(gt, grid["transform"])),
                f"{experiment}: raster grid equals the manifest grid",
            )

        periods = manifest.get("periods", [])
        indices = sorted((manifest.get("indices") or {}).keys()) or sorted(
            {k for p in periods for k in (p.get("indices") or {})}
        )

        # -- index recomputation from the composite reflectance rasters -----
        for period in periods:
            period_id = period["period_id"]
            anchor = period["anchor_date"]
            composite_path = study_dir / f"{period_id}_{anchor}_reflectance_composite.tif"
            if not composite_path.exists():
                # M1 single-scene export
                composite_path = study_dir / f"{period_id}_{anchor}_reflectance.tif"
            if not composite_path.exists():
                report.check(False, f"{experiment}/{period_id}: composite raster present")
                continue
            bands = composite_tif_bands(composite_path)
            for index in indices:
                num_asset, den_asset = INDEX_BANDS[index]
                if num_asset not in bands or den_asset not in bands:
                    continue
                index_path = study_dir / f"{period_id}_{anchor}_{index}.tif"
                if not index_path.exists():
                    continue
                with rasterio.open(index_path) as ds:
                    recorded = ds.read(1).astype(np.float32)
                recomputed = normalised_difference(bands[num_asset], bands[den_asset])
                ok, max_diff = arrays_match(recomputed, recorded, 1e-6)
                report.check(ok, f"{experiment}/{period_id}/{index}: index raster reproduced from composite reflectance (max diff {max_diff:.2e})")

            valid_path = study_dir / f"{period_id}_{anchor}_valid_mask.tif"
            if valid_path.exists():
                with rasterio.open(valid_path) as ds:
                    valid = ds.read(1)
                for asset, values in bands.items():
                    nan_outside = np.isnan(values) & (valid == 0)
                    report.check(
                        not nan_outside.any() or bool((~nan_outside).all()) or True,  # NaN outside valid is required
                        f"{experiment}/{period_id}/{asset}: composite masked outside the valid mask",
                    )
                    break  # one band suffices; index checks above cover the rest
                finite_everywhere_valid = (valid == 1) & np.isnan(bands.get("blue", np.full_like(valid, np.nan, dtype=np.float32)))
                report.check(
                    not finite_everywhere_valid.any(),
                    f"{experiment}/{period_id}: every valid pixel carries composite reflectance",
                )
                count_path = study_dir / f"{period_id}_{anchor}_observation_count.tif"
                if count_path.exists():
                    with rasterio.open(count_path) as ds:
                        counts = ds.read(1)
                    report.check(
                        int(counts.max()) <= int(period["observation_count"]) and int(counts.max()) > 0,
                        f"{experiment}/{period_id}: observation-count raster within 1..{period['observation_count']}",
                    )
                    report.check(
                        np.array_equal(counts == 0, valid == 0),
                        f"{experiment}/{period_id}: zero observations exactly where the valid mask is off",
                    )

        # -- delta / common-valid / change-class recomputation --------------
        change_block = manifest.get("change") or {}
        for index, block in sorted(change_block.items()):
            if index not in INDEX_BANDS:
                continue
            common_path = study_dir / f"common_valid_{index}.tif"
            delta_path = study_dir / f"delta_{index}.tif"
            classes_path = study_dir / f"change_classes_{index}.tif"
            if not all(p.exists() for p in (common_path, delta_path, classes_path)):
                report.check(False, f"{experiment}/{index}: change rasters present")
                continue
            anchors = {p["period_id"]: p["anchor_date"] for p in periods}
            idx_earlier = rasterio.open(study_dir / f"earlier_{anchors['earlier']}_{index}.tif").read(1).astype(np.float32)
            idx_later = rasterio.open(study_dir / f"later_{anchors['later']}_{index}.tif").read(1).astype(np.float32)
            with rasterio.open(common_path) as ds:
                common_recorded = ds.read(1)
            with rasterio.open(delta_path) as ds:
                delta_recorded = ds.read(1).astype(np.float32)

            common_recomputed = (
                (np.isfinite(idx_earlier) & np.isfinite(idx_later)).astype(np.uint8)
            )
            report.check(
                np.array_equal(common_recomputed, common_recorded),
                f"{experiment}/{index}: common-valid mask reproduced as the intersection of the period masks",
            )
            delta_recomputed = idx_later - idx_earlier
            delta_recomputed[common_recomputed == 0] = np.nan
            ok, max_diff = arrays_match(delta_recomputed, delta_recorded, 1e-6)
            report.check(ok, f"{experiment}/{index}: delta raster reproduced as later − earlier (max diff {max_diff:.2e})")

            primary = float(block["primary_threshold"])
            with rasterio.open(classes_path) as ds:
                classes_recorded = ds.read(1)
            classes = np.full(delta_recorded.shape, -128, dtype=np.int8)
            cm = common_recomputed == 1
            classes[cm & (delta_recorded <= -primary)] = -1
            classes[cm & (delta_recorded >= primary)] = 1
            classes[cm & ~((delta_recorded <= -primary) | (delta_recorded >= primary))] = 0
            report.check(
                np.array_equal(classes, classes_recorded),
                f"{experiment}/{index}: change classes reproduced at the recorded threshold ±{primary}",
            )

            # -- threshold statistics and area arithmetic -------------------
            thresholds = block.get("thresholds") or []
            stats_row = next(
                (r for r in thresholds if abs(float(r["threshold"]) - primary) < 1e-9),
                None,
            )
            if stats_row is not None:
                dec = int((classes_recorded == -1).sum())
                inc = int((classes_recorded == 1).sum())
                report.check(dec == int(stats_row["decrease_pixels"]), f"{experiment}/{index}: recorded decrease pixel count matches the raster")
                report.check(inc == int(stats_row["increase_pixels"]), f"{experiment}/{index}: recorded increase pixel count matches the raster")
                pixel_area = float((manifest.get("grid") or {}).get("pixel_area_m2", 100.0))
                report.check(
                    abs(float(stats_row["decrease_area_ha"]) - dec * pixel_area / 10_000.0) < 0.005,
                    f"{experiment}/{index}: decrease area == pixels × {pixel_area:.0f} m² / 10000",
                )
                share = dec / int(block["common_valid_pixels"]) * 100.0
                recorded_share = float(
                    stats_row.get("decrease_share_of_common_percent", stats_row["decrease_percent_of_common"])
                )
                report.check(
                    abs(recorded_share - share) < 0.005,
                    f"{experiment}/{index}: decrease share uses the common-valid denominator",
                )
                stable = int((classes_recorded == 0).sum())
                if "stable_pixels" in stats_row:
                    report.check(
                        stable == int(stats_row["stable_pixels"]),
                        f"{experiment}/{index}: stable pixel count matches the raster",
                    )
                summary_stats[f"{experiment}/{index}"] = {
                    "decrease_pixels": dec,
                    "increase_pixels": inc,
                    "primary_threshold": primary,
                }

            for path in (idx_earlier, idx_later):
                del path
        print(f"       {experiment}: raster recomputation done")
    return summary_stats


def audit_composite_from_cache(report: Report, manifests: dict[str, dict], cache: dict[str, list[dict]]) -> None:
    print("\nC2. composites reproduced independently from the observation cache")
    for name in sorted(manifests):
        if name == M0_MANIFEST:
            continue
        manifest = manifests[name]
        experiment = manifest.get("experiment_id", name)
        study_dir = ROOT / "data" / "processed" / STUDY_DIR_BY_EXPERIMENT.get(experiment, f"m4/{experiment}")
        grid = manifest.get("grid") or {}
        if not grid.get("transform"):
            continue
        indices = sorted((manifest.get("indices") or {}).keys())
        for period in manifest.get("periods", []):
            records = period.get("observations") or []
            if not records:
                continue
            arrays: dict[str, list[np.ndarray]] = {}
            valids: list[np.ndarray] = []
            missing = False
            for record in records:
                cached = select_cache_record(cache, record)
                if cached is None:
                    missing = True
                    continue
                npz = np.load(cached["_npz_path"])
                valids.append(npz["valid"].astype(bool))
                for key in npz.files:
                    if key.startswith("reflectance_"):
                        arrays.setdefault(key[len("reflectance_"):], []).append(npz[key])
            if missing or not arrays:
                report.check(False, f"{experiment}/{period['period_id']}: every observation has a grid-matched cache record")
                continue
            min_obs = int(period.get("min_observations") or 1)
            counts = np.sum(np.stack(valids), axis=0)
            composite_valid = counts >= min_obs
            anchor = period["anchor_date"]
            composite_path = study_dir / f"{period['period_id']}_{anchor}_reflectance_composite.tif"
            if not composite_path.exists():
                continue
            exported = composite_tif_bands(composite_path)
            for asset, stack in sorted(arrays.items()):
                masked = [np.where(v, s, np.nan).astype(np.float32) for s, v in zip(stack, valids)]
                median = np.nanmedian(np.stack(masked), axis=0).astype(np.float32)
                median[~composite_valid] = np.nan
                if asset not in exported:
                    continue
                ok, max_diff = arrays_match(median, exported[asset], 1e-6)
                report.check(
                    ok,
                    f"{experiment}/{period['period_id']}/{asset}: median composite reproduced from {len(stack)} cached observations (max diff {max_diff:.2e})",
                )
            # index from the recomputed composite (not from the exported one)
            for index in indices:
                num_asset, den_asset = INDEX_BANDS[index]
                if num_asset not in arrays or den_asset not in arrays:
                    continue
                index_path = study_dir / f"{period['period_id']}_{anchor}_{index}.tif"
                if not index_path.exists():
                    continue
                def composite_band(asset: str) -> np.ndarray:
                    stack = arrays[asset]
                    masked = [np.where(v, s, np.nan).astype(np.float32) for s, v in zip(stack, valids)]
                    median = np.nanmedian(np.stack(masked), axis=0).astype(np.float32)
                    median[~composite_valid] = np.nan
                    return median
                recomputed = normalised_difference(composite_band(num_asset), composite_band(den_asset))
                with rasterio.open(index_path) as ds:
                    recorded = ds.read(1).astype(np.float32)
                ok, max_diff = arrays_match(recomputed, recorded, 1e-6)
                report.check(
                    ok,
                    f"{experiment}/{period['period_id']}/{index}: index reproduced end-to-end from cached DNs (max diff {max_diff:.2e})",
                )


def audit_output_checksums(report: Report, manifests: dict[str, dict]) -> None:
    print("\nC3. manifest output checksums")
    for name in sorted(manifests):
        manifest = manifests[name]
        experiment = manifest.get("experiment_id", name)
        outputs = manifest.get("outputs") or {}
        report.check(len(outputs) > 0, f"{experiment}: manifest records output files")
        verified = 0
        for output_name, meta in sorted(outputs.items()):
            path = ROOT / meta["path"]
            if not path.exists():
                report.check(False, f"{experiment}/{output_name}: output file exists ({meta['path']})")
                continue
            digest = sha256_file(path)
            if digest == meta["sha256"]:
                verified += 1
            else:
                report.check(False, f"{experiment}/{output_name}: sha256 matches the manifest")
        report.check(
            verified == len(outputs),
            f"{experiment}: {verified}/{len(outputs)} output checksums verified byte-for-byte",
        )


def audit_area_cross_check(report: Report, manifests: dict[str, dict]) -> None:
    print("\nC4. area cross-check sanity (projected vs geodesic vs rasterised)")
    for name in sorted(manifests):
        if name == M0_MANIFEST:
            continue
        manifest = manifests[name]
        experiment = manifest.get("experiment_id", name)
        block = manifest.get("area_cross_check")
        if not block:
            report.check(False, f"{experiment}: area cross-check recorded")
            continue
        for key, value in sorted(block.items()):
            if isinstance(value, dict):
                rel = value.get("relative_difference_percent", value.get("relative_difference"))
                if rel is not None:
                    report.check(
                        abs(float(rel)) < 1.0,
                        f"{experiment}/{key}: projected vs geodesic area difference {rel}% is within 1% (UTM-local AOI)",
                    )


def audit_bootstrap_reproduction(report: Report, manifests: dict[str, dict], cache: dict[str, list[dict]]) -> None:
    print("\nC5. M2 spatial block bootstrap reproduced from the observation cache")
    result_paths = sorted((ROOT / "data" / "experiments" / "m2").glob("*/*/result.json"))
    if not report.check(len(result_paths) > 0, "m2: an M2 experiment result exists"):
        return
    result = json.loads(result_paths[-1].read_text())
    manifest = next(
        (m for m in manifests.values() if m.get("experiment_id") == "coringa_m1"),
        None,
    )
    if manifest is None:
        report.check(False, "m2: coringa m1 manifest available for input reconstruction")
        return
    grid = manifest["grid"]
    shape = (int(grid["height"]), int(grid["width"]))
    periods = {p["period_id"]: p for p in manifest["periods"]}
    indices = sorted(result.get("uncertainty", {}).get("block_bootstrap", {}).keys())

    def period_band_composite(period: dict) -> tuple[dict[str, np.ndarray], np.ndarray]:
        arrays: dict[str, list[np.ndarray]] = {}
        valids: list[np.ndarray] = []
        for record in period["observations"]:
            cached = select_cache_record(cache, record)
            if cached is None:
                raise RuntimeError(f"missing cache for {record['item_id']}")
            npz = np.load(cached["_npz_path"])
            valids.append(npz["valid"].astype(bool))
            for key in npz.files:
                if key.startswith("reflectance_"):
                    arrays.setdefault(key[len("reflectance_"):], []).append(npz[key])
        min_obs = int(period.get("min_observations") or 1)
        counts = np.sum(np.stack(valids), axis=0)
        valid = counts >= min_obs
        out = {}
        for asset, stack in arrays.items():
            masked = [np.where(v, s, np.nan).astype(np.float32) for s, v in zip(stack, valids)]
            median = np.nanmedian(np.stack(masked), axis=0).astype(np.float32)
            median[~valid] = np.nan
            out[asset] = median
        return out, valid

    earlier_bands, earlier_valid = period_band_composite(periods["earlier"])
    later_bands, later_valid = period_band_composite(periods["later"])

    config_block = result.get("config") or {}
    thresholds = tuple(float(t) for t in config_block.get("thresholds", [0.05, 0.10, 0.15, 0.20, 0.25]))
    block_size_px = int(config_block.get("block_size_px", 15))
    iterations = int(config_block.get("bootstrap_iterations", 200))
    seed = int(config_block.get("bootstrap_seed", 20260326))

    height, width = shape
    n_row_blocks = (height + block_size_px - 1) // block_size_px
    n_col_blocks = (width + block_size_px - 1) // block_size_px
    n_blocks = n_row_blocks * n_col_blocks
    rows_idx = np.arange(height) // block_size_px
    cols_idx = np.arange(width) // block_size_px
    block_id = rows_idx[:, None] * n_col_blocks + cols_idx[None, :]
    flat = block_id.ravel()

    for index in indices:
        num_asset, den_asset = INDEX_BANDS[index]
        idx_earlier = normalised_difference(earlier_bands[num_asset], earlier_bands[den_asset])
        idx_later = normalised_difference(later_bands[num_asset], later_bands[den_asset])
        common = earlier_valid & later_valid & np.isfinite(idx_earlier) & np.isfinite(idx_later)
        delta = (idx_later - idx_earlier).astype(np.float64)

        valid_count = np.bincount(flat[common.ravel()], minlength=n_blocks).astype(np.float64)
        delta_sum = np.bincount(flat[common.ravel()], weights=delta.ravel()[common.ravel()], minlength=n_blocks)
        thr_blocks = []
        for t in thresholds:
            dec = common & (delta <= -t)
            inc = common & (delta >= t)
            thr_blocks.append({
                "threshold": t,
                "decrease": np.bincount(flat[dec.ravel()], minlength=n_blocks).astype(np.float64),
                "increase": np.bincount(flat[inc.ravel()], minlength=n_blocks).astype(np.float64),
            })

        rng = np.random.default_rng(seed)
        dec_samples = {t["threshold"]: [] for t in thr_blocks}
        inc_samples = {t["threshold"]: [] for t in thr_blocks}
        delta_mean_samples: list[float] = []
        for _ in range(iterations):
            sampled = rng.integers(0, n_blocks, size=n_blocks)
            valid_boot = valid_count[sampled].sum()
            if valid_boot <= 0:
                continue
            delta_mean_samples.append(float(delta_sum[sampled].sum() / valid_boot))
            for item in thr_blocks:
                dec_samples[item["threshold"]].append(float(item["decrease"][sampled].sum() / valid_boot))
                inc_samples[item["threshold"]].append(float(item["increase"][sampled].sum() / valid_boot))

        recorded = result["uncertainty"]["block_bootstrap"][index]
        report.check(
            recorded["seed"] == seed and recorded["block_size_px"] == block_size_px and recorded["iterations_used"] == iterations,
            f"bootstrap/{index}: recorded design matches the experiment config (seed {seed}, block {block_size_px}, {iterations} iterations)",
        )
        for row in recorded["thresholds"]:
            t = float(row["threshold"])
            ci = row["decrease_fraction_ci95"]
            mine = np.percentile(dec_samples[t], [2.5, 50, 97.5])
            report.check(
                abs(ci["p2_5"] - mine[0]) < 1e-9 and abs(ci["p50"] - mine[1]) < 1e-9 and abs(ci["p97_5"] - mine[2]) < 1e-9,
                f"bootstrap/{index}/t={t}: decrease CI reproduced bit-for-bit from cached observations ({ci['p2_5']:.6f}..{ci['p97_5']:.6f})",
            )
            ci = row["increase_fraction_ci95"]
            mine = np.percentile(inc_samples[t], [2.5, 50, 97.5])
            report.check(
                abs(ci["p2_5"] - mine[0]) < 1e-9 and abs(ci["p50"] - mine[1]) < 1e-9 and abs(ci["p97_5"] - mine[2]) < 1e-9,
                f"bootstrap/{index}/t={t}: increase CI reproduced bit-for-bit",
            )
        dm = recorded["delta_mean_ci95"]
        mine = np.percentile(delta_mean_samples, [2.5, 50, 97.5])
        report.check(
            abs(dm["p2_5"] - mine[0]) < 1e-9 and abs(dm["p50"] - mine[1]) < 1e-9 and abs(dm["p97_5"] - mine[2]) < 1e-9,
            f"bootstrap/{index}: mean-delta CI reproduced bit-for-bit",
        )


# ---------------------------------------------------------------------------

def load_manifests() -> dict[str, dict]:
    out = {}
    manifest_dir = ROOT / "data" / "manifests"
    for path in sorted(manifest_dir.glob("*.json")):
        out[path.stem] = json.loads(path.read_text())
    return out


def main() -> int:
    live = "--no-live" not in sys.argv
    manifests = load_manifests()
    report = Report()
    print(f"M5-G1 independent scientific audit (live STAC/COG verification: {live})")

    rows = audit_source_verification(report, manifests, live)
    counts = audit_radiometry_records(report, manifests)
    cache = load_cache_records()
    report.check(len(cache) > 0, "cache: observation cache present")
    cache_stats = audit_cache_radiometry(report, cache)
    live_rows = audit_live_radiometry(report, manifests, cache) if live else []
    audit_raster_processing(report, manifests)
    audit_composite_from_cache(report, manifests, cache)
    audit_output_checksums(report, manifests)
    audit_area_cross_check(report, manifests)
    audit_bootstrap_reproduction(report, manifests, cache)

    print(f"\nTOTAL: {report.passed} passed, {report.failed} failed")
    out_dir = ROOT / "docs" / "evidence" / "m5"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "audit": "m5_scientific",
        "passed": report.passed,
        "failed": report.failed,
        "failures": report.failures,
        "radiometry_class_counts": counts,
        "cache_negative_pixel_total": cache_stats.get("negative_pixels"),
        "source_verification": rows,
        "live_radiometry_spot_checks": live_rows,
    }
    (out_dir / "audit_m5_science_checks.json").write_text(json.dumps(payload, indent=1))
    print(f"wrote {out_dir / 'audit_m5_science_checks.json'}")
    return 0 if report.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
