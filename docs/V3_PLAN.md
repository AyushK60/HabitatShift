# HabitatShift version 3: plan and handoff

Written 2026-11-12. This is the working plan for version 3. A new chat (any model) should be able to read this
file and continue without any earlier conversation.

---

## 0. How to use this file in a new chat

Paste this into a new Claude Code chat opened in this repository:

> Read `docs/V3_PLAN.md` fully, then `README.md`, `docs/METHODOLOGY.md` and `docs/RESULTS.md`. We are working on
> HabitatShift version 3. Tell me which phase and task is next according to section 9 (progress log), confirm the
> plan for that task in a few lines, then do it. Keep every new concept explained in `docs/LEARNING.md`. Update the
> progress log in `docs/V3_PLAN.md` when a task is done.

Rules for whoever continues the work:

- Work one task at a time and keep the progress log (section 9) current.
- Every new concept, library or method choice gets a short plain-language entry in `docs/LEARNING.md` (see
  section 7). The owner will study these after exams and must be able to defend every choice in interviews.
- Keep the version 2 habit: say plainly when a result is "not reliably different from noise". Never claim more than
  the data supports. Reference datasets are other products, not ground truth; call it "agreement", not "accuracy".
- Stay within free tiers and the hardware in section 1.
- Do not delete version 2 results. Version 3 adds to them.
- Commit only when the owner asks. Use a normal human author name, never an "agent" name.

---

## 1. Who this is for and what it must achieve

**Owner:** B.Tech CSE student from Nepal, 7th semester (Nov 2026), CGPA 8.5/10. Applying in the next cycle
(deadlines around Dec 2027) to master's and PhD programmes in the US, Europe, Canada and Australia.

**Purpose of the project:** show that the owner can take ML/AI beyond core computer science and apply it carefully
in several fields (natural hazards, ecology, forestry, urban studies). It is not aimed at one lab type. A professor
reading it should see: a clear research question, sound ML, honest evaluation, real-world relevance, and a person
who can work across disciplines.

**Hardware and accounts:**

- Laptop GPU: NVIDIA RTX 5050, 8 GB VRAM. System RAM: 24 GB.
- Free tiers only: Google Earth Engine (noncommercial/research, free), Microsoft Planetary Computer (free STAC
  access), NASA Earthdata/ASF (free), Kaggle (free GPU hours), Google Colab (free), Hugging Face (free), GitHub Pages.
- Windows 11, Python 3.11, existing `.venv`.

**Main outputs by the end:**

1. A clear research result across four fields (section 3).
2. A small trained deep-learning model with honest error bars (Phase 3).
3. A short paper: a preprint and, if possible, a workshop submission (Phase 4).
4. A public demo link anyone can open (GitHub Pages).
5. `docs/LEARNING.md`: a study guide covering every concept used.

---

## 2. Where version 2 stands (starting point)

What exists (see `README.md`, `docs/RESULTS.md`, `docs/ARCHITECTURE.md`):

- Backend: FastAPI + rasterio/numpy pipeline (`backend/app/`) reading Sentinel-2 L2A from the Element 84 Earth
  Search STAC catalogue. Modules: `catalog/`, `acquisition/`, `preprocess/`, `indices/`, `analysis/change.py`,
  `experiments/` (thresholds, estimators, uncertainty), `pipeline/` (engine, custom runs, provenance).
- Frontend: React 19 + TypeScript + Vite + MapLibre (`frontend/`), with swipe comparison, pixel probe, experiments
  pages, an offline static showcase, and a "your own area" page that needs the backend.
- Six studies (`studies/registry.yaml`): `coringa_coastal`, `chilika_wetland`, `western_ghats_forest`,
  `kathmandu_urban`, `himalaya_purepu_2025`, `himalaya_langtang_2026`.
- Methods: index differences (NDVI, NDWI/MNDWI, NDBI, NDSI) on a shared valid footprint; threshold sweeps;
  **per-pixel noise test** (scene-to-scene spread in each period gives a standard error; change counts only if it
  exceeds 3 x SE); Hansen validation in Western Ghats; monthly time series with seasonal fit (Kathmandu, Western
  Ghats); 20 m resolution sensitivity; Random Forest agreement with ESA WorldCover (M5).
