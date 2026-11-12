# M2-G0 — Visual comparison and validity repair

**Milestone:** M2-G0 (mandatory visualization gate)
**Study under test:** `coringa_coastal`
**Baseline protected:** M1 at `60a2a65`, tag `m1-verified`; M0 at `aa42c31`, tag `m0-verified`
**Scope:** presentation and interaction correctness only. No M0/M1 raster, statistic, scene ID, grid, cache or manifest value was changed.

---

## 1. What was reported

The independent browser review found that the M1 proof viewer was hard to trust as a temporal comparison:

- the ΔNDVI / ΔNDWI / ΔMNDWI view put a detailed difference map beside a nearly uniform copper footprint;
- the valid-mask view was dominated by the same uniform footprint;
- side-by-side images appeared to start at different vertical positions;
- swipe imagery showed blank strips, mismatched image bounds and a divider that did not align with geographic features;
- the divider could not be dragged reliably, and could not be used with touch or keyboard.

These were real presentation defects. The underlying masks were not defective.

---

## 2. Root-cause diagnosis

### 2.1 The valid footprint is scientifically correct

The exported rasters were inspected directly, independently of the preview code:

| Quantity | Measured value |
|---|---|
| Analysis grid | 429 × 390 px, EPSG:32644, 10 m |
| Grid pixels | 167,310 |
| AOI pixels | 165,136 |
| Earlier valid pixels | 165,136 |
| Later valid pixels | 165,136 |
| Common-valid pixels | 165,136 |
| Masked / outside-AOI pixels | 2,174 |
| Common-valid fraction of AOI | 100.0% |
| Common-valid area | 1,651.36 ha / 16.5136 km² |

`earlier_valid`, `later_valid` and `common_valid` are byte-identical binary masks inside the AOI. The common mask is exactly `earlier_valid & later_valid`. A uniform shared-valid footprint is therefore mathematically expected. It was **not** rounded, filled or manufactured.

The incorrect impression came from presentation:

1. `coverage_to_png()` paints `valid & comparable` copper `(214, 138, 93)`. On the change layers this is the same family of colour used for **positive** index change, so a fully valid AOI looked like a positive-change layer.
2. The change view paired a derived difference raster with the common-valid mask as if they were two equivalent temporal observations.
3. The mask preview occupied half the comparison workspace even when it carried no spatial variation.

### 2.2 The swipe geometry was built from two independent cards

The old CSS and DOM caused the alignment symptoms directly:

```css
.pane .slot {
  width: 100%;
  aspect-ratio: 1 / 1;      /* source raster is 429 × 390, not square */
  object-fit: contain;
}

.compare[data-mode="swipe"] .pane + .pane {
  position: absolute;
  inset: 0;                 /* covers the first card's caption area */
  clip-path: inset(0 0 0 var(--split, 50%));
}
```

- The `1 / 1` aspect ratio letterboxed every 429 × 390 raster inside a square box.
- The second absolute pane started at the top of the first **card**, while the first image started **below its caption**. The second image was therefore shifted upward by the caption height, creating the blank strip and mismatched top edge.
- The second caption was hidden, so the two sides no longer shared a common header geometry.
- The divider had `pointer-events: none`; the only interaction was `pointermove` on the whole container. There was no pointer capture, no click-to-place, no touch handling, no keyboard control and no reset.

### 2.3 Difference and quality semantics were conflated

The frontend treated a derived difference raster and a validity mask as two peer images. It also mixed temporal, change and quality layers in one long row of equally weighted tabs. Both problems were presentational, not numerical.

---

## 3. Repairs

### 3.1 One shared image stage

Every comparison now uses one explicit raster stage:

```css
.stage {
  position: relative;
  width: 100%;
  aspect-ratio: var(--raster-aspect, 429 / 390);
  overflow: hidden;
}
.stage img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
```

`--raster-aspect` is set from `grid.width / grid.height` in the actual study summary. The stage, not an independently cropped card, owns the geographic bounds. Captions, toolbars and metadata sit outside the stage and cannot change its width, height or image mapping.

### 3.2 Side-by-side comparison

- Two equal grid columns, each containing a fixed-height caption block and a stage with the same explicit aspect ratio.
- Both stage widths and heights are identical at every tested desktop width.
- Both images fill exactly the same stage bounds; the same raster coordinate maps to the same relative screen coordinate in both panes.
- At narrow widths the panes stack, but each still preserves the source aspect ratio.

