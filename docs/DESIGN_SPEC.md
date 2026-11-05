# Design specification — "Midnight Teal & Copper"

**Scope.** This document fixes the visual and interaction contract *before* the
product UI is built (roadmap M0 item 9; consumed by M3, audited in M5). It
records the tokens and rules the M0 proof viewer actually implements, plus the
page-level sketches and map interactions that M3 must deliver. Nothing here is
aspirational decoration: every rule is either enforced in code today or listed
as an explicit M3 obligation.

**Enforcement points in this repository**

| Rule | Enforced by |
|---|---|
| Design tokens | `frontend/styles.css` (`:root` custom properties) |
| Masked/invalid pixels are neutral charcoal, never green or transparent | `backend/app/preprocess/preview.py` (`INVALID_RGB`) |
| One fixed NDVI ramp for both dates, so equal values share a colour | `preview.NDVI_RAMP`, `preview.ndvi_to_png` |
| Legend generated from the same ramp that renders the pixels | `preview.ndvi_legend` → `data/previews/coringa_coastal/ndvi_legend.{png,json}` |
| AOI boundary drawn from the rasterised geometry, never a CSS overlay | `preview.draw_aoi`, `preprocess.grid.aoi_raster_mask` |
| No fabricated numbers in the UI | `frontend/app.js` renders only `/api/study` (pipeline output) |
| The viewer cannot compute values the pipeline did not measure | `backend/app/api/app.py` serves stored artifacts only |
| Keyboard focus, reduced motion, contrast | `frontend/styles.css` `:focus-visible`, `prefers-reduced-motion`, measured ratios below |

## 1. Colour tokens

Values are the actual custom properties in `frontend/styles.css`.

| Token | Value | CSS variable | Usage |
|---|---|---|---|
| Midnight Teal | `#193C43` | `--teal` | Top bar, panel headings, primary surfaces |
| Teal Soft | `#24545C` | `--teal-soft` | Hover/pressed states on teal (reserved) |
| Copper | `#D68A5D` | `--copper` | Brand mark, AOI outline, comparable-pixel highlight, banner rule |
| Warm Ivory | `#F2F0EB` | `--ivory` | Page background |
| Sea Glass | `#7FABA7` | `--sea-glass` | Brand tag, valid-pixel map tone |
| Deep Charcoal | `#18272D` | `--charcoal` | Body text, technical surfaces, masked pixels, focus ring |
| Light Rule | `#D8D3C8` | `--rule` | Separators and component boundaries |
| Paper | `#FBFAF6` | `--paper` | Elevated panels and the comparison figures |

**Measured contrast** (WCAG 2.1 relative luminance, computed from the values
above):

| Pair | Ratio | Passes |
|---|---|---|
| `#18272D` on `#F2F0EB` (body text) | 13.49:1 | AAA |
| `#18272D` on `#FBFAF6` (panel text) | 14.71:1 | AAA |
| `#193C43` on `#F2F0EB` (headings) | 10.43:1 | AAA |
| `#F2F0EB` on `#193C43` (top bar text) | 10.43:1 | AAA |
| `#CFE0DD` on `#193C43` (top-bar note) | 8.68:1 | AAA |
| `#56686D` on `#F2F0EB` (mono labels) | 5.13:1 | AA |
| `#56686D` on `#FBFAF6` (legend note, table headers) | 5.59:1 | AA |
| `#6D5A44` on `#F2F0EB` (eyebrow) | 5.77:1 | AA |
| `#7FABA7` on `#193C43` (brand tag) | 4.68:1 | AA |
| `#D68A5D` on `#F2F0EB` (copper as text) | 2.41:1 | **fails — never used for text** |

Copper is decorative and data-semantic only; all small text uses charcoal,
teal or the label greys above. The focus ring is charcoal, not copper, because
copper does not reach the 3:1 non-text contrast minimum against the ivory/paper
surfaces that contain the focusable elements.

**Data-semantic colours (must never be re-used as brand decoration)**

| Meaning | Value | Source of truth |
|---|---|---|
| Masked / invalid / outside AOI | `#18272D` charcoal | `preview.INVALID_RGB` |
| Valid observation | `#7FABA7` sea glass | `preview.coverage_to_png` |
| Comparable in both dates | `#D68A5D` copper | `preview.coverage_to_png(comparable=…)` |
| NDVI ramp | 9 fixed stops, `-1.0 → 1.0` | `preview.NDVI_RAMP` |
| Himalayan case (M3/M4) | restrained stone/ice/snow greys, no new brand hue | this contract |
| Kathmandu case (M3/M4) | terracotta/urban grid emphasis | this contract |