- Verification: about 443 pytest tests, independent audits in `verification/`, browser suites in `tools/visual/`,
  byte-identical fresh reproduction.

Honest weaknesses found in the Nov 2026 review (version 3 fixes these):

1. No research question with a new answer. The findings are mostly about measurement quality.
2. Very small areas (about 24 km²) and mostly two dates.
3. The ML is weak and circular: a Random Forest learns to copy WorldCover, another model's labels. No deep learning,
   no foundation models.
4. Little real biology/ecology despite the name.
5. Over-engineered and AI-sounding docs (milestone codes like M4-R3, "label-gate BLOCKED"), git author named
   "HabitatShift M0 Agent".
6. Nothing is hosted; reviewers cannot click a link.

The best asset to keep: **the noise test**. Version 3 makes it the fair yardstick for comparing ML methods.

---

## 3. The version 3 research question

> **Can geospatial foundation-model embeddings detect real surface change more reliably than spectral indices, once
> both are judged against the same scene-to-scene noise, and does the answer hold across different fields?**

Plain explanation: a foundation model turns each pixel into a vector (a list of numbers) that summarises what is
there. Comparing a pixel's vector on two dates gives a change score. Spectral indices (NDVI etc.) give another
change score. Both scores move a little even when nothing changes (clouds, haze, sun angle, sensor noise). We
measure that background wobble, keep only change that rises above it, and check which method's surviving change
agrees better with independent reference data.

Why this question is good for the owner:

- The **method** is the ML/CS part (embeddings, calibration, deep learning, conformal prediction).
- The **four applications** prove cross-field ability.
- It builds on version 2's strongest idea instead of throwing work away.
- Recent work notes that raw embedding distances are not on a consistent scale across pixels or time; a
  noise-calibrated comparison addresses exactly that gap.

### The four fields

| Field | Study | Change type | Reference data (independent check) |
|---|---|---|---|
| Natural hazards / cryosphere (**flagship**, Nepal link) | 20-50 glacial lakes in Nepal, 2017-2026, radar + optical | Lake growth, drainage, outburst | Published glacial-lake outlines (Glacial Lake Observatory ESSD dataset on Zenodo, ICIMOD inventory, Hi-MAG), plus clear-sky Sentinel-2 water masks |
| Ecology / wetlands | Chilika lagoon (existing study) | Water extent and aquatic vegetation | JRC Global Surface Water monthly history (via Earth Engine) |
| Forestry | Western Ghats (existing study), possibly a larger area with real loss | Forest loss | Hansen Global Forest Change |
| Urban studies | Kathmandu (existing study) | New built-up area | Dynamic World / ESA WorldCover, Google Open Buildings temporal layer if usable |

Note: the Western Ghats area showed almost no change in version 2 (about 5 Hansen loss cells). For Phase 2, add or
swap in a nearby area with clearly recorded loss so the test has something to detect. Keep the stable area as a
"no-change control" (also useful: a method that flags change there is producing false alarms).

---

## 4. Phases in detail

Timeline assumes exams now, full-time-ish work from about January 2027, applications Oct-Dec 2027.

### Phase 0: Clean-up and foundations (Nov-Dec 2026, light work during exams)

Goal: make version 2 presentable and set up the study guide.

Tasks:

0.1 **Git author.** Set `git config user.name` / `user.email` to the owner's real name for future commits. Do not
    rewrite old history unless the owner explicitly asks (rewriting is irreversible on shared branches).
0.2 **Docs trim.** Shorten `README.md` and the main docs to human length; remove milestone jargon (M0-M5 codes,
    "label-gate", "findings/2") from user-facing text; keep archive docs in `docs/archive/`. The `humanize-repo`
    skill can help audit this.
0.3 **Host the offline showcase** on GitHub Pages (static build of `frontend/dist`, the showcase mode already works
    without the backend). Add the link at the top of the README.
0.4 **Create `docs/LEARNING.md`** with entries for every concept already in version 2 (see section 7 list).
0.5 **Repo housekeeping.** Decide what to do with the untracked `.impeccable/` folder (probably add to
    `.gitignore`). Make sure large rasters are not committed.

Done when: README reads like a person wrote it, demo link works, LEARNING.md covers version 2 concepts.