### 3.3 Swipe comparison

- One `.swipe-stage`; both periods are absolutely positioned over exactly the same pixel bounds.
- The later layer is one clipped overlay: `clip-path: inset(0 0 0 var(--split))`.
- One divider line and grip sit at the same clip boundary.
- Captions and the interaction toolbar are outside the stage.
- The split is stored as a percentage, so browser resizing cannot introduce an absolute pixel offset.

### 3.4 Swipe interaction

- Click or tap to position the divider.
- Pointer drag with `setPointerCapture`, `pointerup` / `pointercancel` / `lostpointercapture` cleanup.
- Touch-compatible pointer handling with `touch-action: none` on the comparison stage only.
- Keyboard control on the divider (`role="slider"`, `tabindex="0"`, `aria-valuemin/max/now/valuetext`):
  - `←` / `↓` and `→` / `↑` step 1%;
  - `Shift` + arrow steps 10%;
  - `PageUp` / `PageDown` step 10%;
  - `Home` = 0%, `End` = 100%.
- Visible reset to 50%; double-click also resets.
- The split survives layer and analysis switches; resizing preserves the percentage.
- Reduced-motion mode removes the overlay transition.

### 3.5 Analysis modes instead of one tab row

The viewer now separates three questions:

1. **Historical** — shared-viewport earlier/later comparison for true colour, false colour, NDVI, NDWI, MNDWI, valid masks and observation counts. Supports side-by-side and swipe.
2. **Change** — one primary derived difference map with a diverging legend, explicit zero reference, common-valid coverage, measured difference statistics, measured threshold response and small earlier/later context previews. The validity layer supports the map; it does not replace a second observation.
3. **Quality** — coverage cards, neutral valid masks, neutral masked-pixel view, observation-count maps and per-pixel count histograms. The default quality layer is observation count because that is where genuine spatial variation exists.

The layer buttons are grouped under **Imagery**, **Spectral indices**, **Change analysis** and **Quality**. The temporal view switch is hidden in Change and Quality modes.

### 3.6 Neutral validity presentation

New presentation-only assets are generated from the same exported valid-mask rasters:

- `earlier_valid.png`, `later_valid.png`, `common_valid.png` — neutral sea-glass valid, charcoal masked, dark neutral AOI boundary. Copper is not used for validity.
- `masked_common.png` — light canvas with a neutral hatch over genuinely masked pixels.
- `earlier_invalid.png`, `later_invalid.png`, `common_invalid.png` — transparent RGBA overlays with a neutral hatch over invalid pixels only.
- `quality.json` — measured counts, observation histograms, source paths and SHA-256 hashes.

Generation command:

```powershell
.\.venv\Scripts\python.exe scripts\build_g0_presentation.py --study coringa_coastal
```

The builder reads the exported GeoTIFF masks, independently rasterises the AOI geometry, and refuses to write if the raster counts disagree with the frozen M1 summary. It writes only under `data/previews/g0/<study>/`. It does not touch `data/processed/m1`, `data/previews/m1`, the M1 summary or the M1 manifest, and it refuses silent overwrite unless `--force` is passed.

### 3.7 Loading, missing and error states

- Missing previews produce a visible hatched “Preview unavailable” stage rather than a collapsed or shifted frame.
- Empty change blocks, missing bundles and M0 fallback produce explicit empty states.
- The M0 fallback remains usable for historical comparison; Change and Quality are disabled when only the M0 bundle is present.
- The overlay toggle is only offered where a validity overlay is meaningful.

---

## 4. Regression and verification results

### 4.1 Numerical preservation

- M0/M1 summary, manifest and status files were byte-identical after the repair; `git diff` over `data/processed/m1` and `data/manifests` is empty.
- The M1 study was reproduced from `studies/experiments/coringa_m1.yaml` before and after the repair. The engine reported 26/26 checks and the independent audit 22/22 checks.
- The G0 builder cross-checks its raster counts against the frozen summary and fails on any mismatch.

### 4.2 Python tests

Baseline:

- 230 offline tests passed; 6 live tests passed in the original baseline run.
- `scripts/audit_m1.py --study coringa_coastal`: 22 checks, all passed.

New G0 tests:

- `backend/tests/test_g0_presentation.py`: neutral palette, geometry, count agreement, overlay transparency, no-silent-overwrite, source hashes, shared-stage frontend contract.
- `backend/tests/test_g0_api.py`: presentation endpoint, G0 file serving and traversal guard.

