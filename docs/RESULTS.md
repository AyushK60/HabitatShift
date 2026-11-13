# Results

**Every number below is a candidate spectral signal between two fixed past dates in a small area. Nothing here
verifies environmental change, and the machine learning numbers measure agreement with a reference map, not ground
truth.** Longer write-ups are in `archive/M4_STUDY_RESULTS.md` (index-difference findings) and
`archive/M5_EXPERIMENT_RESULTS.md` (audits and machine learning). The recorded results are in `data/findings/`.
The version 2 noise test, Hansen validation and time series are summarised in the [README](../README.md#findings-worth-knowing).

## Index-difference baseline

Principal recorded signal at |change| >= 0.15 on the shared valid footprint.

| Study | Periods | Common-valid | Principal signal |
|---|---|---|---|
| **Coringa** (reference study) | 2020-03-26 to 2025-03-25 | recorded in the first experiment | threshold sweeps, estimator families, block-bootstrap intervals; 149/149 audit checks |
| **Chilika dry** | 2020-02 to 2025-02 | 100 % | NDWI: 4.20 % lower / 22.34 % higher (146.09 / 777.89 ha of 3,373 ha); redistribution, not a loss signal |
| **Chilika post-monsoon** | 2020-11 to 2025-11 | 100 % | NDWI: 11.51 % lower / 3.60 % higher (388.10 / 121.70 ha) |
| **Western Ghats** | 2020-02 to 2025-02 | 100 % | NDVI essentially stable: 0.14 % lower / 0.38 % higher (3.45 / 8.99 ha of 2,377 ha); no deforestation claim possible |
| **Kathmandu** | 2020-03 to 2025-03 | 100 % | NDBI-led candidate increase, with recorded built-up versus bare-soil confusion |
| **Purepu** (Himalaya 2025) | 2025-04 to 2025-10 | partial evidence | supraglacial-lake question; visible partial-evidence note in the app |
| **Langtang** (Himalaya 2026) | 2026-08 to 2026-10 | optical limits | seasonal and illumination guardrails recorded |

## Independent audit

4111 of 4111 checks pass, including live STAC verification of every satellite item (with the 2021 training imagery),
radiometry checks on real COG pixels, bit-for-bit recomputation of composites, indices, differences and classes from
the cache, and bit-for-bit reproduction of the block bootstrap. One provenance defect (checksum drift) was found and
corrected. Three limitations are documented: cache orphans, bright-snow reflectance above 1.0, and duplicate
band-set cache records.

## Random Forests (agreement with ESA WorldCover v200)

| Study | Classes | Test agreement | Macro-F1 (supported classes) | Geographic hold-out range |
|---|---|---|---|---|
| Chilika dry | water / land | 0.997 | 0.956 | 0.988-0.997 |
| Chilika post-monsoon | water / land | 0.992 | 0.892 | 0.983-0.992 |
| Western Ghats | forest vegetation / other | 0.995 | 0.652 | 0.995-0.998 |
| Coringa | vegetation / water / other | 0.887 | 0.618 | 0.883-0.924 |
| Kathmandu | built-up / vegetation / bare / water | 0.853 | 0.478 | 0.853-0.921 |

Notes:

- Kathmandu "bare" is never predicted (F1 0.000, 153 pixels of support). Kathmandu water has no test pixels, so it
  is not reported.
- Western Ghats macro-F1 is held down by a 4 % minority class.
- Coringa mangroves have no supervised experiment, because the two authoritative inventories disagree inside the
  area.
- Predicted shifts, such as Kathmandu built-up +19.0 percentage points from 2020 to 2025, point the same way as the
  NDBI findings. That is consistency, not corroboration.

## Robustness

- **Patch size:** the recorded 25-pixel findings are unaffected. At 50 pixels the collections thin out (Western
  Ghats NDVI decrease: 7, then 3, then 0 patches).
- **Bootstrap block size:** from 10 to 30 pixels, the NDVI interval width goes from 0.017 to 0.028. The recorded
  15-pixel design sits inside that range.
- **Features:** feature groups are largely redundant (withholding one changes agreement by 0.01 or less).
- **Resolution (Kathmandu, 20 m vs recorded 10 m):** signs are preserved but fractions shrink, for example NDBI
  increase 6.82 % to 4.75 % and NDVI decrease 11.26 % to 8.37 % (common-valid pixels 43,728 to 10,938). The 10 m run
  remains the result. See `data/experiments/m5_resolution/`.

## Later additions

- **Water reference cross-check (WorldCover vs JRC Global Surface Water):** `scripts/run_m5_gsw_crosscheck.py`
  compares the two reference products, so it is not an accuracy test. Overlap (IoU) is 0.98-0.99 for Chilika at
  occurrence thresholds up to 50 %, and 0.58-0.65 for Coringa, where the products disagree about tidal and
  aquaculture water. No earlier recorded result was changed.
- **Complete patch inventory:** `scripts/build_component_inventory.py` lists every changed patch of at least 25
  pixels, not just the top five. Totals match the audited selection in all 7 experiments (for example Coringa 686,
  Chilika dry 294, Western Ghats 13).
- **Two-method direction check:** the index method and the model agree on direction in four of five ML experiments.
  Coringa disagrees (vegetation-index net share -2.96 vs predicted vegetation share +0.84 pp) and is reported as
  such (`docs/figures/fig2_two_methods_direction.svg`).
- **Technical report:** [`paper/HabitatShift_Technical_Report.pdf`](paper/HabitatShift_Technical_Report.pdf).

## Screenshots

Both research views read the same recorded results through one shared reader. Examples:
[explore view](evidence/m4-r3/m4_r3_explore_selected_1440.png),
[ML research view](evidence/m5/m5_ml_research_mode.png).