### Phase 1: Radar data and the glacial-lake time series (Jan-Feb 2027)

Goal: add Sentinel-1 radar, which sees through monsoon cloud, and build monthly lake-area time series.

Tasks:

1.1 **Sentinel-1 access.** Use the Microsoft Planetary Computer STAC collection `sentinel-1-rtc` (radiometrically
    terrain corrected, free, via `pystac-client` + `planetary-computer` signing). Fallback: ASF HyP3 on-demand RTC
    (free NASA Earthdata account). Add a `backend/app/catalog` source for it next to the Earth Search client.
1.2 **Radar preprocessing.** VV and VH backscatter in dB; speckle filtering (Lee or refined Lee, 5x5 or 7x7);
    terrain shadow/layover masks (very important in the Himalaya, steep slopes create false "water"); a DEM
    (Copernicus GLO-30, free on Planetary Computer / AWS).
1.3 **Lake selection.** Pick 20-50 Nepal glacial lakes with different sizes and risk levels (e.g. Tsho Rolpa,
    Imja Tsho, Thulagi, Chamlang Tsho, plus the existing Purepu/Lende Khola site). Store them in
    `studies/registry.yaml` or a new `studies/lakes.yaml` with sources.
1.4 **Water masks.** Optical: MNDWI threshold on clear Sentinel-2 scenes (existing code). Radar: VV/VH backscatter
    threshold (Otsu per lake buffer as a baseline). Produce monthly lake area 2017-2026 for each lake, with gaps
    marked when no usable data exist.
1.5 **Noise test for lakes.** Apply the version 2 idea: multiple scenes per month give a spread, so each monthly
    area has an uncertainty; flag area changes that exceed it.
1.6 **Check against references.** Compare lake outlines/areas with the Glacial Lake Observatory dataset and other
    inventories for overlapping dates. Report agreement (IoU, area difference), not accuracy.
1.7 **Frontend.** A "Glacial lakes" page: map of lakes, click a lake to see its area time series (optical vs radar
    with uncertainty bands), and before/after images.

Done when: monthly area series exist for all chosen lakes from both sensors, with uncertainty, compared against at
least one reference, shown in the UI, with tests for the new code paths.

Key risk: radar water detection fails on frozen lakes (ice) and in steep terrain. Record it and mask winter months
for frozen lakes rather than hiding it.

### Phase 2: Foundation models vs indices, judged by the noise test (Mar-Apr 2027)

Goal: answer the research question in all four fields.

Tasks:

2.1 **Choose models (all free):**
    - **Prithvi-EO-2.0** (NASA/IBM, open, Hugging Face `ibm-nasa-geospatial`, via the `terratorch` library). Use the
      300M version in fp16 for inference on 8 GB VRAM. Takes 6 HLS/Sentinel-2 bands.
    - **Clay v1.5** (open, Hugging Face `made-with-clay`). Multi-sensor, can also take Sentinel-1.
    - **AlphaEarth Foundations satellite embeddings** (Google DeepMind) via Earth Engine dataset
      `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`: 64-dimension vectors at 10 m, **annual only**, precomputed (no GPU
      needed). Not open weights.
    - **Light baseline:** TorchGeo SSL4EO-S12 pretrained ResNet-18/50 (small, fast, open).
2.2 **Embedding extraction.** For Prithvi/Clay/SSL4EO: run the model on **every clear scene** in each period (not
    just a composite) so the noise test can be computed in embedding space. Tile into chips with overlap, batch on
    GPU, cache embeddings to disk (`.npy` or Zarr) with provenance (model name, version, weights hash, scene IDs).
2.3 **Change scores.** Cosine distance between period embeddings per pixel/patch. For indices, the version 2 deltas.
2.4 **Noise calibration (the key step).** For each method, compute within-period scene-to-scene spread of the
    embedding (or index) and turn the change score into a signal-to-noise ratio (change / standard error). For
    AlphaEarth, which has no per-scene embeddings, estimate noise from year-to-year variation over known-stable
    years/pixels and state this difference clearly.
2.5 **Evaluation against references** in each field: precision, recall, F1 at matched false-alarm rates; PR-AUC of
    the raw score and of the noise-calibrated score; false-alarm rate on the stable control area. Use spatial block
    splits for anything that is tuned, so nearby pixels do not leak between train and test.
