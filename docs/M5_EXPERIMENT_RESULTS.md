# M5 — Experiment results

**Status:** complete. Companion documents: `M5_SCIENTIFIC_AUDIT.md`,
`M5_ML_LABEL_FEASIBILITY.md`, `M5_ML_METHODOLOGY.md`, `M5_LIMITATIONS.md`.
All numbers below are read from the recorded artifacts (no re-derivation in
this document); the independent audits re-verify them from the raw artifacts.

## 1. Independent scientific audit (M5-G1)

- **3184/3184 checks** (`scripts/audit_m5_science.py`, no production imports).
- All 40 unique Sentinel-2 L2A items verified against the live Earth Search
  catalog (dates, baselines, sensors, assets, scale/offset, nodata, EPSG).
- Radiometry conventions classified across the corpus: **8 raw-DN (pre-04.00),
  26 offset-baked (`boa_offset_applied=true`), 6 empirically corrected,
  0 declared-offset** — no observation anywhere applies the −0.1 offset, and
  the double-offset guard holds on every record.
- Live COG re-reads per convention confirm the recorded decisions against the
  pixels actually stored (declared transform measured non-physical for the
  empirical items; recorded evidence means reproduced independently).
- Median composites, indices, deltas, common-valid masks and threshold
  classes reproduced from the observation cache **bit-for-bit**; the Coringa
  M2 block bootstrap reproduced **bit-for-bit** from the recorded seed.
- Issues found and dispositioned: I1 stale manifest output checksums
  (corrected with backups + root-cause fix + regression test), I2 superseded
  cache orphans (documented, provably never loaded), I3 reflectance > 1.0 on
  bright Himalayan snow/ice pixels (documented limitation), I4 duplicate
  band-set cache records (documented, auditor hardened).

## 2. Supervised Random Forest experiments (M5-G3)

Reference: ESA WorldCover v200 (2021). Training imagery: 2021-epoch composites
acquired through the audited M1 chain. All metrics are **agreement with the
reference product** on spatially separated 1-km block folds — never
ground-truth accuracy. Per-class metrics with < 50 test pixels are **not
reported** (recorded as such, never estimated).

| Study | Classes | Test agreement | Macro-F1 (supported) | Balanced acc. |
|---|---|---|---|---|
| Chilika dry | water / land | **0.997** | 0.956 | 0.975 |
| Chilika post-monsoon | water / land | **0.992** | 0.892 | 0.981 |
| Western Ghats | forest-veg / other | **0.995** | 0.652 | 0.600 |
| Coringa | vegetation / water / other | **0.887** | 0.618 | 0.609 |
| Kathmandu | built-up / vegetation / bare / water | **0.853** | 0.478 | 0.461 |

Per-class detail worth knowing:

- **Kathmandu**: built-up F1 0.914 (IoU 0.842), vegetation F1 0.519, bare F1
  0.000 (153 test px, never predicted — bare soil is spectrally absorbed by
  built-up in the dry season), water gated (0 test px in the deterministic
  fold pattern). The classifier reproduces the *reference product* well for
  built-up, moderately for vegetation, and fails for bare — all recorded.
- **Western Ghats**: overall agreement 0.995 is dominated by the 96 % tree
  majority; the minority "other" class drives macro-F1 down to 0.652 — the
  imbalance is documented, not hidden.
- **Chilika**: the water/land split is essentially perfect against the
  reference (the lagoon is unambiguous at 10 m in both seasons).

### Geographic generalisation (each fold held out in turn)

Agreement ranges across the three geographically different held-out blocks:
Chilika dry 0.988–0.997, post-monsoon 0.983–0.992, Western Ghats 0.995–0.998,
Coringa 0.883–0.924, Kathmandu 0.853–0.921. Stability is measured, not
assumed; the ranges are recorded per study in the result files.

### Application to the mathematical-baseline epochs (candidate signals only)

| Study | Predicted shift (later − earlier) | Relation to the mathematical finding |
|---|---|---|
| Kathmandu | built-up +19.0 pp, vegetation −11.9 pp | same direction as the recorded NDBI-increase findings; **consistent, not corroborating** — both are candidate signals |
| Western Ghats | forest-veg +0.1 pp (essentially stable) | the mathematical NDVI findings are threshold-localised decreases of specific components; the classifier's coarse class fractions cannot confirm or deny them — recorded as no-decision |
| Chilika dry | water +1.3 pp | directionally consistent with the corrected radiometry story (2025 reads as water again) |
| Chilika post-monsoon | water +0.03 pp | stable, matching the mathematical "no large water change" reading |
| Coringa | vegetation +0.8 pp, water −1.1 pp | within seasonal/tidal variability; no claim |

Model confidence is recorded per class but is explicitly **not** accuracy.

## 3. Exploratory K-means (M5-G4)

Two studies only (deliberately not all six): Kathmandu (k=8) and Coringa
(k=6) on the 2025 application composites, z-score-scaled features, seed
20261108. Clusters are spectral-similarity groups with recorded per-cluster
mean features and an exploratory crosstab against the RF prediction — no
cluster is named as an environmental class and no change is inferred from
clustering.

## 4. Robustness (M5-G5)

- **MMU sensitivity** (all 7 experiments, MMU 10/25/50 px): the recorded
  25-px findings are unaffected; inventories thin out at 50 px (e.g. Western
  Ghats NDVI decrease: 7 → 3 → 0 components) — the top-5 collections are
  threshold- and MMU-local inventories, as already disclosed.
- **Bootstrap block-size** (Coringa, blocks 10/15/25/30 px, recorded seed):
  NDVI t=0.15 decrease-fraction CI width grows 0.0172 → 0.0206 → 0.0255 →
  0.0283. The recorded 15-px design sits inside the measured range; larger
  blocks retain more within-block dependence and widen the interval.
- **ML feature sensitivity** (withheld-group retrains): agreement deltas are
  small (Kathmandu 0.853 → 0.848 reflectance-only → 0.845 indices-only →
  0.851 no-SWIR) — the feature groups are largely redundant; SWIR carries
  the largest single importance in Kathmandu (0.209).
- The five uncertainty categories (measurement, observation-selection,
  threshold, classification, reference-label) are reported separately
  everywhere and are never combined into one confidence score.

## 5. Product integration (M5-G6)

- New additive artifact `studies/m5ml_findings.json`
  (`habitatshift-m5ml-index/1`), generated by `scripts/build_m5ml_findings.py`
  from the recorded runs (per-experiment containers in
  `data/findings_m5ml/` reference the frozen `habitatshift-findings/2`
  containers by SHA-256 — the frozen records are untouched).
- **Explore** shows an "Additional ML reference experiment (M5)" block with
  the plain-language summary and the recorded agreement; studies without an
  ML record (Himalayan pair) show an explicit no-record note.
- **Research Mode** exposes model configuration, split design, the per-class
  evaluation table (with support-gated "not reported" cells), framing,
  application epochs, geographic stability and guardrails — all read from
  the same generated artifact; the mathematical method blocks render
  unchanged alongside.
- Verification: `verify_m5_ml.mjs` **23/23 live and 23/23 showcase**
  (backend stopped), asserting UI numbers equal the artifact at recorded
  precision; disclosure audit `audit_m5ml_disclosure.py` **96/96**
  (provenance checksums, negation-aware claim scan, gating propagation).
