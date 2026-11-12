# M2 — Uncertainty, sensitivity and robustness

**Run:** `20261107T102819Z_d70f3978` · **Study:** `coringa_coastal`

This document describes every uncertainty quantity M2 measures, what it does
and does not assert, and where each is recorded. Nothing here is a
fabricated confidence statement; every number is computed from stored arrays
by documented procedures.

---

## 1. Cloud / observation coverage

Measured (`result.json → coverage`):

- Both periods contain 3 observations (earlier: 2020-03-26/21/31; later:
  2025-03-25/30/2025-04-01).
- Per-period valid pixels equal the full AOI (165,136 px = 1,651.36 ha);
  common-valid fraction of the AOI is 100 % for NDVI, NDWI and MNDWI.
- Per-pixel observation counts and their histograms come from the M1
  observation-count rasters; the viewer's Quality mode displays them.
- Excluding lower-quality observations is exercised structurally by the
  leave-one-out estimators (each removes one observation and reports the
  full threshold sweep), rather than by re-picking scenes.

A uniform 100 % footprint is a property of this study's cloud masking, not a
defect and not a manufactured result.

## 2. Threshold uncertainty (sensitivity, not confidence)

The threshold sweep (0.05 → 0.25) is a deterministic sensitivity analysis of
candidate-change area to an analysis parameter. Measured response for the
primary median composite (decrease / increase, % of common-valid):

| Index | 0.05 | 0.10 | 0.15 | 0.20 | 0.25 |
|---|---|---|---|---|---|
| NDVI | 37.95 / 23.87 | 21.06 / 14.22 | 11.68 / 8.72 | 6.87 / 5.46 | 4.37 / 3.38 |
| NDWI | 22.61 / 37.23 | 12.89 / 19.42 | 7.64 / 9.84 | 4.68 / 5.49 | 2.92 / 3.32 |
| MNDWI | 41.13 / 29.63 | 25.37 / 20.00 | 13.26 / 13.71 | 6.30 / 9.30 | 3.21 / 6.13 |

The candidate-decrease area at t = 0.05 is roughly nine times the value at
t = 0.25 for NDVI. No threshold in this sweep is "correct"; the sweep exists
so no single number can be quoted without its parameter.

## 3. Temporal robustness (observation selection)

Recorded per index (`temporal_robustness`), across the 17 temporal
estimators (2 composites + 1 anchor + 9 single pairs + 6 leave-one-out, with
the M0 raster separate). For NDVI decrease-fraction at t = 0.15:

- min 9.17 %, max 42.76 %, range 33.59 points, mean 16.30 %, std 7.64.
- Leave-one-out composites stay within 6.44 points of the composite value —
  an order of magnitude narrower than the single-pair spread.

Interpretation: **observation selection, not landscape change, dominates
single-scene estimates at this tidal site.** The M1 median-composite design
reduces that variance rather than amplifying it.

## 4. Spatial block bootstrap

Design (documented in code and in `result.json → uncertainty`):

- The grid is partitioned into contiguous 15 px (150 m) square blocks
  (754 total, all containing valid data).
- Blocks are resampled with replacement (200 iterations, seed 20260326);
  within-block spatial dependence is retained, between-block dependence is
  ignored.
- The valid mask and thresholds are held fixed; only area fractions of the
  fixed classes and the mean delta are resampled.

Measured 95 % percentile intervals for NDVI at t = 0.15:
decrease fraction 0.106–0.127 (point 0.117); increase fraction
0.078–0.098 (point 0.087). For comparison the pixel-independent binomial
approximation (±1.96·√(p(1−p)/n)) is also recorded and is demonstrably
narrower — it understates spatial dependence and is shown only to make that
point.

**What this interval is:** the resampling variability of an area fraction
for this AOI, this grid and this classification. **What it is not:** a
confidence interval for mangrove extent, a validation of the threshold, or a
statement about any other site.

## 5. Interpretation limitations (mandatory context)

Recorded verbatim in `result.json → interpretation_guardrails` and displayed
in the viewer:

- Candidate-change areas are threshold-dependent descriptions of index
  difference, not verified environmental change.
- For Coringa, an NDVI decrease is not evidence of mangrove loss: tides,
  seasonality, sun-angle differences and mixed pixels can produce the same
  signal. The 2020 and 2025 anchor scenes differ in tidal state.
- Cloud masking relies on the provider SCL product; terrain shadow is not
  independently re-derived.
- Surface reflectance is the provider L2A product; no independent
  atmospheric correction is performed.
- Areas are planimetric on the documented grid; UTM scale distortion is
  small but nonzero.
- No independent reference labels exist for this AOI and period
  (`M2_LABEL_FEASIBILITY.md`); nothing in M2 may be quoted as accuracy.

## 6. What would strengthen the uncertainty story (future work)

- A formal spatial model (e.g., block sizes swept over a range) to test
  sensitivity of the bootstrap interval to block choice.
- Tide-height covariates for each acquisition date, to separate tidal from
  vegetation signals in the creek cells.
- Independent labels (see the feasibility audit) to convert sensitivity
  ranges into error rates.