2.6 **Report** one main table (methods x fields) and one figure per field. State plainly where no method beats
    noise.

Done when: the table exists with honest confidence intervals (block bootstrap, reuse `experiments/uncertainty.py`)
and a written answer to the research question, positive or negative. A negative answer ("indices are as good or
better after noise calibration") is still a publishable, interesting result if it is done carefully.

Memory tips for 8 GB VRAM: fp16 / `torch.autocast`, batch size 4-16, 224x224 chips, `torch.no_grad()`, free GPU
memory between models; move the 600M models or big batches to Kaggle (free GPU, about 30 h/week).

### Phase 3: A small trained model with honest error bars (May-Jun 2027)

Goal: show hands-on deep learning plus modern uncertainty quantification.

Tasks:

3.1 **Task:** segment glacial-lake water in Sentinel-1 radar images (works in cloud, where optical fails).
3.2 **Labels (weak supervision):** water masks from clear-sky Sentinel-2 scenes taken within a few days of a
    Sentinel-1 scene, cleaned with reference outlines. Record label noise as a limitation.
3.3 **Model:** U-Net (e.g. `segmentation_models_pytorch`) with a small encoder, or fine-tune a light Prithvi/Clay
    head via `terratorch`. Loss: BCE + Dice (handles class imbalance). Inputs: VV, VH, DEM slope.
3.4 **Split by lake, not by pixel** (some lakes entirely held out), plus a time hold-out (train on earlier years,
    test on later).
3.5 **Conformal prediction:** calibrate on held-out lakes so each predicted lake area comes with an interval that
    holds at a chosen rate (e.g. 90%). Pixel-level conformal or conformal risk control for segmentation; lake-area
    intervals are the easiest to explain. Check empirical coverage on test lakes and report it honestly.
3.6 **Use it:** fill the cloudy monsoon months in the Phase 1 lake series with the radar model's predictions plus
    intervals; show this in the UI (visibly marked as model predictions).
3.7 **Optional public dataset check:** evaluate on Sen1Floods11 (public Sentinel-1 flood dataset) to show the model
    is not overfitted to a handful of lakes.

Done when: trained model, test metrics by held-out lake, coverage check for intervals, weights and training config
saved with seeds, and the monsoon gap-filling shown in the UI.

### Phase 4: Paper, demo and polish (Jul-Aug 2027)

Tasks:

4.1 **Short paper** (4-6 pages): question, data, methods, results table, limitations. Write in LaTeX (Overleaf free).
4.2 **Preprint:** post on arXiv (cs.CV or eess.IV; first-time submitters may need an endorsement) or EarthArXiv
    (easier, no endorsement). Gives a permanent public link for the CV.
4.3 **Workshop submission (optional, if timing fits):** Climate Change AI workshops (NeurIPS / ICLR), ML for Remote
    Sensing (ICLR), or an IGARSS student paper. Check the current year's deadlines; they change every year.
4.4 **Demo:** update the GitHub Pages showcase with a page per field and the lake explorer. Keep it fast and static.
4.5 **README rewrite** around the research question and headline result, with the demo link and paper link first.
4.6 **CV entry and statement paragraph** drafted from real numbers (update `docs/CV_BLURB.md`).
4.7 **Owner study pass:** owner works through `docs/LEARNING.md` and the code; practise explaining each choice.

### Buffer and applications (Sep-Dec 2027)

September is buffer for slipped work and reviewer feedback. October-December: applications, emailing professors
with the demo and paper link.

---

## 5. Data and tools summary (all free)

| What | Source | Access |
|---|---|---|
| Sentinel-2 L2A | Element 84 Earth Search (already used) | STAC, no account |
| Sentinel-1 RTC | Microsoft Planetary Computer `sentinel-1-rtc`; fallback ASF HyP3 | STAC + `planetary-computer` signing; Earthdata account |
| DEM | Copernicus GLO-30 | Planetary Computer / AWS |
| AlphaEarth embeddings | Earth Engine `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` | Earth Engine noncommercial account |
| JRC Global Surface Water | Earth Engine `JRC/GSW1_4/...` | Earth Engine |
| Hansen forest change | Earth Engine `UMD/hansen/global_forest_change_*` | Earth Engine |
| Dynamic World | Earth Engine `GOOGLE/DYNAMICWORLD/V1` | Earth Engine |
| Glacial-lake outlines | Glacial Lake Observatory (ESSD preprint, Zenodo), ICIMOD inventory, Hi-MAG | Download |
| Prithvi-EO-2.0 | Hugging Face `ibm-nasa-geospatial`, `terratorch` | Free |
| Clay v1.5 | Hugging Face `made-with-clay` | Free |
| SSL4EO-S12 weights | TorchGeo | Free |
| GPU overflow | Kaggle (about 30 GPU h/week), Colab free | Free account |

New Python dependencies likely needed: `torch` (CUDA build for the RTX 5050; recent GPUs need a recent CUDA
build, check compatibility first), `torchgeo`, `terratorch`, `segmentation-models-pytorch`, `planetary-computer`,
`earthengine-api`, `xarray`/`rioxarray`, `zarr`. Pin versions in `backend/requirements.txt` as version 2 does and
re-run `pip-audit`.

Licences: record every new dataset and model licence in `docs/DATA_PROVENANCE.md` (version 2 already has the
pattern).

---

## 6. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Foundation models too big for 8 GB VRAM | fp16, smaller chips/batches, smaller variants, Kaggle GPU |
| RTX 5050 not supported by the installed PyTorch build | Install a PyTorch build with a recent CUDA version; Kaggle/Colab for heavy runs meanwhile |
| Radar water detection unreliable on frozen lakes or steep slopes | Mask frozen months and shadow/layover; report the masked share |
| Reference outlines do not cover the chosen years | Use clear-sky Sentinel-2 masks as the reference, clearly labelled |
| Earth Engine export limits | Small areas, export at 10-30 m, batch exports; AlphaEarth is annual so data volume is small |
| Results are negative (indices win) | Still report: "after noise calibration, foundation-model change scores do not beat indices for X" is a useful finding |
| Time runs short | Minimum viable version 3 = Phase 0 + Phase 1 + Phase 2 with two fields (lakes + one other) + preprint |

---

## 7. `docs/LEARNING.md` topics (study guide for the owner)

Each entry: what it is, why it is used here, the one or two things an interviewer may ask, a link to read more.

Version 2 concepts: optical satellite basics (bands, reflectance, Sentinel-2 L2A, Sen2Cor, SCL cloud mask), STAC
and COGs, spectral indices (NDVI, NDWI, MNDWI, NDBI, NDSI), compositing, change thresholds, standard error and the
3 x SE rule, block bootstrap confidence intervals, minimum mapping unit, spatial autocorrelation and spatial block
cross-validation, Random Forest, macro-F1 vs overall agreement, class imbalance, why "agreement" not "accuracy",
seasonal decomposition / harmonic fit for time series, resolution effects (10 m vs 20 m).

Version 3 concepts: synthetic aperture radar basics (backscatter, VV/VH, dB, speckle, RTC, shadow/layover), Otsu
thresholding, DEMs and slope, self-supervised learning and foundation models (masked autoencoders, ViT basics),
embeddings and cosine distance, signal-to-noise calibration, PR-AUC vs ROC-AUC, U-Net, Dice/BCE loss, weak
supervision and label noise, spatial and temporal hold-out, conformal prediction (split conformal, coverage),
mixed precision (fp16) and GPU memory, reproducibility (seeds, pinned versions, weight hashes).

---

## 8. Other directions that could be explored (instead of or after version 3)

Ranked roughly by how well they fit the owner's goal (ML applied across fields) and the free-tier hardware.

1. **Landslide mapping after the monsoon in Nepal.** Very strong Nepal relevance. Sentinel-1/2 change detection
   plus a segmentation model; public landslide inventories exist (e.g. post-2015 Gorkha earthquake inventories,
   NASA Global Landslide Catalog). Could be a fifth field in version 3 or a follow-up.
2. **Monsoon flood mapping with radar.** Sentinel-1 + the public Sen1Floods11 dataset; Terai floods in Nepal/Bihar.
   Fits the original flash-flood motivation directly. Overlaps with Phase 3 code, so cheap to add later.
3. **Ecology: species and habitat modelling.** Link Chilika water/vegetation dynamics to waterbird counts (eBird,
   GBIF) or build species distribution models with satellite covariates (Western Ghats endemics). The most
   "biology" option; strengthens the multidisciplinary claim for ecology/conservation advisors.
4. **Agriculture and food security.** Crop-type or crop-calendar mapping in the Nepal Terai from Sentinel-1/2 time
   series (temporal deep learning: LSTM/Transformer/TempCNN). Strong for agriculture, economics and development
   programmes.
5. **Snow cover and water resources.** Snow-cover trends in Nepal basins (MODIS + Sentinel-2) linked to river flow;
   hydrology angle.
6. **Air quality in Kathmandu.** Sentinel-5P NO2/aerosol with ground stations; public health / environmental
   science angle. Different data type (atmospheric), shows breadth.
7. **Urban heat islands.** Landsat thermal + land cover in Kathmandu; urban planning / public health angle.
8. **Forest biomass and carbon.** GEDI lidar footprints + Sentinel-1/2 to predict canopy height or biomass
   (regression with spatial validation); climate/carbon-market relevance.
9. **Natural-language map assistant.** An LLM agent that answers questions like "did this lake grow since 2020?" by
   calling the pipeline as tools and quoting the uncertainty. Shows applied AI/LLM skills; must never let the model
   invent numbers. Good demo, weaker as research.
10. **Time-series anomaly detection.** Compare classical breakpoint methods (BFAST-style) with deep models for
    detecting the date of change, not just whether it happened.

Directions to avoid or treat with care: super-resolution "sharpening" of 10 m imagery (invents detail, conflicts
with the project's honesty theme); disaster prediction or early-warning claims (cannot be validated here; say
"monitoring", not "prediction").

---

## 9. Progress log

Update this table as work happens (newest at the bottom).

| Date | Phase.task | Status | Notes |
|---|---|---|---|
| 2026-11-12 | Plan | Done | Version 3 plan written after review of version 2. Nothing built yet. |
| | 0.1 | Not started | Next task. |

---

## 9. Progress log

- 2026-11-12: Phase 0 done except hosting and git email (Pages deferred by choice). Phase 1 pilot complete for 3 lakes (radar and optical series, Hi-MAG check, Glacial Lakes page). Phase 2: Prithvi embeddings, noise-calibrated comparison framework and a Hansen evaluation on one forest area (see docs/V3_RESULTS.md); result so far is a tie with simple baselines. Phase 3 not started. Next: lakes as a Phase 2 field, second forest area and model, lake expansion for Phase 3.
- 2026-11-12 (later): Phase 2 forest field done with two areas (Bastar, Odisha) and two models (Prithvi, SSL4EO ResNet-50 RGB). Result: no foundation model beats a signed NDVI baseline; see docs/V3_RESULTS.md. Next: lakes as a field, third area, Earth Engine fields, then lake expansion and Phase 3.
- 2026-11-12 (later still): Phase 2 lakes field done against a Sentinel-1 reference; effectively one growing lake (Imja). Prithvi and raw bands beat MNDWI but are tied; noise calibration matters here. Next: third forest area, lake expansion (needed for Phase 3), Earth Engine fields.
- Phase 3 core done: pair set built (30 lakes, 3,227 pairs), U-Net trained, conformal area intervals checked (hold
  on new dates, under-cover on unseen lakes). Results in V3_RESULTS.md. Left: monsoon gap-filling in the lake series,
  wider calibration, several seeds.
- Phase 4 drafted: paper in `docs/paper/v3/` (single Markdown source, built to LaTeX and an HTML/PDF preview by
  `scripts/build_paper.py`; figures by `scripts/make_paper_figures.py`; numbers checked by
  `backend/tests/test_paper_numbers.py`). README rewritten around the research question; CV blurbs updated.
  Not done by design: arXiv/EarthArXiv posting, workshop choice, GitHub Pages hosting (all outward-facing, owner decides),
  reference verification, a real LaTeX compile, and the owner's study pass over `docs/LEARNING.md`.
- Correction found while drawing the paper figures: indices and raw bands raise up to 41% placebo false alarms (NDWI),
  not 33%; fixed in V3_RESULTS.md and LEARNING.md.
