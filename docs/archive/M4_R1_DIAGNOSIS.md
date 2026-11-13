# M4-R1 G0 — Reproduction and diagnosis

**Scope.** M4-R1 corrections (§2–§13 of the brief) plus the additional
"What Changed?" guided-interpretation feature (§15). This record covers the
G0 gate: baseline verification and root-cause diagnosis of every reported
issue before any fix.

**Baseline verified before any change** (2026-11-07, branch `m4-studies`,
HEAD `dd8f13e`):

| Check | Result |
|---|---|
| `python -m pytest` | **313 passed** |
| `npm run build` (tsc + vite) | clean (chunk-size warning only, unchanged) |
| `tools/visual/verify_m4.mjs` with backend | **39/39 passed** |
| `tools/visual/verify_m4_showcase.mjs` without backend | **10/10 passed** |

Working-tree modifications before G0 were only regenerated M2 evidence
screenshots (PNG re-encodes, already present at HEAD review time); they are
part of the checkpoint commit.

---

## Diagnosed root causes

### 1. "Explore the Atlas" jumps straight into Coringa (§2)

`LandingPage` renders `<Link to="/workstation">`, and `WorkstationPage`
falls back to `DEFAULT_STUDY = "coringa_coastal"` when the route has no
`studyId` (`frontend/src/pages/WorkstationPage.tsx:37`). Confirmed in the
browser: the hero link's `href` is `#/workstation` and the workstation
mounts straight into the Coringa investigation. Same applies to the primary
navigation's Workstation link. **Fix (G1):** a study-selection experience at
`/workstation` (no studyId) with direct URLs preserved.

### 2. Gallery rows of 2 / 3 / 1 cards (§3)

`frontend/src/styles/landing.css`: `.study-grid` is `repeat(6, 1fr)` with
`.study-card { grid-column: span 2 }` but `.study-card--lead
{ grid-column: span 3 }`. Coringa therefore occupies 3 columns, Chilika +
Western Ghats fill 4 of the remaining 3 → wraps, and the tail cards land
alone. Exactly the observed 2/3/1 pattern. **Fix (G1):** uniform 3-column
grid (all cards span 2 of 6), tablet 2-column, mobile 1-column, consistent
card heights.

### 3. Later image blank / swipe "stops responding" after tab switching (§5, §6)

**One root cause, reproduced live.** `MapCompare` renders the later map cell
as `{!singleMap && (<div className="map-cell map-later">…)}` and the
map-init effect runs once per `georef`. Switching Historical → Change (or
Quality) *unmounts* the later div; returning to Historical mounts a **new,
empty div**, while `mapsRef` still holds the MapLibre instance bound to the
now-detached old div. Measured in the browser after the exact sequence
Historical → Change → Quality → Historical:

```
laterCanvasInDom: false      ← the visible later host has no canvas
laterMapDetached: true       ← the MapLibre instance's container is detached
```

Consequences: the later side of swipe/side-by-side renders the page
background (perceived "later image is blank", and "swipe no longer works" —
the divider itself still follows the pointer, measured split moving
50% → 15% → 80%, but the revealed region is empty). The earlier map never
unmounts, so it survives — matching the report that only the later side is
affected. **Fix (G3):** keep the later cell mounted for the map's lifetime
(CSS-hidden when unused) so the instance is never orphaned, and re-attach/
resize on visibility changes.

### 4. Opacity control does not actually drive the blend (§7)

Reproduced with an instrumented MapLibre instance (Western Ghats, opacity
mode): moving the slider updates React state (readout 30%) but the later
raster's `raster-opacity` **stayed at 1**. Two defects in
`MapCompare`'s layer-painting effect:

1. `applyImageLayer(later, "layer-later", …, 1)` is called with a hard-coded
   opacity **and then again** with the slider value. The first call runs
   immediately; the second call's `whenStyleReady` deferral is pending on a
   map `idle` that never fires (the detached map from issue 3 stops
   completing render cycles), so the slider value never lands.
2. Content and paint concerns are conflated: every opacity tick re-issues
   `source.updateImage(...)` (full image reload + decode) instead of only
   updating the paint property — the flicker source on a healthy map.