**Result:** all new tests passed; full offline suite passes.

### 4.3 Real-browser verification

Tooling: Playwright 1.65.0 with headless Chromium 158. The viewer was served by uvicorn on `127.0.0.1:8096`.

The browser script:

- visited the real viewer, not a DOM mock;
- checked 5 viewports: 1920×1080, 1440×900, 1280×800, 768×900, 390×844;
- checked 7 divider positions: 0, 10, 25, 50, 75, 90 and 100%;
- substituted one identical georeferenced raster on both sides and compared the stage screenshots pixel-for-pixel at every split;
- checked side-by-side identical-pattern alignment;
- switched through imagery, index, validity and observation-count layers and re-checked stage bounds;
- tested click, pointer drag with capture/release, keyboard arrows/Home/End/Shift, reset, overlay toggle and resize stability;
- checked the Change mode has one derived map, a 100% coverage indicator, measured threshold rows and a visible legend;
- checked Quality mode reports 100% on all three coverage cards, explains that uniform coverage is expected, and keeps observation counts readable;
- checked no browser console errors, no uncaught page errors and no failed network requests.

**Result:** **323 / 323 browser checks passed**, with **23 screenshots**.

Pixel alignment at every split and viewport had mean channel difference ≤ 0.5 and at most a negligible fraction of antialiased edge samples above 4/255, consistent with fractional CSS widths. There was no spatial offset, no blank strip and no divider drift.

### 4.4 Evidence

Screenshots and machine-readable results:

- `docs/evidence/m2/g0_side_1440.png`
- `docs/evidence/m2/g0_side_390.png`
- `docs/evidence/m2/g0_swipe_1440_50.png`
- `docs/evidence/m2/g0_swipe_390_50.png`
- `docs/evidence/m2/g0_swipe_split_000.png` … `g0_swipe_split_100.png`
- `docs/evidence/m2/g0_change_1440.png`, `g0_change_390.png`
- `docs/evidence/m2/g0_change_overlay_1440.png`, `g0_change_overlay_390.png`
- `docs/evidence/m2/g0_quality_1440.png`, `g0_quality_390.png`
- `docs/evidence/m2/g0_quality_common_1440.png`, `g0_quality_common_390.png`
- `docs/evidence/m2/g0_quality_masked_1440.png`, `g0_quality_masked_390.png`
- `docs/evidence/m2/g0_valid_mask_side_1440.png`, `g0_valid_mask_side_390.png`
- `docs/evidence/m2/g0_browser_results.json`

Reproduce the browser run:

```powershell
$env:HABITATSHIFT_PORT='8096'
.\.venv\Scripts\python.exe -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8096
# in a second shell:
$env:HABITATSHIFT_URL='http://127.0.0.1:8096/'
npm install --prefix tools/visual
npx playwright install chromium
node tools\visual\verify_g0.mjs
```

---

## 5. Limitations

- The identical-pattern browser test replaces the later preview `src` with the earlier preview at runtime. It tests the viewer’s geometry, clipping and interaction, not the satellite sensors’ absolute geolocation. Source registration was separately checked from the raster headers: both periods share EPSG:32644, the same affine transform, the same 429 × 390 shape and the same grid signature.
- The source rasters are 10 m analysis products. Pixel-level agreement in the viewer does not claim sub-pixel geolocation accuracy beyond the underlying Sentinel-2 L2A registration.
- M0 fallback previews were not regenerated with the neutral G0 palette; M0 remains a compatibility path. The M1 bundle is the primary research viewer.
- The uniform common-valid footprint is correct **for this study**. The same quality layout will show partial masks and hatched unavailable pixels if a future study has incomplete coverage, but no partially invalid M1 study exists yet to exercise that path visually.
- This gate repairs presentation and interaction only. It makes no new environmental claim and does not tune thresholds, train models or estimate uncertainty. Those are M2 research stages.

---

## 6. Gate decision

**M2-G0: PASS**

- Common-valid footprint numerically verified.
- Uniform masks represented honestly with neutral colours and 100% coverage indicators.
- Difference maps presented as derived change maps, not as a temporal pair.
- Side-by-side stages share exact bounds.
- Swipe uses one registered viewport, one clip boundary and one divider.
- Mouse, touch-like pointer, click, keyboard, reset and resize behaviour tested in a real browser.
- No M0/M1 numerical result changed.
- Existing tests pass; new tests pass; browser checks pass.
