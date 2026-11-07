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

## G2 — spatial highlighting and finding navigation

Most of §3.3 already existed (real polygons, muted direction colours,
teal-selected outline, focus fly-to, Reset View, overlay toggle, AOI extent);
this gate closed the remaining gaps:

- **Finding clicks no longer trigger the pixel probe.** A click on a
  findings polygon previously fired BOTH the selection handler and the
  generic map click — in non-live (showcase) mode that raised the
  "Live pixel sampling needs the backend" error and yanked the inspector to
  the Pixel Probe tab on every region click. A one-shot ref now suppresses
  the generic handler for that click; verified: selecting Region 07 on the
  Kathmandu map keeps the Explore tab active, shows the matching
  evidence_id card and raises no pixel error.
- **Stable region identifier tooltip (§3.3):** hovering a region shows a
  compact brand-styled popup — display id, ΔINDEX direction, area, candidate
  direction, and the full `evidence_id` — so map-to-panel selection starts
  from the stable identifier.
- Verified panel→map (card/related-link click selects + flies), map→panel
  (region click selects and highlights via the evidence_id paint expression),
  zoom-to-region with maxZoom cap, and reset-to-study-area.

G2 verification: verify_m4 **51/51**, showcase **11/11**, m2_experiments
**31/31**, build clean, tooltip + selection screenshots recorded.

## G3 — Research Mode technical evidence panel

The M4-R2 G7 evidence-record tab is now a full Research Mode workspace
(§4), still reading the same sealed record through the same selection:

- **Mathematical methods (§4.2):** a per-finding method block renders only
  the operations actually recorded for that finding — index definition with
  bands and the band-resolution note, `ΔI = I_later − I_earlier` with the
  record's own delta definition, the candidate-selection rule as an
  inequality (`ΔNDBI ≤ −0.15` for a decrease, `ΔNDVI ≥ +t` for an
  increase, inclusive), what the threshold controls, the component pipeline
  (algorithm, connectivity, MMU discard, top-5 curated selection with the
  no-evidence-records caveat) and the shared-valid denominator. Formulas
  are set in a dedicated mono/legend block; no unrelated formulas appear.
- **Feature & data inspector (§4.3):** source observations (scene ids,
  dates, dataset), input measurements (formula, bands, threshold, grid,
  delta-raster and valid-mask sha256 prefixes), spatial measurements
  (pixels, area, mean/median, denominator, share, holes) — with an explicit
  levels note separating the region summary (this record), per-pixel values
  (not part of the record; Pixel Probe where live) and study-wide summaries
  (the findings container shown in Explore).
- **Threshold sensitivity (§4.4):** the recorded label with its exact
  `label_rules` text, primary threshold, and a neighbours table (t − 0.05 /
  t + 0.05: component pixels, retained fraction, growth factor) using the
  existing G6 classification verbatim; caption states it is a transparency
  category, not a confidence score.
- **Relationships (§4.5):** recorded overlap rule shown; links are
  clickable and open the related record in place (selection is shared
  state, so the study context and tab are preserved).
- **Provenance & exports (§4.6):** full method provenance (algorithm,
  version, parameters, git commit, software versions, generated time,
  sealed output checksum) plus client-side **record JSON** and **record
  CSV** downloads. The CSV is a deterministic `section,field,value`
  flatten (`evidenceRecordToCsv` in the shared adapter); the JSON is the
  record verbatim. Verified: downloads carry the correct filename
  (`<evidence_id>.json` / `.csv`), schema `habitatshift-evidence-record/1`,
  and 141 CSV rows for a Kathmandu record.
- Masking/cloud limitations from the record render under Evidence quality.
- Back-link "← Back to the Explore the Evidence card" keeps §8 navigation
  symmetric.

G3 verification: verify_m4 **51/51**, showcase **11/11**, m2_experiments
**31/31**, build clean, math-block/sensitivity screenshots recorded.

## G4 — shared navigation and provenance integration

- **Direct links to findings (§8):** the workstation URL carries the
  selection as `#/workstation/<study>?finding=<evidence_id>`, with
  `&view=research` for the Research Mode record. A pasted link switches the
  analysis to What Changed?, selects the finding, flies the map to its real
  geometry and opens the requested experience; unknown ids are ignored
  without error. The URL is kept in sync on every selection/tab change
  (`replace` navigation), so a copied address always carries the
  evidence_id. The reflection effect deliberately waits until the deep link
  is resolved, so it never strips the parameter before the container loads.
- **Selection stability across navigation (§2):** one `selectedEvidenceId`
  state drives the Explore card, the Research Mode record and the map
  highlight; returning to Explore preserves it; study switching clears it
  together with the findings payload (verified: no kathmandu content leaks
  into a chilika session).
- Existing Historical / Change / Quality / What Changed? functionality is
  untouched; Explore and Research remain What-Changed inspector modes, and
  the What am I looking at? guide, Pixel Probe, ROI and Acquisition tabs
  keep working (suite-verified).

G4 verification: verify_m4 **51/51**, showcase **11/11**, m2_experiments
**31/31**, build clean; deep-link and study-switch probes recorded.

## G5 — study-specific interpretation and top-five disclosure verification

- **PARTIAL visibility (§6, test #14):** the Explore overview now shows a
  prominent PARTIAL-evidence note for the one restricted investigation
  (Himalayan 2025 / Purepu), verified in the browser.
- **New independent audit** `scripts/audit_m4r3_disclosure.py`
  (schema `habitatshift-m4r3-disclosure-audit/1`, output
  `docs/evidence/m4-r3/study_interpretation_checks.json`) verifies from the
  recorded artifacts only, **106/106 checks passing**:
  - disclosure math per experiment: container recorded count == audited
    recorded count == policy artifact recorded count, and
    recorded + unrecorded == audited components ≥ MMU (152 + 1368 = 1520);
  - per-study interpretation themes (§6) present in container text:
    Coringa tidal/turbidity/no-ecological-claim/composite limits; Chilika
    water-level + seasonality + turbidity (both seasons, kept as separate
    experiments); Western Ghats shadow + candidate-signal framing; Purepu
    monsoon/shadow/volume-and-dam limits with PARTIAL status propagating
    into every evidence record; Langtang snow/cloud/optical-only limits;
    Kathmandu bare-soil/construction/building confusion guardrails;
  - forbidden claims: no assertive sentence (negation-aware sentence
    splitting, so the honest "not verified deforestation…" guardrails do
    not false-positive) presents candidates as verified deforestation,
    verified new construction/buildings, or a verified collapse footprint.
- The interpretation content itself remains the deterministic,
  generation-time templates recorded in the evidence records (M4-R2 G5);
  no AI-generated text was added at the interface layer.

G5 verification: disclosure audit **106/106**, verify_m4 **51/51**,
showcase **11/11**, m2_experiments **31/31**, build clean.
