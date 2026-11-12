# M0 feasibility and gate report — Coringa two-date observation

**Gate statement.** M0 is complete on its own terms: one bounded non-disaster
AOI (Coringa / Godavari delta) has **two physically real Sentinel-2 L2A
observations from distinct years**, pixel-aligned on one documented grid, with
measured QA-masked NDVI, an independently re-checked index, a provenance
manifest, a working proof viewer, and an honest Nepal/Kathmandu availability
record. Nothing in this report is estimated: every number is read from
`data/manifests/m0_primary_study.json` and
`data/processed/coringa_coastal/summary.json`, both written by the pipeline.

## 1. What was built

| Component | Location | Role |
|---|---|---|
| STAC client | `backend/app/catalog/` | bounded search, pagination, retries, rate limit, local response cache, asset verification |
| Windowed COG reader | `backend/app/acquisition/` | HTTPS byte-range reads via `WarpedVRT`, one output grid |
| Radiometry | `backend/app/acquisition/assets.py` | per-item scale/offset resolution and verification |
| Masking | `backend/app/preprocess/masks.py` | SCL policy, AOI mask, reflectance sanity mask |
| Index | `backend/app/indices/ndvi.py` | NDVI, delta, statistics, thresholded area |
| Rendering | `backend/app/preprocess/preview.py` | true colour, NDVI, validity PNGs, fixed-ramp legend |
| Provenance | `backend/app/provenance/` | manifest assembly and validation |
| Study build | `scripts/build_primary_study.py` | end-to-end run + independent NDVI re-check |
| Nepal probe | `scripts/probe_event_feasibility.py` | real availability record for D1, D2, Kathmandu |
| Proof API | `backend/app/api/app.py` | serves only stored artifacts |
| Proof viewer | `frontend/` | two-date comparison, layer toggle, swipe, measured metadata |
| Tests | `backend/tests/` | 132 offline + 6 live |

## 2. Study, AOI and grid

- Registry entry: `studies/registry.yaml` → `coringa_coastal` (status
  `processed`).
- AOI: `82.2450–82.2850 E`, `16.7100–16.7450 N`, a hand-chosen rectangular
  working window over the mangrove/creek complex south of Kakinada — **not** the
  official sanctuary boundary.
- Area: 16.516 km². Analysis CRS: `EPSG:32644` (UTM 44N), derived from the AOI
  centroid.
- Grid: 10 m pixels, 429 × 390 px (167,310 px), transform
  `[10, 0, 632700, 0, -10, 1851790]`, signature `ad1601d5620e5f23`. Both dates and
  the delta raster share this signature.
- 165,136 px (98.7 % of the window) fall inside the AOI polygon.

## 3. What the catalogue actually returned

Search windows come from the registry: earlier `2020-01-01 → 2020-05-31`, later
`2025-01-01 → 2025-05-31`. Both searches applied an `eo:cloud_cover ≤ 60 %`
server-side filter and were scored by **measured in-AOI SCL validity**, not by
global cloud percentage. To keep the run bounded, at most 24 candidates per
search were measured; candidates beyond that budget are returned unmeasured and
never treated as usable.

| Period | Items accepted | Measured in AOI | Usable (≥ 0.60 valid) | Chosen scene | Date | Scene cloud |
|---|---|---|---|---|---|---|
| Earlier | 58 | 24 | 20 | `S2A_44QPD_20200326_1_L2A` | 2020-03-26 05:14:04 UTC | 0.037 % |
| Later | 26 | 24 | 18 | `S2B_44QPD_20250325_0_L2A` | 2025-03-25 05:14:10 UTC | 5.010 % |

Both scenes are MGRS tile `44QPD`; acquisition times are five years and ~2 days
of calendar season apart. The later search was explicitly ranked by day-of-year
proximity to the earlier acquisition (circular day-of-year distance), giving a
**+2 day seasonal gap** — the scene dates are 2020-03-26 and 2025-03-25.

