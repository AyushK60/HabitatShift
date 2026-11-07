# M2 — Research experiments: methods and measured results

**Study:** `coringa_coastal` · **Experiment:** `coringa_m2`
**Recorded run:** `20261107T102819Z_d70f3978` (fingerprint `d70f3978…`,
git commit recorded in `manifest.json`)
**Inputs:** frozen M1 bundle (`data/processed/m1/coringa_coastal`), frozen M0
bundle, content-addressed observation cache (3 earlier + 3 later Sentinel-2
L2A observations). No imagery was downloaded; no M0/M1 artefact was modified.

Reproduce:

```powershell
.\.venv\Scripts\python.exe scripts\run_experiment.py --config studies\experiments\coringa_m2.yaml
# independent audit:
.\.venv\Scripts\python.exe scripts\audit_m2.py
```

An unchanged rerun is served from the recorded run directory (content
fingerprint over the canonical config plus every input hash). A `--force`
rerun creates a NEW timestamped directory; nothing is ever overwritten.

---

## 1. Hypotheses (registered before execution)

The hypotheses below are stored verbatim in the experiment YAML and copied
into `result.json`, so they cannot be edited after the numbers are known:

- **H1 (threshold sensitivity)** — candidate-change area decreases
  monotonically as the threshold tightens 0.05 → 0.25, and the ranking of the
  three indices by candidate-change fraction is stable across the sweep.
- **H2 (composite vs single scene)** — the 3×3-observation median composite
  yields a smaller absolute mean delta than the single-scene pairs.
- **H3 (temporal robustness)** — leave-one-out composites shift the
  candidate-change fraction less than the spread across single-scene pairs.
- **H4 (cross-pipeline consistency)** — the frozen M0 single-scene NDVI delta
  and the M1 anchor single-scene delta agree on the shared valid footprint.
- **H5 (validity role)** — the common-valid footprint is complete, so
  estimator differences come from observation selection, not validity masks.

## 2. Design

- **Grid:** 429 × 390 px, EPSG:32644, 10 m (100 m² per pixel); AOI
  165,136 px = 1,651.36 ha; common-valid fraction 100 % for all indices.
- **Index definitions** are unchanged from M1: NDVI = (B08−B04)/(B08+B04),
  NDWI = (B03−B08)/(B03+B08), MNDWI = (B03−B11)/(B03+B11) on surface
  reflectance; compositing is median reflectance then index (not median of
  indices).
- **Classification rule** is fixed and symmetric: decrease
  `Δ ≤ −t`, increase `Δ ≥ +t`, stable otherwise; classes partition the
  common-valid footprint exactly (checked at every threshold and estimator).
- **Estimators** (55 surfaces = 19 NDVI, 18 NDWI, 18 MNDWI):
  median composite, mean composite, anchor single pair, 3×3 = 9 single-scene
  pairs, 6 leave-one-out composites per index, plus the frozen M0 NDVI raster.
- **Thresholds:** 0.05, 0.10, 0.15, 0.20, 0.25 (primary 0.15).
- **Uncertainty:** spatial block bootstrap, 15 px (150 m) blocks,
  200 resamples, seed 20260326.

## 3. Measured results — primary median composite

Mean Δ (later − earlier) on the common-valid footprint reproduces the M1
headline exactly: NDVI **−0.020471**, NDWI **+0.018959**, MNDWI
**−0.006188**.

### Threshold response (candidate-change fraction of the 1,651.36 ha footprint)

| Index | t | decrease ha (%) | stable (%) | increase ha (%) |
|---|---|---|---|---|
| NDVI | 0.05 | 626.71 (37.95) | 38.18 | 394.13 (23.87) |
| NDVI | 0.10 | 347.71 (21.06) | 64.73 | 234.75 (14.22) |
| NDVI | 0.15 | 192.91 (11.68) | 79.60 | 143.98 (8.72) |
| NDVI | 0.20 | 113.45 (6.87) | 87.67 | 90.16 (5.46) |
| NDVI | 0.25 | 72.12 (4.37) | 92.25 | 55.81 (3.38) |
| NDWI | 0.05 | 373.38 (22.61) | 40.16 | 614.77 (37.23) |
| NDWI | 0.10 | 212.87 (12.89) | 67.69 | 320.69 (19.42) |
| NDWI | 0.15 | 126.12 (7.64) | 82.53 | 162.45 (9.84) |
| NDWI | 0.20 | 77.31 (4.68) | 89.83 | 90.59 (5.49) |
| NDWI | 0.25 | 48.19 (2.92) | 93.76 | 54.85 (3.32) |
| MNDWI | 0.05 | 679.16 (41.13) | 29.24 | 489.37 (29.63) |
| MNDWI | 0.10 | 418.89 (25.37) | 54.63 | 330.26 (20.00) |
| MNDWI | 0.15 | 218.97 (13.26) | 73.03 | 226.40 (13.71) |
| MNDWI | 0.20 | 104.10 (6.30) | 84.40 | 153.58 (9.30) |
| MNDWI | 0.25 | 52.96 (3.21) | 90.66 | 101.24 (6.13) |

