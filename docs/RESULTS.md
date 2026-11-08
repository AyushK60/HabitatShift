# HabitatShift — results

**Nature of every number below: candidate spectral signals measured between
two fixed past dates in small AOIs. Nothing here verifies environmental
change; the ML numbers measure agreement with a reference product, not
ground truth.** Full detail: `M4_STUDY_RESULTS.md` (mathematical findings),
`M5_EXPERIMENT_RESULTS.md` (audits + ML), and the sealed records in
`data/findings/`.

## Mathematical change detection (baseline)

| Study | Periods | Common-valid | Principal recorded signal (at |Δ| ≥ 0.15 on the shared-valid footprint) |
|---|---|---|---|
| **Coringa** (reference) | 2020-03-26 → 2025-03-25 | frozen M0–M2 | M2 experiment: 149/149 audit checks; threshold sweeps, estimator families, block-bootstrap CIs |
| **Chilika dry** | 2020-02 → 2025-02 | 100 % | NDWI: 4.20 % lower / 22.34 % higher (146.09 / 777.89 ha of 3,373 ha) — redistributive, not a loss signal |
| **Chilika post-monsoon** | 2020-11 → 2025-11 | 100 % | NDWI: 11.51 % lower / 3.60 % higher (388.10 / 121.70 ha) |
| **Western Ghats** | 2020-02 → 2025-02 | 100 % | NDVI essentially stable: 0.14 % lower / 0.38 % higher (3.45 / 8.99 ha of 2,377 ha) — no deforestation claim possible |
| **Kathmandu** | 2020-03 → 2025-03 | 100 % | NDBI-led candidate increase, with recorded built-up/bare-soil confusion guardrails |
| **Purepu** (Himalaya 2025) | 2025-04 → 2025-10 | PARTIAL evidence | supraglacial-lake question; prominent in-product PARTIAL note |
| **Langtang** (Himalaya 2026) | 2026-08 → 2026-10 | optical-only limitations | seasonal/illumination guardrails recorded |

## M5 independent audit (new)

3184 → **4111/4111 checks** once the ML training manifests joined the ledger:
live STAC verification of all satellite items (incl. 2021 training imagery),
per-convention radiometry verification on real COG pixels, bit-for-bit
composite/index/delta/class recomputation from the cache, bit-for-bit block
bootstrap reproduction. One provenance defect found and corrected (M4-R1
checksum drift), three documented limitations (cache orphans, bright-snow
reflectance > 1.0, duplicate band-set cache records).

## Supervised Random Forests (M5, agreement with ESA WorldCover v200)

| Study | Classes | Test agreement | Macro-F1 (supported) | Geographic hold-out range |
|---|---|---|---|---|
| Chilika dry | water/land | 0.997 | 0.956 | 0.988–0.997 |
| Chilika post-monsoon | water/land | 0.992 | 0.892 | 0.983–0.992 |
| Western Ghats | forest-veg/other | 0.995 | 0.652 | 0.995–0.998 |
| Coringa | vegetation/water/other | 0.887 | 0.618 | 0.883–0.924 |
| Kathmandu | built-up/vegetation/bare/water | 0.853 | 0.478 | 0.853–0.921 |

Honest notes: Kathmandu bare is never predicted (F1 0.000, 153 px support);
Kathmandu water is gated (0 test px); Western Ghats macro-F1 is limited by
the 4 % minority class; Coringa mangroves have **no** supervised experiment
(the two authoritative inventories disagree inside the AOI — recorded).
Predicted application shifts (e.g. Kathmandu built-up +19.0 pp 2020→2025)
are candidate signals consistent in direction with the mathematical NDBI
findings — **consistency, never corroboration**.

## Robustness (M5)

- MMU sensitivity: recorded 25-px findings unaffected; collections thin out
  at 50 px (WG NDVI decrease 7→3→0 components).
- Bootstrap block size 10→30 px: NDVI CI width 0.017→0.028 (recorded 15-px
  design measured inside the range).
- ML feature groups largely redundant (withheld-group deltas ≤ 0.01).
- Resolution sensitivity deferred with recorded rationale.

## Product surfaces

Both research experiences render the sealed records through one shared
adapter; the M5 ML layer is additive (`habitatshift-m5ml-findings/1`
referencing the frozen records by SHA-256). Screenshots:
`docs/evidence/m4-r3/`, `docs/evidence/m5/` (e.g.
[m4_r3_explore_selected_1440.png](evidence/m4-r3/m4_r3_explore_selected_1440.png),
[m5_ml_research_mode.png](evidence/m5/m5_ml_research_mode.png)).