The full candidate list (IDs, dates, scene cloud, footprint fraction, measured
valid fraction, failure notes) is stored per period in the manifest under
`search.earlier.scores` and `search.later.scores`; the selection policy and
measurement budget are stored alongside them.

## 4. Radiometry: the offset trap, resolved with evidence

Both items declare `raster:bands.scale = 0.0001` and a nominal offset of `-0.1`
(baseline 05.00 and 05.11), which is the Sentinel-2 `BOA_ADD_OFFSET` introduced
at baseline 04.00. Earth Search also sets
`earthsearch:boa_offset_applied = true` on these items, meaning the COG digital
numbers **already include** the offset.

Applying the declared `-0.1` a second time drove dark pixels negative, produced
impossible NDVI values (`|NDVI| > 1`) and a visibly wrong comparison. The
pipeline therefore resolves the offset per item:

| Case | Offset applied |
|---|---|
| Pre-04.00 product (no `BOA_ADD_OFFSET`) | `0.0` |
| 04.00+ and `earthsearch:boa_offset_applied = false` | `-0.1` |
| 04.00+ and `earthsearch:boa_offset_applied = true` | `0.0` |

Both M0 items take the third row; the manifest records `offset: 0.0` and the
exact reason string per band. `verify_radiometry()` fails the build if the
declared scale, asset key, nodata or GSD disagree with the catalogue.

## 5. Masking and index

- Mask policy: SCL classes **2, 4, 5, 6, 7, 11 accepted**; classes **0, 1, 3,
  8, 9, 10 rejected** (nodata, saturated/defective, cloud shadow, medium/high
  cloud, thin cirrus).
- Also rejected: pixels outside the AOI polygon and non-finite reflectance.
- `NDVI = (B08 − B04) / (B08 + B04)` on float32 surface reflectance; zero
  denominators are turned into NaN, as are any `|NDVI| > 1` values that survive
  masking. Masked pixels are NaN in the GeoTIFFs and charcoal in the previews —
  never interpolated.
- SCL is read at 20 m with nearest-neighbour resampling; reflectance bands are
  read at 10 m with bilinear resampling. The manifest states both.

Measured per-date results over valid AOI pixels:

| Period | Date | AOI valid | NDVI mean | Median | p05 | p95 |
|---|---|---|---|---|---|---|
| Earlier | 2020-03-26 | 99.998 % | 0.5332 | 0.6486 | −0.2314 | 0.9555 |
| Later | 2025-03-25 | 95.796 % | 0.4433 | 0.4663 | −0.0616 | 0.7866 |

## 6. Two-date difference (observed, not interpreted)

| Quantity | Value |
|---|---|
| Common-valid pixels | 158,190 (95.79 % of AOI, 1,581.9 ha) |
| `suitable_for_comparison` | **true** (threshold 50 %) |
| ΔNDVI mean | −0.0877 |
| ΔNDVI median | −0.1254 |
| ΔNDVI p05 / p95 | −0.3970 / +0.2852 |
| Decrease at `\|ΔNDVI\| ≥ 0.15` | 67,650 px = 676.5 ha |
| Increase at `\|ΔNDVI\| ≥ 0.15` | 16,601 px = 166.01 ha |
| Unchanged at that threshold | 73,939 px |

The threshold `0.15` is a **preliminary summary parameter**, not a validated
change-detection threshold; it is declared as such in the manifest
(`delta.threshold`). These are *observed spectral differences*, not a
land-cover verdict.

## 7. Independent verification

`verify_ndvi_independently()` re-reads the written reflectance and NDVI
GeoTIFFs, samples 400 valid pixels per date with a fixed seed, recomputes
`(NIR − RED) / (NIR + RED)` from the stored bands, and checks the grid.

| Check | Earlier | Later |
|---|---|---|
| Max absolute NDVI difference (400 px) | **0.0** | **0.0** |
| Mean absolute difference | 0.0 | 0.0 |
| Georeferencing matches the analysis grid | yes | yes |
| Every masked pixel is NaN in the stored raster | yes | yes |

Build result: `scientific re-check: PASS`.

## 8. Proof viewer