**Fix (G3):** never orphan the later map; separate "image content" updates
(URL change → `updateImage`) from "paint" updates (opacity →
`setPaintProperty`, always immediate); remove the duplicated call.

### 5. Quality panel mixes outside-AOI pixels with masked-inside-AOI (§4)

`qualityFromSummary` (`frontend/src/api/bundle.ts`) computes
`masked_pixels = aoi_pixels − common_valid_pixels` and the inspector labels
it "Masked or outside grid". For Western Ghats: AOI 237,774 px, shared valid
237,774 px → "Masked or outside grid: 0", while the rectangular grid holds
539 × 445 = 239,855 px — the 2,081 outside-AOI pixels are silently dropped
from the display. The binary-mask reading ("all Sea Glass") is scientifically
correct; the accounting labels are not. **Fix (G2):** report the seven
distinguished quantities (AOI px, grid px, outside-AOI px, earlier-invalid
in AOI, later-invalid in AOI, shared valid, unavailable), each with the
correct denominator, across all six investigations; keep the map rendering
strictly from the recorded binary masks.

### 6. Kathmandu imagery hard to interpret (§8)

Measured preview sizes (1 preview px = 1 analysis pixel):

| Study | Preview | Grid |
|---|---|---|
| Kathmandu | **201 × 225 px** | 10 m analysis grid |
| Coringa | 429 × 390 px | 10 m |
| Western Ghats | 539 × 445 px | 10 m |
| Chilika | 635 × 560 px | 10 m |

Kathmandu's AOI is only ≈2.0 × 2.3 km, so the workstation stretches ~200 px
of genuine 10 m data across the map viewport — the blur is dominated by the
small AOI, not by thumbnail downscaling (previews are already 1:1 with the
analysis grid) or compression. There is no higher-resolution information in
the rasters to recover. **Fix (G4):** resolution transparency (native 10 m
labels beside imagery, explicit "individual buildings are not resolvable"),
verify the earlier/later stretch consistency for honest comparison, and an
explicit note that no purchased or licensed high-resolution reference is
integrated (per §8: no billing without user approval). No data source
replacement.

### 7. Swipe view "feels more zoomed in" (§10)

Side-by-side fits the AOI bounds into a half-width cell; swipe fits the same
bounds into the full-width stage, so MapLibre picks a higher zoom. **Fix
(G5):** a shared camera policy — fit-to-extent control ("Fit Entire Study
Area"), preserved camera across mode/analysis switches where appropriate,
and synchronized extents (already guaranteed by the later-map sync logic).

### 8. Experiments page is Coringa-only (§11)

`ExperimentsPage` hard-codes `api.experimentLatest("coringa_m2")`. Only
Coringa has an M2 experiment run; the other studies have M1 summaries and
bundle charts but no experiment runs. **Fix (G6):** study selector with
truthful per-study content: Coringa shows the recorded M2 run; other
studies show their genuine descriptive measurements (bundle charts /
threshold sweeps) with clearly labelled "planned / not available" sections
rather than invented experiments.

### 9. "What Changed?" guided interpretation (additional feature §15)

Not yet started. Requires (G7) a deterministic findings-generation step over
the processed change rasters (connected components on thresholded
differences, polygon extraction in a projected CRS, areas, denominators,
stored as a reproducible structured output included in the bundles) and
(G8) the workstation view + findings panel + "What am I looking at?" layer
explainer, driven exclusively by that recorded output. Study-specific
interpretation frames per §15.4; no defensible region → honest "no mapped
finding" instead of an invented polygon.

---

## Evidence captured during G0

Interactive browser session (1440×900) against the running
backend; measured states are quoted verbatim above. Formal screenshot
evidence for the fixed build is produced per gate under `docs/evidence/m4-r1/`.

## Gate plan

| Gate | Content |
|---|---|
| G1 | Navigation + gallery correction |
| G2 | Quality accounting + Western Ghats blank-map fix |
| G3 | Swipe lifecycle + opacity fix |
| G4 | Kathmandu rendering transparency |
| G5 | Fit-to-extent + viewport refinements |
| G6 | Experiments study selector |
| G7 | Findings generation pipeline (raster → structured findings) |
| G8 | "What Changed?" workstation experience |
| G9 | Regression suites, visual QA, handoff docs |
