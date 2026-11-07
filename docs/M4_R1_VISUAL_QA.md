# M4-R1 Visual QA — corrections, map reliability and the What Changed? experience

**Status:** complete and verified. Branch `m4-studies`. Companion records:
`docs/M4_R1_DIAGNOSIS.md` (G0 root causes, with measured reproduction
evidence) and `docs/M4_R1_HANDOFF.md` (what changed and how to run it).

---

## 1. Verification summary

| Check | Result |
|---|---|
| Backend tests (`python -m pytest`) | **363 passed** (313 baseline + 50 new findings-integrity tests) |
| Browser suite with backend (`tools/visual/verify_m4.mjs`) | **49 passed, 0 failed** (40 M4 checks + 9 new M4-R1 checks) |
| Showcase suite without backend (`tools/visual/verify_m4_showcase.mjs`) | **11 passed, 0 failed** (incl. the new no-backend What-Changed check) |
| Production build (`tsc --noEmit && vite build`) | clean |
| Independent M2 audit of the frozen Coringa reference | untouched by M4-R1 (no frozen artefact modified; findings are written to a new `data/findings/` tree) |

Screenshot evidence: `docs/evidence/m4-r1/`.

---

## 2. Root causes and fixes (per brief section)

### §2 Explore the Atlas / Workstation navigation — G1 (`682e968`)

**Root cause.** The hero CTA linked to `/workstation`, and `WorkstationPage`
fell back to `DEFAULT_STUDY = "coringa_coastal"`.
**Fix.** The CTA now scrolls to the study gallery on the landing page
(hash-router-safe controlled scroll); `/workstation` without a study id
renders a new Study Picker (all six investigations, real statuses and
acquisition dates); direct study URLs still bypass the picker. The app shell
no longer applies the fixed-height workstation chrome to the picker page.

### §3 Study gallery layout — G1 (`682e968`)

**Root cause.** `.study-card--lead { grid-column: span 3 }` on a 6-column
grid produced the reported 2/3/1 rows.
**Fix.** Uniform 3-column desktop grid (2 balanced rows of equal-width
cards, verified in-browser: one distinct card width, two rows), 2-column
tablet, 1-column mobile; consistent 4:3 media with cover-cropping (no
distortion); the lead card keeps its copper identity without breaking the
rhythm.

### §4 Quality-mask accounting — G2 (`876bef0`)

**Root cause.** `qualityFromSummary` reported `masked = aoi − common` under
the label "Masked or outside grid", silently dropping the grid−AOI
difference (Western Ghats: 2,081 px).
**Fix.** The coverage panel now reports all seven distinguished quantities:
AOI pixels, rectangular-grid pixels, **outside-AOI-inside-grid (2,081 — not
observations)**, earlier/later valid, earlier/later-invalid inside AOI,
shared valid, and **masked-inside-AOI (0)**, each with the correct
denominator. Numerically verified for all six bundles. The validity layer
note now states explicitly that the layer records observation validity, not
image sharpness or a general quality score. The binary-mask map rendering
was already correct and is unchanged.

### §5 + §6 Blank later image / swipe after tab switching — G3 (`fa66bd8`)

**Root cause (one bug, two symptoms).** MapCompare unmounted the later map
cell for Change/Quality; the map-init effect only runs per `georef`, so
returning to Historical left a new empty div with the MapLibre instance
bound to a detached container (measured: `laterCanvasInDom: false`,
`laterMapDetached: true`).
**Fix.** The later cell stays mounted for the map's lifetime and is
CSS-hidden instead. Verified after the exact sequence
Historical → Change → Quality → Historical: canvas attached, full size,
imagery painted on both sides (evidence screenshot).

### §7 Opacity view — G3 (`fa66bd8`)

**Root causes.** (a) Two `applyImageLayer` calls per tick, the first
hard-coded to opacity 1, the second deferred to a map `idle` that could
never fire; (b) content and paint concerns conflated — every slider tick
re-issued `updateImage` (full image reload/decode). Additionally the
old composition could never produce a true blend (the later map's opaque
background covered the earlier map).
**Fix.** Opacity mode now composites on the primary map: the later raster is
a second image source whose `raster-opacity` the slider drives — 0 % and
100 % are true endpoints, 50 % a genuine raster-over-raster blend, pan/zoom
stays live, and content updates (`updateImage`) happen only when the URL
changes (instrumented: zero image reloads across rapid slider drags; the
paint property tracks the slider exactly). Covered by two suite checks.

### §8 Kathmandu image quality — G4 (`4df276e`)