`scripts/serve_viewer.ps1` starts the FastAPI app plus the static frontend
(`http://127.0.0.1:8091/` by default). The page renders only `/api/study`
content: scene IDs, dates, scene cloud, AOI valid fraction, NDVI means, delta
statistics, verification results and attribution. Layer buttons switch between
true colour, NDVI and validity previews for both dates; the NDVI legend comes
from the same fixed ramp used to render the pixels; "Swipe" clips the later
image over the earlier one on the shared grid.

Verified in the in-app browser at the M0 checkpoint:

- `/api/health`, `/api/study`, `/api/manifest`, `/api/legend` and
  `/files/preview/ndvi_legend.png` return 200;
- both comparison panes and the legend load;
- **zero console errors**.

## 9. Nepal and Kathmandu feasibility

Full measured detail: `docs/M0_HIMALAYAN_DATA_FEASIBILITY.md`, derived from
`scripts/probe_event_feasibility.py` and `data/cache/event_feasibility.json`.

Summary of what the catalogue supports today:

- **D1, Purepu lake drainage, 8 July 2025** — usable pre-event scene
  `S2B_45RUM_20250421_0_L2A` (valid 1.000) and usable post-monsoon scene
  `S2B_45RUM_20251021_0_L2A` (valid 1.000). The only usable immediate
  post-event scene is the same-day `S2C_45RUM_20250708_0_L2A` at 0.632 valid;
  later July passes fail (0.446, 0.317, 0.055, 0.022). **There is no clean
  same-week pair**; the honest comparison is seasonal (April → October 2025)
  with snow-cover change as a confounder of the same size as the event.
- **D2, Langtang Lirung collapse, 26 August 2026** — tightest usable pair
  `S2C_45RUM_20260812_0_L2A` (14 days before, valid 0.707) →
  `S2C_45RUM_20260928_0_L2A` (33 days after, valid 1.000). Residual cloud,
  snow evolution and terrain shadow remain confounders; no volume, routing or
  damage claim is supported.
- **Kathmandu urban pilot** — availability is not the constraint: 122 accepted
  scenes in the 2020 window and 69 in the 2025 window, with a near-exact
  seasonal pair `S2B_45RUL_20200331_1_L2A` → `S2A_45RUL_20250329_0_L2A` (both
  valid 1.000, 2-day day-of-year gap). Bare soil and construction are the
  interpretation risk, not data supply.

D1 and D2 remain **distinct investigations** (different `event_mechanism` in
the registry, enforced by a registry test). External event context (NDRRMA
2025, ICIMOD 2026) is cited as literature only.

## 10. Reproducibility

Environment (recorded in the manifest): Python 3.11.9, numpy 2.2.6, rasterio
1.4.3, GDAL 3.9.3, pyproj 3.7.1, shapely 2.0.7, pystac_client 0.9.0, on
Windows.

```powershell
# from the repository root, using the project venv
.venv\Scripts\python.exe scripts\build_primary_study.py     # rebuild study + manifest
.venv\Scripts\python.exe scripts\probe_event_feasibility.py # rebuild Nepal/Kathmandu record
.venv\Scripts\python.exe -m pytest -q -m "not live"         # offline suite
.venv\Scripts\python.exe -m pytest -q -m live               # network suite
.\scripts\serve_viewer.ps1                                  # proof viewer
```

Deterministic inputs: the registry, the search request bodies, the analysis
grid and the fixed random seed (`20260804`) for verification sampling.
Catalogue responses and per-scene SCL valid-fraction memos are cached under
`data/cache/` (git-ignored) with a 7-day TTL; `--force-refresh` on the build
and the probe discards them.

Artifacts at the checkpoint:

- `data/manifests/m0_primary_study.json` (63,015 bytes) — committed provenance.
- `data/processed/coringa_coastal/summary.json` (4,172 bytes) — committed,
  consumed by the viewer; rasters in that directory are git-ignored.
