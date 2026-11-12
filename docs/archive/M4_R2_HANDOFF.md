# M4-R2 handoff

**Status:** complete, ready for user review. Branch `m4-r2-evidence`, based
on the M4-R1 final state `40d9415` (verified before any change: 363 pytest /
49+11 browser checks / M2 audit 149/149 / 152 findings on disk and in
bundles). No ML implemented, no deployment, no external push.

M4-R2 audited, validated, strengthened and formalised the M4-R1 spatial
findings into a reusable Evidence Engine. The 152 candidate findings were
**not** recreated: every recorded measurement was independently verified to
reproduce exactly, and the work went into validation, provenance and schema —
not new map regions.

---

## 1. What M4-R2 delivered

1. **G0 baseline (all verified, nothing assumed):** 363 pytest, frontend
   build, 49+11 browser checks, M2 independent audit 149/149, findings
   counted per investigation (30/30/30/11/20/12/19 = 152, identical between
   `data/findings/` and every embedded bundle), branch `m4-r2-evidence` created.
2. **G1 method protocol:** `docs/M4_R2_METHOD_PROTOCOL.md` — the formal
   rules (ΔI = later − earlier; |Δ| ≥ t inclusive; shared-valid intersection
   with finiteness; index registry + MNDWI/NDSI duplication rule;
   4-connectivity; MMU; geometry pipeline), each verified against the
   implementation before documentation. No calculation changed.
3. **G2 independent numerical verification:** a standalone audit
   (`scripts/audit_findings_m4r2.py`) sharing no code with the generator —
   its own flood-fill labelling instead of scipy, fresh raster reads,
   roundtrip geometry checks — recomputed masks, component counts,
   per-finding statistics, denominators and geometry. **1614 → 2837 checks,
   all passing** (count grew as G4/G6 added record checks). Three initial
   audit failures were diagnosed and fixed as audit bugs (rounding
   tolerance, a malformed shapely check, tie-order matching); no recorded
   value changed.
4. **G3 geometry/MMU audit:** all six studies on 10 m UTM grids (100 m²/px),
   so the 25 px MMU = 0.25 ha is physically consistent everywhere. Every
   polygon vertex grid-aligned (≤ 0.05 px after the recorded 6-dp rounding),
   shapely-valid, AOI-contained. **Documented display simplification:** the
   recorded polygon was the component's exterior ring; 127/152 components
   enclose interior holes (51,050 masked px). G4 preserves the interior
   rings explicitly; the pixel-count analytical area remains the measurement
   of record. **Completeness boundary quantified:** 1,520 components ≥ MMU
   exist but only the top 5 per index × direction are recorded (1,368
   unrecorded) — the documented deterministic selection rule, now counted
   per experiment rather than invisible.
5. **G4 versioned Evidence Records:** findings container schema
   `habitatshift-findings/2` (strictly additive), per-finding
   `habitatshift-evidence-record/1` with identification, source observations
   (scene IDs, dates), input measurements (formula, bands, threshold, grid,
   input sha256s), spatial measurements, evidence quality, relationships and
   method provenance (git commit, pipeline version, software versions,
   parameters, sealed sha256 output checksum). Stable content-derived
   `evidence_id`s. Fields the pipeline cannot supply are `null`, never
   invented. Schema doc: `docs/M4_R2_EVIDENCE_SCHEMA.md`.
6. **G5 six-study validation:** `docs/M4_R2_VALIDATION.md` — per-study
   guardrails verified programmatically in the generated records (no
   deforestation/building/collapse-footprint claims; tidal, turbidity and
   terrain-shadow limitations; Chilika seasonal separation; D1 PARTIAL).
7. **G6 relationships + sensitivity:** 219 cross-index overlap links
   (equal-area UTM intersection ≥ 10 % of the smaller region, max 8 per
   finding) so overlapping measurements are explicitly related, never
   presented as independent events, never merged. Per-finding threshold
   sensitivity at t ± 0.05 with transparent labelled categories and their
   exact rules recorded with each result (11 words for persistent… see
   schema doc). A threshold-stable label is explicitly not a
   verified-change statement.
8. **G7 product integration:** new **Evidence record** inspector tab
   (Research Mode) rendering the full sealed record for the same selected
   `evidence_id` the Explore card shows; the Explore card gained
   plain-language threshold behaviour and overlapping-measurements sections.
   Both views read one payload — no independent computation. Bundles embed
   everything; Showcase Mode runs with the backend stopped (11/11 checks).

## 2. Findings verified (per investigation)