**Diagnosis.** Previews are 1:1 with the analysis grid (201×225 px) — the
blur is the genuine 10 m limit over a ≈2×2.3 km AOI, not thumbnail
upscaling. But the recorded stretch bounds differed ~15 % between the two
dates, rendering the later composite systematically darker — a misleading
comparison (verified problem).
**Fix.** `scripts/regenerate_comparable_previews.py` re-renders the
true/false-colour previews of all M4 studies from the frozen reflectance
composites with ONE joint per-band 2–98 percentile stretch over both
periods' valid pixels (engine rendering code, gamma and AOI outline
unchanged), updates the recorded stretch provenance in the run
summaries/manifests, and the bundles were rebuilt (checksums refresh at
build time). No analytical raster was touched; Coringa's frozen reference
was excluded. Resolution transparency: a native-resolution tag rides the
map ("10 m/px native"), and the inspector states band resolutions and that
10 m does not resolve individual buildings; no licensed high-res reference
was integrated (per §8: no purchases/billing), and the interface says the
detail limit shown is the genuine limit of the open data.

### §9 Fit Entire Study Area — G5 (`8d96839`)

A toolbar control fits the complete study AOI into the viewport (small
margin), synchronized across both maps via the existing camera-sync. Works
from any view/mode; zooming into detail remains available. Suite-checked on
a large study (Kathmandu's overview zoom is already ~15, so the check uses
Western Ghats where fit is measurable).

### §10 Swipe layout

With the map lifecycle fixed and the camera preserved across mode changes,
swipe no longer changes zoom when switching modes (same map instance); the
fit control provides the full-extent view the brief prioritises.

### §11 Experiments study selector — G6 (`01a722e`)

The Experiments page now has a six-investigation selector and renders each
study's genuine outputs from the portable bundle (works without backend):
interactive threshold-sensitivity and period-mean charts, candidate-change
area tables, and can/cannot-conclude lists. An **Experiment availability**
panel labels every row as *Recorded experiment* / *Descriptive measurement*
/ *Planned — not available*; Coringa additionally shows its recorded M2 run
header and hypothesis verdicts when the backend serves it. Nothing is
invented for studies without experiment runs.

### §12 Layout and scrolling

The study picker fixed-height issue was fixed in G1; no global zoom or
transforms were introduced; responsive checks (13. no horizontal overflow)
pass at 1920/1440/1280/768/390.

### §15 What Changed? — G7 (`fed49a1`) + G8 (`fe0b7c2`)

**G7 — findings generation** (`scripts/generate_findings.py`, schema
`habitatshift-findings/1`): connected components (4-connectivity) on the
frozen Δ-index rasters at each index's recorded primary threshold, inside
the common-valid footprint only; minimum mapping unit 25 px (0.25 ha);
top regions per index/direction by area in deterministic order; true
polygon geometry from `rasterio.features.shapes` on the native UTM grid,
projected to WGS84 (pyproj) — no hand-drawn geometry; every finding records
source rasters, threshold, pixel count, area (projected CRS), mean/median
Δ, the common-valid denominator, periods and limitations; interpretation
strings are deterministic templates per study framework (§15.4) with only
the measured numbers interpolated. 152 findings across 7 experiments,
embedded per experiment in the bundles. 50 pytest tests assert the
invariants (MMU, area convention, denominator, traceability, unique IDs,
closed rings, bundle embedding).

**G8 — workstation experience:** a fourth analysis view "What changed?"
renders the Δ-index base layers with the recorded regions as subdued,
low-opacity overlays (muted teal/copper distinct from the brand's active
colours, never obscuring the imagery). Selecting a finding zooms to its
true geometry and reveals the full interpretation card (title, location,
observation period, observed measurement with units and denominator,
plain-language meaning, possible explanations with confounders, evidence
strength incl. coverage/masking, cannot-conclude); clicking a mapped region
selects it (map and panel stay in sync); the overlay toggles; "Reset View"
clears the selection and restores the full extent. The findings overview
(§15.6) states the region counts by direction, signal types, dates,
shared-valid footprint, the MMU and the candidate/insufficient-evidence
categories. The **"What am I looking at?"** control explains the current
layer (§15.5): type, exact band composition, native resolution, legend,
what values mean, how to read the colours, and what the layer cannot
establish — with explicit distinctions between true-colour, false-colour,
index, difference, validity and count maps. The experience works in
Showcase Mode (suite-checked without backend).

---

## 3. Additional defects found and fixed during G9

- **Cross-study state leak on study switches** (found by the new suite
  checks): `/workstation` did not remount on `studyId` change, leaking
  analysis/tab state and causing a one-frame stale render that fetched
  another study's bundle assets (404s). Fixed with a keyed remount
  (`<WorkstationForStudy key={studyId}>`).
- Suite-harness fixes: cwd-independent evidence paths; exact-match locators
  after "What changed?" made substring matches ambiguous; the NDBI
  guardrail check now performs the real user flow (select the layer).

## 4. Remaining limitations (honest)

- Kathmandu's intrinsic detail limit is the data itself (10 m, small AOI);
  the interface now explains this rather than hiding it.
- Findings exist only where the frozen Δ-rasters and MMU produce them; the
  Himalayan studies' findings are seasonal-caveated by template and remain
  candidate signals (D1 stays PARTIAL).
- The Experiments page renders Coringa's full recorded-run sections only
  when the backend serves them; offline it shows the bundle mirror (stated
  in the page).
- No licensed high-resolution reference imagery was integrated for
  Kathmandu (would require billing approval per §8).
