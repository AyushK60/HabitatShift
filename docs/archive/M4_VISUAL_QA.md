# M4 visual QA & browser verification

**Result: all checks pass.** Backend-enhanced suite **39/39**
(`docs/evidence/m4/m4_browser_results.json`), backend-independent showcase
suite **10/10** (`docs/evidence/m4/showcase_no_backend_results.json`), pytest
**313 passed**, independent M2 audit **149/149**.

## How to re-run

```powershell
# backend suite (uvicorn on :8098 serving frontend/dist)
HABITATSHIFT_URL=http://127.0.0.1:8098/ node tools/visual/verify_m4.mjs

# showcase suite (no Python at all — any static server on frontend/dist)
cd frontend/dist; python -m http.server 8099
node tools/visual/verify_m4_showcase.mjs   # edit BASE_URL to :8099 first

python -m pytest                           # 313 passed
```

## What the M4 suite covers (beyond the preserved M3 contracts)

1. Gallery renders **six processed investigations** with real bundle media and
   per-study routes; the 2025 event carries the recorded PARTIAL chip and is
   the only partial card.
2. Chilika exposes **both matched experiments**; switching updates the
   recorded acquisitions on the same grid.
3. Interactive charts: hover snaps to the nearest recorded point with a
   vertical guide and a tooltip carrying exact values, units, valid-pixel
   denominators and a plain-language interpretation; tooltip values verified
   against the recorded threshold sweep.
4. Keyboard: arrow keys walk recorded points, Enter pins, Escape dismisses;
   touch tap pins.
5. Every chart states what **can** and what **cannot** be concluded.
6. D1 renders as a PARTIAL event investigation with the same-day observation
   recorded and its exclusion from difference baselines explained; the
   "lake area ≠ discharged volume" and external-InSAR statements are visible.
7. D2 is a distinct rock–ice collapse view (different mechanism text, no
   PARTIAL chip, event date 2026-08-26).
8. Kathmandu exposes NDBI with the "not a building detector" guardrail.
9. Bundles are served as static artefacts carrying experiments, chart series,
   checksums and attribution; the workstation labels its evidence mode.
10. Coringa still activates the live probe (pixel probe returns measured
    reflectance + indices) and all M3 interaction contracts (synchronised
    side-by-side maps, hover/touch/keyboard swipe, reset, layer switching,
    quality views, experiments workspace, responsive 1920→390 layouts).
11. Methods page documents the radiometry correction and the portable showcase.
12. Console/page-error hygiene: zero page errors, zero failed requests,
    no unexpected console errors.

## Showcase without backend (10/10)

With only `frontend/dist` on a static file server (no Python process):
landing, all five non-reference study workstations (map layer loaded from
`/studies/<id>/previews/…`), the Chilika experiment switcher, dock charts and
the interactive tooltip all work. The only failing request is the backend
reachability probe (`/api/studies/registry`), whose failure is the documented
mechanism that switches the UI into showcase mode. Processed scientific
layers require no internet connection; basemaps are plain colour fills, so
the whole showcase also works offline.

## Screenshots (docs/evidence/m4/)

- `m4_landing_1440_gallery.png` — six-study gallery with real composites.
- `m4_chilika_workstation_1440.png` — Chilika dry-season swipe comparison.
- `m4_interactive_chart_hover.png` / `m4_interactive_chart_keyboard.png` —
  tooltip and pinned-keyboard states on the threshold chart.
- `m4_d1_event_view.png` / `m4_d2_event_view.png` — the two separate event
  investigations.
- `m4_kathmandu_workstation.png`, `m4_pixel_probe_live.png`,
  `m4_methods_1440.png`, responsive sets (1920/1440/1280/768/390).
- `showcase_no_backend_chilika.png` — showcase with the backend stopped.

## Bugs found and fixed during QA

1. **Study-switch crash.** Navigating between studies could throw
   `Error: Style is not done loading` from MapLibre and unmount the whole
   React tree. Fixed with guarded teardown, a style-ready deferral helper
   (`whenStyleReady`, `idle`-based because `once("load")` never re-fires), and
   a MapLibre error filter for benign lifecycle messages. Stress-tested with
   repeated switches.
2. **Bundle path rebasing.** Showcase preview URLs were constructed without
   the bundle prefix (landing) or from unrebased paths (gallery); fixed in
   `bundle.ts`/`LandingPage.tsx` and verified by a zero-404 probe across all
   routes.
3. **Live/showcase mixing.** When the backend was reachable, the live
   resolver received rebased bundle paths and 404'd; the rebase is now
   conditional on the resolved evidence mode.
4. **Dock state persistence.** The expanded dock persisted across study
   switches and covered the map; study-specific state now resets on study
   change.
