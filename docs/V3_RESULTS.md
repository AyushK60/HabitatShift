# Version 3 results (working notes, preliminary)

Status: five forest areas evaluated against a reference, with two foundation models, plus a noise check on twelve areas.
This is a partial answer to the research question: forest loss only. Numbers come from `data/experiments/v3_fm/` and
can be regenerated with the scripts named below.

## Question

Do change scores from a geospatial foundation model detect real surface change better than spectral indices, when
every method is judged against the same scene-to-scene noise?

## How scores are made

Each scene becomes one feature vector per 16 x 16 pixel patch (160 m): a single index, five indices together, six raw
bands, or an embedding from one of two models. Change is the distance between the earlier and later period means. The
noise comes from pairs of scenes in the same period, so the same calibration works for vectors of any length
(`backend/app/foundation/compare.py`). Unsigned scores cannot say whether a change is a gain or a loss, so a signed
NDVI-decrease baseline is added for forest loss.

Models:
- **Prithvi-EO-2.0-300M** (NASA/IBM, Apache-2.0), six bands, 1024 numbers per patch.
- **SSL4EO-S12 ResNet-50, RGB only** (CC-BY 4.0), layer-3 features, 1024 numbers per patch. A deliberately light
  baseline: it sees no infrared bands. The 13-band SSL4EO models were not used because only six L2A bands were
  fetched.

## Forest loss against Hansen

Reference: Hansen Global Forest Change v1.12 (2000-2024), CC-BY 4.0. Agreement with another satellite product, not
accuracy. Plantation clearing, thinning and burning can all appear as "loss".

Design fixed before any score was seen (`scripts/run_fm_evaluation.py`): eligible patch = at least 50% forest;
positive = at least 10% of the patch lost in 2022-2024; clean negative = under 2% lost in 2021-2024; patches between
are set aside. Uncertainty: spatial block bootstrap (1.28 km blocks, 500 resamples), paired against the signed NDVI
baseline. Earlier scenes February to March 2021, later scenes February to March 2025, three scenes each, all fully
valid.

| | Bastar, Chhattisgarh (19.22 N, 81.17 E) | Odisha (19.83 N, 83.87 E) |
|---|---|---|
| Eligible / positive / clean negative patches | 2,239 / 446 / 1,429 | 1,308 / 301 / 781 |
| Base rate (random score) | 0.238 | 0.278 |

Average precision of the noise-calibrated score (ROC-AUC in brackets):

| Score | Bastar | Odisha |
|---|---|---|
| NDVI decrease (signed) | 0.716 (0.835) | 0.758 (0.839) |
| Six raw bands | 0.708 (0.851) | 0.563 (0.761) |
| Prithvi | 0.689 (0.876) | 0.555 (0.795) |
| SSL4EO ResNet-50 RGB | 0.658 (0.834) | 0.506 (0.748) |
| NDVI (unsigned) | 0.617 (0.784) | 0.533 (0.734) |
| NDWI | 0.608 (0.737) | 0.707 (0.830) |
| Five indices together | 0.468 (0.642) | 0.556 (0.730) |

Paired difference from the signed NDVI baseline (95% interval; * means the interval excludes zero):

| Score | Bastar, average precision | Odisha, average precision |
|---|---|---|
| Prithvi | -0.105 to +0.050 | -0.308 to -0.116 * |
| SSL4EO ResNet-50 RGB | -0.135 to +0.017 | -0.351 to -0.155 * |
| Six raw bands | -0.082 to +0.056 | -0.294 to -0.106 * |

Reading:
- In neither of these first two areas does a foundation model beat the signed NDVI baseline. In Bastar they are not
  distinguishable; in Odisha both are clearly worse. Three further areas follow below with the same result.
- Prithvi is not better than plain raw bands in either area. The RGB-only ResNet is about as good as Prithvi, so the
  infrared bands and the larger model add little here.
- Both models and both areas share a pattern at the fixed rule z > 3: embeddings catch more real loss but flag many
  more clean patches (Bastar: Prithvi 48% recall at 5.6% false positives, signed NDVI 24% at 0.6%; Odisha: Prithvi
  60% at 20%, signed NDVI 37% at 1.8%). At a matched false-positive rate the signed NDVI baseline is at least as good.
