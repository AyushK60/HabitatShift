# M4-R1 G10 Visual QA — interactive chart layout, tooltips and hover refinement

**Status:** complete and verified. Branch `m4-studies`.
Companion records: `docs/M4_R1_VISUAL_QA.md` (G1–G9) and
`docs/M4_R1_HANDOFF.md`.

This gate is a pure presentation refinement of the interactive research
charts (`frontend/src/charts/`). **No scientific data, bundle schema, or
recorded value was touched** — every number shown in tooltips comes from the
same frozen bundle artefacts as before.

---

## 1. Verification summary

| Check | Result |
|---|---|
| Backend tests (`python -m pytest`) | **363 passed** (unchanged baseline) |
| Browser suite with backend (`tools/visual/verify_m4.mjs`) | **49 passed, 0 failed** |
| Showcase suite without backend (`tools/visual/verify_m4_showcase.mjs`) | **11 passed, 0 failed** |
| New G10 chart probe (`tools/visual/verify_g10.mjs`) | **22 passed, 0 failed** |
| Production build (`tsc --noEmit && vite build`) | clean |

Screenshot evidence: `docs/evidence/m4-r1-g10/` (13 screenshots +
`g10_probe_results.json`).

---

## 2. Root causes and fixes (per brief section)

### §1 Chart proportions

**Root cause.** Charts stretched edge-to-edge of the text column (no maximum
width) at a fixed 240 px height → excessively wide, short plots.

**Fix** (`InteractiveChart.tsx`, `charts.css`).
- Default height **240 → 320** px; plot container capped at **max-width 860 px**.
- Comfortable margins (top 18 / right 24 / bottom 52 / left 68) — the left
  margin now always fits 4-digit y ticks; y-axis title moved to x=14.
- More y gridlines (5 nice ticks) in the taller plot.
- Verified: rendered plot 858×320 (ratio 2.68) at 1440 px; charts fit the
  column at 390/768/1024 px.

### §2 Tooltip clipping

**Root causes.** The tooltip lived *inside* `.ichart-plot`, which had
`overflow: hidden` — anything past the plot edges was cut. Placement used a
naive `width * 0.62` flip and a guessed `top`, never measured the tooltip
itself, and never considered the viewport.

**Fix.**
- The SVG now sits in its own clipped wrapper (`.ichart-svg`); the tooltip is
  a **sibling overlay** that can never be clipped by the plot frame.
- Placement is computed in a `useLayoutEffect` **after measuring the rendered
  tooltip**: preferred right of the guide → flipped left when room runs out →
  clamped inside the plot **and** the visible viewport. Runs before paint, so
  the reposition is never seen mid-frame.
- A scroll/resize listener re-clamps while a (pinned) tooltip is open, so it
  stays readable when the user scrolls.
- Absolutely positioned at all times → **zero layout shift** on appearance.

Verified: contained at centre, left edge, right edge, top edge, bottom edge,
narrow desktop and mobile (probe checks 4–9, 18, 20). The expanded details
panel may legitimately extend below a plot shorter than itself; it remains
fully viewport-visible (probe check 11).

### §3 Hover simplification

**Root cause.** One tooltip row per visible series with every row's full
interpretation → an enormous multi-series tooltip.

**Fix.**
- Hover now picks the nearest series **by vertical pointer distance** at the
  snapped x (mouse); taps and keyboard pins default to the first series with
  a point there, and **ArrowUp/ArrowDown cycles series** at the current point.
- Collapsed tooltip: series name, exact x, exact y with unit **and
  denominator** (`% of shared-valid AOI`), recorded facts, one concise
  interpretation, and a `Details ▾` toggle.
