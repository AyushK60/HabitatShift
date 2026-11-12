# M1 science engine — reproducible raster processing and temporal change

**Status.** M1 is implemented, verified against real Sentinel-2 L2A data for
the Coringa / Godavari study, and reproducible offline from cached source data.
It builds on the M0 checkpoint (`aa42c31`, tag `m0-verified`) without changing
M0's own summary, manifest, scene selection or viewer fallback.

This document describes *what the engine does and why*. Measured results are in
[`M1_NUMERICAL_AUDIT.md`](M1_NUMERICAL_AUDIT.md); the evidence that the results
are correct is in [`M1_VERIFICATION.md`](M1_VERIFICATION.md); the honest limits
are in [`M1_LIMITATIONS.md`](M1_LIMITATIONS.md). Claim rules are governed by
[`SCIENCE_PROTOCOL.md`](SCIENCE_PROTOCOL.md).

---

## 1. Scope

M1 turns two bounded periods of Sentinel-2 L2A observations into:

- one common analysis grid;
- per-period surface-reflectance composites with per-pixel observation counts
  and validity masks;
- NDVI, McFeeters NDWI and Xu MNDWI on those composites (plus tested NDSI and
  NDBI primitives that this study does not interpret);
- matched-valid difference maps, candidate thresholds and projected areas;
- georeferenced rasters, fixed-ramp previews, summary JSON/CSV and a validated
  reproducibility manifest;
- read-only API endpoints and a minimal viewer that shows the M1 bundle.

M1 deliberately does **not** include machine learning, land-cover
classification, causal attribution, or the M3 product UI.

---

## 2. Module map

| Stage | Module | Responsibility |
|---|---|---|
| Configuration | `backend/app/pipeline/config.py` | load and validate experiment YAML; resolve registry AOI |
| Catalogue | `backend/app/catalog/` | bounded STAC search, pagination, asset verification |
| HTTP/cache | `backend/app/http.py` | retries, rate limit, offline cache-only mode |
| Selection/scoring | `backend/app/preprocess/scoring.py` | in-AOI SCL valid-fraction scoring under a budget |
| Window reads | `backend/app/acquisition/cog.py` | `WarpedVRT` byte-range reads onto the analysis grid |
| Radiometry | `backend/app/acquisition/assets.py` | per-item scale/offset verification, DN → reflectance |
| Masking | `backend/app/preprocess/masks.py` | SCL policy, AOI mask, finite-reflectance mask |
| Compositing | `backend/app/preprocess/composite.py` | per-pixel temporal median/mean, observation counts |
| Indices | `backend/app/indices/spectral.py` | index registry: bands, formula, native resolution, ramp |
| Change | `backend/app/analysis/change.py` | shared-valid intersection, thresholds, classes, areas |
| Previews | `backend/app/preprocess/preview.py` | true/false colour, index/difference/count PNGs, legends |
| Provenance | `backend/app/pipeline/provenance.py` | manifest schema, validation, SHA-256 output records |
| Orchestration | `backend/app/pipeline/engine.py` | stage sequencing, exports, independent verification |
| CLI | `scripts/run_study.py` | reproducible entry point (`--offline`, `--verbose`) |
| Audit | `scripts/audit_m1.py` | independent re-derivation from exported files |
| API | `backend/app/api/app.py` | read-only M0 + M1 endpoints |

No module in the processing path imports the API or the frontend.

---

## 3. Processing stages

### 3.1 Selection and scoring

Each period searches the catalogue over its configured date window with a
server-side cloud-cover ceiling. Candidates are **scored by measured in-AOI SCL
valid fraction**, not by the global scene cloud percentage. Measurement is
bounded by `measurement_budget`; candidates beyond the budget are left
unmeasured and are never treated as usable.

Within a period the engine selects up to `max_observations` scenes:

1. the usable scene whose acquisition is nearest the period anchor;
2. then the nearest usable scenes on **distinct calendar dates**, within
   `anchor_max_offset_days`;