- Noise calibration (z against raw distance D) does not change the ranking. What it gives is a threshold that means
  the same thing across methods, and even that only partly holds in Odisha.
- The ordering is stable when positives include 2021, or when the cut-off is 5% or 20%.


### Three further forest areas (pre-registered)

Added to test whether the Bastar and Odisha result holds in other forest types. The areas, the inclusion rule and the
seasonal windows were written down in `studies/forest_expansion_prereg.yaml` before any score was computed; the
evaluation script is unchanged.

- Four regions were registered: Kodagu and Wayanad (moist evergreen forest and plantations, Western Ghats), Garo Hills
  (hill forest with shifting cultivation, Meghalaya), Nepal Terai near Chitwan (sal forest) and the Shivalik foothills
  (Uttarakhand).
- An area is evaluated only if the Hansen labels alone give at least 150 positive and 300 clean-negative patches and
  three fully valid scenes exist in each period.
- The four boxes centred on the stated points all failed that screen (2, 29, 2 and 3 positives): an arbitrary 8 km box
  of forest holds little recent clearing. The registration was then amended (Amendment 1), still before any scene or
  score, so that each box is the one with the most positive patches in a 0.4 degree window, chosen from labels only
  (`scripts/select_forest_boxes.py`, `studies/forest_expansion_selected.json`).
- Kodagu (171), Garo Hills (426) and Shivalik (273) passed. Chitwan's best box had 40 positives, so it failed and is
  not evaluated; it was not replaced.
- Because of this selection the boxes, like Bastar and Odisha, over-represent active clearing.

| Area | Eligible patches | Positive | Clean negative | Base rate |
|---|---|---|---|---|
| Kodagu | 2,276 | 174 | 1,951 | 0.082 |
| Garo Hills | 2,415 | 427 | 1,410 | 0.232 |
| Shivalik | 1,747 | 273 | 1,262 | 0.178 |

Average precision of the noise-calibrated score (ROC-AUC in brackets) and the paired difference from the signed NDVI
baseline (95% interval; * excludes zero):

| Score | Kodagu, AP (AUC); paired difference | Garo Hills, AP (AUC); paired difference | Shivalik, AP (AUC); paired difference |
|---|---|---|---|
| NDVI decrease (signed) | 0.542 (0.915); baseline | 0.552 (0.782); baseline | 0.772 (0.902); baseline |
| Six raw bands | 0.550 (0.925); -0.020 to +0.049 | 0.503 (0.726); -0.113 to +0.027 | 0.188 (0.471); -0.636 to -0.506 * |
| Prithvi | 0.516 (0.911); -0.097 to +0.043 | 0.480 (0.776); -0.111 to -0.030 * | 0.638 (0.898); -0.226 to -0.043 * |
| SSL4EO ResNet-50 RGB | 0.220 (0.758); -0.405 to -0.230 * | 0.307 (0.659); -0.276 to -0.209 * | 0.612 (0.893); -0.261 to -0.073 * |
| NDVI (unsigned) | 0.534 (0.915); -0.018 to -0.001 * | 0.281 (0.536); -0.307 to -0.231 * | 0.124 (0.319); -0.707 to -0.544 * |
| NDWI | 0.508 (0.897); -0.063 to -0.005 * | 0.203 (0.405); -0.386 to -0.302 * | 0.123 (0.309); -0.708 to -0.544 * |
| Five indices | 0.518 (0.906); -0.066 to +0.015 | 0.261 (0.518); -0.330 to -0.244 * | 0.155 (0.442); -0.672 to -0.526 * |

Reading:
- No foundation model beats the signed NDVI baseline in any of the five areas. Prithvi ties it in Bastar and Kodagu and
  is clearly worse in Odisha, Garo Hills and Shivalik. SSL4EO is clearly worse in four areas.
- Prithvi is not better than raw bands in four of five areas. Shivalik is the exception, because raw bands and
  indices score near chance there (raw bands AUC 0.47). A possible cause is that the leaf state of deciduous sal forest
  in February to March differs between years; this was not tested.
- Kodagu has a low base rate (0.082), so its AP values are low in absolute terms but well above chance.

## Glacial lakes against Sentinel-1 radar

`scripts/fm_make_study.py --lake`, `scripts/fm_lake_reference.py`, `scripts/run_fm_lake_evaluation.py`.

