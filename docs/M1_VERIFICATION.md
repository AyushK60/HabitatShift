# M1 verification record

**Verdict.** The M1 implementation is verified on real Sentinel-2 L2A data,
reproducible offline, and checked by two independent mechanisms: the engine's
own post-export verification and a separate audit script that does not import
the engine. No test, check or audit below failed.

All commands are run from the repository root on Windows PowerShell with the
project virtual environment.

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m "not live"
.\.venv\Scripts\python.exe -m pytest -q -m live
.\.venv\Scripts\python.exe scripts\run_study.py --config studies\experiments\coringa_m1.yaml --offline
.\.venv\Scripts\python.exe scripts\audit_m1.py --study coringa_coastal
```

---

## 1. Test suite

| Suite | Result |
|---|---|
| Offline (`pytest -q -m "not live"`) | **230 passed** |
| Live catalogue (`pytest -q -m live`) | **6 passed** |

The offline suite uses synthetic arrays and local synthetic GeoTIFFs only. It
covers, among other things:

- radiometry: scale/offset application, baseline-04.00 offset resolution,
  baked-in offset suppression, missing/incorrect metadata rejection;
- cross-baseline radiometry: the same pixel value under different baselines is
  not silently treated as the same reflectance;
- NoData and SCL masking: cloud, shadow, cirrus, saturated and nodata removal,
  AOI clipping, finite-reflectance mask;
- reprojection: WGS84 source onto the UTM analysis grid;
- resampling policy: bilinear reflectance, nearest categorical mask, and a
  test proving bilinear would corrupt categorical classes;
- index formulas: known values, division by zero, NaN invalids, negative
  reflectance rejection, missing bands, shape mismatch, registry metadata;
- temporal compositing: odd/even median, mean, observation counts, minimum
  observation rule, grid/shape/band-set mismatch, all-masked periods, cloud
  coverage change, cache-key determinism;
- change analysis: shared-valid intersection, difference maps, inclusive
  threshold boundaries, directional counts, quantiles, area conservation,
  unit conversion, percentage-of-common validity, threshold sensitivity;
- configuration: required fields, unknown indices, invalid bounds, inverted
  windows, bad thresholds, missing files, unknown studies;
- manifest: schema validation, required sections, period scene/date
  requirements, output-record hashing, byte-size records, tamper detection;
- previews: invalid colour, index ramps, difference sign colours, saturation,
  observation-count ordering, legend JSON;
- API: health, study discovery, summary/status/layers/indices/change/
  provenance, file serving, traversal guard, unknown study, missing artefact;
- engine stages: selection, anchor-window fallback, distinct-date rule,
  minimum observations, bounded reads, cache round-trip, corrupt-cache
  fallback, offline cache miss, corrupt raster, deterministic repeat reads,
  grid checks, area cross-check.

Live tests are limited to the catalogue/network boundary; they do not assert
science numbers.

---

## 2. Engine verification (26/26)

`run_study.py` re-opens every exported artefact and performs 26 checks. The
summary and manifest both record `all_passed: true`, `check_count: 26`,
`failed_checks: []`.

| Group | Checks | What is checked |
|---|---|---|
| Grid georeferencing | 12 | Every period raster (reflectance, valid mask, count, 3 indices) matches the window's CRS, shape, transform and grid tag |
| Observation counts | 2 | `count > 0` exactly matches the valid mask; counts stay within configured bounds; maximum is 3 |
| Index recomputation | 6 | Each index is recomputed on a deterministic 400-pixel sample and compared with the exported GeoTIFF; masked pixels must be NaN; native-resolution metadata must match |
| Delta recomputation | 3 | `later − earlier` on a deterministic sample matches the exported delta |
| Threshold counts | 3 | Decrease/increase/valid pixel counts match the exported arrays; thresholded classes conserve the valid area |

All sampled differences were `0.0` in the recorded run.

---

## 3. Independent audit (22/22)

`scripts/audit_m1.py` deliberately does **not** import the processing engine.
It re-derives the numbers from the written files:

| Check | Result |
|---|---|
| Manifest output hashes and byte sizes | PASS |
| All GeoTIFFs share one CRS/shape/transform | PASS |
| Grid matches `summary.json` | PASS |
| Index recomputation (earlier: NDVI/NDWI/MNDWI) | PASS |
| Index recomputation (later: NDVI/NDWI/MNDWI) | PASS |
| Observation count matches valid mask (earlier, later) | PASS |
| Valid fraction equals valid pixels / AOI pixels | PASS |
| Delta recomputation (NDVI/NDWI/MNDWI) | PASS |
| Threshold counts, areas, conservation, percentages | PASS |
| Area cross-check (projected vs geodesic vs raster) | PASS |
| Summary/manifest scene and grid agreement | PASS |
| Engine verification flag agrees in summary and manifest | PASS |

**22 checks, all passed.** The audit exits `0` only when every check passes.

---

## 4. Offline reproducibility

The real run was executed online, then rebuilt with `--offline` from the local
catalogue and observation caches.

- **21 GeoTIFF rasters** were hashed before and after the offline rebuild.
- The file set was identical.
- **Every SHA-256 hash was byte-identical.**

```
hash before: 21 rasters
offline run: exit 0, verification 26/26
same names: True
differing rasters: []
```

The committed manifest is the offline rebuild: it records
`http_requests: 0`, `bytes_downloaded: 0`, and stage timings around 2 s. This
is deliberate — it demonstrates that the published bundle can be regenerated
without network access from the cached source data. The online run produced the
same rasters.

`--offline` is not a silent fallback: a missing observation cache entry raises
`ObservationCacheMiss` and stops the run.

---

## 5. Manifest integrity

- Every output record is written with path, kind, byte count and SHA-256.
- The audit re-hashes all recorded outputs; none differed.
- The manifest is validated against the M1 schema before it is written; an
  incomplete manifest is rejected rather than published.
- Scene IDs, observation dates and grid signature agree between
  `summary.json` and the manifest.

Summary record counts:

| Document | Output records |
|---|---|
| `summary.json` (`outputs`) | 51 |
| `m1_coringa_coastal.json` (`outputs`) | 53 |

The manifest additionally records `summary.json` and `summary.csv`, which are
written by the same final stage and therefore are not present in the summary's
own output map.

---

## 6. Browser verification

The M1 viewer was served from `http://127.0.0.1:8095/` and checked in the
in-app browser.