3. if no scene falls inside the anchor window, the nearest usable scene is
   used and `fallback_used: true` is recorded.

One scene per calendar date is kept (the higher-scoring item wins). The same
scene cannot be selected for both periods. Every candidate, its score, the
measured valid fraction and the selection report are stored in the manifest.

### 3.2 Bounded COG reads and reprojection

Only the bands an index actually needs are fetched, plus blue for true-colour
previews and SCL for masking. Each band is read as a windowed COG request and
warped directly onto the single analysis grid through a `WarpedVRT`, so no
full-scene download occurs.

- Continuous reflectance bands: **bilinear** resampling.
- SCL (categorical): **nearest** resampling, so class codes are never blended.

This is the only reprojection in the pipeline. No stage later mixes grids.

### 3.3 Radiometry

`reflectance = DN * scale + offset`, with both constants read from each item's
own `raster:bands` metadata and cross-checked against the collection
definition. A mismatch is a hard error, never a silent guess.

Sentinel-2 baseline 04.00 introduced `BOA_ADD_OFFSET = −1000`
(offset `−0.1`). Earth Search records `earthsearch:boa_offset_applied`:

| Item metadata | Offset applied |
|---|---|
| baseline < 04.00 | 0.0 |
| baseline ≥ 04.00, offset not baked in | −0.1 |
| baseline ≥ 04.00, `boa_offset_applied=true` | 0.0 |

The exact decision and its reason are written per item into the manifest. In
this study every selected item reports `boa_offset_applied=true`, so the
effective offset is 0.0 while the declared offset remains −0.1.

### 3.4 Masking

A pixel is valid for an observation when **all** of the following hold:

- it is inside the AOI polygon;
- its SCL class is accepted for this profile;
- every fetched reflectance band is finite.

SCL policy (coastal/vegetation profile):

| Accepted | Rejected |
|---|---|
| 2 dark area, 4 vegetation, 5 not vegetated, 6 water, 7 unclassified, 11 snow/ice | 0 no data, 1 saturated/defective, 3 cloud shadow, 8 cloud medium, 9 cloud high, 10 thin cirrus |

Class 11 is accepted so the same profile can be reused in the Himalaya study;
it does not occur at Coringa. Invalid pixels become `NaN`; nothing is
interpolated across space or time to fill them.

### 3.5 Temporal compositing

Within a period, reflectance is composited **per pixel before any index is
computed**. This matters: compositing NDVI values is not the same operation.

- Default method: median.
- Even observation count: NumPy `nanmedian`, i.e. the mean of the two central
  values.
- Only valid observations contribute to a pixel.
- Every pixel records how many observations contributed.
- The composite is invalid where fewer than `min_observations` contributed.
- Observations on different grid signatures, shapes or band sets cannot be
  combined; the composite raises instead.

The engine exports the observation-count raster and a discrete count preview so
a two-observation pixel can never be mistaken for a three-observation pixel.

### 3.6 Index computation

All indices are `(a − b) / (a + b)` on composite surface reflectance.

| Key | Formula | Bands | Native | On 10 m grid |
|---|---|---|---|---|
| `ndvi` | `(NIR − Red) / (NIR + Red)` | B08, B04 | 10 m | native |
| `ndwi` | `(Green − NIR) / (Green + NIR)` | B03, B08 | 10 m | native |
| `mndwi` | `(Green − SWIR1) / (Green + SWIR1)` | B03, B11 | 20 m | upsampled |
| `ndsi` | `(Green − SWIR1) / (Green + SWIR1)` | B03, B11 | 20 m | upsampled |
| `ndbi` | `(SWIR1 − NIR) / (SWIR1 + NIR)` | B11, B08 | 20 m | upsampled |

Rules enforced by the registry and the index primitive:

- division by a denominator whose magnitude is below `1e-6` yields `NaN`;
- non-finite inputs yield `NaN`;
- negative reflectance (an offset artefact) is rejected, not clipped;
- missing bands raise `IndexSpecError`;
- NDSI and NDBI are registered and tested but are not interpreted as glacier
  or urban change in this study.

