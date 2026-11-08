# HabitatShift

HabitatShift is a local scientific research platform that measures and
explains candidate surface changes in six study areas from Sentinel-2
satellite observations, combining a FastAPI backend (analysis, experiments,
sealed evidence records) with a React + TypeScript + MapLibre frontend
(**Explore the Evidence**, **Research Mode**, pixel probe, experiments
workspace, and a fully offline static Showcase).

**What it is:** mathematical/statistical change detection as the baseline,
with label-gated machine learning as an additional method where appropriate
reference data exist. Every result is a *candidate spectral signal* between
two fixed past dates — the platform never claims verified environmental
change, never predicts disasters, and runs on `127.0.0.1` only.

## Documentation map

| Document | Content |
| --- | --- |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | system architecture + diagrams |
| [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) | the hybrid methodology (math baseline + gated ML) |
| [`docs/SCIENCE_PROTOCOL.md`](docs/SCIENCE_PROTOCOL.md) | the full scientific processing protocol |
| [`docs/DATA_PROVENANCE.md`](docs/DATA_PROVENANCE.md) | data sources, licences, attribution |
| [`docs/RESULTS.md`](docs/RESULTS.md) | study summaries, audit + ML results |
| [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) | the complete limitation record |
| [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) | setup, verification suites, reproduction |
| [`docs/FINAL_AUDIT.md`](docs/FINAL_AUDIT.md) | the end-of-M5 audit ledger |
| milestone records (`docs/M0_…`–`docs/M5_…`) | gate-by-gate history, incidents, handoffs |

## One-click start and stop (Windows)

| Script | What it does |
| --- | --- |
| `start.bat` | Checks the Python virtual environment and backend dependencies, builds `frontend/dist` if it is missing (needs Node.js/npm), picks a free localhost port (prefers **8098**, then 8099–8298), starts the backend hidden, waits until it responds, then opens HabitatShift in the default browser. If a session is already running it opens the existing one instead of starting a duplicate. |
| `stop.bat` | Stops exactly the session started by `start.bat` — it verifies the recorded PID's command line is *this project's* uvicorn backend before terminating anything. Unrelated Python processes are never touched. |

### Requirements

- Python 3.11 venv at `.venv` (create with `py -3.11 -m venv .venv`, then
  `.venv\Scripts\pip install -r backend\requirements.txt` — pinned exactly;
  currently free of known advisories per `pip-audit`).
- Node.js/npm only when `frontend/dist` is missing (the scripts build it).
- No administrator privileges. The server binds to `127.0.0.1` only.

### Manual start (equivalent)

```powershell
cd frontend && npm run build        # only needed when frontend/dist is missing
cd ..
.venv\Scripts\python.exe -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8098
```

Without the backend, any static server on `frontend/dist` serves the full
offline Showcase mode.

## Tests and verification

```powershell
.venv\Scripts\python.exe -m pytest        # 404 backend tests
cd frontend && npm run build              # production build (type-checks too)
```

Independent audits re-derive the science without importing production code —
see [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) for the audit scripts, the
browser suites, and the fresh-environment reproduction (which regenerates a
study from original source data into byte-identical GeoTIFFs).

## Data and licences

Sentinel-2 L2A via the Element 84 Earth Search STAC catalogue (AWS Open
Data) — *"Contains modified Copernicus Sentinel data, processed by ESA"*.
M5 reference labels: ESA WorldCover v200 (CC-BY 4.0) and Global Mangrove
Watch v3.0 (CC-BY 4.0), recorded per artifact in
[`docs/DATA_PROVENANCE.md`](docs/DATA_PROVENANCE.md). Raw data, caches and
runtime files are git-ignored; no secrets or credentials exist in the repo.
