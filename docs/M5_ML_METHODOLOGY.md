# M5-G3 — Supervised machine-learning methodology

**Status:** implemented for the four label-gated studies (Kathmandu,
Western Ghats, Chilika dry, Chilika post-monsoon, plus Coringa
vegetation/water under its PARTIAL gate). Both Himalayan investigations
remain ML-free by design. Independent audit: `scripts/audit_m5_ml.py`
— **107/107 checks**, including bit-for-bit retraining reproducibility.

## 1. Data

### Training imagery (2021 epoch, matched to the label epoch)

Acquired per study through the audited M1 chain (search → in-AOI SCL scoring
→ observation selection → empirical radiometry acceptance → SCL masking →
median composite), one composite per application season:

| Study | Window | Selected observations | Composite |
|---|---|---|---|
| Kathmandu | 2021-02-28..04-30 (anchor 03-30) | 3 (2021-03-26/28, 04-02) | `data/processed/m5_ml/kathmandu_m5_ml/training_2021-03-30_reflectance_composite.tif` |
| Western Ghats | 2021-01-20..03-10 (anchor 02-19) | 3 | …/western_ghats_m5_ml/training_2021-02-19_… |
| Coringa | 2021-02-26..04-25 (anchor 03-26) | 3 | …/coringa_m5_ml/training_2021-03-26_… |
| Chilika dry | 2021-01-18..03-09 (anchor 02-17) | 3 | …/chilika_dry_m5_ml/training_2021-02-17_… |
| Chilika post-monsoon | 2021-10-09..11-29 (anchor 11-08) | 3 | …/chilika_postmonsoon_m5_ml/training_2021-11-08_… |

Provenance manifests: `data/manifests/m5ml_<study>.json`
(schema `habitatshift-m5ml-training/1`: full search report, per-observation
radiometry + evidence, grid, outputs with SHA-256). Frozen M4 artifacts were
not touched; the observation cache is shared, content-addressed and
policy-versioned exactly as in M4.

### Reference labels

ESA WorldCover v200 (2021 epoch, 10 m, CC-BY 4.0), read live per AOI and
nearest-resampled onto each analysis grid. **These are reference-product
labels, not ground truth** — every metric below measures agreement with this
product. Class mappings per study are recorded in each result
(`class_mapping`). Coringa carries no mangrove class: the two authoritative
mangrove inventories disagree inside the AOI (WC-95 = 284 px vs GMW-2020 =
13 px), so none were manufactured.

## 2. Features

Per pixel of the 10 m analysis grid, in a recorded order:

- reflectance: blue, green, red, NIR (native 10 m), SWIR1 (native 20 m,
  bilinearly resampled by the pipeline; recorded as upsampled, never claimed
  native);
- the study's registered indices, recomputed from the composite bands with
  the standard algebra: NDVI, NDWI, MNDWI, NDBI (per study config).

No texture, no coordinates, no ancillary products — deliberately, so the
feature space stays interpretable and comparable with the mathematical
baseline's inputs.

## 3. Spatial split design (no leakage)

The grid is partitioned into contiguous 100-px (1 km) square blocks, and
each block is assigned to one of three folds by the deterministic diagonal
stripe pattern `(row_block + col_block) mod 3` → train / validation / test.

- No pixel is ever split across folds; within-block spatial dependence is
  retained by design.
- Same-fold blocks are separated by at least one full block in the stripe
  direction; there is no random adjacent-pixel mixing.
- Every fold covers the whole AOI geographically, so each is a genuine
  geographic sample of the scene.
- Known consequence (recorded in every result as `design_note`):
  deterministic blocking concentrates rare classes unevenly across folds;
  per-class test support is reported and metrics are **gated** (suppressed,
  not fabricated) below 50 test pixels.

## 4. Model

`sklearn.ensemble.RandomForestClassifier` — 300 trees, `min_samples_leaf=2`,
`max_features="sqrt"`, `class_weight="balanced_subsample"` (the documented
imbalances), `random_state=20261108`, `n_jobs=-1`. Hyperparameters, seed,
software versions (scikit-learn 1.9.1, joblib 1.6.0, numpy 2.2.6) and the
feature list are recorded verbatim in every result; scikit-learn and joblib
are pinned in `backend/requirements.txt`.

## 5. Evaluation — agreement with the reference product, never "accuracy"

On the held-out test fold only: confusion matrix, per-class precision /
recall / F1 / IoU, macro-F1 (over all classes and over supported classes
separately), overall agreement, balanced accuracy. Each result states its own
framing string: *"agreement with the ESA WorldCover v200 reference product on
spatially separated test blocks; NOT independent ground-truth accuracy"*.

Additionally, **geographic generalisation is measured, not assumed**: the
model is retrained three more times, each time holding out a different fold
as the test region, and the agreement spread across the three geographically
different held-out blocks is recorded (`geographic_stability`).

## 6. Application to the mathematical-baseline epochs

The frozen classifier is applied to the existing 2020 and 2025 M4 median
composites (the exact rasters the mathematical findings were computed on).
Outputs per epoch: predicted class fractions over valid pixels, mean
confidence of the predicted class (recorded explicitly as model confidence,
**not** accuracy), and the full prediction raster (`prediction_<tag>.npy`).
The predicted fraction shift between epochs is compared with the
mathematical Δ-index finding — as two independent candidate signals, where
both agreement and disagreement are recorded.

**Cross-epoch assumption (limitation, not a verified fact):** applying a
classifier trained on 2021 imagery to 2020/2025 composites assumes class
spectra are stable across those epochs (sensor S2A/B/C, Sen2Cor versions,
seasonal states matched per application season). This is stated in every
result's guardrails and in `M5_LIMITATIONS.md`.

## 7. Reproduce

```bash
python scripts/run_m5_training_imagery.py     # network: 2021 imagery via the M1 chain
python scripts/run_m5_ml.py                   # trains, evaluates, applies, writes artifacts
python scripts/audit_m5_ml.py                 # independent audit (offline)
```