- `data/previews/coringa_coastal/*` (9 PNGs + 1 JSON legend) — committed.
- 18 processed/preview files total, 7,028,546 bytes.
- Local cache: 144 files, 24,077,823 bytes (not committed).
- Network use for the final build: 2 catalogue requests, 0 bytes downloaded
  (cache hit); SCL and band windows were read as COG range requests. No AWS
  credentials are used anywhere.

## 11. Test evidence

- `pytest -q -m "not live"`: **132 passed**, 6 deselected.
- `pytest -q -m live`: **6 passed** — real collection metadata, real search
  items, anonymously readable COGs, windowed read with reflectance conversion,
  SCL class handling and real-pixel NDVI bounds.
- Covered invariants include NDVI formula and denominator guards, NaN masking,
  SCL accept/reject policy, coordinate/grid alignment (`assert_same_grid` with
  `atol=1e-6`), radiometry offset resolution, search request bounds, manifest
  schema, preview colour semantics, scene-scoring budget/cache behaviour, and
  registry consistency (D1 ≠ D2 mechanism).

## 12. M0 acceptance checklist (roadmap §M0)

| Requirement | Status |
|---|---|
| Repository, toolchain, setup/verification scripts | Done |
| `studies/registry.yaml` with flexible metadata | Done |
| Earth Search client: AOI/date/cloud, pagination, retries, UA, rate limit, cache | Done |
| Small Coringa AOI, two seasonally comparable periods | Done (16.5 km², 2020 / 2025) |
| Log actual candidates; select on AOI validity, not global cloud | Done (IDs + measured fractions in manifest) |
| B02/B03/B04/B08/SCL window reads, masks, previews, georeferencing | Done |
| JSON provenance manifest, licensing, no fabricated scenes | Done |
| Minimal proof page with dates, coverage, metadata | Done, zero console errors |
| Design tokens, typography, sketches, required interactions | `docs/DESIGN_SPEC.md` |
| Scientific invariant tests | 132 offline tests |
| Himalayan spike for both events, exact candidates and visibility limits | `docs/M0_HIMALAYAN_DATA_FEASIBILITY.md` |
| ICIMOD/NDRRMA as external literature; UNOSAT rights note | Recorded as literature only |
| Kathmandu 2020/2025 availability + soil/urban risks | `docs/M0_HIMALAYAN_DATA_FEASIBILITY.md` §E |
| Exact STAC IDs, dates, attribution on images | Yes — manifest, captions, footer |
| Independent check of georeferencing and sampled reflectance/NDVI | Yes — max abs difference 0.0 |
| Git checkpoint | Made after this report |

## 13. Limits and non-claims

- Tidal stage, water level and turbidity differ between the two dates and are
  **not controlled**. Part of the negative ΔNDVI may be tidal or atmospheric
  rather than ecological.
- Mixed mangrove/water pixels at 10 m; no species, biomass or health claim.
- The AOI is a hand-placed working window, not an official boundary.
- Global scene cloud is not the decision metric; the manifest stores both the
  scene figure and the measured in-AOI figure so the difference is auditable.
- The ±0.15 threshold summary is descriptive only.
- No causal attribution of the observed difference to any event or policy.
- The Nepal AOIs are approximate (±2 km) and have not been snapped to verified
  shorelines or detachment scars; no damage, volume or routing claims.
- M0 makes no ML, classification or prediction claim.

## 14. Blockers

None for M0. The only material scientific constraint is the D1 observation gap
described in §9; it is a documented limitation, not a blocker.

## 15. Handoff to M1

1. Scene selection already supports a measurement budget and memoised in-AOI
   validity; M1 should extend it to multi-date compositing and per-pixel
   observation counts.
2. The grid/crop logic is single-window; M1 needs configurable AOI chips and a
   documented resampling policy per index.
3. Add NDWI/MNDWI (and gated NDSI/NDBI) on the same mask framework, with
   study-type-aware mask policies.
4. Replace the image-swipe viewer with the M3 map stack once the renderer
   decision is made (`docs/DESIGN_SPEC.md` §8).
5. Carry the manifest schema forward unchanged where possible; downstream
   consumers already depend on `periods`, `delta`, `search` and `outputs`.
