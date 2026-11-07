# M3 handoff

**Status:** complete, ready for user review. Branch `m3-workstation`.
**Baseline:** M2 `7953225` untouched; scientific artefacts byte-identical.
**Architecture decision:** `docs/architecture/M3_ARCHITECTURE_DECISION.md`
**Verification:** `docs/M3_VISUAL_QA.md` (33/33 browser checks, 290 pytest)

---

## 1. Run it

```powershell
# one-time (already done on this machine):
cd frontend
npm install
npm run build          # emits frontend/dist

# every run:
cd ..
python -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8098
# open http://127.0.0.1:8098/
```

- With a build present, `/` serves the M3 product and `/legacy` serves the
  M0–M2 proof viewer.
- Without a build, `/` serves the legacy viewer exactly as M2 did, so every
  M2 reproduction command still works.
- Frontend development: `cd frontend && npm run dev` (Vite on :5173,
  proxying `/api` and `/files` to :8096 — change the proxy target in
  `frontend/vite.config.ts` if you use another port).

## 2. Re-run verification

```powershell
python -m pytest                                   # 290 passed
HABITATSHIFT_URL=http://127.0.0.1:8098/ `
  node tools/visual/verify_m3.mjs                  # 33/33 browser checks
```

## 3. Map of the code

```
frontend/
  src/api/            typed client for the read-only backend routes
  src/components/     shell (nav/footer), shared SwipeStage (hover-follow),
                      small UI atoms
  src/pages/          LandingPage, WorkstationPage, ExperimentsPage, MethodsPage
  src/workstation/    MapCompare (MapLibre), Inspector, Dock, layers.ts
  src/styles/         tokens (DESIGN_SPEC §1), shell, landing, swipe,
                      workstation, experiments, methods
  legacy/             the untouched M0–M2 proof viewer (served at /legacy)
backend/app/api/app.py   additive routes: /georef, /pixel, /roi,
                         /api/studies/registry, dist/legacy static serving
backend/tests/test_m3_api.py   georef corners, pixel values, ROI labelling,
                               registry serving
tools/visual/verify_m3.mjs     the 33-check Playwright suite
docs/evidence/m3/              screenshots + m3_browser_results.json
```

## 4. Scientific integrity contract in the UI

- Every number originates from a stored artefact; the API serves them
  verbatim. `/pixel` and `/roi` sample the same frozen GeoTIFFs server-side
  and label their source in the response.
- Quality layers explain what earlier/later/shared valid mean, why the three
  masks are byte-identical for this study (165,136 = 165,136 = 165,136 px),
  and the AOI-vs-grid denominator (165,136 vs 167,310 px, 2,174 masked/outside).
- Uncertainty language is "resampling variability for this AOI and grid",
  never a population confidence interval.
- No supervised classification numbers anywhere (insufficient independent
  labels — M2 finding).
- The two Himalayan events remain separate registry entries with separate
  event dates; neither has processed imagery, and neither pretends to.

## 5. Deferred / known limits

- Touch drag in swipe mode moves the divider (not the map); pan/zoom on touch
  via side-by-side or opacity mode.
- Image-source map placement is valid for kilometre-scale AOIs; large studies
  would need tiled serving (ADR §3 trigger).
- React/TS unit tests (Vitest) were not added; coverage is pytest + the
  Playwright suite. If unit tests are wanted at M4, re-add vitest (removed
  to keep `npm audit` clean while unused).
- `npm audit`: 0 vulnerabilities at handoff (maplibre-gl 6.16.0).

## 6. Git checkpoints

| Commit | Gate |
|---|---|
| `c69d87e` | M3-G0 scaffold, georef/pixel/ROI endpoints, ADR |
| `fa20dae` | M3-G1 design system, shell, landing, gallery |
| `1d2afce` | M3-G2 workstation (maps, inspector, dock) |
| `870b4df` | M3-G3+G4 UI: experiments + methods pages |
| (this commit) | M3-G4 verification, docs, hardening |
