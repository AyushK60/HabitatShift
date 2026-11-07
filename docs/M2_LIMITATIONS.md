# M2 — Limitations and what cannot be claimed

## What M2 does NOT claim

1. **No environmental change verdict.** Every "candidate decrease/increase"
   is a threshold-dependent index difference. At t = 0.15, NDVI decrease
   covers 11.68 % of the AOI; at t = 0.05 it covers 37.95 %. Quoting any of
   these as "mangrove loss" or "water gain" is forbidden.
2. **No supervised accuracy.** No independent reference labels exist for
   this AOI and period (see `M2_LABEL_FEASIBILITY.md`). There is no trained
   model, no accuracy/F1/confusion matrix, no feature importance anywhere in
   M2. The supervised path is blocked, honestly and by construction
   (structural tests fail if such keys appear).
3. **No confidence intervals about the landscape.** The block-bootstrap
   intervals quantify resampling variability of an area fraction under
   stated exchangeability assumptions for this AOI and grid. They are not
   population CIs, and they do not validate any threshold.
4. **No cross-site generalization.** All results are single-AOI
   (Coringa). Transfer to other sites is out of scope for M2.
5. **No sub-pixel geolocation claims.** The M0↔M1 pixel identity verifies
   internal grid registration of the two pipelines, not the absolute
   geolocation accuracy of Sentinel-2.

## Method limitations

- **Estimator differences are not errors.** The anchor/M0 estimator reports
  42.77 % candidate NDVI decrease at t = 0.15 versus 11.68 % for the median
  composite. This measures observation-selection sensitivity (tide state,
  sun angle, atmosphere per scene), which is exactly why the composite is
  the headline estimator.
- **Tidal confounding.** The 2020 and 2025 acquisitions differ in tidal
  state; creek-cell water signals (NDWI/MNDWI changes) are strongly
  tide-affected. No tide covariate is modelled in M2.
- **Seasonal window.** Both periods are Feb–Apr windows, matched seasonally
  but not identically in phenological phase.
- **SCL-based masking.** Cloud/shadow exclusion relies on the provider's
  Scene Classification Layer; terrain shadow is not independently
  re-derived. For this study the masking produced a complete common-valid
  footprint, which itself means mask uncertainty is not exercised.
- **SWIR resolution.** MNDWI uses B11 at native 20 m resampled to the 10 m
  grid; MNDWI edges are effectively coarser than NDVI edges.
- **Bootstrap assumptions.** Block exchangeability is an assumption, not a
  tested property; between-block dependence is ignored.
- **Single site, single season pair.** The whole sensitivity study is one
  landscape at one seasonal pairing; response curves elsewhere will differ.

## Engineering limits

- The experiment cache keys on config + input content, not on engine code
  versions; a code change that alters results without a config/input change
  would be served the stale cached run. Mitigation: the runner's documented
  cache contract is "same inputs, same config → same result", and the audit
  verifies the recorded run against the frozen inputs; a deliberate recompute
  is `--force`.
- `run_experiment.py` run ids embed a wall-clock timestamp; result contents
  other than `generated_utc`/`run_id` are reproducible.
- The viewer's Experiments section reads one run (the newest). Comparing two
  runs side by side is future work.
- Playwright checks ran headless; touch behaviour is pointer-event based and
  was validated as pointer events, not on physical hardware.
