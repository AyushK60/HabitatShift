# HabitatShift science protocol

**Version 1.0 (M1).** This protocol governs what HabitatShift computes, how it
reports it, and which claims an output may support. It applies to every M0 and
M1 artefact. When a result and this document disagree, the result is wrong or
the protocol must be revised explicitly — never silently.

---

## 1. First principles

1. **Measured, not assumed.** Every published number must trace to a stored
   artefact and be reproducible from the recorded inputs.
2. **One grid, stated once.** A comparison is valid only on a single documented
   CRS, transform, shape, resolution and NoData convention.
3. **Mask, never fill.** Invalid pixels are excluded, not interpolated across
   time or space.
4. **Difference is not classification.** A spectral difference is a physical
   signal, not a land-cover label or a cause.
5. **Uncertainty is part of the result.** Resolution, confounders, thresholds
   and limitations are reported with the number, not after it.
6. **Fail loudly.** Missing metadata, mismatched grids, uncached offline data
   or failed verification stop the run.

---

## 2. Definitions

| Term | Meaning in this project |
|---|---|
| Observation | One Sentinel-2 L2A item read onto the analysis grid |
| Period | A bounded date window with an anchor date and a selection policy |
| Composite | Per-pixel summary (median by default) of valid observations in a period |
| Valid pixel | Inside AOI **and** accepted SCL class **and** all fetched reflectance bands finite |
| Common-valid footprint | Pixels with a finite index value in **both** periods for that index |
| Candidate change | `|later − earlier| ≥ threshold` at a stated threshold |
| Suitable for comparison | Common-valid footprint ≥ 50 % of AOI (usability gate, not a verdict) |

A **scene** is never treated as a pixel-level truth source. A **composite** is
not a dense time series. A **threshold crossing** is not a change class.

---

## 3. Data and radiometry

- Collection: Sentinel-2 L2A from the documented catalogue
  (`sentinel-2-l2a`, Element 84 Earth Search for the current studies).
- Reflectance: `DN × scale + offset`, with scale and offset read from each
  item's own metadata and verified against the collection definition.
- Baseline 04.00 offset policy: apply the declared `−0.1` offset only when it
  is not already baked into the DNs (`earthsearch:boa_offset_applied`). Never
  double-correct.
- Negative or non-finite reflectance is invalid; it is not clipped into range.
- No independent atmospheric correction is claimed. The provider L2A product
  is the reflectance source.

---

## 4. Masking policy

For the coastal/vegetation profile:

- **Accepted SCL classes:** 2 dark area, 4 vegetation, 5 not vegetated,
  6 water, 7 unclassified, 11 snow/ice.
- **Rejected SCL classes:** 0 no data, 1 saturated/defective, 3 cloud shadow,
  8 cloud medium probability, 9 cloud high probability, 10 thin cirrus.
- Valid = AOI ∩ accepted SCL ∩ finite reflectance.
- Invalid pixels become `NaN` and never enter statistics or compositing.

Any change to this policy is a protocol change and must be recorded in the
manifest and the study documentation. A profile that accepts snow/ice does not
by itself validate glacier-change claims.

---

## 5. Compositing policy

- Reflectance is composited per pixel **before** indices are computed.
- Default method: median. Even counts use the mean of the two central values.
- Only valid observations contribute.
- Every pixel reports its contributing observation count.
- The composite is invalid below the configured minimum count.
- Observations on different grids, shapes or band sets cannot be combined.
- Two periods are compared; extra observations improve robustness but do not
  turn the result into a time series.

---

## 6. Index definitions

All indices are normalised differences on composite surface reflectance:

| Index | Formula | Bands | Native resolution |
|---|---|---|---|
| NDVI | `(NIR − Red) / (NIR + Red)` | B08, B04 | 10 m |
| NDWI (McFeeters) | `(Green − NIR) / (Green + NIR)` | B03, B08 | 10 m |
| MNDWI (Xu) | `(Green − SWIR1) / (Green + SWIR1)` | B03, B11 | 20 m |
| NDSI | `(Green − SWIR1) / (Green + SWIR1)` | B03, B11 | 20 m |
| NDBI | `(SWIR1 − NIR) / (SWIR1 + NIR)` | B11, B08 | 20 m |

Rules:

- denominator magnitude below `1e-6` → `NaN`;
- non-finite input → `NaN`;
- missing band → hard error;
- shape mismatch → hard error;
- SWIR-based indices computed on the 10 m grid must be labelled
  `upsampled: true` and must state that they contain no genuine 10 m SWIR
  detail.

NDSI and NDBI are tested primitives. They must not be interpreted as glacier or
urban change without a separate, validated study.

---

## 7. Change and area rules

- `delta = later − earlier`; invalid wherever either period is invalid.
- Thresholds classify `delta ≤ −t` (decrease), `−t < delta < t` (stable),
  `delta ≥ t` (increase). Boundaries are inclusive.
- Report every configured threshold, not only the primary one.
- Report the common-valid footprint in pixels, hectares and square kilometres.
- Area = projected pixel area × pixel count. Hectares = m² / 10 000;
  square kilometres = m² / 1 000 000.
- Percentages of decrease/increase are relative to the common-valid footprint,
  and must say so.
- Report an independent projected/geodesic/raster area cross-check.
- Never present a single threshold's area as *the* amount of change without the
  sensitivity table.

---

## 8. Claim taxonomy