NDVI ramp stops actually shipped:

`-1.00 #24424F`, `-0.40 #56706A`, `-0.15 #A89E7C`, `-0.02 #C4B284`,
`0.10 #B0BA8A`, `0.25 #8CA87A`, `0.45 #568A60`, `0.65 #2C6C4E`,
`1.00 #124A38`.

Rule: a brand colour may never replace a data colour. If a legend needs a hue
the ramp does not contain, the ramp is extended deliberately and re-documented
here rather than improvised per screen.

## 2. Typography

| Role | M0 implementation | M3 target | Fallback chain |
|---|---|---|---|
| Editorial display (h1) | `--serif` | Newsreader (self-hosted, subset) | `"Iowan Old Style", "Palatino Linotype", Georgia, serif` |
| Interface / body | `--sans` | IBM Plex Sans | `"Segoe UI", system-ui, -apple-system, "Helvetica Neue", sans-serif` |
| Scientific metadata, scene IDs, legends | `--mono` | IBM Plex Mono | `ui-monospace, "SFMono-Regular", "Cascadia Mono", Consolas, monospace` |

Type scale at M0: `h1 clamp(2.1rem, 4.6vw, 3.4rem)`, body `16px/1.55`, lede
`≤62ch`, mono labels `0.66–0.9rem` with `0.10–0.18em` letter spacing.
Minimum rendered size anywhere: `0.66rem` uppercase mono labels only; no body
copy below `0.8rem`. M3 must keep the small-label floor above 11 px effective.

## 3. Page inventory and sketches

### 3.1 M0 proof viewer (built, `frontend/index.html`)

```
┌──────────────────────────────────────────────────────────────┐
│ teal topbar: ◆ HabitatShift   M0 · data proof   [note]       │
├──────────────────────────────────────────────────────────────┤
│ STUDY A · COASTAL ECOTONE                                    │
│ Coringa / Godavari delta            (editorial serif h1)     │
│ lede …                                                       │
│ AOI facts: CRS | resolution | raster px | comparable px | …  │
│ [banner: only when comparison is not suitable]               │
│ Layer:  [True colour] [NDVI] [Valid mask]                    │
│ Compare:[Side by side] [Swipe]                               │
│ ┌──────────── earlier 2020-03-26 ─┬──────── later 2025-03-25 ┐│
│ │      real PNG preview           │      real PNG preview    ││
│ └─────────────────────────────────┴──────────────────────────┘│
│ [NDVI legend strip]  + legend note (masked = charcoal)       │
│ ┌ measured metadata ┬ validity & limits ┬ provenance ┐       │
└──────────────────────────────────────────────────────────────┘
```

The proof viewer deliberately shows *measurements and masks*, not a hero
marketing layout: its job is to let a reviewer check data reality in seconds.
The "swipe" mode is a CSS clip of two images already aligned on the same grid;
it is not a map and makes no georeferencing claim beyond the shared grid
signature.

### 3.2 Landing (M3)

```
┌ teal nav ────────────────────────────────────────────────────┐
│ HabitatShift   Atlas  Study areas  Methods  Experiments      │
├──────────────────────────────────────────────────────────────┤
│  "Read the landscape.                    ┌─────────────────┐ │
│   Trace what changed."                   │ real georef.    │ │
│  subline: real scenes, multi-date,        │ true-colour /   │ │
│  reproducible results                    │ false-colour    │ │
│  [Explore the Atlas] [View the Method]   │ comparison      │ │
│  provenance line under the image         └─────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ five case entries (asymmetric editorial grid, real imagery)  │
│ 3-step "acquisition → mask → evidence" narrative             │
│ credibility strip: open data · documented scenes · repeatable │
└ footer: attribution, licences, limits, repo ─────────────────┘
```

Hero imagery must be a real generated preview with its scene IDs and dates
printed next to it. No 3D globe, no gradient mega-hero, no decorative satellite
photography.

### 3.3 Workstation (M3) — 1440×900

```
┌ nav ─────────────────────────────────────────────────────────┐
│ study header: region · windows · sensor · valid coverage ·   │
│               method · provenance                            │
├──────────────────────────────────────┬───────────────────────┤
│ geography stage 65–75 %              │ research inspector    │
│  synchronized maps, swipe handle,    │  25–35 %: layers,     │
│  locked pan/zoom, scale bar,         │  legends, pixel/ROI   │
│  attribution, missing-data hatch     │  values, cloud notes  │
├──────────────────────────────────────┴───────────────────────┤
│ analysis dock: timeline · distributions · transitions · model │
└──────────────────────────────────────────────────────────────┘
```