Areas: Tsho Rolpa, Imja Tsho and Thulagi (the pilot lakes). Optical scenes October to November 2018 against 2024. The
2018 window had only one clear scene per lake, so the noise scale comes from the three later scenes only.

Reference: change in Sentinel-1 water frequency per 160 m patch between the two periods (radar scenes within 20 days of
each window, usable orbits only). Radar is a different sensor from the optical data under test, so this is not
circular, but it has its own errors (it underestimates some lakes). Agreement, not accuracy.

Design fixed before scores were seen: patches within about 1 km of the lake; positive = at least 25% of the patch
changed water state; clean negative = under 5%; patches between set aside; unsigned scores, because lakes can grow or
shrink; spatial block bootstrap, paired against MNDWI.

Radar shows real change at only one lake: Imja Tsho grew from about 1.09 to 1.66 km2 between the periods, while
Tsho Rolpa (1.38 to 1.42) and Thulagi (0.71 to 0.69) stayed put. The 44 positives are 34 at Imja, 6 at Thulagi and 4
at Rolpa, so this is effectively a test on one growing lake, and the intervals are wide.

Average precision (ROC-AUC) of the noise-calibrated score, base rate 0.055:

| Score | Average precision | ROC-AUC |
|---|---|---|
| Six raw bands | 0.755 | 0.905 |
| Prithvi | 0.750 | 0.920 |
| NDVI | 0.614 | 0.912 |
| MNDWI (water index) | 0.569 | 0.855 |
| Five indices together | 0.569 | 0.886 |
| SSL4EO ResNet-50 RGB | 0.449 | 0.856 |

Paired difference from MNDWI (95% interval; * excludes zero): Prithvi +0.02 to +0.23 average precision *, raw bands
+0.01 to +0.23 *, SSL4EO -0.32 to +0.23 (unclear), NDVI -0.15 to +0.14 (unclear).

Reading:
- Prithvi beats the MNDWI baseline, but so do raw bands, and the two are indistinguishable. There is no sign that the
  foundation model adds anything beyond plain reflectance here.
- MNDWI is a weak baseline at this site. It assumes clear dark water, and earlier in this project optical water area
  at Imja was 27% below the Hi-MAG outline. Part of the gap is the baseline failing, not the models succeeding.
- Noise calibration matters here, unlike forest: raw bands score 0.755 with the noise-calibrated z and only 0.183 with
  the raw distance; Prithvi 0.750 against 0.336. Patches with high scene-to-scene noise (shadow, snow, glacier
  surface) are down-weighted. This was not tested with a paired interval, and the single-lake design limits how far to
  trust it.
