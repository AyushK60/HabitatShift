# M3 — Visual QA and browser verification

**Milestone:** M3 (complete product UX, signature visual design, research workstation)
**Baseline protected:** M2 at `7953225`; branch `m3-workstation`
**Scope:** product interface and presentation. No M0/M1/M2 raster value, mask,
statistic, scene ID, threshold, seed or manifest field was changed. The
backend gained read-only endpoints (`/georef`, `/pixel`, `/roi`,
`/api/studies/registry`) and static-serving of the built product; all new
computation is server-side sampling of the already-frozen GeoTIFFs, explicitly
labelled in every response (see `docs/architecture/M3_ARCHITECTURE_DECISION.md`).

---

## 1. What was built

| Surface | Route | Contents |
|---|---|---|
| Landing / Atlas | `/` | Editorial hero with the real Coringa swipe comparison (dates, scene IDs, attribution from the M1 summary), measured facts strip, registry-driven five-study gallery with true statuses, acquisition→mask→evidence narrative, credibility strip |
| Research workstation | `/workstation` | MapLibre georeferenced map comparison (side-by-side synchronised, hover-follow swipe, opacity), change and quality analyses, research inspector (legend/meaning, acquisition, pixel probe, ROI), collapsible analysis dock |
| Experiments | `/experiments` | Recorded M2 run: threshold explorer (index/threshold switching), estimator comparison, block-bootstrap uncertainty, hypothesis verdicts, guardrails, exports |
| Methods | `/methods` | Eleven documented method steps, study-recorded limitations, status vocabulary, provenance exports, attribution/licensing |
| Legacy proof viewer | `/legacy` | The untouched M0–M2 viewer, still served with its file contract test |

Design system: Midnight Teal & Copper per `docs/DESIGN_SPEC.md`; self-hosted
Newsreader (variable), IBM Plex Sans, IBM Plex Mono. Copper is never used for
small text on ivory (contrast 2.41:1 — the AA-safe `--copper-deep` tone is
used instead). Scientific ramps (NDVI/NDWI/MNDWI, diverging change map,
copper observation counts, neutral validity) are unchanged data semantics.

## 2. Numerical preservation

- `git diff` over `data/processed`, `data/manifests`, `data/previews` and
  `studies/` is empty for the whole milestone (presentation and product code
  only; the registry is served verbatim, never rewritten).
- Full offline pytest suite after every gate: **290 passed** (284 baseline +
  6 new M3 API tests in `backend/tests/test_m3_api.py`).
- The one frontend-coupled backend test (`test_g0_presentation.py`) was
  re-pointed at `frontend/legacy/` with its assertions unchanged.

## 3. Real-browser verification (Playwright/Chromium)

Tool: Playwright 1.65 against the production build served by uvicorn
(`tools/visual/verify_m3.mjs`). Result: **33 / 33 checks passed**, machine
readable in `docs/evidence/m3/m3_browser_results.json`.

| # | Check | Result |
|---|---|---|
| 1 | Landing renders hero headline; "Explore the Atlas" navigates to the workstation | pass |
| 2 | Gallery shows honest Feasibility/Planned statuses; Study A card opens the investigation | pass |
| 3 | Side-by-side maps stay synchronised (zoom + centre identical after zooming) | pass |
| 4 | Divider follows mouse hover with no click (25%→75%+); position survives cursor exit | pass |
| 5 | Touch tap places divider; synthetic touch drag moves divider (20%→70%) | pass |
| 6 | Keyboard: arrows ±1%, Shift+arrows ±10%, Home=0, End=100; `role="slider"` semantics | pass |
| 7 | Reset returns divider to 50% | pass |
| 8 | Layer switch updates both maps' raster sources (explicit per-layer mapping audit) | pass |
| 9 | Shared-valid layer explains byte-identical masks; coverage accounting shows 165,136 AOI px vs 167,310 grid px; observation-count legend note present | pass |
| 10 | Pixel probe click returns measured B08 NIR + NDVI (server-side full-resolution sample) | pass |
| 11 | Experiments page shows ≥3 recorded charts; uncertainty never described as a population CI | pass |
| 12 | Threshold switch (±0.25) and index switch (NDWI/MNDWI) update measured areas | pass |
| 13 | No horizontal overflow at 1920/1440/1280/768/390; workstation comparison fits viewport height on desktop | pass |
| 14 | Methods page exposes manifest export; manifest and experiments endpoints serve recorded JSON | pass |
| 15 | No console errors, page errors or failed network requests (after fixing empty-URL MapLibre image sources) | pass |

