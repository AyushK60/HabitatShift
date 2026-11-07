# M2 — Verification record

**Milestone verdict: PASS** (see `M2_LIMITATIONS.md` for the honest scope of
that verdict; the supervised-ML component is explicitly blocked, not faked).

---

## 1. Gate sequence

| Gate | Scope | Evidence |
|---|---|---|
| M2-G0 | Visualization repair (committed separately as `593675e` before research work) | `M2_G0_VISUAL_REPAIR.md`, 23 screenshots, 323/323 browser checks |
| M2-G1 | Experiment framework: validated config, runner, fingerprint cache, manifest | `studies/experiments/coringa_m2.yaml`, `backend/app/experiments/*`, `scripts/run_experiment.py` |
| M2-G2 | Threshold baselines, sensitivity, estimator comparison | recorded run `20261107T102819Z_d70f3978`, `M2_EXPERIMENTS.md` |
| M2-G3 | Label feasibility audit → supervised path blocked | `M2_LABEL_FEASIBILITY.md`, blocked status recorded in config and result |
| M2-G4 | Uncertainty + research workbench UI | `M2_UNCERTAINTY.md`, viewer Experiments section, 40/40 browser checks |
| M2-G5 | Independent verification | `scripts/audit_m2.py` 149/149; full test suite; this document |

## 2. Test results (final state)

- **Offline suite:** 270 passed (231 pre-existing + 39 new M2 tests), 0
  failed (`python -m pytest backend/tests -q --ignore=backend/tests/test_live.py`).
- **Live tests:** 6 passed (`backend/tests/test_live.py`, real catalogue in
  read-only mode).
- **Browser harness:** 40/40 checks, 0 console/page/network errors
  (`tools/visual/verify_m2_experiments.mjs`).
- **Numerical audit:** 149/149 checks (`scripts/audit_m2.py`).

## 3. M0/M1 preservation

- `git status` clean of modifications to `data/processed/m1`,
  `data/processed/coringa_coastal`, `data/manifests`, `data/previews/m1`,
  `data/cache` — all M2 code and outputs are additive.
- Composite means reproduce the frozen M1 headline exactly (NDVI −0.020471,
  NDWI +0.018959, MNDWI −0.006188); verified in tests and by the audit.
- M0 delta raster: bit-identical to the M1 anchor single-scene delta on all
  158,168 shared pixels.
- The G0 presentation assets and M1 previews are untouched.

## 4. Reproducibility verification

- Rerunning `scripts/run_experiment.py` with unchanged inputs hits the
  content fingerprint and serves the recorded run (observed in-session).
- `--force` writes a new timestamped directory; the runner refuses to
  overwrite an existing run directory.
- Charts regenerate byte-identically from the same arrays (determinism
  covered by unit tests on the SVG writer).
- Manifest records git commit, Python/NumPy/rasterio versions and SHA-256
  for every artifact and input.

## 5. UI/backend agreement

- The Experiments section fetches `/api/experiments/coringa_m2/latest`,
  which reads the recorded `result.json` verbatim; the audit re-checks
  API-vs-record agreement (group 9).
- Export links (result JSON, manifest, both CSVs) verified reachable with
  HTTP 200 by the browser harness; the exported result contains no
  supervised metric keys.

## 6. Commands

```powershell
# tests
.\.venv\Scripts\python.exe -m pytest backend/tests -q --ignore=backend/tests/test_live.py
.\.venv\Scripts\python.exe -m pytest backend/tests/test_live.py -q

# experiment + audit
.\.venv\Scripts\python.exe scripts\run_experiment.py --config studies\experiments\coringa_m2.yaml
.\.venv\Scripts\python.exe scripts\audit_m2.py

# viewer
$env:HABITATSHIFT_PORT='8097'
.\.venv\Scripts\python.exe -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8097

# browser harness
$env:HABITATSHIFT_URL='http://127.0.0.1:8097/'
node tools\visual\verify_m2_experiments.mjs
```
