# Design system: Survey Sheet

A research publication, not a dashboard. Real Sentinel imagery carries the colour; the interface is quiet: very light cool tones, near-black type, one deep-blue accent. The home page opens on a full-bleed satellite image of Imja Tsho that plays 2018 to 2024 and marks the lake that grew.

## Colour

| Role | Token | Value |
|---|---|---|
| Ink (type, selected states) | `--ink` | #0d1320 |
| Accent (actions, links, primary data series) | `--accent` / `--accent-deep` | #1b4f9c / #123a75 |
| Accent tint (explain blocks, success) | `--accent-soft` | #dbe6f6 |
| Page | `--page` | #f3f6fa |
| Band sections | `--band` | #e8eef7 |
| Plates and cards | `--plate` / `--plate-2` | #fbfcfe / #eef2f8 |
| Rules | `--rule` / `--rule-strong` | #d3dae6 / #a9b4c8 |
| Secondary data series | `--optical` / `--model` | slate #6b7690 / light blue #5b8bd6 |
| Warning | `--alert` | #b3261e |

Chart series use shades of the blue plus slate and ink; hue is never the only cue (hollow versus filled marks, line weight). Old variable names (`--teal`, `--copper`, `--ivory`) are remapped to these.

## Type

Source Serif 4 for headings and large numbers; Hanken Grotesk for text and controls; JetBrains Mono for scene ids and small data. Self-hosted through `@fontsource`.

## Shape and layout

Square corners (2 px). No pill or oval containers. Content width 1280 px; the top bar, hero text and page content share one left edge (`--edge`). Sections alternate between the page tone and a slightly deeper band. Findings are ruled rows with a real figure beside plain text, not cards.

## Motion

Home hero: a 14 second loop (2018, fade to 2024, fill the new lake and label it); year buttons jump and pause it. Route changes rise and fade in 360 ms; bars and counters animate once; the guided tour rings its target. All of it respects `prefers-reduced-motion` (the hero then shows the 2024 state, static).

## Components

- Top bar: transparent over the home photograph, solid white once scrolled and on every other page.
- Audience switch (Plain words / Technical) drives every `Explain` block under graphs.
- `HeroChange`, `BeforeAfter`, `ScoreBars`: figures built from real data by `scripts/make_site_figures.py`.
- `DotPlot`: method scores with 95% intervals printed on the row; hover only highlights.
- Charts: readout docked in a fixed strip above the plot so nothing covers data.
- Guided tour: site-wide, nine steps, keyboard operable.

## Rules

Uncertainty is always drawn. Negative results get the same weight as positive ones. No gradient text, no coloured side borders, no kicker labels above headings, no decorative imagery: every picture is a real scene or a real model output, and says so.
