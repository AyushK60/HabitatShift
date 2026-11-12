# M4-R3 visual QA

Status: complete. All screenshots live in `docs/evidence/m4-r3/` and are
committed. Product: existing Midnight Teal & Copper system untouched — new
surfaces reuse the workstation tokens (`--teal`, `--copper`, `--ivory`,
serif/sans/mono stack), the existing `.segmented` / `.insp-facts` /
`.finding-*` components and the muted data-semantic map colours.

## Reviewed views

| Screenshot | Viewport | What was checked |
|---|---|---|
| `explore_overview_1440.png` | 1440×900 | Explore the Evidence overview: meaning paragraph, facts (period, footprint, overlaps, MMU), curated-selection disclosure, finding groups; brand palette intact; selected region teal-outlined on the map |
| `explore_filters_1440.png` | 1440×900 | Filter block: direction / index / threshold behaviour / related / region search render compactly, no wrapping defects, count line ("Showing 19 of 19") |
| `explore_390.png` | 390×844 | Mobile: workstation stacks, no horizontal overflow (0 px measured after the card wrap fix) |
| `map_tooltip_selection_1440.png` | 1440×900 | Region hover tooltip (display id, Δindex direction, area, evidence_id) over the change map; overview + disclosure visible beside it |
| `m4_r3_explore_selected_1440.png` | 1440×900 | Selected finding card open with measurement facts; map highlight matches |
| `research_math_block_1440.png` | 1440×900 | Research Mode mathematical method block: index definition, ΔI formula, candidate-selection inequality, component pipeline incl. top-5 curated-selection caveat, denominator |
| `research_sensitivity_1440.png` | 1440×900 | Threshold-sensitivity neighbours table + recorded label rules |
| `m4_r3_partial_study_1440.png` | 1440×900 | Purepu PARTIAL-evidence note in the Explore overview |
| `m4_r3_responsive_1920x1080 / 1280x800 / 768x900 / 390x844.png` | 4 viewports | Explore + selected finding card; overflow ≤ 1 px asserted per viewport in the suite |
| `showcase_research_mode.png` | 1440×900 | Static showcase (backend stopped): Research Mode fully rendered from the bundle |

## Findings and fixes during QA

1. **390 px overflow, 14 px, finding card** — pre-existing on the unmodified
   build (verified by rebuilding from the unmodified tree and re-measuring);
   caused by the unbreakable record/source mono line. Fixed with
   `overflow-wrap: anywhere` on the card's mono/fact lines. All viewports now
   measure 0 px overflow with a card open.
2. **Hover tooltip intercepted region clicks** — the MapLibre popup sat under
   the pointer at click time; set `pointer-events: none` on
   `.maplibregl-popup.findings-hover` (it is purely informational).
3. **Method-block wording** — the Δ-definition legend duplicated the
   record's own "on the shared-valid grid" phrasing; reduced to the recorded
   definition + grid line.
4. No other visual defects observed; typography, spacing and colour usage
   follow the existing workstation system, and no card exceeds readable
   dimensions (the eight guided questions use a compact `h5` question style).

## Verdict

Explore the Evidence and Research Mode are visually consistent with the
existing product, readable at every supported viewport, and free of
horizontal overflow. The judge-pass evidence is the committed screenshot set
plus the machine-checked overflow/console assertions in
`m4_r3_browser_results.json` (35/35) and `showcase_no_backend_results.json`
(17/17).