- Expanded section: **other series at this x value**, **measurement context**,
  and **limitations** (the chart's cannot-conclude statements).
- Pointer moves originating inside the tooltip are ignored by the plot, so
  reaching the toggle never re-picks the series or collapses the panel.

### §4 Legends and labels

**Root cause (duplicated legend labels).** Coringa's recorded M2 run carries
**six** threshold series (3 indices × `composite_mean` / `composite_median`
estimators) but `ThresholdChart` labelled every series `Δ<INDEX> decrease`,
so each index appeared twice, indistinguishable.

**Fix.** Labels now disambiguate the configuration — e.g.
`ΔMNDWI decrease · mean composite` / `· median composite` — with the full
technical `estimator_id` shown in the tooltip facts and a dedupe safety net
that appends the recorded primary threshold if a collision ever remains.
Series ids also became unique (`ndvi:composite_mean`), so legend toggles
affect the right series.

**Root cause (estimator labels).** X ticks printed the estimator *family*
(`leave_one_out` repeated 6×) and hover labels were scene-id-long.

**Fix.** The estimator chart is now a **categorical x axis** with compact
per-configuration tick labels (`anchor`, `mean`, `median`, `M0`,
`LOO 03-26`, `03-26×04-01`), rotated −38° with extra bottom margin so they
never collide with the axis title. Full names ("Leave-one-out median ·
earlier without 2020-03-26") and raw estimator ids stay on the point and in
the tooltip.

**Root cause (repeated dates).** The period-means chart mapped anchor dates
to 0/1 and used numeric ticks — fractional ticks like 0.2 all rounded to the
same date string.

**Fix.** The means chart is categorical too: each recorded anchor date
appears **exactly once** on the axis (probe checks 12–13).

### §5 Readability

- Selected recorded point now carries a colour **halo** plus a larger dot
  (previously a barely visible size change).
- Tick font 9.5 → 10.5 px, tick fill `#56686d` → `#47606a` (better contrast
  on the ivory panel); axis titles 11 px.
- Percentages keep one consistent format (`toFixed(2)` + explicit
  `% of shared-valid AOI` denominator); units are stated in every tooltip.
- Gridlines kept and slightly strengthened.
- **Fixed while auditing:** the screen-reader data table under every chart
  used class `visually-hidden` which had **no CSS definition** — the full
  table rendered visibly under each chart (pre-existing defect, also the
  mobile horizontal-overflow source; tables ignore `overflow: hidden`). The
  class is now defined properly (`clip-path` + `table-layout: fixed`).
- Long technical identifiers (scene/estimator ids) wrap inside the tooltip
  (`overflow-wrap: anywhere`) instead of bleeding past its edge.
- Midnight Teal & Copper identity untouched (teal/copper palette, dark
  charcoal tooltip, copper Details control).

### §6 Behaviour preservation

All existing contracts re-verified by the suites:
mouse hover with nearest-recorded-point snapping (no interpolation),
click-to-pin / Esc-to-dismiss (probe 16–17), keyboard navigation with the
tooltip mirrored to the live region, touch taps, legend toggles (now with
correct unique ids), recorded values (verify_m4 checks 4–6, showcase
tooltip check), and the plain-language interpretation strings (unchanged
templates).

### §7 New regression coverage

`tools/visual/verify_g10.mjs` — 22 checks with edge-case screenshots:
legend distinctness, single-series tooltip, units/denominator, containment
at left/right/top/bottom, expanded details content + containment, estimator
tick audit, means date audit, proportion check, pin/Esc, 1024 px and 390 px
layouts (no horizontal overflow), and console/page-error sweep.

---

## 3. Evidence

```
docs/evidence/m4-r1-g10/g10_threshold_chart_coringa.png   distinct 6-entry legend
docs/evidence/m4-r1-g10/g10_tooltip_normal.png            single-series tooltip
docs/evidence/m4-r1-g10/g10_tooltip_left_edge.png         left-edge containment
docs/evidence/m4-r1-g10/g10_tooltip_right_edge.png        right-edge flip
docs/evidence/m4-r1-g10/g10_tooltip_top_edge.png          top-edge containment
docs/evidence/m4-r1-g10/g10_tooltip_bottom_edge.png       bottom-edge containment
docs/evidence/m4-r1-g10/g10_tooltip_expanded.png          expanded details panel
docs/evidence/m4-r1-g10/g10_period_means_chart.png        dates once, no repeats
docs/evidence/m4-r1-g10/g10_estimator_chart.png           short rotated labels, wrapped ids
docs/evidence/m4-r1-g10/g10_narrow_1024.png               narrow desktop
docs/evidence/m4-r1-g10/g10_mobile_390.png                mobile layout
docs/evidence/m4-r1-g10/g10_mobile_tooltip_right_edge.png mobile tooltip containment
docs/evidence/m4-r1-g10/g10_probe_results.json            machine results
```

## 4. Files changed

```
frontend/src/charts/InteractiveChart.tsx   placement engine, nearest-series hover,
                                           categorical x axis, halo, margins, height
frontend/src/charts/charts.css             proportions, overlay split, details panel,
                                           .visually-hidden definition, wrap rules
frontend/src/charts/studyCharts.tsx        label dedupe, estimator short labels,
                                           categorical flags, estimator facts
tools/visual/verify_g10.mjs                new 22-check G10 probe
docs/evidence/m4-r1-g10/                   screenshots + machine results
```

## 5. Stopping point

M4-R1-G10 complete. No M4-R2, M4-R3 or M5 work started. Awaiting user review.
