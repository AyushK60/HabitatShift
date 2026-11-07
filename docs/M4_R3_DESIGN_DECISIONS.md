# M4-R3 design decisions

Status: living document, updated at each gate. Milestone: M4-R3 — Explore the
Evidence & Research Mode, two experiences over one scientific evidence engine.

## G0 — preflight, architecture, shared evidence adapter

### Baseline verified before any change (branch `m4-r3-experiences`, from `m4-r2-evidence` @ `b738b62`)

| Suite | Result |
|---|---|
| pytest | 403 collected, run exits 0 (403 passed) |
| Independent M4-R2 findings audit | 2837 passed, 0 failed |
| M2 independent numerical audit | 149/149 |
| Frontend production build | clean |
| `verify_m4.mjs` (backend up) | 51 passed, 0 failed |
| `verify_m4_showcase.mjs` (static only) | 11 passed, 0 failed |
| `verify_m2_experiments.mjs` | **stale — refreshed this gate (see below), now 31 passed, 0 failed** |

Working tree on arrival contained one stray modified artifact,
`docs/evidence/m2/g0_browser_results.json`: an incomplete re-run of the M2 G0
browser suite (223/223 checks, then the browser closed mid-suite, `failure`
field set — strictly worse than the committed complete 323/323 run). It was
restored to the committed version; existing scientific artifacts are preserved.

### Stale test-contract dispositions (brief §1, §11)

1. **`verify_m3.mjs` — retired (deleted).** Header already documented it as
   superseded by `verify_m4.mjs`; its landing-page contract expects the
   pre-M4-R1 product by design. `verify_m4.mjs` carries the evolved contract,
   including the same five viewports (1920/1440/1280/768/390), experiments
   charts, provenance and responsive checks. Historical M3 documents
   (`M3_VISUAL_QA.md`, `M3_HANDOFF.md`) are untouched records of their time.
2. **`verify_m2_experiments.mjs` — refreshed to the current product.** The
   suite still targeted the pre-M4-R1 landing section (`#experiments` on the
   landing page); that content moved to the `/experiments` route at M4-R1 G1
   and the suite was never updated. Investigation of the committed evidence
   shows the suite has actually been failing-with-zero-checks since at least
   M4-R2 G8: the `m2_browser_results.json` committed at G8 records `passed: 0,
   failed: 0, checks: []` — i.e. the "22 passed" claimed in the G8 commit
   message was not backed by the committed artifact. The refreshed suite
   drives the current `/experiments` page (six-investigation selector,
   availability honesty, descriptive M1 outputs, threshold-area consistency,
   guardrails, exports, recorded-M2-run state, missing-run fallback state,
   390 px overflow, console/page/request error guards): **31 passed, 0
   failed**. This is recorded here as an explicit correction to the M4-R2
   final report.

### Core architectural rule (brief §2)

One shared evidence source, one read path:

```
Existing scientific outputs (data/findings/*, sealed)
  → Evidence Records (habitatshift-findings/2 + habitatshift-evidence-record/1,
    embedded byte-identical in every showcase bundle)
  → Shared Evidence Adapter  frontend/src/evidence/adapter.ts
  → Explore the Evidence / Research Mode
```

Decisions:

- **The adapter is the only read layer.** Both experiences resolve findings
  with `findingByEvidenceId(payload, evidence_id)` and read every displayed
  value from that one `BundleFinding`. No second computation path exists.
- **`evidence_id` is the join key.** Selection state, map features, related
  findings, direct links and exports carry the stable content-derived
  `evidence_id` (`ev-<experiment>-<index>-<dir>-<x>-<y>`), not array indices.
- **No new measurements.** The browser never recomputes statistics; it renders
  recorded values. The adapter only derives presentation-neutral aggregates
  that are themselves deterministic reads of the records (e.g. counting the
  recorded relationship links).
