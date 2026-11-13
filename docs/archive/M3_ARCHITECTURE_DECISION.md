# M3 architecture decision — product shell, map renderer and raster access

**Status:** accepted (M3-G0, 7 November 2026)
**Baseline protected:** M2 at `7953225` (verified before any change; full offline
pytest suite green on the untouched tree)
**Scope:** frontend product architecture and browser raster access. No M0/M1/M2
raster value, mask, statistic, scene ID, threshold or manifest field changed.

---

## 1. Decisions

| # | Decision | Chosen | Alternatives rejected |
|---|---|---|---|
| D1 | Product frontend stack | **React 19 + TypeScript + Vite 6**, per roadmap §"Frontend" | A second vanilla-JS page family (rejected: the workstation state graph — layer, analysis, split, inspector, dock, experiment selectors — outgrew what the M2 proof viewer's imperative DOM code models cleanly) |
| D2 | Map renderer | **MapLibre GL JS 5**, raster *image sources* pinned to the real grid corners | TiTiler/rio-tiler dynamic tile server (rejected for M3: adds a service dependency and COG tiling infrastructure for a 429×390 px AOI — the entire raster is already smaller than one 512 px tile); deck.gl (rejected: heavier than needed) |
| D3 | Browser raster strategy | **Small colourised PNG previews served from `data/previews/`**, placed geographically via a new `/api/m1/study/{id}/georef` endpoint; **original GeoTIFFs are never sent to the browser** | Serving Cloud-Optimised GeoTIFFs directly (rejected: multi-MB downloads in the browser and no guarantee of bounded memory); client-side reprojection (rejected: the browser must not re-derive science geometry) |
| D4 | Pixel inspection | **Server-side sampling** of the full-resolution M1 GeoTIFFs via `/api/m1/study/{id}/pixel?lon=&lat=` | Client-side pixel sampling from preview PNGs (rejected: preview pixels are colourised/stretched, not reflectance; a value read from a PNG would not be a measurement) |
| D5 | ROI statistics | **Server-side full-resolution window statistics** via `/api/m1/study/{id}/roi`, response explicitly labelled `"source": "full-resolution server-side GeoTIFF window"` | Client-side preview statistics (rejected for M3 primary path; the labelling rule in the M3 brief forbids presenting downsampled numbers as full-resolution) |
| D6 | Legacy viewer | **Preserved at `/legacy`** (`frontend/legacy/`) with its FastAPI serving path; the M2-G0 verified swipe/quality behaviour remains reachable and its file-level test contract moved with it | Deleting the proof viewer (rejected: M2 verification evidence references it; "do not remove working functionality") |

## 2. Bounded technical proof (what was actually verified before committing)

1. `npm install` resolves `maplibre-gl@5`, `react@19`, Vite 6 and the three
   self-hosted font packages (`@fontsource-variable/newsreader`,
   `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono`); `npm run build`
   emits a working bundle with the fonts as local assets (no CDN at runtime).
2. Georeferencing is real, not estimated: the M1 summary already stores the
   grid transform, UTM bounds and EPSG; `/georef` reprojects the four raster
   corners to EPSG:4326 with pyproj and returns them. For
   `coringa_coastal` the corners are
   `[82.24492, 16.74526], [82.28516, 16.74501], [82.28493, 16.70977],
   [82.24469, 16.71001]` — matching the AOI in `studies/registry.yaml`.
3. `/pixel` returns measured reflectance (e.g. `nir_B08 = 0.3168`,
   `ndvi = 0.8376` at `82.265E, 16.728N`), valid-mask value, observation count
   and per-index delta, read from the exported GeoTIFFs with rasterio.
4. `/roi` returns full-resolution window statistics with the labelling rule
   of D5 enforced in the response payload.
5. Full offline pytest suite passes after the additive backend changes.

## 3. Known accuracy caveat, stated honestly

MapLibre raster *image sources* interpolate between the four corner
coordinates; the UTM→WGS84 grid convergence across this 4.3 km window is far
below one 10 m pixel, so the placement error is negligible *at this AOI size*.
If a future study spans tens of kilometres, image sources must be replaced by
true tiled serving (D2 rejected option) — that is a documented M4+ trigger,
not a silent assumption.

## 4. Why not a full React rewrite of the M2 viewer's logic

The M2-G0 repair produced verified presentation logic (shared raster stage,
pointer-capture swipe, neutral validity presentation) less than a day before
M3 started. M3 keeps those files runnable at `/legacy` and re-implements the
*product* interactions natively in React; the swipe hover behaviour, compact
layout and quality explanations are new code rather than mutations of verified
code. The file-level frontend contract test (`test_g0_presentation.py`)
now points at `frontend/legacy/` so the M2 guarantees remain enforced.

## 5. Serving contract

- `uvicorn backend.app.api.app:app` serves the built M3 product from
  `frontend/dist` at `/` when a build exists, and the legacy viewer at
  `/legacy`. Without a build, `/` serves the legacy viewer exactly as M2 did,
  so the M2 reproduction commands in `docs/M2_G0_VISUAL_REPAIR.md` still work.
- The backend remains read-only over stored artefacts; the only new
  computation (`/pixel`, `/roi`) reads the same frozen GeoTIFFs the engine
  exported and writes nothing.
