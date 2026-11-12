# M5 — Limitations

Honest limitations, grouped by kind. Read together with `M5_LIMITATIONS.md`'s
predecessors (`M1_LIMITATIONS.md`, `M2_LIMITATIONS.md`, `M4_R3_HANDOFF.md`
§6), which remain in force.

## 1. What the ML results are — and are not

- **Every supervised metric is agreement with ESA WorldCover v200**, itself a
  classification product with its own error structure. Nothing in M5 is
  validated against independent ground truth. No per-pixel reference labels
  exist for any study AOI, and none were manufactured.
- **Cross-epoch application assumption.** Classifiers are trained on
  2021-epoch imagery and applied to the 2020 and 2025 composites. This
  assumes class spectra are stable across epochs (sensor S2A/B/C, Sen2Cor
  versions, seasonal state matched per application season). This assumption
  is not independently verified; a systematic radiometric or seasonal drift
  would bias the predicted fractions in ways this design cannot measure.
- **Class imbalance.** Kathmandu water (0.5 % of the AOI) and bare (1.5 %),
  Western Ghats non-forest (4 %) have thin reference support; per-class
  metrics below the 50-test-pixel floor are suppressed rather than reported,
  and supported-but-small classes (e.g. Kathmandu bare, 153 px) carry high
  variance.
- **Honest failures are recorded, not repaired**: Kathmandu bare is never
  predicted (F1 0.000); the Western Ghats minority class drives macro-F1 to
  0.652 despite 0.995 agreement. Model confidence outputs are confidences,
  never accuracy.
- **Coringa mangroves have no supervised experiment**: the two authoritative
  inventories disagree inside the AOI (WorldCover-95 = 284 px vs GMW-2020 =
  13 px). Neither was chosen as "truth"; the disagreement is the recorded
  result.
- **K-means clusters are spectral groups**, not classes; k was chosen for
  interpretability, not optimised; clustering carries no change meaning.

## 2. Measurement and processing limitations (standing + M5 findings)

- **Candidate spectral signals only.** Nothing in the platform verifies
  environmental change. The ML-vs-mathematical comparisons in
  `M5_EXPERIMENT_RESULTS.md` are two candidate signals side by side —
  agreement between them is consistency, never corroboration or proof.
- **Reflectance above 1.0 on bright Himalayan snow/ice pixels** (up to ~1.66
  in blue) is retained by the SCL policy (class 11 snow/ice is valid) and
  bounded in the indices; this is a Sen2Cor/terrain/brightness artifact and a
  real measurement limitation for both Himalayan studies (audit issue I3).
- **(Update: completed post-M5 for Kathmandu at 20 m; see RESULTS.md.) Grid-resolution sensitivity was deferred** (recorded rationale in
  `data/experiments/m5_robustness/result.json`): the 10 m grid is the
  recorded measurement convention, and a 20 m reprocess would create a second
  set of frozen outputs. Available on demand via the engine.
- **Top-5 selection remains a curated inventory** (M4-R3 disclosure): the
  M5 MMU sensitivity shows how quickly region collections thin out at larger
  MMUs — the recorded findings are threshold- and MMU-local.
- **Superseded-policy cache records** remain on disk (audit issue I2): they
  are provably unloadable (policy-versioned keys, load-time re-validation)
  but are retained rather than deleted, and must not be consumed by external
  tools without the same policy check.
- **Duplicate band-set cache records** exist for several items (issue I4);
  external consumers must select records by band coverage, as the M5 audit
  script does.

## 3. Scope boundaries

- The two Himalayan investigations intentionally have **no supervised ML**
  (label-gate BLOCKED): their evidence remains the mathematical change
  detection with its recorded PARTIAL (Purepu) and optical-only/seasonal
  (Langtang) limitations.
- No disaster prediction, no real-time monitoring, no deployment: the
  platform measures candidate spectral change in five small AOIs between
  fixed past dates.
- JRC Global Surface Water was not integrated (no working download endpoint
  established during the feasibility window); Chilika water labels therefore
  inherit WorldCover's water classification instead of an observation-based
  water product. This is a recorded future upgrade, not a silent substitution.

## 4. Verification boundaries

- `verify_m5_ml.mjs` asserts display formatting (1–3 dp) when comparing UI
  numbers to artifacts; a formatting change would need the assertions updated.
- The ML retraining reproducibility check is deterministic at the recorded
  seed on the recorded software versions (scikit-learn 1.9.1); a dependency
  upgrade requires re-running `audit_m5_ml.py` and re-pinning.
- The 2025 Earth Search radiometry convention remains empirically validated
  per read, not authoritatively resolved per product: the catalog still
  declares the −0.1 offset for the affected 2025 items, and the physical
  floor test (with the baseline guard as backstop) is the recorded defence.