- **Completeness disclosure is generated, not typed.** The audited top-five
  selection boundary (152 recorded / 1,520 qualifying / 1,368 unrecorded)
  lives in the audit artifact; `scripts/build_selection_policy.py` derives
  `frontend/public/studies/selection_policy.json`
  (schema `habitatshift-selection-policy/1`) from it programmatically. The
  generated totals reproduce the audit exactly (30/30/30/11/20/12/19 recorded;
  656/264/200/2/119/51/76 unrecorded = 1,368). Evidence-record containers and
  their sealed checksums are NOT modified.
- **Offline-first.** Everything the two experiences display is inside the
  study bundles already (M4-R2 G7 verified byte-identity with
  `data/findings/`). The only new frontend asset is the small
  `selection_policy.json`; when it cannot be fetched, the UI degrades to the
  policy text recorded in the findings container and shows counts as
  unavailable — never invented.

### Gate plan

- G1 Explore overview + finding cards + filters (this branch's public face)
- G2 spatial highlighting + finding navigation (map ↔ panel, zoom, links)
- G3 Research Mode technical panel (methods, inspector, sensitivity, provenance, exports)
- G4 shared navigation (Explore ↔ Research, evidence_id stability, direct links)
- G5 study-specific interpretation guardrails + top-five disclosure
- G6 portable showcase integration (offline verification)
- G7 full testing + visual QA + handoff documents

## G1 — Explore the Evidence overview, cards, filters

- **Selection now carries `evidence_id` everywhere.** The workstation's
  selection state, the map overlay (`["get","evidence_id"]` paint expression,
  click handler) and both inspector panels resolve findings by the stable
  content-derived `evidence_id`; the GeoJSON features carry it as a property.
  Array indices and per-experiment `finding.id` are no longer selection keys.
- **Tab naming (§8):** the two What-Changed inspector tabs are now labelled
  "Explore the Evidence" and "Research Mode" (internal ids unchanged, so
  `.finding-detail` / `.evidence-record` class contracts survive).
- **Overview summary (§3.2):** recorded candidate findings with direction
  split, indices involved, recorded relationship links (count + how many
  regions), observation period, shared-valid footprint with denominator
  wording, MMU — all read through `buildEvidenceOverview()` from the
  container, no recomputation.
- **Curated-selection disclosure (§5) placed in the overview:** states the
  top-5-per-index-direction rule, the recorded count, the audited count of
  additional qualifying components (from `selection_policy.json`), and that
  the list is not a complete inventory. When the artifact is unavailable the
  policy text renders without counts — counts are never invented.
- **Filters (§3.5):** direction, index, threshold-sensitivity category
  (persistent / moderate / sensitive — the recorded M4-R2 labels via
  `sensitivityKey`, not a new score), overlap availability, and a region text
  search over display id / title / location. Filters only narrow the recorded
  list; the UI says so explicitly.
- **Finding cards (§3.4)** restructured to the eight guided questions (What
  was observed / Where / When / What was measured / What does it mean / What
  could explain it / How much evidence supports it / What should we not
  conclude), with the measurement block read from `spatial_measurements`
  (mean/median Δ, threshold, area with hole accounting, shared-valid
  denominator, share) and the evidence block from `evidence_quality`
  (observation support, valid coverage, sensitivity in plain language with
  the recorded category named, related-measurement count).
- **Overlapping measurements are clickable:** opening a related finding
  selects it by evidence_id and flies the map (panel→map selection).
- **"Open the Research Mode record →"** switches to the Research Mode tab for
  the same evidence_id.
- **Responsive fix (pre-existing):** the finding card's long record/source
  line forced 14 px horizontal overflow at 390 px on the unmodified build
  too; fixed with `overflow-wrap: anywhere` on the card's mono/fact lines.
- Suite contract updates: `verify_m4.mjs` and `verify_m4_showcase.mjs` click
  the renamed tabs and assert the evolved card wording; candidate-framing and
  card-content checks keep their semantics.

G1 verification: verify_m4 **51/51**, showcase **11/11**, m2_experiments
**31/31**, production build clean; screenshots at 1440 and 390 confirm the
Midnight Teal & Copper identity and no overflow.
