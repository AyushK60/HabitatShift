# M4-R2 Validation — six-study evidence review

**Status:** M4-R2 G5 deliverable. Study-by-study validation of the Evidence
Engine against the brief's per-study requirements. All checks were executed
programmatically against the generated evidence records (results inline; the
mechanical verification common to every study lives in
`docs/M4_R2_FINDINGS_AUDIT.md`).

Common baseline (all six investigations): 10 m UTM analysis grid, 25 px =
0.25 ha MMU, threshold |Δ| ≥ 0.15 inclusive, 4-connectivity, top-5
components per index × direction, shared-valid denominator recorded, frozen
M1/M4 delta rasters of record, sealed evidence records with sha256
checksums, stable content-derived `evidence_id`s.

---

## A — Coringa mangrove/tidal delta (coringa_m1, 30 findings)

- Indices: NDVI, NDWI, MNDWI (t = 0.15 each; shared-valid 165,136 px).
- Candidate decrease/increase NDVI regions carry the mangrove-context
  template: canopy change, water-level/turbidity differences, tidal state —
  explicitly **not** evidence of mangrove destruction.
- **Tidal and turbidity limitations:** present in every finding's
  explanations/cannot-conclude (verified programmatically).
- **M2 experiment intact:** the M2 independent numerical audit passes
  149/149 against the frozen Coringa run (re-verified at G0 of this
  milestone); no M2 output was modified.
- Geometry: grid-true polygons with interior holes preserved; areas from
  pixel counts on the projected grid.

## B — Chilika lagoon (chilika_m4_dry, chilika_m4_postmonsoon; 30 + 30)

- Two separate experiments with genuinely different acquisition periods —
  the seasonal separation is structural, not rhetorical (verified: different
  earlier/later anchor dates).
- Water-index signals (NDWI, MNDWI) plus NDVI context on the same
  shared-valid footprint (348,129 px each).
- **Seasonal vs longer-term:** every finding's cannot-conclude states the
  signal is not established outside the compared seasons and that exposed
  lakebed must not be read as permanent wetland loss.
- Dry-season and post-monsoon findings are distinct evidence records; no
  cross-season merging was performed.

## C — Western Ghats forest (western_ghats_m4, 11 findings)

- NDVI differences with NDWI context; complete validity footprint.
- **No deforestation language:** the only deforestation mention is the
  cannot-conclude guardrail "That deforestation occurred (no independent
  verification)" — verified for every finding.
- **Terrain-shadow limitation** recorded in every meaning text and in the
  evidence-quality limitations.
- Small candidate regions are consistently labelled candidate spectral
  signals, never canopy-loss assertions.

## D1 — Purepu supraglacial-lake drainage 2025 (himalaya_purepu_2025_m4, 20)

- **PARTIAL status preserved and now consistent:** the findings payload and
  every per-finding evidence record carry `evidence_status = "partial"`
  (G4 fixed an M4-R1 inconsistency where the bundle said partial but the
  findings said processed).
- NDWI (lake/liquid-water), NDSI (snow/ice), NDVI context; seasonal
  (April → October) pair explicitly caveated in every meaning text.
- Event attribution is refused in every cannot-conclude; no discharge,
  depth or damage claims exist anywhere in the records.

## D2 — Langtang Lirung 2026 (himalaya_langtang_2026_m4, 12)

- NDSI snow/ice signals, NDWI liquid-water, NDVI context on the shared
  footprint (93,736 px).
- **Collapse-footprint guardrail verified:** every finding's
  cannot-conclude refuses identification of highlighted regions as the
  verified collapse footprint; no spectral region is presented as event
  evidence without independent spatial confirmation.
- Snow/ice context dominates the meaning texts as recorded.

## E — Kathmandu urban (kathmandu_m4, 19)

- NDBI differences with NDVI/NDWI context on the shared footprint
  (43,728 px).
- **Building-detection guardrail verified:** the 10 m resolution limitation
  ("10 m pixels cannot resolve buildings") is present in the
  cannot-conclude set; NDBI is always a candidate built-up/impervious
  signal, with bare-soil/construction confusion stated.
- No individual-building or verified-expansion claims exist.

---

## Cross-study integrity rules (verified)

1. **No MNDWI/NDSI duplication:** no experiment presents both indices;
   nothing is double-counted as independent evidence.
2. **Study-specific interpretation:** all interpretation text is
   deterministic per study (no generic sign-based explanations).
3. **Recorded limitations travel with the data:** every one of the 152
   evidence records embeds its study's recorded limitations in
   `evidence_quality.masking_and_cloud_limitations`.
4. **PARTIAL only where restricted:** `partial` appears exclusively for
   D1; all other experiments are `processed`.

## Verdict

All six investigations validate against the brief's study-specific
requirements. The guardrails that matter most scientifically (no
deforestation/building/collapse-footprint claims, seasonal separation,
PARTIAL honesty, no duplicated measurements) are enforced in the generated
records themselves, not just in documentation.
