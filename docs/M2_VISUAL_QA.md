# M2 — Visual QA of the research workbench

**Tooling:** Playwright 1.65.0, headless Chromium 158, against the real
uvicorn-served viewer (no DOM mock).
**Harness:** `tools/visual/verify_m2_experiments.mjs`
**Result:** **40/40 checks passed**, 0 console errors, 0 page errors,
0 failed network requests.

Reproduce:

```powershell
$env:HABITATSHIFT_PORT='8097'
.\.venv\Scripts\python.exe -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8097
# second shell:
$env:HABITATSHIFT_URL='http://127.0.0.1:8097/'
node tools\visual\verify_m2_experiments.mjs
```

---

## What is tested (all against live backend values)

1. **Experiment loading** — the Experiments section appears, names the
   recorded run id, states "no supervised labels were used anywhere in this
   run", and renders ≥7 overview rows including fingerprint and 100.00 %
   common-valid coverage.
2. **Hypothesis verdicts** — exactly five verdict lines H1–H5 with chips
   computed by the runner.
3. **Threshold explorer** — five threshold buttons; index switching (ndvi →
   mndwi) updates the Δ-label and the areas; threshold switching (0.15 →
   0.05) increases the candidate-decrease area; the area-conservation row
   reads "holds (0 px residual)"; the threshold-response chart embeds and is
   served as `image/svg+xml`.
4. **Method comparison** — ≥17 estimator rows for the selected index at the
   primary threshold, with a note naming the index; the estimator-comparison
   chart embeds.
5. **Uncertainty** — method named ("spatial block bootstrap"), "200 of 200
   requested" resamples, seed 20260326 displayed, 95 % ranges displayed, M0↔M1
   anchor agreement row (158,168/158,168 identical pixels), bootstrap chart
   embedded.
6. **Guardrails & exports** — ≥4 guardrails including "not verified
   environmental change" and the observation counts; four export links
   (result JSON, manifest, two CSVs) all reachable with HTTP 200; the
   exported result contains no accuracy/F1 keys.
7. **Responsive** — no horizontal overflow at 390 px; the section reflows to
   a single column.
8. **Missing-run state** — with the API returning 404, the section states
   the exact runner command instead of showing fabricated content.

## Screenshots (`docs/evidence/m2/`)

- `m2_experiments_overview_1440.png` — overview card with run facts and
  H1–H5 verdict chips.
- `m2_experiments_threshold_1440.png` — threshold explorer card with
  index/threshold controls, measured areas, conservation row and the
  threshold-response chart.
- `m2_experiments_methods_1440.png` — method-comparison card (18 MNDWI
  estimators at ±0.15 with measured areas).
- `m2_experiments_uncertainty_1440.png` — block-bootstrap table and chart.
- `m2_experiments_section_1440.png` — the lower card row (uncertainty,
  guardrails, exports).
- `m2_experiments_390.png` — mobile layout.
- `m2_experiments_missing_run.png` — explicit no-run state.
- `m2_browser_results.json` — machine-readable check record.

## Defect found and fixed during QA

**Method-comparison rows rendered hundreds of pixels tall.** Root cause: the
global `.meta th { white-space: nowrap }` rule let long estimator labels
monopolise the table width, squeezing value cells to ~21 px, so every value
wrapped into ~20 lines. Fixed by scoping `white-space: normal; width: 44%`
to `.table-scroll .meta th` (`frontend/styles.css`); verified by measuring
row heights in the browser (361 px → 64 px) and by re-running the harness.

Two harness-side defects were also fixed during QA (not product defects):
evidence paths were cwd-dependent (`path.resolve` → script-relative with
`fileURLToPath`), and a smooth-scroll animation meant viewport screenshots
sometimes fired before scrolling settled (replaced with element screenshots).

## Limitations

- The G0 comparison stages (swipe/side-by-side alignment) were verified in
  the previous gate and are unchanged here; this harness covers the new
  Experiments section.
- Chart legibility at 390 px relies on the SVG `viewBox` scaling; text in
  charts is small on phones but remains zoomable.
