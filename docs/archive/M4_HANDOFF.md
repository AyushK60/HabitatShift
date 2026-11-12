# M4 handoff

**Status:** complete, ready for user review. Branch `m4-studies`, based on the
M3 baseline `d569dc8` (verified before any change). No external push or
deployment. M5 not started.

---

## 1. What M4 delivered

1. **Five studies, six investigations processed** from real Sentinel-2 L2A
   observations: Chilika (matched dry-season + matched post-monsoon — the
   documented seasonal-sensitivity pair), Western Ghats (Supa taluk forest
   block, with Copernicus GLO-30 DEM context), two separate Himalayan event
   investigations (D1 PARTIAL, D2 constrained), and the Kathmandu built-up
   pilot. Coringa's frozen M0–M2 evidence was verified untouched (149/149
   audit checks) and remains the reference case.
2. **A radiometry correctness fix with recorded provenance**: the 2025 Earth
   Search reprocessing stores baseline-05.11 DNs without the baked +1000
   offset while metadata still declares it. The engine now validates every
   observation's applied transform against a physical floor, retries
   scale-only, refuses observations that satisfy no convention, and records
   the full evidence per observation (`docs/M4_radiometry_incident.md`).
3. **A standardized study-bundle architecture** (schema
   `habitatshift-m4-bundle/1`): per study, a checksummed
   `frontend/public/studies/<study_id>/bundle.json` plus flat preview copies —
   study metadata, AOI, georeferenced grid placement, per-experiment M1
   summaries with full threshold sweeps, distilled chart series, quality
   information, interpretation guardrails (can/cannot-conclude), DEM and
   event context, provenance and SHA-256 checksums. Built by
   `scripts/build_showcase_bundles.py`; validated by
   `backend/tests/test_m4_bundles.py`.
4. **A portable Showcase Mode**: the website renders every completed study
   with no Python backend — verified 10/10 with the backend stopped. Live
   Analysis (pixel probe, ROI, validity overlays) remains a clearly labelled
   enhancement that activates only when the backend serves the study's frozen
   outputs (today: Coringa).
5. **An interactive, explanatory chart system** (one reusable component,
   `frontend/src/charts/InteractiveChart.tsx`): hover snapping to nearest
   recorded points (no interpolation), vertical guide, tooltips with series,
   exact x/y values, units, denominators and interpretation; click-to-pin,
   Esc-to-dismiss, touch tap, full keyboard navigation, legend series
   toggles, no layout shifts, and a visually hidden recorded-value table for
   screen readers. Applied to threshold sensitivity, per-period means,
   estimator comparison and block-bootstrap uncertainty (Coringa) across the
   M2 SVG-chart generation and all new M4 charts.
6. **Distinct study experiences** on a shared shell: the Coringa reference
   workstation (unchanged layout, now bundle-driven), Chilika's experiment
   switcher, the two separate Himalayan event views (own timelines, known
   unprocessed observations, external references, InSAR boundary statement),
   the Kathmandu NDBI guardrail view, and the Western Ghats DEM context
   panel. The landing gallery shows real processed composites for all six
   cards and the recorded PARTIAL verdict for D1.

## 2. Verification results (all re-runnable)

| Check | Result |
|---|---|
| Backend tests (`python -m pytest`) | **313 passed** (290 baseline + 8 radiometry + 15 bundle) |
| Browser suite with backend (`tools/visual/verify_m4.mjs`) | **39/39 passed** |
| Showcase suite, backend stopped (`tools/visual/verify_m4_showcase.mjs`) | **10/10 passed** |
| Independent M2 audit (`scripts/audit_m2.py`) | **149/149 passed** |
| Production frontend build (`tsc --noEmit && vite build`) | clean (chunk-size warning only, unchanged from M3) |
| `npm audit` | 0 vulnerabilities (no new dependencies added in M4) |
| Engine verification per M4 run | 20–32 checks each, all passed |

Screenshots and machine-readable results: `docs/evidence/m4/`.

## 3. Studies: exact source scenes

Full per-window tables: `docs/M4_FEASIBILITY.md` (scene selection) and
`docs/M4_STUDY_RESULTS.md` (recorded numbers). Highlights:

- **Chilika dry**: `S2B_45QUB_20200217_0_L2A` + 2 → `S2C_45QUB_20250215_0_L2A` + 2.
- **Chilika post-monsoon**: `S2A_45QUB_20201108_1_L2A` + 2 → `S2B_45QUB_20251117_1_L2A` + 2.
- **Western Ghats**: `S2B_43PDS_20200219_1_L2A` + 2 → `S2B_43PDS_20250222_0_L2A` + 2.
- **D1**: `S2B_45RUM_20250421_0_L2A` + 2 → `S2B_45RUM_20251021_0_L2A` + 2;
  same-day `S2C_45RUM_20250708_0_L2A` (0.632) recorded but not used as a
  difference baseline.
