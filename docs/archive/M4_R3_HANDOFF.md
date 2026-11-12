# M4-R3 handoff

**Status:** complete, ready for user review. Branch `m4-r3-experiences`,
based on `m4-r2-evidence` @ `b738b62`. No ML implemented, no deployment, no
external push. M4-R3 delivered the two research experiences — **Explore the
Evidence** (public, guided) and **Research Mode** (technical) — over the
existing sealed evidence records, with one shared read path and no new
science.

Companion documents: `M4_R3_DESIGN_DECISIONS.md` (gate-by-gate decisions and
verification), `M4_R3_EXPLORE_MODE.md`, `M4_R3_RESEARCH_MODE.md`,
`M4_R3_VISUAL_QA.md`.

## 1. What was implemented

- **G0 — architecture.** Shared Evidence Adapter
  (`frontend/src/evidence/adapter.ts`) as the single read layer:
  `findingByEvidenceId`, `buildEvidenceOverview`, `relatedFindingsFor`,
  `thresholdSensitivity`, sensitivity plain-language mapping, record CSV
  flattening. New generated artifact `selection_policy.json`
  (`habitatshift-selection-policy/1`, via `scripts/build_selection_policy.py`
  from the audit artifact — never hand-copied). Stale test contracts
  resolved (see §3).
- **G1 — Explore.** Overview summary from the container; curated-selection
  disclosure with audited counts; filters (direction, index, threshold
  behaviour, overlap availability, region search — narrowing only);
  finding cards restructured to the eight guided questions; clickable
  overlapping measurements; "Open Research Mode" link. Selection state,
  map paint expressions and both panels now keyed by `evidence_id`.
- **G2 — spatial navigation.** Region clicks no longer leak into the
  pixel-probe path; stable-identifier hover tooltip (display id, Δindex
  direction, area, evidence_id); map↔panel selection, fly-to and reset
  verified.
- **G3 — Research Mode.** Per-finding mathematical method block; source
  observations / input measurements / spatial measurements with levels note;
  evidence quality incl. masking limitations; threshold-sensitivity
  neighbours table with recorded rules verbatim; clickable related records
  in place; provenance; verbatim JSON + deterministic CSV record exports.
- **G4 — shared navigation.** Direct finding links
  (`?finding=<evidence_id>[&view=research]`) that switch the analysis,
  select and fly; URL reflects selection/tab continuously; selection stable
  across Explore↔Research; cleared on study switch with no stale leak.
- **G5 — interpretation guardrails.** PARTIAL-evidence note for Purepu;
  new independent audit `scripts/audit_m4r3_disclosure.py` (106/106):
  disclosure math per experiment, per-study interpretation themes, PARTIAL
  propagation, negation-aware forbidden-claim scan.
- **G6 — portable showcase.** Showcase suite extended 11→17 checks, all
  passing with the backend stopped: overview + audited disclosure counts,
  Research Mode record, JSON export and deep links all work offline from
  the static bundles. No rasters duplicated; bundle checksums untouched.
- **G7 — verification.** New `verify_m4_r3.mjs` suite (35 checks) including
  UI-numbers-equal-record assertions (area, mean Δ, denominator,
  sensitivity neighbours to recorded precision); full battery re-run (§5);
  visual QA pass.

## 2. Evidence records powering the experiences

The same 152 records as M4-R2, untouched: `data/findings/*.json`
(`habitatshift-findings/2` with embedded `habitatshift-evidence-record/1`),
embedded byte-identical in every showcase bundle
(30/30/30/11/20/12/19 per experiment). The only new frontend asset is
`frontend/public/studies/selection_policy.json`. The **selection cap is
communicated** in three places: the Explore overview disclosure (recorded
vs additional qualifying components, per experiment), the Research Mode
method block (top-5 rule + "no evidence records" caveat), and the generated
policy artifact itself. Per-study unrecorded counts: Coringa 656, Chilika
dry 264, Chilika post-monsoon 200, Western Ghats 2, Purepu 119, Langtang
51, Kathmandu 76 (1,368 total).