| Experiment | Findings | Numerical agreement |
|---|---|---|
| coringa_m1 | 30 | exact (555 audit checks) |
| chilika_m4_dry | 30 | exact (555) |
| chilika_m4_postmonsoon | 30 | exact (555) |
| western_ghats_m4 | 11 | exact (209) |
| himalaya_purepu_2025_m4 | 20 | exact (375) |
| himalaya_langtang_2026_m4 | 12 | exact (231) |
| kathmandu_m4 | 19 | exact (357) |
| **Total** | **152** | **2837/2837** |

## 3. Records corrected, and why

No measurement changed. Two genuine defects were found and fixed:

1. **Purepu PARTIAL inconsistency (M4-R1 legacy):** the bundle-level
   `evidence_status` said `partial` but the findings payload and per-finding
   records said `processed`. Fixed at generation; PARTIAL now propagates
   into every Purepu evidence record.
2. **Exterior-ring display geometry (M4-R1 legacy):** recorded polygons
   omitted interior holes. Interior rings are now preserved and the hole
   pixels counted (`hole_pixel_count`); display renders holes as holes.
   Analytical areas were already correct and are unchanged.

Everything else was additive: schema, provenance, sensitivity,
relationships, integration.

## 4. Known scientific limitations (unchanged by M4-R2, now recorded per finding)

- Candidate spectral signals only; no independent ground truth anywhere.
- MNDWI/NDSI share band algebra; no experiment uses both, and the rule is
  documented for future profiles.
- The 1,368 components ≥ MMU below the top-5 cap are not findings (by
  recorded rule).
- SWIR-derived indices (MNDWI, NDSI, NDBI) ride on 20 m native bands
  upsampled to the 10 m grid.
- Threshold sensitivity covers threshold choice only; observation-selection
  variability and reference/classification uncertainty are distinct sources
  not covered by the label.

## 5. Test results (final verification)

| Suite | Result |
|---|---|
| pytest (incl. 50 findings-integrity + new M4-R2 evidence tests) | **403 passed** |
| Independent M4-R2 findings audit (`audit_findings_m4r2.py`) | **2837 passed, 0 failed** |
| M2 independent numerical audit (`audit_m2.py`) | **149/149** |
| Browser suite with backend (`verify_m4.mjs`, incl. 2 new M4-R2 checks) | **51 passed, 0 failed** |
| Showcase suite without backend (`verify_m4_showcase.mjs`) | **11 passed, 0 failed** |
| M2-experiments browser suite (`verify_m2_experiments.mjs`) | **22 passed, 0 failed** |
| Frontend production build | passes (tsc + vite) |
| Legacy M3 browser suite (`verify_m3.mjs`) | **pre-existing failure, not M4-R2** — the suite was last updated at M4-G6 and expects the pre-M4-R1 landing; M4-R1 G1 restructured the landing and declared 49+11 as its suites. Left untouched (out of M4-R2 scope); should be refreshed or retired in a follow-up. |

## 6. Git commits

| Commit | Gate |
|---|---|
| `78b46ba` | G1 method protocol |
| `0ba8239` | G2 independent numerical verification |
| `3eb4100` | G3 geometry + MMU audit record |
| `e13b724` | G4 versioned Evidence Records |
| `2e14076` | G5 six-study validation |
| `720923f` | G6 relationships + threshold sensitivity |
| `8a6fdf8` | G7 Explore/Research integration |
| *(this commit)* | G8 handoff + final verification |

Working tree: clean at release (evidence screenshots regenerated by suite
runs are committed with G8).

## 7. Deliverables

- `docs/M4_R2_METHOD_PROTOCOL.md` — formal mathematical rules
- `docs/M4_R2_EVIDENCE_SCHEMA.md` — versioned record schema
- `docs/M4_R2_VALIDATION.md` — six-study validation
- `docs/M4_R2_FINDINGS_AUDIT.md` — independent audit record
- `docs/M4_R2_HANDOFF.md` — this document
- `docs/evidence/m4-r2/` — audit results JSON, evidence screenshot
- `scripts/audit_findings_m4r2.py` — reusable independent auditor
- `backend/tests/test_m4_r2_evidence.py` — evidence-record integrity tests

## 8. Suggested next steps (M5, not started)

- Supervised feasibility work per the roadmap; M4-R2's evidence records are
  the ready-made training-data inventory boundary (with the honest caveat
  that none of the regions are labels).
- Refresh or retire the stale `verify_m3.mjs` legacy suite.
- Optional: paginate/simplify geometry if bundles grow (152 records embed
  comfortably today; bundle sizes unchanged at ~5.5 MB for the largest).