| Check | Result |
|---|---|
| Page loads M1 bundle, not M0 fallback | PASS |
| All 10 layer buttons render and switch | PASS |
| All layer previews return images (`naturalWidth > 0`) | PASS |
| All legends load for NDVI, NDWI, MNDWI, Δ layers, observation count | PASS |
| Console errors | none |
| Network responses with status ≥ 400 | none (25 `/files/` requests) |
| Facts panel values match `summary.json` | PASS |
| Meta panel dates, scenes, counts and index means match | PASS |
| Notes panel threshold/area values match summary for all three indices | PASS |
| "Limited comparison" banner hidden when all indices suitable | PASS |

Displayed and verified values included `EPSG:32644`, `10 m`,
`429 × 390 px`, `16.516 km²`, `3 / 3` observations, `100.0 %` worst-index
common-valid coverage, and threshold-0.15 areas of `192.91 / 143.98 ha`
(NDVI), `126.12 / 162.45 ha` (NDWI) and `218.97 / 226.40 ha` (MNDWI).

A screenshot could not be captured because the browser tool requires a visible
desktop tab ("Screenshot needs a visible tab"). The DOM/network verification
above is the available evidence; no screenshot is claimed.

---

## 7. What is not verified

- No independent field or high-resolution reference data was available, so no
  index value is validated against ground truth.
- Tidal stage, turbidity and phenology are not controlled; the comparison is
  seasonally matched, not physically matched.
- The provider SCL product is trusted for cloud/shadow/cirrus screening; it is
  not re-derived.
- Atmospheric correction is the provider L2A product; it is not independently
  recomputed.
- No claim is made that a threshold crossing corresponds to a specific land
  cover transition.

These are scientific limits, not implementation failures. They are expanded in
[`M1_LIMITATIONS.md`](M1_LIMITATIONS.md).