- The ordering is not stable across scores (the RGB model's raw distance scores 0.799), which shows how loose a single
  lake is as a test.

### Added lake and pooled result (amendment of 13 November 2026)

The pilot result above rests on one changing lake. To widen it, a radar-only screen (`scripts/screen_lake_change.py`,
outputs in `data/experiments/v3_fm/lake_screen/` and `lake_screen_2020/`) looked at all 30 lakes of `studies/lakes.yaml`
before any optical scene or score was read. The rule and every later step are written in
`studies/lake_expansion_amendment.yaml`: add each non-pilot lake with at least 10 radar positives.

- 2018 against 2024: `himag_gl087092e27798n` 22 positives, `himag_gl086611e27779n` 14, next lake 5.
- Neither has a clear 2018 optical scene (best valid fraction 0.31 and 0.80; the rule asks 0.9). The earlier period for
  the added lakes moved to October to November 2020 (earliest year with three clear dates for both).
- Screen repeated, 2020 against 2024: `gl087092` 15 positives (radar area 1.87 to 2.18 km2), kept;
  `gl086611` 7 positives, dropped by the rule and not evaluated.
- The added lake has three clear scenes in each period. Its radar reference uses usable orbits from its 2019 to 2020
  scenes.

Pooled over four lakes (59 positive, 1,037 clean patches; 34 Imja Tsho, 15 `gl087092`, 6 Thulagi, 4 Tsho Rolpa),
average precision of the noise-calibrated score (ROC-AUC): six raw bands 0.644 (0.900), Prithvi 0.625 (0.880), NDVI
0.477 (0.734), five indices 0.448 (0.747), MNDWI 0.445 (0.755), SSL4EO RGB 0.434 (0.872). Paired difference from MNDWI
(95% interval): raw bands +0.06 to +0.24, Prithvi +0.06 to +0.22 (both exclude zero); NDVI, five indices and SSL4EO
include zero. Raw bands and Prithvi are not distinguishable from each other, as before. The raw distance D gives raw
bands 0.203, Prithvi 0.347 and SSL4EO RGB 0.705 (highest of all; z was the pre-specified score).

Caveats: the added lake was chosen because radar shows change at it; the added lake uses 2020 as the earlier year, the
pilot lakes 2018; per-lake scores were not examined; Prithvi AP 95% interval is 0.22 to 0.85.

### Lakes one at a time (exploratory, 13 November 2026)

`scripts/run_fm_lake_subsets.py` -> `data/experiments/v3_fm/lakes/subsets.json`. Same patches, labels and scores as the
pooled evaluation, grouped differently. Run after the pooled result, in answer to a review point that 34 of 59 positives
sit at Imja Tsho. The pilot-only group reproduces the recorded pilot numbers (Prithvi 0.75, raw bands 0.76, MNDWI 0.57).

Average precision of z, MNDWI / raw bands / Prithvi / SSL4EO RGB (positives, spatial blocks holding positives):
Imja Tsho 0.60 / 0.81 / 0.80 / 0.55 (34, 4); added lake 0.05 / 0.64 / 0.56 / 0.70 (15, 3); Thulagi 0.84 / 0.90 / 0.93 / 1.00
(6, 2); Tsho Rolpa 0.01 / 0.04 / 0.04 / 0.13 (4, 2); all lakes except Imja 0.23 / 0.41 / 0.34 / 0.41 (25, 7).

Paired difference from MNDWI (95% interval): Imja alone, Prithvi -0.16 to +0.27, raw bands -0.18 to +0.27 (both include
zero). Without Imja: raw bands +0.01 to +0.37, Prithvi 0.00 to +0.25, SSL4EO RGB +0.06 to +0.35. Added lake alone: raw bands
+0.06 to +0.83, Prithvi +0.01 to +0.70.

Reading: the pooled advantage over MNDWI is carried mainly by the added lake, where MNDWI is at chance (AUC 0.44). At
Imja, models and MNDWI are not clearly different. The pooled set has only 11 spatial blocks with positives. Why MNDWI fails at
the added lake was not examined.

## Linear probe on the frozen features (exploratory, 13 November 2026)

`scripts/run_fm_probe.py`; design in `studies/probe_design.yaml` (written before the run); results in
`data/experiments/v3_fm/probe/evaluation.json` (original C grid) and `evaluation_wider_C.json` (sensitivity).

L2 logistic regression on the signed noise-calibrated change vector, leave one forest area out, C chosen inside the
training areas. Controls: a probe on six raw bands, one on five indices. Two analyses were added after the first run
(paired Prithvi probe against six-band probe; wider C grid, because C sat at the lowest value) and are exploratory.

Forest, average precision of the held-out area, signed NDVI / Prithvi probe / six-band probe:
Bastar 0.72 / 0.77 / 0.81; Odisha 0.76 / 0.79 / 0.76; Kodagu 0.54 / 0.49 / 0.55; Garo Hills 0.55 / 0.57 / 0.59;
Shivalik 0.77 / 0.85 / 0.80. The Prithvi probe beats signed NDVI in Bastar and Shivalik (paired intervals exclude zero)
and, with the wider grid, only just in Odisha. The six-band probe is as good: Prithvi probe minus six-band probe is
negative in Bastar and Kodagu on the original grid, and not clearly positive in any area under both grids. The SSL4EO RGB
probe is worse than signed NDVI in four areas.

Lakes (four lakes pooled, secondary): Prithvi probe 0.77 against six-band probe 0.61 on the original grid, 0.54 against
0.39 on the wider grid; paired intervals +0.03 to +0.35 and -0.02 to +0.29. Not robust, not read as evidence.

Reading: a trained readout recovers an advantage over the unsupervised signed baseline, but raw reflectance with the same
readout does about as well, so the gain comes from labels and the sign of the change, not from pretraining.

## Extra checks after review (exploratory, 13 November 2026)

`scripts/run_fm_extra_checks.py` -> `data/experiments/v3_fm/extra_checks.json`.

- Paired AP difference, Prithvi z minus six-raw-band z, forest: Bastar -0.06 to +0.02, Odisha -0.08 to +0.05, Kodagu -0.09
  to +0.02, Garo Hills -0.09 to +0.03 (all include zero); Shivalik +0.35 to +0.52 (raw bands collapse there). RGB model minus
  raw bands: clearly negative in Kodagu and Garo Hills, clearly positive in Shivalik.
- Between-year z on Hansen clean patches (nothing lost), median z per area, range over five areas: raw bands 0.7 to 1.5,
  five indices 0.5 to 2.0, Prithvi 1.5 to 2.3, SSL4EO RGB 1.7 to 2.8. Share above z>3: Prithvi 3% to 20%, RGB 3% to 37%, raw
  bands 1% to 6%. The within-period noise understates the between-year spread of the embeddings.
- Sensitivity variants in each area's `evaluation.json`: signed NDVI matches or beats both embeddings in 13 of 15 variants;
  exceptions Bastar and Garo Hills with positives from 2021 (Prithvi +0.03 and +0.02 AP).
- Five-indices probe (run with the others, previously unreported): AP 0.65, 0.66, 0.53, 0.54, 0.75 against signed NDVI 0.72,
  0.76, 0.54, 0.55, 0.77; worse in Bastar, Odisha and Shivalik.
- Prithvi-EO-2.0 was pretrained on Harmonized Landsat and Sentinel-2 data at 30 m (arXiv:2412.02732); our pixels are 10 m.
- Registration commits: `9fc28c3` registration, `163885b` label screen, `aa13ce3` amendment, `fb7e7c7` box selection,
  `d5ebab4` scoring scripts, `d020079` added-area scores. Lake amendment and probe design were committed with their results.

## Noise check without a reference (twelve areas)

`scripts/run_fm_noise_check.py`. One scene of a period is compared with the rest of the same period, so every flagged
patch is a false alarm. Both embedding models flag almost nothing in this test (0 to 3.4% at z > 3), while indices and
raw bands flag 0 to 41% (medians 3 to 13%; NDWI reaches 40.5% in one area).

Do not read this as "embeddings are better calibrated". On Bastar, NDVI flags 23% of patches in the placebo test but
only 1% of Hansen's clean negatives in the real comparison, so the placebo rate depends on how alike the noise is in
the two periods. A more likely reading is that embeddings vary little between scenes taken days apart but respond to
differences between years (season, illumination, phenology) that Hansen does not count as loss. That has not been
tested.

## What this does and does not show

- For forest loss in five Indian areas, a simple signed NDVI baseline matches or beats Prithvi and a small RGB model
  in every area. This is a negative result for the foundation models on this task, and is reported as one.
- A foundation model gives no direction of change, which is a real limitation for loss detection.
- Five forest areas (three chosen by a label-only search for active clearing), one effective lake, three scenes per period and one reference product per field do not settle the
  question. Urban and wetland fields are not yet tested.

## Still to do

- Urban and wetland fields, which need Dynamic World or JRC monthly data through Earth Engine.
- Check the explanation for the extra embedding flags (where do they fall, and what is there?).
- A third forest area in a different climate, and Clay as a third model if its code can be used safely.

## Radar water model (small U-Net) and conformal area intervals

`backend/app/segmentation/`, `scripts/train_lake_unet.py`; numbers in `data/experiments/v3_unet/evaluation.json`.

Data: 3,227 pairs of a Sentinel-1 scene (VV, VH) and a clear Sentinel-2 water mask within 3 days, 30 Nepal lakes,
2020-2022. After dropping pairs whose optical water is not at least 3 dB darker in radar than its surroundings (and
labels under 20 pixels), 2,421 pairs remain. Inputs: VV, VH, slope, a missing-radar flag, 256 x 256 crop around each lake.
Model: U-Net, 1.94 million weights, BCE + Dice, 40 epochs, about 8 minutes on the laptop GPU, one seed.

Split, fixed before training: 20 lakes train, 4 calibrate, 6 test (chosen by a hash of the lake id). On the training
lakes, 2020-2021 trains and 2022 is a time test. The label is the optical water rule, so every number is agreement with
that rule, not accuracy against the ground.

Mean intersection-over-union (IoU) with the optical mask, against the Otsu radar rule already used in the lake series:

| Set | U-Net | Otsu rule |
|---|---|---|
| Random 10% of training pairs (epoch choice) | 0.82 | 0.58 |
| Same lakes, 2022 (time hold-out) | 0.80 | 0.54 |
| 4 calibration lakes | 0.77 | 0.68 |
| 6 unseen test lakes | 0.67 | 0.55 |

Reading:
- The U-Net agrees with the optical mask better than the plain radar rule everywhere, by 0.1 to 0.25 IoU.
- It drops from 0.80 on new dates to 0.67 on new lakes. Generalising to unseen lakes is the harder part, and 6 lakes is a small test.
- Part of the gain may be that the model learns the optical rule's quirks (for example, how it treats shadow) rather
  than true water. Without a hand-mapped reference this cannot be separated.

Conformal intervals for lake area (split conformal, relative error, calibrated on the 4 calibration lakes):

| Target coverage | Time test, same lakes | Unseen test lakes |
|---|---|---|
| 80% | 82% | 58% |
| 90% | 90% | 74% |
| 95% | 95% | 80% |

- On new dates at known lakes the intervals hold their promised coverage. On unseen lakes they do not: 90% intervals
  covered 74%, because the calibration lakes were easier than the test lakes (IoU 0.77 against 0.67). Conformal
  prediction assumes the calibration and test data are exchangeable, and lake-to-lake difference breaks that.
- Coverage by test lake at 90%: from 100% down to 44% (Thulagi), so it is lake-dependent, not noise.
- Median relative area error is 5% on the time test and 14% on unseen lakes. With only 4 calibration lakes, a wider
  calibration set or lake-level cross-validation is the obvious fix and has not been tried.
- Do not describe these intervals as 90% intervals for a new lake. They are for new dates at lakes like the training lakes.

Three training seeds on the same split (U-Net mean IoU, sd): new year at known lakes 0.797 (0.001), 6 unseen lakes
0.698 (0.025), against 0.541 and 0.552 for the radar rule. The advantage holds in every seed. Single-split coverage of
90% intervals on unseen lakes was 74%, 75% and 78% in the three seeds.

### Cross-validated intervals (all 30 lakes held out in turn)

`scripts/cv_lake_unet.py`. Five folds of whole lakes; each fold's model never saw its lakes. Lake area is the water
patch touching the lake seed on the whole tile, optical-valid pixels only. Intervals are calibrated on the out-of-fold
errors of the other four folds and checked on the fold left out. 2,421 scenes, 30 epochs per fold, median relative area
error 9%.

| Promised | Achieved, all lakes | Folds (range) | Lakes more than 10 points short |
|---|---|---|---|
| 80% | 81% | 36% to 97% | 9 of 30 |
| 90% | 87% | 53% to 98% | 8 of 30 |
| 95% | 94% | 82% to 99% | 6 of 30 |

- Pooled over lakes the coverage is close to the promise, which the single 4-lake calibration set could not give.
- It is not uniform: two lakes have 0% coverage and two folds fall well short at 90% (53% and 75%). Most lakes are at
  90 to 100%. The intervals are right on average and wrong for a minority of lakes, which a user cannot tell in
  advance.
- The cause was not investigated. Small, partly ice-covered or shadowed lakes are the likely candidates, since area
  errors there are large relative to the lake.
- Whole-tile IoU is 0.49 because the model also marks other dark ground in the 8 km tile as water; area is measured on
  the lake patch only.

### Radar series from the model

`scripts/run_unet_lake_series.py` applies each lake's held-out model to its Sentinel-1 scenes (usable orbits only) and
writes `monthly_unet.json` with a conformal interval (90%, relative half-width from all folds) and a flag for months
that have no optical value. These are model output, shown in purple on the Glacial lakes page.

The model series and the Otsu radar series do not agree everywhere. At Imja Tsho the radar rule grows from about 1.1 to
1.7 km2 while the model stays near 1.0 to 1.3 km2 in every year. The model was trained on optical labels, and the
optical rule is known to under-detect turbid, icy water at Imja (earlier work found it 27% below the Hi-MAG outline), so
the model has probably learned that bias. Neither series is ground truth. The model's 90% intervals are wide (about
plus or minus 54% of the area) because they are scene-level and cover all 30 lakes.

Not done: a hand-mapped or Sen1Floods11 check, explaining the badly covered lakes.