`IndexSpec.native_resolution_m` and `upsampled_to_analysis_grid` are written
into the summary and manifest. MNDWI at 10 m is explicitly flagged: bilinear
upsampling of 20 m SWIR **does not create genuine 10 m detail**.

### 3.7 Change analysis

For each index:

1. compute `delta = later_index − earlier_index` on the common grid;
2. build `common_valid = isfinite(earlier) & isfinite(later)`; the difference
   map is `NaN` everywhere else;
3. classify at each configured threshold:
   - decrease: `delta ≤ −threshold`
   - stable: `−threshold < delta < threshold`
   - increase: `delta ≥ threshold`
4. count pixels and convert to area with the projected pixel area;
5. report quantiles and the full distribution summary;
6. report the same counts at every threshold so sensitivity is visible.

Class raster codes are `int8`: `−1` decrease, `0` stable, `1` increase,
`−128` invalid. Percentages of directional change are always **of the
common-valid footprint**, never of the full AOI.

A pair is flagged `suitable_for_comparison=false` if the common-valid
footprint falls below `min_comparable_valid_fraction` (0.50). That flag is a
usability gate, not a scientific verdict.

### 3.8 Area calculation

- pixel area = projected pixel area of the analysis grid (10 m → 100 m²);
- hectares = m² / 10 000; square kilometres = m² / 1 000 000;
- areas are planimetric on `EPSG:32644`;
- an independent cross-check computes the AOI polygon area in the projected
  CRS, the geodesic area on the WGS84 ellipsoid, and the rasterised pixel-count
  area. The relative differences are recorded in the summary.

### 3.9 Exports and provenance

Every run writes, under its configured output directories:

- reflectance composite (5 bands + descriptions);
- period valid mask and observation-count raster;
- one GeoTIFF per index;
- delta raster, class raster and common-valid mask per index;
- true-colour, false-colour, index, delta, mask and count PNGs;
- fixed-ramp legend PNGs plus machine-readable legend JSON;
- `summary.json`, `summary.csv`, `status.json`;
- a validated `m1_<study>.json` manifest with SHA-256, byte size and kind for
  every output.

The manifest records study/AOI/grid, catalogue, search requests and scores,
selected item IDs and dates, radiometry decisions, composite parameters, index
formulas and resolutions, thresholds, area conventions, verification results,
software versions and limitations.

### 3.10 Independent verification

After export the engine re-opens the written files and checks them against the
in-memory result and the published policy: grid georeferencing, observation
counts, index recomputation on a deterministic pixel sample, delta
recomputation, threshold counts and area conservation. The run fails if any
check fails.

`scripts/audit_m1.py` is a second, separate check that does not import the
engine: it re-reads the exported rasters, recomputes formulas, counts, areas
and hashes, and compares them with `summary.json` and the manifest.

---

## 4. Grid and resolution policy

There is exactly one analysis grid per run:

- CRS, affine transform, width, height and resolution are fixed once from the
  AOI and `analysis.resolution_m`;
- every input is warped directly onto it;
- every raster export carries the same grid and is re-checked after writing;
- the grid signature (SHA-256 prefix of CRS + transform + shape + resolution)
  is written into the summary, the manifest and each GeoTIFF tag.

For this study: `EPSG:32644`, 10 m, 429 × 390 px, transform
`[10, 0, 632700, 0, −10, 1851790]`, signature `ad1601d5620e5f23`.

Important resolution distinction:

- NDVI and NDWI use only 10 m bands and are genuinely 10 m products.
- MNDWI/NDSI/NDBI use native 20 m SWIR upsampled to the 10 m grid. They carry
  **no genuine 10 m SWIR information**; their effective resolution is 20 m.
  The summary, manifest, legend note and viewer all state this.

---

## 5. Configuration and CLI

Experiment configuration is YAML, validated before any network access:

