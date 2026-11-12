# HabitatShift — setup guide

## Quick start (Windows)

Double-click `start.bat` (or run it in a terminal). It:
1. checks `.venv` and backend dependencies;
2. builds `frontend/dist` if missing (needs Node.js/npm);
3. picks a free localhost port (prefers 8098);
4. starts the backend bound to `127.0.0.1`, waits for health, opens the
   browser; refuses duplicates.

Stop with `stop.bat` — it terminates exactly its recorded pid and touches
no unrelated process.

## From scratch

```powershell
git clone <repo> habitatshift ; cd habitatshift
py -3.11 -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt   # pinned exactly
cd frontend ; npm install ; npm run build ; cd ..
.venv\Scripts\python.exe -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8098
```

Without the backend, any static server on `frontend/dist` serves the full
offline Showcase mode.

## Tests and verification suites

```powershell
.venv\Scripts\python.exe -m pytest                      # 404 backend tests
cd frontend ; npm run build                             # tsc + vite build
node tools\visual\verify_m4.mjs                         # 51 checks (backend up)
node tools\visual\verify_m4_r3.mjs                      # 35 checks (backend up)
node tools\visual\verify_m2_experiments.mjs             # 31 checks (backend up)
node tools\visual\verify_m5_ml.mjs                      # 23 checks (backend up)
node tools\visual\verify_m4_showcase.mjs                # 17 checks (backend STOPPED, port 8099 static)
```

## Independent audit scripts (re-derive everything, import no production code)

```powershell
.venv\Scripts\python.exe verification\audit_m5_science.py     # 4111 checks (network for live sections; --no-live to skip)
.venv\Scripts\python.exe verification\audit_findings_m4r2.py  # 2837 checks
.venv\Scripts\python.exe verification\audit_m2.py             # 149 checks
.venv\Scripts\python.exe verification\audit_m5_ml.py          # 107 checks (offline)
.venv\Scripts\python.exe verification\audit_m5ml_disclosure.py# 96 checks (offline)
```

## Reproduce a scientific result from original source data

```powershell
python -m venv %TEMP%\hs_fresh_venv
%TEMP%\hs_fresh_venv\Scripts\pip install -r backend\requirements.txt
%TEMP%\hs_fresh_venv\Scripts\python.exe scripts\reproduce_m5_fresh.py
```

This re-downloads every observation of the `chilika_m4_dry` experiment into
an **empty** cache, reprocesses into a sandbox, and asserts the regenerated
change statistics equal the recorded ones and the delta/classification/
common-valid GeoTIFFs are **byte-identical** (verified: yes). Frozen outputs
are never written.

## Re-run the ML experiments (network required)

```powershell
.venv\Scripts\python.exe scripts\run_m5_training_imagery.py  # 2021 imagery via the audited M1 chain
.venv\Scripts\python.exe scripts\run_m5_ml.py                # train/evaluate/apply + artifacts
.venv\Scripts\python.exe scripts\build_m5ml_findings.py      # regenerate the additive disclosure layer
```

Determinism: fixed seeds everywhere (ML 20261108, bootstrap 20260326,
verify 20261106); software versions pinned in `backend/requirements.txt`.

## Regenerating showcase bundles (only if evidence changes — frozen in M5)

```powershell
.venv\Scripts\python.exe scripts\build_showcase_bundles.py
```

## Dependencies security

```powershell
pip install pip-audit
pip-audit -r backend\requirements.txt --no-deps        # currently: zero known advisories
```