### 3.4 Nepal study (M3/M4) — one study, two event tabs

```
[ Study D · Himalayan evidence ]  ( D1 2025 lake drainage | D2 2026 rock–ice )
subregion switcher: source area · crossing · downstream valley
per tab: pre/post swipe · exact acquisition times · index/difference layer ·
         cloud/missing-data hatch · provenance block ·
         "what the evidence supports" vs "what it does not"
```

The two events never share a tab, a legend heading or a metric label. Stone/ice
tonality is used for the cryosphere layers; casualty numbers and disaster
footage are out of scope per roadmap §7.5. Each tab must show the *measured*
temporal gap between the observations it compares (see
`docs/M0_HIMALAYAN_DATA_FEASIBILITY.md`: D1 has no clean same-week pair).

### 3.5 Kathmandu (M3/M4)

Terracotta/urban grid emphasis, NDVI/NDBI channels presented as *candidate*
signals with the bare-soil negative control visible in the same panel.

## 4. Required map interactions (M3 acceptance list)

- [ ] Vertical before/after swipe on exactly co-registered rasters (same grid signature)
- [ ] Side-by-side with locked pan/zoom and a shared scale bar
- [ ] Opacity overlay and true/false-colour toggle
- [ ] Index layer (NDVI/NDWI/MNDWI) plus delta heatmap with a fixed legend
- [ ] Change-threshold slider recomputing summary statistics from precomputed rasters
- [ ] Click-to-inspect: per-date band reflectance, index value, valid count, coordinates, item IDs
- [ ] Draw/select ROI for locally recomputed statistics, labelled client- or server-side
- [ ] Observation time-strip with exact acquisition dates and quality masks
- [ ] One-click methodology/provenance export
- [ ] Study-type-aware panels (no universal NDVI dashboard for every study)

M0 contributes the data side of these interactions: a single grid signature per
study (`AnalysisWindow.signature()`), pixel-aligned GeoTIFFs, and a manifest
that carries every value an inspector panel will show. M0 implements only the
first item in a limited form (image swipe, not a map).

## 5. Accessibility and responsive rules

- Visible focus ring: `2px solid var(--charcoal)` with `2px` offset on every
  interactive element; skip link to the comparison region.
- Reduced motion: `prefers-reduced-motion` disables smooth scrolling; no
  autoplaying animation of imagery.
- Body text contrast ≥ 4.5:1 (`#18272D` on `#F2F0EB` = 13.49:1); mono labels
  ≥ 4.5:1 at their rendered size (ratios measured above). Legends are never
  encoded by colour alone; units and numeric breaks are printed.
- Layout must stay usable at 1920×1080, 1440×900, 1280×800, 768 px and 390 px.
  Below 760 px the comparison collapses to a single column and controls wrap
  (implemented in `styles.css`).

## 6. Design QA checklist (roadmap section 7.6) — M0 status

| Check | Status at M0 |
|---|---|
| Consistent typography/spacing/theme between proof viewer and future pages | Implemented for the proof viewer; contract fixed for M3 |
| Imagery is dataset-derived, attribution visible | Yes — PNG previews from real scenes, attribution in the footer and manifest |
| No misleading "10 m" claims for coarser products | Yes — the 20 m SCL is nearest-neighbour resampled and documented as such in the manifest |
| Screenshots at 1920/1440/1280/768/390 | **Not yet done** — M0 ships no interactive map; required at M3 |
| No overflow, unreadable legends, tiny default panels | Verified manually on the proof viewer; re-verify at M3 |
| No P0/P1 console errors, keyboard focus, contrast, reduced motion | Focus ring, skip link, reduced-motion and measured contrast implemented; viewer loads with zero console errors |
| Browser E2E for swipe/zoom/layers/pixel inspection/exports | **Not yet** — depends on the M3 map stack |

## 7. Prohibited visuals

Neon gradients, purple/black "AI dashboard" styling, glow effects, generated
illustrative imagery presented as data, repeated identical card grids, large
empty regions, unreadable micro-type, decorative animation, mismatched page
themes, and any visualisation that implies a measurement the pipeline did not
make.

## 8. Open items handed to M3

1. Map renderer decision (MapLibre GL JS vs. a TiTiler/rio-tiler-backed raster
   server) after a bounded technical proof — roadmap section 7.4.
2. Self-hosted font subsetting for Newsreader + IBM Plex, with the fallback
   chains above preserved.
3. Tile/preview pipeline from the existing GeoTIFFs so the browser never loads
   a full-resolution original.
4. Screenshot pack and browser E2E covering the interaction list in section 4.