`studies/experiments/coringa_m1.yaml`

It references the unchanged M0 study registry entry (`coringa_coastal`) and adds
only the processing plan: period anchors and windows, compositing policy,
indices, thresholds and output paths. Validation rejects unknown indices,
invalid observation bounds, inverted windows, anchors outside their window,
non-positive thresholds and unresolvable study IDs.

Run:

```powershell
# from the repository root, inside .venv
.\.venv\Scripts\python.exe scripts\run_study.py --config studies\experiments\coringa_m1.yaml
.\.venv\Scripts\python.exe scripts\run_study.py --config studies\experiments\coringa_m1.yaml --offline
.\.venv\Scripts\python.exe scripts\audit_m1.py --study coringa_coastal
```

Exit codes: `0` all verification passed; `2` at least one audit check failed;
`1` the run could not be completed honestly.

Cache reuse:

- catalogue JSON responses are cached under `data/cache/`;
- SCL valid-fraction measurements are memoised;
- processed observations are cached as `.npz` under
  `data/cache/observations/`, keyed by item ID + grid signature + band set;
- a corrupt observation cache entry is ignored and re-read online, and is a
  hard `ObservationCacheMiss` in `--offline` mode.

`--offline` never touches the network. It fails loudly if a required cache
entry is missing.

---

## 6. API and viewer

The API is read-only and serves stored artefacts only.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | liveness, available M1 studies, pipeline version |
| `GET /api/study` | unchanged M0 summary |
| `GET /api/manifest` | unchanged M0 manifest |
| `GET /api/legend` | unchanged M0 legend |
| `GET /api/m1/studies` | available M1 study bundles + verification status |
| `GET /api/m1/study/{study_id}` | full M1 summary |
| `GET /api/m1/study/{study_id}/status` | stage log and status |
| `GET /api/m1/study/{study_id}/layers` | layer inventory with stable file URLs |
| `GET /api/m1/study/{study_id}/indices` | period dates/scenes and index metadata/stats |
| `GET /api/m1/study/{study_id}/change` | change blocks, thresholds, areas, limitations |
| `GET /api/m1/study/{study_id}/provenance` | reproducibility manifest |
| `GET /api/m1/study/{study_id}/manifest` | alias of provenance |
| `GET /files/m1/{study_id}/{scope}/{name}` | `processed` or `previews` file |

Study IDs are validated against `^[A-Za-z0-9_-]+$`; paths are resolved under
the configured scope root and bare file names are required, which prevents
traversal. Unknown scopes return 404, malformed names 400.

The viewer tries the M1 bundle first and falls back to the unchanged M0 summary
if no M1 bundle exists. M1 layers: true colour, false colour, NDVI, NDWI,
MNDWI, ΔNDVI, ΔNDWI, ΔMNDWI, valid mask and observation count. Legends are
fixed for both periods so equal values share a colour.

---

## 7. Key design decisions

1. **Composite reflectance first, then indices.** Index-of-median is not
   median-of-index; the engine documents and tests the former.
2. **Two periods, up to three observations each.** The headline M1 result is a
   small robust composite, not a dense time series. If extra observations are
   unavailable the engine reports that limitation rather than pretending.
3. **One grid, two resampling policies.** Bilinear for continuous reflectance,
   nearest for categorical SCL.
4. **Shared-valid change only.** No pixel enters change statistics unless it is
   valid in both periods for that index.
5. **Areas from projected pixels.** Not from degrees, not from a Web Mercator
   visualisation.
6. **No causal labels.** A threshold crossing is a candidate spectral signal.
   It is never called deforestation, wetland loss, construction or glacier
   damage.
7. **Fail loudly.** Missing bands, radiometry mismatches, grid mismatches,
   uncached offline observations and verification failures stop the run.
8. **Separate M1 namespaces.** `data/processed/m1/<study>/`,
   `data/previews/m1/<study>/`, `data/manifests/m1_<study>.json`. M0 artefacts
   are untouched.
