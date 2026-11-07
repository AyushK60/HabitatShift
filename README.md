# HabitatShift

HabitatShift is a local scientific research application that measures and
explains candidate habitat/surface changes in six study areas from
Sentinel-2 satellite observations. It combines a FastAPI backend (analysis,
experiments, evidence records) with a React + TypeScript + MapLibre frontend
(Explore the Evidence, Research Mode, Historical/Change/Quality views, and a
fully offline static Showcase built from `frontend/public/studies/` bundles).

## One-click start and stop (Windows)

Two scripts in the project root make local use a double-click affair.

| Script | What it does |
| --- | --- |
| `start.bat` | Checks the Python virtual environment and backend dependencies, builds `frontend/dist` if it is missing (needs Node.js/npm), picks a free localhost port (prefers **8098**, then 8099–8298), starts the backend hidden, waits until it responds, then opens HabitatShift in the default browser. If a session is already running it opens the existing one instead of starting a duplicate. |
| `stop.bat` | Stops exactly the session started by `start.bat`, releases its port and removes the runtime records. It verifies the recorded PID's command line is *this project's* uvicorn backend before terminating anything — unrelated Python processes and applications are never touched. |

### Requirements

- The existing virtual environment at `.venv` (if missing, create it:
  `py -3.11 -m venv .venv` then `.venv\Scripts\pip install -r backend\requirements.txt`).
- Node.js/npm is only needed the first time `frontend/dist` does not exist
  (the scripts then run `npm install` + `npm run build` automatically).
- No administrator privileges. The server binds to `127.0.0.1` only.

### Runtime files

All runtime state lives in a git-ignored `.runtime/` folder at the project
root, so the scripts stay portable and never write into tracked folders:

- `.runtime/server.pid` — PID of the backend process (used by `stop.bat`)
- `.runtime/server.port` — the port actually allocated
- `.runtime/server.url` — the URL opened in the browser
- `.runtime/server.log` — backend output (uvicorn access/error log)
- `.runtime/npm-install.log`, `npm-build.log`, `pip-install.log` — only
  written when a dependency install or frontend build runs

### Notes

- The scripts resolve their own location (`%~dp0`), so the project folder can
  be moved to any drive or path without editing them.
- `start.bat --nopause` / `stop.bat --nopause` skip the end-of-run pause (used
  by automated tests); normal double-click use never needs flags.
- If the port you expect is taken by another application, `start.bat` simply
  picks the next free one and tells you the URL it opened.

## Manual start (equivalent)

```powershell
cd frontend && npm run build        # only needed when frontend/dist is missing
cd ..
.venv\Scripts\python.exe -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8098
# open http://127.0.0.1:8098/
```

Without the backend, any static server on `frontend/dist` serves the full
offline Showcase mode.

## Tests and verification

```powershell
.venv\Scripts\python.exe -m pytest        # backend + audit test suite
cd frontend && npm run build              # production build (type-checks too)
```

Detailed milestone documentation, audits and handoffs live under `docs/`
(see `docs/M4_R2_HANDOFF.md` for the most recent milestone).
