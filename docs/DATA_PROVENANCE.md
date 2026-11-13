# HabitatShift — data provenance and licensing

Every processed artifact carries its provenance in-band: run manifests record
STAC request bodies, matched item ids, per-observation metadata (acquisition
date, processing baseline, per-band asset href + GSD, resolved scale/offset
and the radiometry decision string), grid definition, software versions, git
commit, and SHA-256 of every output file. Evidence records embed their input
raster hashes and a canonical-JSON `output_checksum`.

## Satellite imagery

| Property | Value |
|---|---|
| Product | Sentinel-2 MSI Level-2A (BOA reflectance) |
| Catalog | Element 84 **Earth Search** STAC API v1 (`https://earth-search.aws.element84.com/v1`), collection `sentinel-2-l2a` |
| Access | anonymous (`AWS_NO_SIGN_REQUEST`), byte-range windowed COG reads |
| Licence | Copernicus Sentinel data — free, open and unrestricted use with attribution (ESA Copernicus data policy) |
| Attribution (recorded per run) | "Contains modified Copernicus Sentinel data, processed by ESA; L2A products distributed by the Element 84 Earth Search STAC catalogue (AWS Open Data)." |
| Processing baselines in use | 02.14 / 03.xx (raw DN, no offset) · 05.00/05.11 with `earthsearch:boa_offset_applied=true` (offset baked) · 05.11 with the flag `false` and a **measured metadata inconsistency** — the 2025 reprocessing items store `reflectance × 10000` without the baked offset; the engine's empirical acceptance test detects and corrects this per read (see `docs/archive/M4_radiometry_incident.md` and `docs/archive/M5_SCIENTIFIC_AUDIT.md` §3) |
| Radiometry convention per record | 8 raw-DN · 26 offset-baked · 6 empirically corrected · 0 declared-offset (audited) |

## DEM context (Western Ghats, Himalaya)

Copernicus GLO-30 DEM (ESA/DLR), used for **interpretation context only**
(elevation/shadow discussion) — never a co-registered input to the indices.

## Reference labels (Random Forest experiments)

| Source | Version / epoch | Resolution | Licence | Role |
|---|---|---|---|---|
| ESA WorldCover | v200, 2021 epoch | 10 m | **CC-BY 4.0** — © ESA WorldCover project 2022; attribution embedded in the ML manifests and findings containers | Reference-product labels for Kathmandu, Western Ghats, Chilika, Coringa. Explicitly **not ground truth**; every metric is framed as agreement with this product. |
| Global Mangrove Watch | v3.0, 2020 epoch (NASA MAAP STAC COGs) | 10 m | CC-BY 4.0 (Bunting et al. 2022) | Recorded external reference for Coringa mangrove extent; disagreement with WorldCover inside the AOI is itself a recorded result — no mangrove labels were manufactured. |
| JRC Global Surface Water | occurrence v1.4 (1984–2021), `storage.googleapis.com/global-surface-water/downloads2021/` | 30 m | CC-BY 4.0 (Pekel et al. 2016) | No endpoint was found during the original feasibility check; it is reachable now and used **only** as a second water reference in a reference-vs-reference cross-check (`data/experiments/m5_gsw/`). Not used for training; no earlier recorded result was changed. |
| Hansen Global Forest Change | v1.12 (2000–2024), tile 20N_070E, `storage.googleapis.com/earthenginepartners-hansen/` | 30 m | **CC-BY 4.0** (Hansen et al. 2013, Science 342:850) | Independent forest-loss reference for the Western Ghats validation; only the study window was read and is cached with a SHA-256 in `data/external/hansen_gfc_2024/` |
| Dynamic World | near-real-time | 10 m | CC-BY 4.0 | **Excluded as labels** (model output; agreement with it would be model-to-model twice). |

## Local artifact map

| Path | Content | Git status |
|---|---|---|
| `data/raw/`, `data/processed/`, `data/cache/` | downloaded windows, analysis rasters, observation cache | git-ignored (reproducible from source) |
| `data/manifests/*.json` | run manifests (full provenance + output SHA-256s) | tracked |
| `data/findings/*.json` | sealed mathematical evidence records (`habitatshift-findings/2`) | tracked |
| `data/findings_m5ml/*.json` | separate ML containers (reference the main records by SHA-256) | tracked |
| `data/experiments/m2, m5_ml, m5_kmeans, m5_robustness` | experiment results + manifests | tracked |
| `frontend/public/studies/` | showcase bundles + `selection_policy.json` + `m5ml_findings.json` | tracked |
| `.runtime/`, `.venv/` | runtime state, environment | git-ignored |

## Reproducibility

Every number in the product traces to a tracked manifest or findings file
with checksums. `scripts/reproduce_m5_fresh.py` regenerates a study from the
original source data into a sandbox and verifies byte-identical GeoTIFFs
(see `docs/SETUP_GUIDE.md`).

## Version 3 additions

| Source | Licence | Use |
|---|---|---|
| Sentinel-1 RTC via Microsoft Planetary Computer (`sentinel-1-rtc`) | Copernicus Sentinel data, free and open with attribution; RTC processing by Microsoft | Radar lake series |
| Copernicus GLO-30 DEM via Planetary Computer (`cop-dem-glo-30`) | Copernicus DEM licence, free with attribution | Slope and lake seed |
| Hi-MAG annual glacial lake dataset, Zenodo 4275164 (2008-2017) | CC-BY 4.0 | Reference outlines for the lake comparison (agreement, not accuracy) |
| Prithvi-EO-2.0-300M, `ibm-nasa-geospatial` on Hugging Face | Apache-2.0 | Patch embeddings; weights kept in `data/models/`, not committed |
| SSL4EO-S12 ResNet-50 RGB MoCo, `torchgeo/resnet50_sentinel2_rgb_moco` (Wang et al. 2022) | CC-BY 4.0 | Second, light embedding model; weights in `data/models/` |
| Hansen Global Forest Change v1.12 (2000-2024) | CC-BY 4.0 | Forest-loss reference for the foundation-model comparison (agreement, not accuracy) |
| geoBoundaries gbOpen Nepal ADM0 (simplified) | CC-BY 4.0 | Boundary used to select the lakes in Nepal |

Downloaded datasets and weights live under `data/reference/` and `data/models/` and are git-ignored.

