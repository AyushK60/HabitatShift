# M5-G7 — Technical reliability and performance

**Status:** complete. All results below were executed on the `m5-release`
branch, on the upgraded dependency set (see §4).

## 1. Backend

- Full suite: **404 tests pass** (twice: project venv and a freshly created
  venv built solely from `backend/requirements.txt`).
- Invalid-input handling is under test: study/experiment id sanitisation
  (400 on malformed ids), path-traversal guards on every file route
  (`x..y.png` → 400, unknown scope/study → 404) — `test_m1_api.py`,
  `test_g0_api.py`, `test_m3_api.py`.
- Corrupt-data handling is under test: corrupt observation cache is discarded
  and re-read (`test_m1_engine.py::test_corrupt_observation_cache_is_ignored`),
  corrupt rasters raise `RasterReadError`
  (`test_corrupt_raster_raises_read_error`), corrupt radiometry is rejected
  by the empirical acceptance test (`test_m4_radiometry.py`, 8 tests).
- Partial-download/network robustness: all traffic goes through one HTTP
  session (30 s timeout, 4 retries, 0.25 s rate limit, byte-range COG
  reads); bounded pagination (≤ 200 items), bounded measurement budget
  (≤ 24 SCL reads per search), `MAX_WINDOW_PIXELS = 4_000_000` grid guard,
  budgeted byte estimates before every read.
- New in M5: manifest-output checksum regression test (catches any artifact
  rewrite that does not update provenance).

## 2. Frontend and product

- Production build (tsc + vite): clean.
- Browser suites (Playwright): `verify_m4.mjs` 51/51, `verify_m4_r3.mjs`
  35/35 (includes 4-viewport responsive overflow checks), 
  `verify_m2_experiments.mjs` 31/31, `verify_m5_ml.mjs` 23/23.
- Portable showcase with the backend stopped: `verify_m4_showcase.mjs` 17/17
  and `verify_m5_ml.mjs` (showcase mode) 23/23 against a static file server.

## 3. Startup / shutdown scripts

- `start.bat --nopause`: dependency + build checks, free-port search
  (preferred 8098 then +1..+200), backend health-checked before the browser
  opens, `.runtime` records written.
- **Duplicate startup**: a second invocation detects the running session and
  reports `HabitatShift is already running (pid …) — Opening the existing
  session instead of starting a duplicate`; the pid file is unchanged and no
  second uvicorn starts.
- `stop.bat --nopause`: stops exactly its managed pid, removes `.runtime`
  records, and explicitly reports an unrelated listener as "not ours and was
  left untouched" (verified behaviour during M5-G0 and after every run).

## 4. Dependency security review (found and corrected)

`pip-audit` (2.10.1, OSV/PyPI advisory DB) against the pinned requirements
found **89 advisories in 4 packages**:

| Package | Was | Advisories | Now |
|---|---|---|---|
| starlette (via fastapi) | 0.46.2 | many (fix ≤ 1.3.1) | **1.10.0** |
| fastapi | 0.115.11 | constrained by starlette | **0.162.2** |
| requests | 2.32.3 | 2 | **2.34.2** |
| Pillow | 11.1.0 | several (fix ≥ 12.x) | **13.0.0** |
| pytest | 8.3.5 | 1 | **9.2.0** |

All other pins were advisory-free and are unchanged. After the upgrade:
**pip-audit reports zero known vulnerabilities** for the pinned set, the
fresh venv installs purely from `requirements.txt`, and the full 404-test
suite plus every browser suite pass on the upgraded stack. The lock file
(`requirements.lock.txt`) was regenerated from the upgraded environment.

## 5. Licensing, attribution, secrets

- Server binds **127.0.0.1 only** (`start.bat` → uvicorn `--host 127.0.0.1`);
  no route binds a public interface; every dynamic route validates ids and
  file names (§1).
- No secrets or credentials anywhere in the repo; all data access is
  anonymous (`AWS_NO_SIGN_REQUEST`), `.runtime`, `data/raw`,
  `data/processed`, caches and `.venv` are git-ignored.
- Attribution recorded per run in every manifest: Copernicus Sentinel data
  (ESA, free/open with attribution), Element 84 Earth Search catalogue;
  M5 additions: **ESA WorldCover v200 (CC-BY 4.0, © ESA WorldCover project
  2022)** in the M5-ML training manifests and findings containers, and Global
  Mangrove Watch v3 (CC-BY 4.0, Bunting et al. 2022) documented in the
  feasibility report. Licences permit reuse with attribution; attribution is
  embedded in the artifacts themselves.

## 6. Fresh-environment reproduction

A brand-new venv (`python -m venv`, install from `requirements.txt` only) was
used to run:

1. the full 404-test suite — pass;
2. **`scripts/reproduce_m5_fresh.py`**: the frozen `chilika_m4_dry`
   experiment reprocessed end-to-end from the original source data (live
   Earth Search downloads into an empty cache, outputs redirected to a
   sandbox; frozen outputs untouched). Result: **all change statistics
   identical at the primary threshold** (NDVI/NDWI/MNDWI decrease/increase/
   stable/common-valid pixel counts) and **all nine regenerated GeoTIFFs
   (delta / change_classes / common_valid per index) byte-identical** to the
   recorded SHA-256s — the pipeline is deterministic from source data.
3. Reproduction ledger: `docs/evidence/m5/` (verify results, audit checks,
   reproduction JSON in the sandbox — copied checksums into the repo doc).

## 7. Notes

- A disposable static file server used for showcase verification on port
  8099 leaves no owning process after the sandboxed shell exits (socket
  owned by pid 0/Idle); no stray process remains.
- The M5 audit's experiment-extraction was hardened when the M5-ML training
  manifests joined the audit set (they carry `study` as a string); the
  scientific-audit ledger now also live-verifies the 2021 training items
  (**4111/4111 checks**).