During verification the suite caught and drove three real fixes:

1. **MapLibre image sources were created with empty URLs** for optional
   overlays (validity overlay off), causing `InvalidStateError` decode errors
   — sources are now created lazily on the first real image.
2. **A shared style object across the two maps** corrupted the later map —
   each map now gets its own style.
3. **`splitRef.current = split` in the render body** clobbered a pending
   swipe update whenever the same tap also triggered a pixel-probe re-render —
   the ref is now the interaction source of truth, synced from the prop after
   commit.
4. Touch pointers in swipe mode are claimed in the capture phase so the
   divider wins over the map canvas; mouse clicks stay free for the probe.
5. maplibre-gl was upgraded 5.24 → 6.16 (fixes a critical XSS advisory,
   GHSA-jrc7-96c5-q579) with the Vite worker-URL wiring; `npm audit` is now
   clean (0 vulnerabilities); unused vitest was removed (Playwright is the
   frontend test runner).

## 4. Screenshot evidence (`docs/evidence/m3/`)

- `m3_landing_1440x900.png`, `m3_landing_1920x1080.png`, `m3_landing_1280x800.png`, `m3_landing_768.png`, `m3_landing_390.png`
- `m3_landing_1440_gallery.png` — five-study gallery with true statuses
- `m3_workstation_1440_default.png`, `m3_workstation_1440x900.png`, `m3_workstation_1920x1080.png`, `m3_workstation_1280x800.png`, `m3_workstation_768.png`, `m3_workstation_390.png`
- `m3_workstation_1440_swipe_hover.png` — divider mid-image, readout 78/25
- `m3_workstation_1440_mndwi_swipe.png` — index layer in swipe view
- `m3_workstation_1440_quality_shared_valid.png` — coverage accounting + byte-identical explanation
- `m3_workstation_1440_quality_obs_count.png` — observation-count layer
- `m3_workstation_1440_pixel_probe.png` — measured per-period values
- `m3_experiments_1440_top.png`, `m3_experiments_1440_threshold.png`
- `m3_methods_1440.png`
- `m3_browser_results.json` — machine-readable check results

## 5. Known limitations (honest)

- The swipe divider in map swipe mode is pointer-transparent (so map clicks
  keep working for the pixel probe); the divider therefore cannot be
  click-dragged with a mouse — hover-follow, touch drag and the keyboard
  cover all interaction paths.
- In swipe mode a touch drag moves the divider rather than panning the map;
  touch users pan/zoom in side-by-side or opacity mode.
- Map placement uses raster image sources pinned to the four reprojected grid
  corners; at this 4.3 km AOI the UTM→WGS84 convergence error is far below
  one pixel, but studies tens of kilometres wide would need true tiled
  serving (documented trigger in the ADR).
- ROI statistics reuse each index's recorded primary threshold; the ROI tool
  does not invent new thresholds.
- Only the Coringa study has a processed bundle; every other gallery entry
  states its real registry status with an AOI-window schematic (drawn from the
  registry bounds), never fabricated imagery.
- Playwright touchscreen coverage is a real tap plus a synthetic touch-pointer
  drag (Chromium offers no high-level touch-drag); the pointer-handler
  contract it exercises is the same code path real mobile browsers hit.