Area conservation holds for every row (0-pixel residual, percent residual
0.0). Monotonicity holds for every index. The decrease-fraction ranking
MNDWI > NDVI > NDWI is preserved between t = 0.05 and t = 0.15.

**These are sensitivity ranges, not environmental verdicts.** A "decrease" is
a pixel whose index difference crosses an arbitrary symmetric threshold; it
is not deforestation, water loss, or any other causal label.

## 4. Estimator comparison at t = 0.15 (NDVI)

| Family | Estimator | mean Δ | decrease % | increase % |
|---|---|---|---|---|
| composite | median (M1 headline) | −0.0205 | 11.68 | 8.72 |
| composite | mean | −0.0241 | 13.53 | 10.63 |
| anchor_single | 2020-03-26 × 2025-03-25 | −0.0877 | 42.76 | 15.16 |
| single_pairs (9) | all date pairs | −0.0877 … +0.0528 | 9.17 … 42.76 | 8.26 … 22.88 |
| leave_one_out (6) | median minus one obs | −0.0514 … −0.0018 | 11.16 … 18.12 | 10.26 … 16.28 |
| m0_single_scene | frozen M0 raster | −0.0877 | 42.77 | 10.49 |

Key measured findings:

1. **Composite vs single scene (H2 supported):** the single-pair mean deltas
   span −0.0877 to +0.0528 (range 0.1405); the median composite sits at
   −0.0205, well inside that spread. Single-scene estimates are dominated by
   per-scene observation differences (tide state, sun angle, atmosphere), not
   by change of the landscape.
2. **Leave-one-out stability (H3 supported):** removing any single
   observation shifts the decrease fraction by at most 6.44 percentage
   points from the composite value, while the single-pair spread is 33.59
   points at t = 0.15. The composite design, not any individual scene, drives
   the headline.
3. **Cross-pipeline identity (H4 supported):** the M0 raster and the M1
   anchor single-scene delta are **identical on all 158,168 shared pixels**
   (max |difference| = 0.0), with only a 22-pixel footprint difference from
   mask policy. This isolates the composite/observation-selection effect from
   any processing regression: M0's larger "decrease" (42.77 % vs 11.68 %) is
   an estimator difference, not an error.
4. **Validity (H5 supported):** coverage is 100 % for every period and index;
   estimator differences in this study cannot be attributed to mask
   disagreement.

## 5. Hypothesis verdicts

All five hypotheses were evaluated by the runner strictly from measured
numbers: **H1–H5 supported** (see `result.json → hypothesis_verdicts` for the
evidence attached to each verdict).

## 6. Machine-learning status

**No supervised result exists in this milestone.** The label-feasibility
audit (`M2_LABEL_FEASIBILITY.md`) found no independent label source covering
the 2025 period; the supervised path is recorded as blocked in the experiment
config and no accuracy/F1/confusion-matrix key exists anywhere in the result
(tests and the audit both enforce this).

## 7. Research package

Each run directory contains:

- `result.json` — full measured payload (schema `habitatshift-m2-result/1`);
- `manifest.json` — fingerprint, git commit, software versions, input hashes,
  artifact hashes (schema `habitatshift-m2-manifest/1`);
- `estimator_thresholds.csv` — 275 rows (55 estimators × 5 thresholds);
- `threshold_sensitivity.csv` — 15 rows (primary composite);
- `charts/threshold_response.svg`, `charts/delta_histogram_<index>.svg`,
  `charts/estimator_comparison_<index>.svg`, `charts/bootstrap_<index>.svg`
  — generated deterministically from the measured arrays (regenerating a run
  reproduces the SVGs byte for byte);
- `audit_m2_results.json` — written by `scripts/audit_m2.py` after the run.

The viewer's Experiments section reads these via
`/api/experiments/coringa_m2/latest` and displays values verbatim; it never
recomputes.