Use these levels explicitly.

### Level 0 — observation

> "Scene X was acquired on date D and read on grid G."

### Level 1 — measured index

> "The median-composite NDVI over the common-valid footprint was 0.5199 in the
> earlier period and 0.4994 in the later period."

### Level 2 — measured difference

> "At threshold |ΔNDVI| ≥ 0.15, 192.91 ha decreased and 143.98 ha increased on
> the 1,651.36 ha common-valid footprint."

### Level 3 — candidate interpretation (requires explicit caveats)

> "The pattern is consistent with a vegetation-change hypothesis, but tide,
> turbidity, phenology and atmosphere are uncontrolled."

### Forbidden — unsupported assertion

> "192.91 ha of mangrove was lost."
> "The wetland was restored."
> "Construction expanded."
> "Glacier area declined."
> "The delta is degrading."

Level 3 must never be written without the confounder sentence. Forbidden
assertions are never written.

---

## 9. Required provenance

Every run must record:

- study ID, title, question and AOI geometry;
- analysis CRS, transform, shape, resolution, pixel area and grid signature;
- catalogue endpoint, collection, licence and access date;
- each period's search window, request body, returned/accepted counts, scores
  and selected item IDs with dates;
- per-item scale, offset, offset decision and reason;
- SCL policy, composite method, observation bounds and counts;
- index formulas, bands and native resolution;
- thresholds, area convention and area cross-check;
- software versions, pipeline version and verification results;
- relative paths, byte sizes and SHA-256 hashes for every output;
- limitations.

A result without this record is not publishable.

---

## 10. Verification requirements

A run is acceptable only when:

1. the engine's post-export verification passes every check;
2. `verification/audit_m1.py` independently re-derives the headline numbers and
   passes every check;
3. the offline rebuild produces byte-identical rasters on the same stack;
4. the manifest hashes match the files on disk;
5. the viewer's displayed numbers match the summary;
6. no test in the offline or live suite fails.

Any failure blocks publication of that run.

---

## 11. Review checklist

Before a number leaves the repository, confirm:

- [ ] The AOI and grid are stated, including resolution and native resolution.
- [ ] The exact scenes, dates and observation counts are listed.
- [ ] The composite method and minimum observation rule are stated.
- [ ] The masking policy is stated.
- [ ] The index formula and band identities are stated.
- [ ] The common-valid footprint is stated in px, ha and km².
- [ ] The threshold, or the full sensitivity table, is stated.
- [ ] Areas are projected, not degree-derived.
- [ ] The claim level is explicit and no forbidden assertion is present.
- [ ] Confounders and limitations are adjacent to the number.
- [ ] The manifest and hashes are available.
- [ ] No M0 artefact was silently altered.

---

## 12. Change control

- M0 results, scene IDs, grid and viewer fallback remain frozen unless a
  documented reason and a re-verification are supplied.
- A change to radiometry, masking, compositing, indices, thresholds or area
  conventions is a protocol change: bump the pipeline version, update this
  document, re-run verification and record the cause in
  `M1_NUMERICAL_AUDIT.md` or its successor.
- A numerical change caused by a bug fix must be shown to be a fix, with the
  before/after values and the reason. Silent numerical drift is a defect.

## 13. M2 experiment protocol

M2 research experiments are consumers of frozen M0/M1 artefacts and obey
these rules:

1. **Hypotheses before results.** Every experiment YAML states at least two
   hypotheses with the measurement that answers each. The runner copies them
   verbatim into the result; verdicts are computed only from measured
   numbers and are labelled `supported`, `not_supported` or `inconclusive`.
2. **Frozen inputs.** Experiments read the M1 summary/rasters, the M0
   summary/raster and the observation cache; recorded input hashes must
   match at run time and are verified again by the audit. No imagery is
   downloaded and no M0/M1 artefact is modified.
3. **Fixed classification rule.** Decrease `Δ ≤ −t`, increase `Δ ≥ +t`,
   stable otherwise, on the common-valid footprint; classes must partition
   the footprint exactly (0-pixel residual) at every threshold and
   estimator, and the sweep must be monotone.
4. **Area discipline.** Areas derive from integer pixel counts on the
   documented grid (100 m² per 10 m pixel) in hectares and km²; every table
   row carries its own conservation check.
5. **Estimator honesty.** A difference between estimators is an
   observation-selection effect, never a processing regression. The M0
   single-scene raster and the M1 anchor must agree on shared pixels; the
   cross-pipeline comparison records that agreement.
6. **Uncertainty vocabulary.** Threshold sweeps are sensitivity ranges.
   Block-bootstrap intervals are resampling variability for this AOI and
   grid, with stated exchangeability assumptions. Neither is a confidence
   interval about the landscape, and neither validates a threshold.
7. **Supervised claims.** No accuracy, F1, confusion matrix or
   feature-importance number may appear unless it comes from genuine
   held-out independent reference labels with documented provenance and
   spatial separation. When labels are unavailable the run records the
   blocked status and contains none of those keys (enforced by tests and by
   the audit).
8. **Reproducibility.** Runs are content-addressed (fingerprint over the
   canonical config plus every input hash); reruns are served from the
   recorded run; nothing is overwritten. Charts are generated
   deterministically from measured arrays.
9. **Viewer honesty.** The Experiments section displays recorded values
   verbatim via the API; it never recomputes, and a missing run produces an
   explicit empty state.