- **D2**: `S2C_45RUM_20260812_0_L2A` (single, 0.685) → `S2C_45RUM_20260928_0_L2A` + 2.
- **Kathmandu**: `S2B_45RUL_20200331_1_L2A` + 2 → `S2A_45RUL_20250329_0_L2A` + 2.

Every observation's manifest entry records item ID, acquisition time,
platform, baseline, selected assets, scale/offset (including any empirical
correction with its measured evidence), CRS, resolution, transform, nodata,
cloud metadata, measured in-AOI validity and SHA-256s.

## 4. Running it

```powershell
cd frontend && npm run build        # already built; emits frontend/dist
cd ..
python -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8098
# open http://127.0.0.1:8098/
```

Without the backend, any static server on `frontend/dist` gives the full
showcase (all six studies' maps, quality views, charts and provenance; pixel
probe/ROI show honest notes instead of live values).

Rebuild bundles after any reprocessing:
`python scripts/build_showcase_bundles.py` (never overwrites experiment runs;
rebuilds only the website bundles).

## 5. Map of the M4 code

```
scripts/build_showcase_bundles.py   bundle builder (schema m4-bundle/1)
scripts/probe_catalog.py            per-window STAC probe (--measure)
frontend/public/studies/            the six built bundles + registry.json
frontend/src/api/bundle.ts          bundle types, loader, adapters, resolvers
frontend/src/charts/                InteractiveChart.tsx, studyCharts.tsx, charts.css
frontend/src/workstation/layers.ts  per-study dynamic layer registry
frontend/src/workstation/MapCompare.tsx   style-ready deferral, resolver-based URLs
frontend/src/pages/WorkstationPage.tsx    study-aware showcase workstation
frontend/src/pages/LandingPage.tsx        bundle-driven hero + gallery
backend/app/acquisition/assets.py   empirical offset validation + evidence
backend/app/pipeline/engine.py      validated radiometry, cache policy version
backend/tests/test_m4_radiometry.py 8 radiometry tests
backend/tests/test_m4_bundles.py    15 bundle integrity tests
tools/visual/verify_m4.mjs          39-check browser suite
tools/visual/verify_m4_showcase.mjs 10-check no-backend suite
docs/M4_FEASIBILITY.md              scene selection + verdicts (M4-G0)
docs/M4_STUDY_RESULTS.md            recorded results per investigation
docs/M4_radiometry_incident.md      the DN-convention incident and fix
docs/M4_VISUAL_QA.md                verification details + bugs found/fixed
docs/evidence/m4/                   screenshots + JSON results
```

## 6. Honest limitations

- **D1 is PARTIAL by evidence, not by effort**: no clean immediate post-event
  observation exists; only a seasonal April→October comparison is defensible.
- **D2's pre-event scene is monsoon-limited** (one usable observation, 68.5 %
  validity); the dominant recorded change is seasonal snow evolution.
- **No supervised classification anywhere** (no independent labels; M2 finding
  stands). Kathmandu reports candidate signals only.
- **Pixel probe / ROI are live-only** and exist for Coringa; other studies
  show honest notes. Extending them to the M4 studies would mean exposing
  `data/processed/m4/*` through the `/files` + `/pixel` routes — small,
  additive, deferred as unnecessary for the showcase.
- **Western Ghats DEM context is interpretation-only** (not co-registered
  into the indices) and is labelled as such.
- **The showcase bundles add ~28 MB to `frontend/public/`** (preview PNG
  copies; the JSON bundles themselves are ~0.5 MB). They are tracked in Git
  deliberately — they are the portable showcase artefacts. Raw imagery and
  GeoTIFFs stay out of Git.
- The in-app-browser session used during QA observed the same behaviour as
  the Playwright suites; no additional platform-specific issues are known.

## 7. Git checkpoints

| Commit | Gate |
|---|---|
| `d354cce` | M4-G0 verified baseline, five-study feasibility, registry update |
| `f32a5ad` | M4-G1 four study pipelines + empirical BOA-offset validation |
| `014eef5` | M4-G2 two Himalayan event investigations |
| `6e4104b` | M4-G3 bundle builder + six bundles |
| `f382ccf` | M4-G4+G5 study-aware showcase UI + interactive charts |
| `9a83d0f` | hardening: switch-crash fix, path rebasing, suites 39/39 + 10/10 |
| (this commit) | M4-G6 docs, evidence, handoff |