**Limited-evidence studies:** Himalayan 2025 (Purepu) is PARTIAL — now with
a prominent note in the Explore overview and per-record status. Himalayan
2026 (Langtang) keeps its optical-only/seasonal limitations. No study's
interpretation was changed; all guardrails are the recorded generation-time
templates.

## 3. Pre-flight corrections (honesty notes)

1. **`verify_m3.mjs` retired** — superseded by `verify_m4.mjs` (which
   carries the evolved contract incl. all five viewports); documented in
   the design decisions.
2. **`verify_m2_experiments.mjs` was stale and had been silently failing
   with zero checks.** Its committed evidence at M4-R2 G8 records
   `passed: 0, failed: 0, checks: []` — the "22 passed" in the M4-R2 final
   report was **not backed by the committed artifact**. Refreshed to the
   current `/experiments` contract: 31/31. This correction is recorded here
   and in the design decisions explicitly.
3. A stray, incomplete re-run of the M2 G0 browser evidence
   (223/223 then browser-closed, `failure` field set) in the working tree
   was restored to the committed complete 323/323 run.

## 4. Test results (final verification, this branch)

| Suite | Result |
|---|---|
| pytest (full backend) | exit 0 — 403 collected/passed |
| Independent M4-R2 findings audit | 2837 passed, 0 failed |
| M2 independent numerical audit | 149/149 |
| New M4-R3 disclosure/interpretation audit | 106/106 |
| `verify_m4_r3.mjs` (new, incl. record-value equality) | 35 passed, 0 failed |
| `verify_m4.mjs` (backend up) | 51 passed, 0 failed |
| `verify_m4_showcase.mjs` (backend stopped) | 17 passed, 0 failed |
| `verify_m2_experiments.mjs` (refreshed) | 31 passed, 0 failed |
| Frontend production build (tsc + vite) | clean |
| Legacy `verify_m3.mjs` | retired (disposition documented) |

## 5. Git commits

| Commit | Gate |
|---|---|
| `d9b9289` | G0 preflight + adapter + stale-suite dispositions |
| `15966d0` | G1 Explore overview/cards/filters |
| `281e410` | G2 spatial navigation |
| `f9eb54a` | G3 Research Mode panel |
| `8d603c0` | G4 shared navigation / deep links |
| `63baa09` | G5 interpretation + disclosure audit |
| `5a57fba` | G6 portable showcase |
| *(final commit)* | G7 full testing, visual QA, docs |

## 6. Remaining limitations (honest)

- Findings remain **candidate spectral signals**; nothing here verifies
  environmental change. The curated top-5 selection means the displayed
  collections are not complete inventories (disclosed in-product, counted
  per experiment, audited).
- Threshold sensitivity covers threshold choice only; observation-selection
  and reference/classification uncertainty are separate, uncovered sources.
- Per-pixel Δ values are not part of the evidence records; the Research
  Mode levels note directs pixel-level questions to the Pixel Probe (live
  backend studies only).
- Evidence-record exports are client-side captures of the record; the
  sealed `output_checksum` refers to the server-side artifact — the export
  states recorded fields verbatim but is not itself checksum-sealed.
- `verify_m4_r3.mjs` and the refreshed `verify_m2_experiments.mjs` assert
  display formatting (2–3 dp) when comparing UI numbers to records; a
  future format change would need the assertions updated alongside.

## 7. Suggested next steps (M5, not started)

- Supervised feasibility work per the roadmap, using the evidence records
  as the training-data inventory boundary (none of the regions are labels).
- Optional: a complete-component inventory mode (the 1,368 unrecorded
  components have no records; would require generation, not UI work).
- Optional: bundle-level export of a whole findings container (CSV/JSON)
  alongside the per-record exports.
