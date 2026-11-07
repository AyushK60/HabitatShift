# HABITATSHIFT
## Master Product, Scientific, Design & Engineering Roadmap

**Document version:** 1.1 — Nepal–Tibet hazards + Kathmandu urban expansion revision  
**Prepared:** 4 November 2026  
**Status:** Planning baseline — scientifically verified event background, but **no claim that this project has yet downloaded imagery, run an analysis, validated change areas, or passed a milestone**.  
**Intended implementer:** DeepSeek V4.1 Plus / 1017 model through a Cline-style coding client, subject to validation of the actual provider/model identity and tool behavior.  
**Primary working location (proposal):** `E:\ClaudeTrail\HabitatShift` (changeable before implementation).  
**Delivery strategy:** Six gated implementation stages, M0–M5; optional post-release M6.  
**Priority:** Real scientific evidence > correct numerical methods > reproducible experiments > exceptional product experience > additional features.

---

# 1. Executive decision

Build **HabitatShift**, a local-first, research-oriented geospatial change-analysis workstation using genuine open satellite imagery. It will compare **matched geographical areas from different time windows**, quantify vegetation and surface-water changes, visualize confidence and data limitations, and benchmark a transparent spectral-index baseline against classical machine learning where independent labels are available.

The planned first release will provide **five curated, reproducible study areas across India and Nepal/Tibet**—including a Himalayan hazard investigation with two distinctly different events—and a beautiful, cohesive web interface. The primary app will be usable without paying for imagery, an AI API, or a hosted processing server. Data downloads and analysis run on the local computer; the showcase can use genuine, precomputed assets suitable for inexpensive/free static hosting.

Do **not** build a worldwide, 20-year, unrestricted on-demand analysis product in M0–M5. That is a later architecture extension, not a prerequisite for a strong demonstration.

**Research framing:** "How reliably can reproducible, lightweight remote-sensing methods describe observable landscape change across ecological, cryospheric-disaster, and urban settings—and how do clouds, seasonal effects, terrain, sensor resolution, and limited reference labels constrain the conclusions?"

**Motivation:** The July 2025 Purepu supraglacial-lake drainage and the **26 August 2026 Gyirong–Rasuwa rock–ice collapse and cascading flood** demonstrate why access to traceable multi-date satellite evidence matters for Himalayan communities. These are **different hazards**, not two equivalent glacial-lake-outburst events. The October 2026 ICIMOD synthesis specifically says the August 2026 event was **not a conventional GLOF**. HabitatShift is an *educational/research investigation tool*, not an operational warning, casualty estimator, or official disaster assessment. Sources and temporal cutoffs appear in §5, §16 and §18.

**Non-claims:** This project will *not* automatically prove deforestation, wetland loss, environmental causation, flood origin, future glacier collapse, mortality, infrastructure damage, habitat quality, biodiversity change, mangrove species, or land-use legality from a spectral index alone. It reports observed spectral/land-cover signals and uncertainty with provenance.

**User role:** Approve any necessary installations/accounts/permissions, review screenshots and science reports at stage gates, and choose whether to continue. The coding agent performs most implementation, testing, documentation, and data preparation. Progress remains dependent on client continuity, approvals, service availability, and independent verification.

---

# 2. Why this belongs in the portfolio

Existing work already provides substantial project-level exposure to language-model interpretability, ML evaluation, compiler internals, database execution, distributed tracing, and interactive simulation. The clearest new research dimension is **remote sensing + geospatial computation + environmental ML + rigorous temporal evaluation**.

By completion, HabitatShift should demonstrate:

1. **Scientific data engineering:** STAC catalog queries, Cloud Optimized GeoTIFF (COG) range reads, sensor metadata, CRS-aware raster operations, provenance, caching.
2. **Mathematical geospatial methods:** normalized difference indices, scene validity masks, geospatial alignment, spatial area measurement, temporal compositing.
3. **ML experimental design:** baselines, train/validation/test partitioning by geographic regions, metrics, honest comparison to independent references, ablations.
4. **Software engineering:** resilient Python pipeline, API contracts, reproducibility, tests, local processing and static-build exports.
5. **Distinctive data product design:** cartographic visual identity, synchronized spatial comparisons, uncertainty layers, detailed provenance and research reporting.
6. **Cryosphere/disaster evidence:** event-window remote sensing for 2025 lake drainage and 2026 rock–ice collapse, with published independent hazard reports and appropriate limits.
7. **Urban geospatial ML:** built-up candidate mapping and urbanization analysis in Kathmandu Valley, with explicit discrimination of bare soil from construction.

**Resume-ready result:** "Developed a reproducible multisector satellite change-analysis platform using Sentinel-2/Landsat open data, geospatial raster processing and classical ML; investigated environmental, Himalayan hazard and urban landscape changes; built interactive, provenance-linked visual investigations." Replace the general language with *measured results* only after they exist.

---

# 3. Product boundaries and release definition

## 3.1 Must ship in V1

- **Five genuine study areas** (three original Indian landscapes, the Nepal–Tibet Himalayan hazard corridor, and Kathmandu Valley), with multiple scientifically defensible observation windows; the Himalayan site includes two separate event episodes (July 2025 and August 2026). Each site must show actual acquisition evidence or be transparently marked blocked; do not invent imagery to achieve a count.
- An attractive overview/landing page and a functional research workstation with a unified design system.
- Real multispectral Sentinel-2 L2A imagery for V1 core comparisons where adequate scenes are available; no fake before/after pictures.
- True-color and false-color composites; NDVI, a clearly defined water index, difference maps, valid-data masks. Add **case-specific** NDSI/snow-water interpretation for mountain studies and built-up-sensitive features for Kathmandu **only when the bands and validation support them**. Do not force NDVI-based ecology methods onto avalanche/debris impacts or urban expansion.
- Pixel and area statistics derived from actual aligned rasters.
- Side-by-side synchronized maps, vertical swipe comparison, opacity overlay, legends, hover/pixel inspection, date/scene provenance.
- A credible change summary that distinguishes **observed index change** from **validated land-cover transition**, and separates **our own image-derived observations** from **third-party published event/damage assessments**.
- At least one simple index-threshold baseline; threshold parameters recorded and configurable.
- An ML component **only if** real training/reference labels and robust evaluation can be established. Otherwise explicitly mark ML evaluation incomplete and do not manufacture a score.
- Local pipeline, cached datasets, exported processed assets, no paid API at runtime.
- Automated unit/integration/scientific-invariant tests, frontend/browser checks where tooling permits.
- Export research report + machine-readable provenance manifest.

## 3.2 Should ship if quality gates permit

- Multi-date composites within each target period rather than single-scene comparisons.
- Method comparison (spectral rule vs Random Forest and/or a well-defined existing probability dataset).
- Ground-truth/reference sampling workflow, uncertainty diagnostics, spatial holdout evaluation.
- Change-type summaries and transition matrix **only for defensible class predictions**.
- Limited custom AOI mode (tiny bounded areas, explicit max size and date range).
- A curated 3–5-scene time series for one case study.
- For the Himalayan study, support **source-area and downstream-corridor subregions** as separate selectable, bounded AOIs beneath an overview map; do not process a multi-hundred-kilometre mountain corridor as one 10 m raster.

## 3.3 Explicitly out of scope for V1

- Unrestricted worldwide processing, global tiles, real-time arbitrary-globe analytics.
- Training a large satellite foundation model from scratch.
- Carbon stock / biomass or habitat health claims without appropriate ground observations.
- Claims of ecological causation, flood causation, damage valuation, precise flood depths, verified deforestation or disaster prediction from image differencing alone.
- Reproduction of the **2026 ICIMOD Sentinel-1 InSAR deformation estimate** as if available from simple Sentinel-2 differencing; full InSAR processing is a specialized later research extension.
- General-purpose drone imagery/medical imaging support.
- Paid satellite imagery subscriptions or mandatory managed cloud processing.
- User accounts, collaboration, billing, SaaS, RAG, multi-agent systems, model fine-tuning.

---

# 4. Free data: precise sourcing and constraints

## 4.1 Primary: Sentinel-2 Level-2A surface reflectance

- **What:** Georeferenced optical multispectral satellite imagery, many bands at 10 m / 20 m / 60 m native spatial resolutions.
- **Period:** Sentinel-2 mission starts in 2015, but consistent *global* Level-2A historical coverage is not guaranteed back to launch. For the first analysis target approximately 2020 and 2025, subject to local availability and quality.
- **How:** Search the **Element 84 Earth Search STAC API** (`https://earth-search.aws.element84.com/v1`) for `sentinel-2-l2a`; inspect returned collection IDs/assets at runtime rather than assuming every field. Use `pystac-client` and windowed reads of COG assets through `rasterio`/GDAL where accessible.
- **Bands:** B02 blue, B03 green, B04 red, B08 NIR at 10 m; B11 SWIR1 at 20 m; SCL scene classification at 20 m where available. Confirm exact asset keys against selected item metadata.
- **Rules:** Honor scale/offset and baseline harmonization metadata, NoData values, proper cloud/shadow masks, different native band resolutions, correct raster georeferencing. Prefer Sentinel-2 L2A **surface reflectance**, not visually enhanced RGB JPEGs.
- **Fallbacks:** Copernicus Data Space for catalog/download; Microsoft Planetary Computer only after checking current authorization/signed asset workflow. Public services are best effort; cache outputs and log failures.

## 4.2 Historical extension: Landsat Collection 2 Level-2

- **What:** Free historical 30-meter surface reflectance for the last 20 years and more (multiple sensors).
- **Use:** Future 10–20+ year comparisons, especially pre-Sentinel dates.
- **Critical:** Landsat Collection 2 SR conversion uses `reflectance = DN * 0.0000275 - 0.2` for the relevant products, with special NoData/QA handling. Sensor band assignments differ. Never compare raw digital numbers or resample Landsat to 10 m and pretend to have acquired 10 m historical detail.
- **Scientific caution:** Different sensors and methods can produce distribution shifts. Temporal comparisons need documented cross-sensor handling, spatial resolution consistency, seasonal matching and uncertainty.

## 4.3 Auxiliary reference datasets

- **Google Dynamic World:** Nine-class probabilistic 10 m land-cover predictions derived from Sentinel-2, accessible predominantly through Google Earth Engine; use as a comparison/weak reference, **not** unquestioned ground truth. Unpaid Earth Engine project access requires noncommercial eligibility registration/verification; do not block M0 on it.
- **ESA WorldCover:** Land-cover maps for 2020/2021 useful as supplementary context/reference. **Do not** interpret direct 2020→2021 class-map differences as genuine change: the published versions use different algorithms.
- **Independent reference:** Public official/reference polygons, carefully documented manual interpretation, or small datasets with explicitly compatible labels and rights. Any training labels derived from an index threshold must not be used as independent evidence that the same index performs well.

## 4.3a Himalayan hazard and urban auxiliary evidence (case-specific)

- **2025 primary event record:** Nepal's National Disaster Risk Reduction and Management Authority (NDRRMA), *Rasuwa Glacial Flood Situation Report #1* (10 July 2025), describes rapid discharge of a supraglacial lake on the **Purepu Glacier** in Tibet on **8 July 2025**; the report includes a preliminary multi-date Sentinel-2 lake-extent analysis. Historical report area estimates are contextual **published estimates**, not values the app may silently display as its own measurements. Source: `https://ndrrma.gov.np/mediafiles/publications/Rasuwagadhi_Flood_Sitrep1_08072025_.pdf`.
- **2026 primary scientific assessment:** ICIMOD, *Understanding the Gyirong–Rasuwa disaster of 26 August 2026: A preliminary synthesis* (13 October 2026), describes a rock-and-ice collapse on the Langtang Lirung mountain system, subsequent debris-laden flood, uncertainty about cascade mechanisms, and concludes this is **not a conventional GLOF**. ICIMOD separately reports Sentinel-1 InSAR deformation observations; they are a reference to cite, **not** automatic project outputs. Sources: `https://lib.icimod.org/records/r745z-mvm84`, `https://www.icimod.org/press-releases/second-major-himalayan-flood-in-seven-weeks-raises-new-questions-about-mountain-risk/`.
- **2026 reference impact mapping:** UNOSAT published preliminary satellite-detected flood/mudflow/rockflow extents on 28 August 2026, derived from imagery around 26–27 August. Download vector polygons *only if accessible under their terms*, cite product/version/date, and use as an **external preliminary reference**, not unquestionable ground truth. Source: `https://unosat.org/products/4259/`.
- **Sentinel-1 SAR:** Open Copernicus radar data can be useful where optical images are obscured by monsoon clouds, but terrain correction, speckle, layover, shadow, calibration, and co-registration are non-trivial. **Not a first-release requirement**, unless the agent demonstrates a validated bounded pipeline. Sentinel-1 InSAR deformation estimation requires SLC phase-based processing and expert validation, not a generic image subtraction. Source: `https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-1`.
- **Glacier geometry:** RGI 7.0 / GLIMS provide **reference glacier outlines** whose date and purpose must be shown; historical inventory polygons are not contemporaneous proof of event-time glacier boundaries. Sources: `https://rgidata.org/`, `https://www.gtn-g.ch/data_catalogue_glims/`.
- **Topographic context:** Copernicus DEM GLO-90 / publicly accessible GLO-30 tiles may be used to give elevation, slope and approximate context. These are predominantly **older elevation surfaces**, NOT before/after 2026 terrain models; no claim of computed excavation depth or lost ice volume. Some GLO-30 services require registration/authorization as of August 2026. Sources: `https://registry.opendata.aws/copernicus-dem/`, `https://dataspace.copernicus.eu/news/2026-8-25-copernicus-dem-30m-view-service-update`.
- **Kathmandu urban reference:** Use Sentinel-2, optional Landsat for longer periods, independent built-up reference polygons where available and permitted, plus documented OSM/municipal context. Historical OSM feature geometry is **not** automatically a timestamped construction record. Literature already documents that built-up indices confuse buildings with exposed soil and riverbeds. Reference: `https://www.mdpi.com/2072-4292/11/19/2296`.
- **Rights / confidentiality:** Download raw government/UN/ICIMOD figures only under permitted reuse terms. Link to official reports where license or embedded image reuse is unclear. Do not label third-party scientific maps as newly computed project results.

## 4.4 Basemap, imagery and attribution rules

- Interactive geospatial frontend: **MapLibre GL JS** (open-source renderer); map tiles still require a legally permitted provider.
- Prefer a bundled regional overview / prepared georeferenced raster overlay or an explicitly permitted free provider for V1 showcases.
- OpenStreetMap *data* is open, but `tile.openstreetmap.org` tile service prohibits bulk/offline prefetch and has usage requirements. Do not scrape tiles to package them into the app. Render attribution and respect usage policy.
- Include imagery and data acknowledgements: e.g. "Contains modified Copernicus Sentinel data [years]" for adapted Sentinel imagery, plus provider and dataset citations. Record exact data licenses and access dates.

## 4.5 Data availability acceptance checklist

Before claiming a location-period pair is available, save:
- AOI polygon / CRS and selected study dates.
- STAC query, returned item IDs, acquisition timestamps, cloud-cover metadata, asset URLs/identifiers, platform/product processing baseline where available.
- Available useful bands, no-data masks, local valid-pixel fraction.
- Download window dimensions, resolution, data size and source attribution.
- Reproducibility manifest with source URL or stable asset identity.

**Never** replace missing source imagery with a generated picture while calling it real satellite evidence.

---

# 5. Five-site study portfolio, Himalayan event scope and data selection

**Decision:** Keep the original three ecological/environmental cases, **add a Himalayan hazard case with two distinctly different events**, and **add Kathmandu Valley urban expansion**. Five site-level entries, six event/landscape investigations in practice. This is a deliberately mixed-domain research atlas, not a vegetation-only application.

**Integrity rule:** These are *planned* sites. No source scenes, image timestamps, event footprints, model results or area-change numbers are yet verified by this project. Every completed case must cite exact STAC imagery IDs, masks, time window, grid, analysis code and limitations. If one case fails data feasibility, preserve its planned slot and mark it **blocked** pending alternative data or explicit user-approved substitution; do not silently replace with fictional maps.

| ID / portfolio section | Proposed place and question | Investigation type / target periods | Main limitation |
|---|---|---|---|
| A — Coastal Ecotone | **Coringa / Godavari delta, Andhra Pradesh** — spatial patterns of vegetation and surface-water change | Matched-season windows near 2020 and 2025 | Tidal level, turbidity, aquaculture, cloud, mixed mangrove/water pixels; no species claims |
| B — Dynamic Wetland | **Chilika Lake, Odisha** — seasonal vs longer-term lake and shore signals | Matched dry-season 2020/2025 and seasonal sensitivity experiment | Water level/season, turbidity, mixed pixels; no hydrologic cause claims |
| C — Forest Landscape | **Selected Western Ghats** forest landscape — spatial consistency of vegetation signals | Matched-season 2020/2025, after data feasibility | Topographic shadow, complex canopy, season, agriculture vs forest |
| D — Himalayan Evidence | **Upper Lhende / Purepu / Langtang Lirung / Rasuwagadhi corridor, Nepal–Tibet** — what changes are visibly supported around July 2025 and August 2026 disasters? | **Two separate event storylines**, each with pre-/post-windows, multiple small source/corridor AOIs | Cloud/snow/terrain shadows, optical gaps, event causation not inferable from simple differences |
| E — Urban Landscape | **Kathmandu Valley, Nepal** — candidate expansion of built-up/impervious surfaces | Matched windows approx. 2016/2020/2025 where feasible, with 2020→2025 as V1 core | Exposed soil/riverbed confusion, ongoing construction, spatial resolution and independent labels |

## 5.1 Site D — Two *different* Nepal–Tibet disaster episodes

### D1: Purepu supraglacial-lake drainage, 8 July 2025

- **Grounded historical context:** Nepal NDRRMA's 10 July 2025 situation report attributes the Rasuwa flood to rapid discharge of a supraglacial lake on the Purepu Glacier in Tibet; it documents satellite interpretations of lake growth through June/early July and drainage around the event. This is **published context**, not an output of HabitatShift.
- **Data objective:** Find genuine Sentinel-2 observation windows in spring/early summer 2025, immediately before the event if available, and after the event where reasonably clear observations exist; save **exact** scene acquisition dates, not fabricated dates.
- **Target variables:** Optically observable lake/water extent, nearby snow/ice classification and validity, and candidate changes within an AOI around the lake. Optionally show published downstream corridor as geographic context, not a locally derived flood route.
- **Measurement:** Compare water masks using documented NDWI/MNDWI variants and **manual/reference cross-check**; report visible lake area with an uncertainty/threshold-sensitivity range when defensible. Where shoreline mixed pixels/clouds make it indeterminate, state so.
- **Do not claim:** exact discharged volume, dam failure mode, flood height, flood discharge, personal loss, or that this app independently established cause. Area change alone cannot yield volume without bathymetry or water-level measurements.
- **AOI rule:** Start with a small bounding polygon around the published/source-area lake; government reports include approximate location context, but validate selected AOI against georeferenced imagery before use.

### D2: Langtang Lirung rock–ice collapse and cascading flood, 26 August 2026

- **Grounded historical context:** ICIMOD's 13 October 2026 preliminary synthesis characterizes the event as **rock-and-ice collapse and a cascading cryospheric geohazard**, rather than a conventional glacial lake outburst. ESA's 31 August 2026 reporting and UNOSAT's 28 August preliminary map offer independently published satellite context.
- **Data objective:** Compare actual pre-event and post-event Sentinel-2 observations around (a) the high-elevation source/detachment zone, (b) a bounded downstream valley sector, and optionally (c) the Rasuwagadhi crossing. Each region uses its own **small** gridded AOI. Do not process the entire impacted river length in one high-resolution computation.
- **Target variables:** Candidate snow/ice or exposed-ground difference where valid, visibly changed debris/deposition/river-margin signatures where multispectral resolution permits, and map-based context of external impact polygons if legally accessible. These are **observed surface changes**, not a complete causal reconstruction.
- **Published Sentinel-1 InSAR evidence:** ICIMOD reported up to 40 cm of line-of-sight deformation in the pre-collapse interval (7 July–24 August 2026). Display this as an attributed **external literature finding**, only if linked and properly described; do **not** recreate a precise deformation map, issue alerts, or imply predictive capability without an independently verified InSAR workflow.
- **Optical-image limitation:** Monsoon cloud can block crucial before/after dates. Use last suitable pre-event and first suitable post-event observations with exact timestamps and report the time gaps. If no defensible optical match exists, show an explicit *limited-visibility/blocked* result. A cited external map can support narrative context but cannot stand in for our own generated scene analysis.
- **Do not claim:** rock/ice volume, exact flood depth, individual infrastructure loss, casualties, physical causation, or a forecast of future hazards from simple before/after reflectance imagery. Report third-party damage numbers only with their source, date and independent-assessment label, if such numbers are even necessary.

### Himalayan user interface — a single study, two distinct investigations

1. Show a **small geographic overview** of the Nepal–Tibet border region with official/real basemap attribution, approximate event source zones and an annotated downstream corridor. Draw nothing as an exact flood path without a trusted source geometry.
2. Offer tabs **"2025 · Lake drainage"** and **"2026 · Rock–ice collapse"**. Include clear differences in mechanisms and evidence.
3. Each tab provides pre/post swipe, acquisition timestamps, real RGB/false-color imagery where available, selected index/difference layers, clouds/missing-data hatching, provenance, and a concise evidence-versus-interpretation explainer.
4. Optionally compare a reproduced result with cited NDRRMA or UNOSAT external interpretations. **Never** copy official figures into our output metrics.
5. A respectful **"Why this study matters"** block can cite the disasters and the need for transparent transboundary satellite evidence, without sensational injury/death imagery or claiming this product would have prevented the event.

## 5.2 Site E — Kathmandu Valley: a different remote-sensing domain

- **Purpose:** Demonstrate candidate **urban/built-surface change**, not vegetation decline marketed as urban growth.
- **Data:** Sentinel-2 matched-season L2A imagery for approx. 2020 and 2025; a 2016 scene or historical Landsat extension only after availability and cross-sensor limitations are recorded. Use a bounded city/valley AOI; for a large valley, process tiles/regions and aggregate scientifically.
- **Methods:** RGB/false-color visualization, NDVI, optional NDBI `(SWIR1 - NIR) / (SWIR1 + NIR)`, water/bare-surface masks, and a validated built-up classifier **only if labels are independently sourced**. NDBI alone does not prove a pixel is built-up.
- **Reference context:** OSM buildings/roads, authorized municipal maps, or independent sampling may assist **validation and interpretation**, but historical OSM metadata cannot be treated as exact construction dates.
- **Outputs:** Candidate built-surface share and change under a labeled method, mapped ambiguity, threshold sensitivity, selected validation examples, class transitions only after credible classifier validation.
- **Critical test:** Negative controls in bare soil/riverbed/peri-urban exposed ground, where built-up indices commonly produce false positives.

## 5.3 Different geographic scales: overview vs measurements

- For A/B/C: begin approximately 5 × 5 to 15 × 15 km working windows, enlarging only after resource and quality checks.
- For D: **multi-scale view** is required: a geographical overview of the upper watershed/downstream corridor plus separately processed source-area/crossing/valley AOIs. A drawn river line, border or external geometry is **context**, not proof of the precise 2025/2026 flood footprint.
- For E: city-scale overview, bounded processed subtiles or subsets; do not promise all Kathmandu Valley imagery at once at full resolution on a free hosted backend.
- Keep a consistent map projection/geospatial transformation at each analysis level. Raster/metric products must never be inferred from a visual screenshot of a satellite basemap.

## 5.4 Data-first prioritization and fallbacks

- **M0:** Verify at least one straightforward two-date Sentinel-2 site (A/B/C) **and perform an explicit Himalayan 2025/2026 imagery feasibility search**. Track whether post-event optical scenes are usable. Do not postpone all Nepal feasibility until the final stage.
- **M1:** Build shared raster/mask/projection/index machinery and optional case-specific primitives without overfitting to one site.
- **M2:** Verify method-specific validation/uncertainty. Hazard literature is not automatically the same as independent pixel labels.
- **M4:** Expand and publish case bundles in bounded batches. A blocked mountain scene receives an honest *not yet supported* badge with evidence, not a fabricated perfect before/after.
- **User review:** The user selects/approves any replacement case when a proposed source is unusable. The model should document options and avoid endless retries.

---

# 6. Scientific methods: exact computations and safeguards

## 6.1 Satellite preprocessing protocol

1. Query an explicit AOI polygon and time windows; list scene candidates.
2. Rank/select by actual AOI-valid cloud fraction (scene-level cloud % alone is insufficient), acquisition coverage, season matching, availability and processing baseline.
3. Read only target windows and required bands. Prefer COG range requests; cache with content or query identifiers.
4. Read SCL mask; remove NoData, cloud shadows, medium/high cloud, cirrus, snow where inappropriate, invalid or saturated pixels. Preserve a mask of observations excluded and record rationale.
5. Convert asset values to actual reflectance using dataset-specific scaling/offset; verify input asset metadata and harmonization.
6. Reproject and align datasets onto one explicit projected analysis grid; choose suitable local UTM/equal-area CRS for area measurements, not naive latitude/longitude pixel area.
7. Resample continuous reflectance bilinearly or suitably; categorical QA masks using nearest-neighbor; never blur labels.
8. Build within-window valid-pixel composites, record how many clear observations support each pixel. Keep common-valid mask for comparison to avoid denominator mismatch.
9. Compute indices, validity coverage, pixel areas, uncertainty summaries.
10. Export georeferenced rasters and browser-friendly visual assets with legends and provenance.

## 6.2 Spectral indices

- **NDVI:** `(NIR - Red) / (NIR + Red)` with safe denominator handling, clipped/flagged invalid pixels, and fixed band mapping.
- **NDWI (McFeeters):** `(Green - NIR) / (Green + NIR)` used cautiously as water-sensitive signal; explicitly label variant.
- **MNDWI (Xu):** `(Green - SWIR1) / (Green + SWIR1)` if SWIR1 is available. B11 is native 20 m on Sentinel-2; document working grid and upsampling/aggregation.
- Optionally NBR or another index for a scientifically justified additional site, but do not add formulas merely for visual variety.

## 6.3 Change measures

- Valid-mask-aware `delta_NDVI`, `delta_NDWI`, or `delta_MNDWI` on a common analysis grid.
- Per-pixel threshold-defined candidate change, with user-visible threshold and sensitivity plots.
- Compare equal valid geographic footprints; avoid comparing raw "green pixels" across differently masked years.
- Area in hectares/km² from proper projected/equal-area pixel geometry; report valid observation area and percentage coverage.
- Summary distribution, quantiles, counts and optionally confidence intervals from suitable spatial bootstrap—not unsupported model confidence labels.
- Where a trained land-cover classifier is validated: class-to-class transition matrix and class area changes; otherwise **no definitive land-cover transition table**.

## 6.4 Seasonal and atmospheric confounders

- Match months/seasons for core temporal comparisons.
- Show scene count and valid-pixel coverage per period.
- Mark cloud/shadow gaps visibly.
- Support deliberate seasonal-mismatch stress test for one site.
- For coastal sites record tide/time as *uncontrolled possible confounder* unless reliable tide metadata are integrated.
- Do not infer causation from maps (e.g., construction, deforestation, drought) without corroboration.

## 6.5 Classical ML research workbench

### Required baseline
- Rule-based index thresholds, documented and evaluated on independent references where possible.

### Candidate ML model
- Random Forest classifier on reflectance bands + indices + limited textural features, trained only using explicitly sourced labels.
- Feature standardization as appropriate; avoid information leakage across adjacent pixels and across time.
- Spatially separated training/validation/test partitions by polygons/blocks, not random neighboring pixels.
- Record class balance, total independently labeled pixels/areas, scene/time coverage, class definitions and label provenance.

### Evaluation
- Balanced accuracy, macro-F1, per-class precision/recall, confusion matrix and IoU where classification segmentation is appropriate.
- Calibrated probability / reliability and coverage if probabilistic outputs can be validated.
- Geographic holdout and cross-site transfer when label support permits.
- Ablations: bands-only vs indices; single-scene vs composite; thresholds vs Random Forest; matching vs mismatched seasons.
- Variance or confidence intervals only if computed with explicit resampling methodology.
- Baseline must be truly independent of evaluation labels.

### Dynamic World comparison
- Compare with its probability outputs only if legal/API access can be configured; label as **reference model agreement** rather than independently validated accuracy.
- Do not require Google Earth Engine in M0/M1.

### Research fallback
If independent labels prove inadequate, ship scientifically honest **spectral change analysis + uncertainty + reproducibility**, plus an ML module clearly labeled experimental/unvalidated. Never produce invented accuracy values or call circular labels ground truth.

---

## 6.6 Case-specific algorithms and masks — no universal NDVI pipeline

A shared, validated raster alignment and provenance pipeline is **not** the same as one universal change detector. The app must dispatch scientifically justified case methods:

| Study type | Supported first-pass measures | Must not infer from index alone |
|---|---|---|
| Vegetation/coastal (A/C) | NDVI, surface-water-sensitive index, masked delta | Species, ecology, deforestation cause |
| Wetland (B) | NDWI/MNDWI, seasonal water extent, cloud/tide confounders | Permanent wetland loss from one seasonal pair |
| 2025 lake drainage (D1) | Water mask + outline/area under QA, optional NDSI to contextualize snow | Discharged water **volume**, flood hydrodynamics |
| 2026 ice-rock collapse (D2) | Spatially aligned RGB/false-color difference, valid snow/ice context, candidate debris/surface disturbance | Precursor failure prediction, exact displaced volume, flood extent without validation |
| Kathmandu urban (E) | NDBI/NDVI/water features with independent validation, classification if available | Verified new buildings from NDBI alone |

- **NDSI (snow index):** `(Green - SWIR1)/(Green + SWIR1)` where calibrated/valid reflectance, with snow/cloud and shadow QA. Snow/ice are **target classes** in the Himalayan study; do **not** indiscriminately apply a mask that removes them before computing cryosphere results.
- **NDBI (built-up index):** `(SWIR1 - NIR)/(SWIR1 + NIR)` as a feature, **not an independent land-use label**. Retain 20 m/native-band resolution metadata and explicit grid choice.
- **SCL limitations:** Scene classification is an aid, not a flawless glacier/bare-rock classifier; compare threshold/QA sensitivity and acknowledge terrain shadows.
- **Mountain topography:** DEM-derived hillshade/slope may be used for contextual display and illumination checks; a single historical DEM cannot establish post-disaster terrain displacement. Avoid relief displacement and look-angle differences masquerading as change.
- **Event windows:** Use observed acquisition timestamps relative to the **actual event date**, not generic annual averages. Show days-before/after, valid fraction, scene count and resolution; where matched pairs are invalid, **do not output change area**.
- **Published hazard evidence:** Keep a distinct `source_type=external_assessment` channel, with reference publisher, publication date, evidence type, location, claims/limits and URL. Never blend official reported figures into internally computed metrics without explicit labeling.

## 6.7 Disaster-area reference validation: only when evidence supports it

1. Obtain documented reference imagery/extent from government/ICIMOD/UNOSAT if legitimately accessible and suitable for comparison.
2. Align the reference to the project's analysis grid, verify temporal and spatial coverage, and label **preliminary reference**, not universal ground truth.
3. Where pixel-label mapping is meaningful, compute spatial overlap metrics with provenance and spatial resolution caveats; otherwise provide a visual side-by-side and an uncertainty note instead of artificial IoU/F1 values.
4. Reference products from different dates, sensing methods or target classes may **not** be treated as directly comparable labels.
5. Never turn a historical post-event case study into a real-time early warning tool without a separately specified, evaluated safety and monitoring project.

---

# 7. Product design: NOT an AI-looking dashboard

## 7.1 Design thesis: "Midnight Teal & Copper"

**Design identity:** Contemporary Cartographic Editorial.

HabitatShift uses a visually distinctive design system combining modern scientific publishing, professional geospatial research interfaces and premium editorial presentation.

The experience should feel sophisticated, confident, technically precise and visually memorable.

It must not resemble a generic AI or SaaS dashboard.

### Official design tokens

| Token | Value | Usage |
|---|---|---|
| Midnight Teal | `#193C43` | Primary navigation, headings, prominent surfaces |
| Copper | `#D68A5D` | CTAs, selection accents, visual emphasis |
| Warm Ivory | `#F2F0EB` | Main page backgrounds and light workspaces |
| Sea Glass | `#7FABA7` | Secondary interface accents |
| Deep Charcoal | `#18272D` | Primary body text, technical surfaces |
| Light Divider | `#D8DDD9` | Subtle separators and component boundaries |
| White Surface | `#FFFFFF` | Elevated research panels where appropriate |

Use additional accessible semantic colors for errors, warnings, uncertainty, masked pixels, and scientific map legends.

Brand colors must never override the correct scientific representation of imagery or measurements.

### Typography

- Editorial display: Newsreader or Fraunces.
- Interface: IBM Plex Sans or Geist.
- Scientific metadata: IBM Plex Mono.

Use licensed fonts with suitable fallbacks.

### Visual signature

- Sophisticated asymmetrical editorial layouts.
- Carefully framed real satellite imagery.
- Distinctive midnight-teal navigation.
- Warm ivory research workspaces.
- Controlled copper accents.
- Precise cartographic detailing.
- Clear technical typography.
- Professional charts, scientific legends and annotations.
- Smooth, restrained interaction animations.
- Consistent spacing, alignment and information hierarchy.

### Design experience

The landing page must feel like an exceptional research product.

The investigation workspaces must remain technically credible and highly usable.

The five geographical study areas must feel connected through a unified visual language while retaining domain-specific scientific representations.

The Himalayan disaster investigation requires respectful documentary presentation and accurate evidence attribution.

The Kathmandu investigation should emphasize urban mapping and actual land-cover measurements.

### Visual quality restrictions

Avoid:
- Neon gradients.
- Purple-black AI dashboard styling.
- Excessive glow.
- Decorative AI imagery.
- Repetitive generic cards.
- Large empty areas.
- Unreadable small typography.
- Unrelated animations.
- Inconsistent page themes.
- Fabricated scientific visualization.

Ensure accessible contrast and responsive layouts.

**This identity must be applied consistently during M3 and validated during M5.**

## 7.2 Landing page: the hero must be exceptional

**Above the fold, desktop 1440px+:**
- Calm two-part layout: generous editorial headline and CTA on one side, a striking actual georeferenced true-color / false-color comparison preview on the other.
- Hero statement idea: **"Read the landscape. Trace what changed."**
- Subline explaining real satellite scenes, multi-date comparison, and reproducible results.
- Primary action: **Explore the Atlas** (opens first curated site).
- Secondary action: **View the Method**.
- Date and geographic provenance attached to hero preview, not decorative fake data.
- Subtle map swipes/annotation reveals only if driven by genuine prepared imagery.

**Below the fold:**
- **Five** visually distinctive case-study entries with real imagery, geographic context, observation periods and investigative questions. Feature the **Himalayan Evidence** story without displacing the scientifically easier demo that opens first. Nepal site contains two clearly labeled event subviews (2025 and 2026).
- A concise 3-step "from acquisition to evidence" methods narrative.
- Scientific credibility strip: open data / documented scenes / reproducible methodology, no unsupported inflated stats.
- Footer with source acknowledgements, repository link placeholder, limits and contact link only if user supplies one.

Avoid: center-aligned gradient mega-hero, floating random 3D sphere, neon-on-black AI layout, generic metric badges, 3-column repetitive feature cards, decorative satellite photos not related to real studies.

## 7.3 Main workstation: information architecture

Recommended arrangement at 1440×900:

1. **Top navigation** — brand, Atlas, Study Areas, Methods, Experiments, Export; compact context.
2. **Study header** — region, date windows, sensor, valid coverage, methods and provenance link.
3. **Primary geography stage (about 65–75% width)** — interactive synchronized map(s), with compact compare tools integrated into the map not parked in detached boxes.
4. **Research inspector (25–35% width)** — layers, legends, metric interpretation, sample pixel/region values, cloud warnings.
5. **Bottom analysis dock** — timeline, distributions/transition analysis and model comparison tabs; expandable and/or resizable.

Avoid deeply nested scrolling and huge empty panels. Allow workspace maximization and keyboard shortcuts for common map actions.

### Key interactions
- Before/after vertical swipe with exact registered maps.
- Side-by-side with locked pan/zoom.
- Opacity overlay, true/false color toggle.
- NDVI / NDWI / MNDWI + delta heatmap with fixed scientifically interpreted legend.
- Change-threshold slider and immediate recomputation of **precomputed local raster** summaries where feasible.
- Click a pixel to inspect band reflectances, index values for each window, valid observation count, location and source item IDs.
- Draw/select a small ROI for recalculated local statistics (client on precomputed downsample or backend on full-resolution rasters; label distinction).
- Class/probability layers only if model scientifically valid; otherwise show candidate signals with honest names.
- Time-strip of observations (show exact scene dates), quality masks, and missing-data hatch.
- One-click research-methodology and provenance export.
- A **study-type-aware explorer**: ecological index panels for wetlands/forests, an event-timeline and source/downstream subregion switcher for the Himalayan hazard case, and built-up validation/confusion notes for Kathmandu. Do not show an irrelevant universal NDVI dashboard for all five studies.

## 7.4 Mapping implementation

- MapLibre GL JS or another capable open map renderer, chosen after a minimal technical proof.
- Raster layers from georeferenced COGs, bounded PNG/WebP/ZXY pyramids, or a local TiTiler/rio-tiler-backed server as appropriate; no need to load original full TIFF in the browser.
- Prepare static study tiles/rasters for reliable free-hosted demo; client must not make costly/unbounded satellite catalog requests in showcase mode.
- Respect geographic bounds/CRS, map scale and attribution.
- Ensure *one source of truth* for geographic transforms; no CSS-positioned fake overlays.
- Design responsive alternate on tablets/mobile: compare tab/drawer; maps usable, not crushed.

## 7.5 Nepal-origin story and ethical editorial treatment

- The product's **origin story** may briefly say: "HabitatShift was motivated in part by the 2025 and 2026 Himalayan disasters and the need for transparent, reproducible landscape evidence." Do **not** say it was designed before those disasters, prevented them or can predict similar events.
- Use a respectful documentary/cartographic presentation for the Nepal–Tibet case. No dramatic disaster animations, sensational casualty numbers, or fabricated footage. Avoid geographic/political assertions unsupported by data; label the border and referenced place names using authoritative sources.
- Label **2025 lake drainage** and **2026 rock–ice collapse** separately in UI, legends, report headers and metadata.
- Keep warm atlas-paper/forest/clay theme; use a distinct restrained **stone/ice/snow** semantic layer in Himalayan case and a **terracotta/urban grid** emphasis in Kathmandu. These are case-specific encodings, not arbitrary wholesale theme changes.
  - *[M3 reconciliation, 7 Nov 2026: the "warm atlas-paper/forest/clay theme" wording above predates the final identity. The binding theme is §7.1 **Midnight Teal & Copper**, implemented in `docs/DESIGN_SPEC.md`; the stone/ice/snow and terracotta case-specific encodings remain in force on top of it. "The Field Atlas" mentions elsewhere in this roadmap refer to that superseded working name and are preserved as history.]*

## 7.6 Design QA acceptance

- Landing and workbench have consistent typography, spacing, control states and theme.
- Images are real dataset-derived and attribution is visible.
- No misleading "10m" claims for 20m-native products or resampled Landsat.
- 1920×1080, 1440×900, 1280×800, 768px and 390px screenshots checked.
- No overflow, unreadable legends, map/date misalignment or tiny default panels.
- No P0/P1 console errors; keyboard focus/contrast/reduced motion pass.
- Browser E2E verifies swipe, synchronized map, zoom, layer toggles, pixel inspection and exports.

---

# 8. Proposed stack and local setup

## 8.1 Architecture

**Frontend:** React + TypeScript + Vite; MapLibre GL JS; lightweight accessible UI primitives; ECharts/Observable Plot/Recharts for measured statistical charts; CSS variables and carefully organized components. Avoid unnecessary UI frameworks that impose generic dashboard styling.

**Backend:** Python 3.11 or a verified compatible version; FastAPI + Pydantic; rasterio/GDAL, NumPy, xarray (optional), GeoPandas/Shapely, pyproj, `pystac-client`, `stackstac` or `odc-stac` where beneficial, `scikit-learn`, joblib; optional TiTiler only if justified by tile serving.

**Local storage:** content-addressed/canonical directory cache for downloaded windows; manifest JSON; SQLite for job history if useful; GeoTIFF/COG for analytical outputs; quantized tiled image assets for static web showcase. No production DB/server complexity before demonstrated need.

**Background processing:** bounded local job runner, progress states and cancellation; avoid pretending that long downloads are instant. FastAPI can manage orchestration but expensive jobs should not block event loop.

**Testing:** pytest (+ property/invariant tests for raster math), frontend Vitest, Playwright Chromium, reproducibility checksums, optional geospatial tool cross-check using rasterio/GDAL reference operations.

**Target machine:** Windows 11 + 24 GB RAM + NVIDIA RTX 5050 Laptop 8 GB VRAM + WSL2/Docker available. Raster and Random Forest work is CPU-capable; GPU optional for later segmentation work. Do not require CUDA to run M0–M5.

## 8.2 Suggested repository structure

```text
HabitatShift/
  README.md
  .env.example
  .gitignore
  pyproject.toml or backend/requirements.lock
  frontend/
    src/
      app/                 # routes, app shell, state
      design/              # tokens, components, typography
      features/atlas/
      features/studies/
      features/compare/
      features/methods/
      features/experiments/
      features/exports/
      maps/                # geospatial map components
      data-contracts/
    public/studies/        # bounded genuine processed public demos
    tests/
  backend/
    app/api/
    app/catalog/
    app/acquisition/
    app/preprocess/
    app/indices/
    app/change/
    app/ml/
    app/validation/
    app/export/
    tests/
  scripts/
    setup.ps1
    start.ps1
    stop.ps1
    status.ps1
    verify.ps1
    build_showcase.ps1
  studies/
    registry.yaml
    coringa/
    chilika/
    western_ghats/
    himalayan_rasuwa/          # 2025 lake drainage and 2026 rock–ice event, separate windows/AOIs
    kathmandu_urban/
  data/
    cache/                # Git ignored; raw data, temporary outputs
    manifests/            # small, tracked reproducibility records
  docs/
    DESIGN_SPEC.md
    SCIENCE_PROTOCOL.md
    DATA_PROVENANCE.md
    EXPERIMENTS.md
    TEST_REPORT.md
    LIMITATIONS.md
    RELEASE_CHECKLIST.md
    evidence/             # selected browser screenshots
```

Do not commit enormous TIFF assets by default. Keep a compact sampled public demo package, reproducible generator commands, data manifests and legal attribution. Review hosting/file-size limits before bundling raster tiles.

## 8.3 Permissions and user actions

The coding client may request:
- Project-local code/file read-write, repo initialization, test execution, Node/npm and Python package install.
- Normal outbound HTTPS to publicly documented STAC/data hosts, with no broad network scanning.
- Bounded disk usage for satellite windows; startup health checks and local ports.
- Browser automation for visual QA.
- Optional WSL2 use if geospatial dependencies fail on native Windows.

**Not allowed without explicit user approval:** global changes, admin elevation, deleting unrelated files, secrets export, cloud billing, external deployment, registering new accounts, installing unknown executables, or killing unrelated processes. Never paste API keys into README, Git history or logs.

Installations, if required, should be scripted and reversible. Pin versions after the first verified combination. Prefer venv and project-local npm packages. The user reviews permissions at each irreversible step.

---

# 9. SIX-STAGE IMPLEMENTATION ROADMAP — GATED

**Execution policy:** Every stage begins with current repo audit, an explicit acceptance checklist, and a clean Git checkpoint. Every stage ends with real tests, screenshots where UI changes, a concise handoff report, and a recoverable commit. No unverified "PASS" labels. Independent read-only audit after M2 and M5 is recommended.

## M0 — Data feasibility, foundation & design contract

### Objective
Prove end-to-end access to genuine, usable, **multi-date** satellite data for one carefully bounded Indian AOI, while establishing the engineering foundation and a documented non-generic design direction.

### Implement
1. Initialize repository and clean Python/TypeScript toolchain; add setup and verification scripts.
2. Create `studies/registry.yaml` and flexible study metadata schema.
3. Build Earth Search STAC client with AOI/date/cloud query, pagination/bounds, retries with backoff, user-agent, rate limiting and local caching.
4. Choose small first AOI near Coringa (or scientifically better fallback after search); query two seasonally comparable periods near 2020 and 2025.
5. Log *actual* candidate item IDs and cloud metadata; select scenes based on AOI coverage/valid pixels rather than global cloud percent alone.
6. Read B02/B03/B04/B08/SCL in bounded windows; compute valid masks, true-color thumbnails, NDVI previews; check georeferencing and metadata.
7. Save JSON provenance manifest and data licensing acknowledgments; no fabricated scenes.
8. Create small proof webpage showing two true-color scenes, date, valid coverage, coordinate view and metadata; not the full landing product.
9. Define detailed design tokens, typography, page sketches and required map interactions before M3.
10. Write first scientific invariant tests (formula, mask, coordinate transform, known synthetic raster fixtures used **only as tests**, not as real-study outputs).
11. **Himalayan feasibility spike:** query/catalog actual Sentinel-2 scenes around both **8 July 2025** and **26 August 2026**, separated by source-area AOI, with cloud/valid fraction, exact acquisition dates and a non-fabrication verdict. Save `docs/M0_HIMALAYAN_DATA_FEASIBILITY.md`.
12. Record ICIMOD 2026 and NDRRMA 2025 as **external literature context**, not computed project results. Check external UNOSAT polygons availability/rights without making a nonessential registered service a blocker.
13. Make one preliminary availability/quality query for Kathmandu Valley 2020/2025, recording exposed-soil/urban evaluation risks.

### Acceptance / stop gate
- At least one real straightforward AOI (A/B/C) has **two valid, physically real** observations from distinct periods with meaningful overlapping cloud-free coverage. The Himalayan feasibility spike must return exact scene candidates and visibility limits for **both events**; a cloudy/blocked Himalayan pair is an honest M0 result, not an automatic failure of the entire cross-domain platform.
- The two files/images carry exact STAC IDs, acquisition dates, source and lawful attribution.
- Georeferencing and a sampled band reflectance value checked independently.
- Sample NDVI derived from actual pixels, with NaN masking and denominator safeguards. For the Himalayan proof, report visible lake/snow/rock context only if imagery validity supports it; otherwise document which date windows remain obscured.
- First tests and a minimal browser page pass; no placeholder imagery presented as results.
- If no satisfactory pair is found, stop and document candidate scenes and reason; do not press ahead with generated data.

### User review
One screenshot of the proof viewer, scene-ID/date/valid-pixel summary and git/test report. Approval to proceed is based on data reality, not polish.

### Deliverables
`docs/M0_FEASIBILITY.md`, `docs/M0_HIMALAYAN_DATA_FEASIBILITY.md`, `docs/DESIGN_SPEC.md`, `data/manifests/m0_*.json`, reproducible retrieval command, initial scripts and tests.

---

## M1 — Reproducible raster-processing & temporal-change engine

### Objective
Build mathematically correct, composable, tested geospatial processing before pursuing visual effects.

### Implement
1. Scene scoring/selection, within-period compositing, cloud/shadow/invalid masks, observation count per pixel.
2. Configurable bounded AOI, target projected CRS, grid transform, alignment, resampling policy and caching.
3. NDVI, NDWI variant, MNDWI; ensure native band resolution and outputs' documented working resolution. Add **verified, gated** NDSI for selected cryosphere AOIs and NDBI as a *feature* for urban AOIs, with domain-specific mask policies.
4. Validity intersection and delta maps; compute area from projected geometry, with explicit map projection.
5. Summary charts: histogram, quantiles, valid area, change area vs threshold; no unsupported causal labels. Add event-relative dates, missing-data/terrain-shadow quality flags and literature-versus-own-measurement source badges where relevant.
6. Export raster COG/GeoTIFF, analysis manifest, PNG/WebP overlays with consistent color scales and mask visualization. Add `study_type`/`analysis_profile` to support ecology, hazard and urban methods without bogus cross-domain metric comparisons.
7. Implement local FastAPI endpoints or CLI commands for study metadata, imagery/layers, metric summaries and processing status.
8. Deterministic golden tests on toy rasters and at least one actual sampled window with known checksums.
9. Build caching and no-repeat download logic; record asset expiry and refetch behavior.
10. Run cross-check of area and alignment using an independent known geospatial operation.

### Acceptance / stop gate
- Matched before/after rasters have identical grid, CRS, transform, shape and valid-pixel semantics.
- Documented reflectance scaling verified, including correct SCL and NoData handling.
- NDVI correctness tests, area conservation checks and nearest-neighbor QA resampling tests pass.
- A real area/threshold change summary can be reproduced by rerunning scripts.
- Reproducibility manifest contains exact scene items, software versions, thresholds, hashes and output dates.

### User review
Actual before/after/delta outputs, sample table of verified metrics, tests, limitations. No design rework request yet.

### Deliverables
`docs/M1_SCIENCE_ENGINE.md`, `docs/SCIENCE_PROTOCOL.md`, CLI/API, cached processed outputs, unit/integration tests.

---

## M2 — Research experiments, evaluation & uncertainty

### Objective
Move from a map demo to an academically credible small-scale experiment.

### Implement
1. State specific hypotheses or operational questions, independent of results.
2. Implement threshold baseline and parameter sensitivity curves.
3. Build independent label-source audit: provenance, rights, spatial match, resolution, class definitions, label noise and sampling design.
4. If sufficient reference labels: train a Random Forest with documented features, class weights and spatial holdouts; record seeds and hyperparameters.
5. Ensure no geographic/time leakage from feature engineering, overlap, normalization or labels.
6. Add true holdout metrics and confusion matrix; assess class-specific performance.
7. Compare matched-season against deliberately mismatched-season or single-scene conditions where meaningful.
8. Evaluate cloud-validity sensitivity and threshold stability.
9. Optional Dynamic World model agreement only when GEE availability/registration is legitimately solved; never conflate agreement and independent accuracy.
10. For Kathmandu, include a negative-control evaluation on exposed soil/riverbeds and independent built-up references if available; otherwise produce only candidate built-up signal maps.
11. For 2025/2026 disaster cases, compare bounded internally observed changes against cited published evidence *as contextual triangulation*, not training-label truth by default. Do not run unsupported predictive hazard models or infer a 2026 InSAR deformation field from optical change maps.
12. Produce a concise research-style methods/results/limitations package with generated charts tied to actual run data.

### Acceptance / stop gate
- Method comparison can be reproduced from a frozen experiment config.
- All metric values trace back to actual arrays and independent labels, where applicable.
- Geographic train/test separation is automated and documented.
- If labels are insufficient, claim **no supervised accuracy result**, and ship a robust index-based empirical sensitivity study instead.
- Review critical numerical operations and evaluation protocol independently before advancing.

### User review
1–2-page scientific summary with exact hypotheses, data sources, tables, labels, limitations, and a list of what cannot be claimed.

### Deliverables
`docs/M2_EXPERIMENTS.md`, experiment configurations, metrics JSON/CSV, model card if trained, evaluation tests, plots.

---

## M3 — Complete product UX and signature visual design

*[M3 reconciliation, 7 Nov 2026: item 1 below says "The Field Atlas" identity. The executed identity is **Midnight Teal & Copper** (§7.1, `docs/DESIGN_SPEC.md`) — warm ivory background, Midnight Teal primary, Copper accent, Sea Glass secondary, editorial serif (Newsreader) + IBM Plex. Architecture decision for this milestone: `docs/architecture/M3_ARCHITECTURE_DECISION.md`.]*

### Objective
Transform the verified scientific pipeline into a uniquely designed, professional geospatial research workstation.

### Implement
1. Apply "The Field Atlas" identity: warm ivory, pine, clay, editorial serif + precise sans, cartographic details, accessible semantic colors.
2. Build polished asymmetric landing hero using **real cached satellite imagery**, with credible data captions.
3. Build consistent navigation, **five-site** study gallery, Methods, Results, Experiments, and Export entry points. Distinguish two Himalayan event timelines within one site.
4. Implement synchronized before/after MapLibre views, slider swipe and opacity, legends, map-scale/attribution.
5. Implement true-color, false-color, index, delta and valid/masked layers with accurate shared geospatial alignment.
6. Implement context side inspector (coordinate/pixel data, selected geometry, scene IDs, mask reason, numeric values).
7. Implement compact but rich bottom research dock for temporal scene strip, index distribution, thresholds and evaluation charts. The Himalayan mode gets event-relative source-area/downstream AOI switching, with external-evidence citations, rather than ecological-only graphics.
8. Make layer selection, synchronization, map controls, keyboard focus, reduced motion and responsive layout meaningful.
9. Use a single stable investigation state: date windows, region, map bounds, active layer, selected pixel/ROI, threshold and method.
10. Wire all interfaces to actual backend outputs or provenance-preserving static bundles; never put fabricated numbers in design placeholders.
11. Test on 1920/1440/1280/768/390 widths; check browser screenshots and interactions.

### Acceptance / stop gate
- Landing looks like editorial cartography, not a generic dark SaaS dashboard.
- Real study is viewable and analyzable within two user interactions from landing.
- Swipe reveals correctly georegistered images; pixels/coordinates stay aligned when panning and zooming.
- All map legends and mask semantics are visible and accurate.
- No huge blank panes, inaccessible controls, misleading placeholder charts, unexpected console errors or mobile overflow.
- End-to-end browser tests cover core actions.

### User review
Landing full screenshot, study gallery, workstation (three-layer states), before/after compare and mobile, plus short interaction video if agent tools actually support recording.

### Deliverables
`docs/M3_VISUAL_QA.md`, screenshots/evidence, functional web app, design-system components and frontend E2E tests.

---

## M4 — Five cross-domain studies, Himalayan event evidence & portable showcase

### Objective
Deliver a credible portfolio spanning **ecological change (three Indian sites), Himalayan cryospheric disaster evidence (one Nepal–Tibet site with two distinct events), and urban built-surface change (Kathmandu)**. Preserve a single trustworthy data/provenance engine with case-specific analysis methods.

### Delivery batches (checkpoints inside M4)

**M4a — Ecological foundation:** Finalize Coringa, Chilika and Western Ghats case bundles, or transparently documented and user-approved scientific replacements; validate dates, masks, indices, legends, and reports.

**M4b — Nepal–Tibet historical disaster evidence:**
1. Create a Himalayan event registry with **2025-07-08 Purepu lake drainage** and **2026-08-26 Langtang Lirung rock–ice collapse** as separate events.
2. Fetch/verify the best available pre/post Sentinel-2 scenes for each **small** source-area AOI; include a downstream AOI only where usable data exist.
3. Report cloud/terrain/no-data constraints, actual scene dates and time gaps. Permit an honest, marked limited-evidence result if monsoon cloud prevents defensible comparison.
4. For 2025, estimate optical lake-water extent with method/threshold sensitivity if valid; compare cautiously against the NDRRMA published source values as historical context, not silently adopted output.
5. For 2026, visualize measured candidate surface/ice/debris changes with terrain/cloud cautions. Keep ICIMOD's InSAR/deformation and UNOSAT's preliminary post-event extent in a distinctly attributed **external references** panel. No new flood prediction or exact damage valuation.
6. Build a two-event study switcher and source-vs-downstream region selector with properly scoped raster assets and linked provenance.

**M4c — Urban landscape:**
1. Establish Kathmandu 2020/2025 matched-season scenes, optional 2016 contextual observation where valid.
2. Produce NDBI/NDVI/water contextual layers and a **candidate** built-up-change map; run explicit bare-ground negative controls.
3. If independently verified labels suffice, produce a built-up classifier and spatially separated evaluation. If not, suppress accuracy/definitive urban-area claims and label outputs candidate only.
4. Provide an urban-focused inspector with measured reflectance/feature values and transparent ambiguity indicators.

**M4d — Portable showcase and cross-study navigation:**
1. Implement five distinct case cards with actual imagery-derived previews and exact metadata. The Himalayan card contains the two different event subviews.
2. Create compact static bundles from genuine pipeline outputs; include licensed public assets only, manifests and citations. Keep larger raw scenes in ignored local cache.
3. Browser-only Showcase Mode must load all **completed verified** studies with backend stopped. For any study blocked by unavailable imagery or scientifically weak evidence, show an explicit **not yet complete** card with transparent limitations; never simulate results.
4. Maintain locally processed Analysis Mode for bounded custom AOIs if stable. Do not mandate a worldwide feature.
5. Exports: PNG figures with date/scale/legend, CSV/JSON metrics, manifest and an HTML/PDF-ready report; include event-source bibliography and limitations.
6. Benchmark tile/asset sizes, loading performance and memory on the target laptop and on a free static host preview where permissible.

### Acceptance / stop gate
- All five site entries and both Himalayan event entries are present, correctly named, scoped and sourced. **Five scientifically completed case bundles** is the release target—not permission to invent missing imagery.
- Minimum full product success requires **both**: (a) at least three complete verified studies spanning more than one method domain; and (b) a *truthful* Himalayan study with real imagery or an explicitly blocked visibility assessment and linked primary evidence. Do not label a five-site release COMPLETE if any planned site lacks validated outputs.
- For any actual measured map, selected AOI/time window/bands/valid fraction/index/threshold/figure and source STAC item IDs all agree.
- 2025 GLOF-type drainage and 2026 non-conventional rock–ice collapse have **separate** explanatory text and never share a fabricated common causal mechanism.
- Static-only mode works without Python backend; no "live processing" claims in packaged demo.
- Kathmandu NDBI is never presented as unquestioned building ground truth; Himalayan affected-area overlay is never presented as project-derived if obtained from an outside assessment.
- Exports match on-screen selected case/events and the current methodology; all limitations and provider attributions visible.
- Every implemented study is reproducible from cached source data and documented commands; missing data produces a clear error.

### User review
Five study cards, both Himalayan event screens, urban built-up ambiguity view, case reports, screenshot of geographic/temporal map alignment, static-mode proof, and storage/build size summary.

### Deliverables
`docs/M4_CASE_STUDIES.md`, `docs/M4_HIMALAYAN_EVENT_EVIDENCE.md`, `docs/M4_KATHMANDU_URBAN_VALIDATION.md`, event registry, case manifests, static bundles, source bibliography, and updated public-ready README.

---

## M5 — Independent correctness audit, reliability, release and handoff

### Objective
Prove both the science and product are genuinely reliable enough for GitHub and a portfolio demo.

### Implement
1. Fresh local install instructions and reproducibility test on a clean venv/node_modules, or clean environment where practical.
2. Rerun full backend suite, frontend suite, static build and Playwright desktop/mobile journeys.
3. Independent spot-check of scene IDs, exact source dates, CRS, scale factors, masks, index formulas, area measurements, model labels, spatial split and output values.
4. Deliberate negative tests: missing STAC server, 429/rate-limit, corrupt GeoTIFF, all-cloudy observation window, invalid polygon, empty scene search, partial download and huge AOI.
5. Validate that all user-facing claims match measured data; remove unverified effects and fabricated stats.
6. Security review: bounded input, legal tile usage, remote URLs allowlisting, timeouts, path traversal, no secret leakage, localhost default, file safety.
7. Performance: five-site gallery and completed precomputed bundles boot reliably; prevent interactive map lockup, overlong processing, memory exhaustion or enormous commit assets.
8. Browser QA and visual review; repair alignment, overflow and interaction regressions without design reversion.
9. Create technical paper-style report: Abstract, Data, Methods, Experimental design, Results, Limitations, Reproducibility, References.
10. Document setup, usage, launch/stop/status, screenshots, data licenses, Git status/commit and final quality assessment.
11. Prepare Github push-ready repo and free static-host deployment instructions; **do not push or deploy without user approval**.

### Acceptance / release gate
- Science review PASS or explicit unresolved error list.
- All critical and high-severity app defects resolved; only documented acceptable limitations remain.
- Real-browser test reports with inspected screenshots; build works.
- No paid API or large backend needed for curated public showcase.
- Every figure/metric is traceable to original data with reproducibility controls.
- Clear independent limitation statement: preliminary research tool, not ecological ground truth or operational environmental monitoring service.

### User review
Final source/demo, 6–10 high-quality screenshots, test evidence, research report, Git commit and short CV/research-statement blurb based on actual validated achievements.

### Deliverables
`docs/M5_FINAL_AUDIT.md`, `docs/REPRODUCIBILITY.md`, `docs/RELEASE_CHECKLIST.md`, formal report, Git commit and static build.

---

# 10. Credit strategy for a 99-credit coding budget

**Important unknown:** The user saw one "hi" prompt consume one credit at Refuseless. That does **not** establish how intermediate agent tool turns, failed requests, retries, thinking tokens or context compaction are charged. The advertised model label should also be confirmed from provider/client metadata rather than assumed identical to an official DeepSeek release.

## Billing characterization before implementation

1. Record credit balance.
2. Run a bounded real test (list Python version, create one file, run one test in an empty workspace); record agent-visible messages, API requests if accessible and balance difference.
3. Run a second two-tool-call test; compare consumption. Stop if credits deplete per internal request more than expected.
4. Save a usage log in `docs/CREDIT_LEDGER.md`: stage, start/end balance, tool calls if measured, failure count and effectiveness.
5. Do not allow an unbounded self-retry loop, especially around downloads or browser permission failures.

**Provisional allocation IF one user/client turn truly costs one credit:** M0=12, M1=16, M2=17, M3=18, M4=22, M5=8, reserve=6 (total 99). This is planning guidance, not a promise of cost or sufficiency. If each agent turn is billed separately, revise before starting any autonomous stage.

## Agent operating strategy

- Use **one milestone at a time** in a fresh/controlled Cline task with references to roadmap, manifest and last stage report; avoid hundred-thousand-token conversations that duplicate source context.
- Agent may execute its milestone autonomously within permissions, but must stop on genuine data access/authentication/correctness blockers rather than fabricating substitutes.
- Each stage has a maximum bounded task budget/time/attempt policy set through client controls if supported; if unavailable, rely on explicit stop rules and credit monitoring.
- Minimize user supervision: report a screenshot + tests + manifest at each gate, rather than many trivial questions.
- Preserve original data and checkpoint commit; keep a known-good stage branch/tag before risky changes.
- Do not grant blanket unrestricted terminal permissions merely to avoid nighttime approval prompts.

---

# 11. Risk register and mitigation

| Risk | Severity | Mitigation / evidence required |
|---|---|---|
| STAC API unavailable/throttled | High | Retry bounded, alternate public catalog, cache exact items; never fabricate imagery |
| Low cloud-free overlap | High | Match season, composite multiple scenes, shift windows or change documented AOI |
| Inconsistent early Sentinel L2A availability | High | Prefer 2020+ initial years; per-scene check; Landsat for older years in later mode |
| 10m/20m band mismatch | High | Explicit grid resolution/resampling; record true native resolution; test |
| Misregistered images create false change | Critical | CRS/transform equality, co-registration checks, manual visual alignment, control points where possible |
| Seasonal or tidal differences misconstrued | Critical | Matched windows, caution flags, sensitivity analyses, no causation claims |
| Cloud/shadow false positives | High | SCL/QA masks, observation support counts, valid-footprint intersection, spot QA |
| Circular labels and random-pixel ML leakage | Critical | Independent labels, geographic split, label provenance; withhold accuracy claims if unavailable |
| Large raster downloads/disk fill | High | Small AOI, COG windowed requests, size budgets, cache quota, cancellation |
| Empty/sparse UI, generic AI styling | High | Written IA & style contract, screenshot gates, meaningful map interactions before polish |
| Map tile licensing/blocked tiles | Medium | Legal source, attribution, no OSM bulk prefetch, local overlays |
| Unsupported claims in app/report | Critical | Provenance-linked output contracts, scientific review, explicit distinctions |
| Paid provider or unexpected cloud costs | High | No required billing/cloud accounts; approval before charges |
| Agent hallucinates tests or completion | High | Save logs, source/output artifacts, actual browser evidence; independent audit |
| Himalayan monsoon optical gaps | High | Explicit 2025/2026 pre/post scene feasibility, exact window gaps, external evidence labeling; stop or disclose blocked results |
| Confusing two Nepal disasters | Critical | Two event IDs: July 2025 supraglacial-lake drainage versus Aug 2026 rock–ice collapse; independent citations and UI labels |
| Claiming glacier lake area = discharged flood volume | Critical | Lake area is 2D; no discharge, volume, flood-depth or casualty estimate from optical difference |
| Misreading InSAR / terrain shadow | Critical | InSAR evidence only as external literature unless separately validated; no before/after DEM inference from old DEM |
| Urban built-up false positives | High | Kathmandu bare soil/riverbed controls, ground/reference data, explicit NDBI is feature not label |
| Five-site workload exceeds credits/storage | High | M0 feasibility for all domains, M4 batches, scaled sub-AOIs, stage stop rules; honest incomplete labels |
| Agent hits provider credit limit | Medium | Stage gates, reserve budget, local checkpoint and reproducibility documents |

---

# 12. Product data model and contracts

At minimum create validated schemas for:

**StudyArea:** id, name, question, polygon GeoJSON, bounding box, display center, target sensor, seasons, `study_type` (coastal/wetland/forest/hazard/urban), supported analyses, display notes, limitations.

**ObservationWindow:** start/end window, exact acquired timestamps, relative days to event (where relevant), selected item IDs, product/processing version, cloud-valid pixel coverage, snow/terrain-shadow flags, composite method, mask profile, source URLs/license.

**RasterProduct:** study id, period id, layer (RGB/false-color/NDVI/NDWI/MNDWI/delta/mask/class), CRS, transform, width/height, native vs display resolution, NoData semantics, valid mask, tiled asset path/URL, checksum.

**AnalysisResult:** matched footprint, pixel area/units, period values and differences, thresholds, index definition, observations per pixel, valid-area fraction, uncertainty flags and method version.

**ExperimentRun:** config+seed, source and labels, feature list, split polygons, metrics, confusion matrix, ablations, artifacts, environment versions, independent-label boolean.

**HazardEvent:** event ID, exact historical date, name, `hazard_type` (2025 lake drainage / 2026 rock–ice collapse), source/subregion AOIs, evidence references, temporal windows, externally reported claims with publication dates, unresolved questions and cannot-infer list.

**ReferenceAssessment:** source publisher, published date, product ID/DOI/URL, mapped phenomena, spatial/temporal extent, license, source certainty, optional reference geometry, and a **strict external-not-our-computation** flag.

**DomainAnalysisProfile:** study type, indices allowed, target classes, QA snow/mask policy, confusion classes, valid measurement types and forbidden inference rules.

**ProvenanceManifest:** study, data access date, STAC item IDs, asset stable locator, license and attribution, processing steps, code commit, package lock, generated artifact hashes.

**UI state:** active study, time windows, layer, compare mode, map bounds, clicked pixel/geometry, index threshold, method, active finding, selected experiment.

Important: every visible user metric must come from `AnalysisResult`/`ExperimentRun` and link to a `ProvenanceManifest`. No hardcoded outcome numbers in frontend components.

---

# 13. Testing matrix and non-negotiable integrity checks

## Numerical unit tests
- Known NDVI/NDWI/MNDWI values including zero denominators and NoData.
- Reflectance scaling and offsets for each chosen sensor/product.
- QA mask classes and categorical resampling.
- Grid alignment and CRS transformation.
- Constant-image identity: no artificial change where paired arrays are equal.
- Known controlled change raster gives correct per-cell delta, threshold counts and area.
- Valid-mask intersection ensures sample denominators match.
- Area computed in suitable projected grid and correctly converted m² ↔ ha ↔ km².

## Integration tests
- Real fixture STAC metadata persists and can replay from cache offline.
- Two aligned observation periods produce stable manifest and artifacts.
- Failed/empty/out-of-date assets lead to explicit error and no result substitution.
- Static bundle corresponds to the backend's actual calculated outputs.

## Research tests
- No spatial overlap across train/test.
- No use of evaluation labels to select/change thresholds without appropriate validation set.
- Metric recomputation independently matches stored metrics.
- Scene/label dates match the documented experiment and no label leakage.
- 2025 versus 2026 Himalayan event IDs and mechanisms remain distinct under serialization, exports and user-visible text.
- No 2026 ice volume, early-warning skill, flood depth, casualty counts or InSAR deformation field invented from simple reflectance differencing.
- Kathmandu built-up sensitivity includes bare-soil negative controls; no accuracy claim without independently sourced held-out labels.
- Ablation reports full configurations, sample counts and holdout differences.

## Browser tests
- Landing CTA opens actual study.
- Five study entries and two separate Himalayan event investigations are selectable; the UI exposes genuine loading/blocked states for missing scientific data.
- Event tab switches update correct real dates/AOI, citation panel and mask limits; urban tabs do not show irrelevant glacier indices.
- Switch site and periods without stale imagery.
- Before/after maps remain synchronized in position and scale.
- Swipe/opacity reveals different *registered* raster layers.
- Legend, mask, band index, provenance and sample-pixel inspector update correctly.
- Threshold change updates computed statistics, not just marker display.
- Static-showcase works without backend; analysis mode explains missing backend.
- Export contains correct current study and data references.
- Mouse/touch/keyboard controls, mobile drawer, no console errors/overflow.

## Scientific red flags that block release
- Manually painted differences not generated from numerical raster values.
- Different spatial grids compared without alignment.
- "Annual" change inferred from arbitrary unrelated single-date pictures.
- A July 2025 Purepu lake-drainage map described as if it depicted the August 2026 Langtang Lirung rock–ice collapse.
- Ice/rock volume, flood depth or disaster prediction implied by a reflectance difference map.
- NDBI-only bright pixels represented as verified Kathmandu buildings or dated construction.
- Seasonal vegetation change labeled as verified permanent land-cover loss.
- Landsat upsampling portrayed as true 10 m measurement.
- Dynamic World or WorldCover treated as infallible independent ground truth.
- Model performance measured with neighboring pixels randomly split across train/test.
- Confidence scores, area figures or accuracy percentages written by the agent without saved run artifacts.

---

# 14. Demo walkthrough, personal motivation & portfolio narrative

## 14.1 The authentic motivation

**Respectful one-sentence origin story (suggested):**

> "The cross-border Himalayan disasters of 2025 and 2026 made me interested in how openly accessible satellite data can help people examine landscape changes and understand what can—and cannot—be concluded from remote observations. HabitatShift grew from that question."

This is a motivation for the project, **not** a claim that the software could have forecast or prevented either event. Do not present death toll figures without dated authoritative sourcing, and prefer an evidence-centered account over a sensationalized hero.

## 14.2 90-second showcase path

1. Open warm editorial cartographic landing hero containing **real processed imagery** from a completed case study and a short origin-story link.
2. Select **Himalayan Evidence**, then **2025 · Lake drainage**. Show real pre/post observation dates, cloud masks, and source-region lake extent if defensible; mention NDRRMA's independently published report separately from our measurement.
3. Switch to **2026 · Rock–ice collapse**. Show a real limited/validated before-and-after source or corridor comparison, and link ICIMOD's finding that the disaster was **not a conventional GLOF**. Demonstrate uncertainty and scene-coverage flags; never claim predictive warnings.
4. Switch to **Kathmandu Urban Change**. Show matched-season imagery, candidate built-up features and exposed-soil caveats—proving the platform is not just a vegetation calculator.
5. Open **Coringa** or **Chilika**. Swipe synchronized imagery and inspect NDVI/MNDWI measurements with a clicked coordinate and provenance.
6. Open Methods / Experiments and compare reproducible baseline to validated ML **only where independent labels exist**.
7. Open research report, showing STAC acquisition IDs, formulas, event/background bibliography, quality masks and reproducibility manifest.

**Interview talking points:** STAC/COG, CRS and reprojection, multisensor dates, cloud and terrain limitations, lake-water segmentation, hazard-event source separation, spectral index pitfalls, urban exposed-soil confounding, geospatial ML leakage, dataset validation and provenance.

**Publication threshold:** A reproducible method, testable question, suitable independent labels or authoritative external validation, and convincing comparison may support future research discussion. A pretty before/after plus literature references alone do not constitute a publishable novel result.

---

# 15. Future M6: globe-wide exploration / last 10–20 years

**Answer:** A whole-world globe **viewer** is feasible with MapLibre globe rendering or another WebGL mapping framework. A whole-world, arbitrary-ROI, 20-year, instant high-resolution **analysis service** is a different engineering and cost problem.

A realistic later system would:

1. Render a globe/world map using licensed and properly attributed basemaps.
2. Let the user select a **strictly bounded polygon** (e.g., initially ≤25–100 km²) and dates.
3. Query Sentinel-2 STAC for recent years or Landsat STAC for ~20+ years, with cross-sensor rules.
4. Show honest scene availability and quality before accepting a processing job.
5. Execute *bounded on-demand cloud-read/local processing*, or use a paid/eligible compute provider after explicit user choice.
6. Cache results keyed by AOI, sensor, time, process version and mask settings.
7. Queue jobs, impose size/concurrency/timeout limits, report real progress and retry errors.
8. Display native resolution and provenance accurately; provide harmonized coarse-grid comparison for cross-sensor use.

**Staged global expansion:** (a) global scene discovery; (b) bounded per-AOI processing; (c) multi-year time series; (d) scalable hosted jobs, authentication and quota governance if users appear.

**Never claim:** 20 years of Sentinel-2 native 10m observations everywhere. Sentinel-2 does not cover that whole interval; Landsat is a different 30m source. Global metadata viewing is not global free compute.

---

# 16. Sources, documentation & compliance references

Access dates: checked during roadmap preparation, 4 November 2026. Recheck live URLs and terms at implementation time.

1. Element 84 Earth Search STAC — https://element84.com/earth-search and https://earth-search.aws.element84.com/v1
2. Earth Search repository and terms — https://github.com/Element84/earth-search
3. AWS Sentinel-2 L2A COG open dataset — https://registry.opendata.aws/sentinel-2-l2a-cogs/
4. Copernicus Sentinel-2 data/products — https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2
5. Copernicus Sentinel-2 L2A details — https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel2.html
6. Sentinel-2 SCL/band semantics — https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html
7. USGS Landsat Collection 2 — https://www.usgs.gov/landsat-missions/landsat-collection-2
8. USGS Level-2 reflectance scaling — https://www.usgs.gov/faqs/how-do-i-use-a-scale-factor-landsat-level-2-science-products
9. Dynamic World dataset — https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1
10. Google Earth Engine noncommercial access requirements — https://developers.google.com/earth-engine/guides/access
11. ESA WorldCover data and version differences — https://esa-worldcover.org/en/data-access
12. MapLibre GL JS — https://maplibre.org/maplibre-gl-js/docs/
13. OpenStreetMap tile usage policy — https://operations.osmfoundation.org/policies/tiles/
14. TiTiler ecosystem — https://developmentseed.org/titiler/
15. Copernicus Sentinel source attribution/license — https://cds.climate.copernicus.eu/licences/ec-sentinel

---

## 16.1 New event and urban study references (verified 4 November 2026)

16. Government of Nepal NDRRMA, *Rasuwa Glacial Flood Situation Report #1* (10 July 2025): https://ndrrma.gov.np/mediafiles/publications/Rasuwagadhi_Flood_Sitrep1_08072025_.pdf
17. ICIMOD (13 Oct 2026), *Understanding the Gyirong–Rasuwa disaster of 26 August 2026: A preliminary synthesis*: https://lib.icimod.org/records/r745z-mvm84
18. ICIMOD press release (13 Oct 2026), two Himalayan events and Sentinel-1 InSAR external evidence: https://www.icimod.org/press-releases/second-major-himalayan-flood-in-seven-weeks-raises-new-questions-about-mountain-risk/
19. ESA (31 Aug 2026), *Nepal flash flood imaged by satellites*: https://www.esa.int/Applications/Observing_the_Earth/Copernicus/Sentinel-2/Nepal_flash_flood_imaged_by_satellites
20. UNOSAT (28 Aug 2026), preliminary Rasuwa/Nuwakot impact mapping, product 4259: https://unosat.org/products/4259/
21. Copernicus Sentinel-1 data: https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-1
22. Copernicus DEM public AWS access, licensing and coverage cautions: https://registry.opendata.aws/copernicus-dem/
23. Copernicus 2026 GLO-30 View Service access changes: https://dataspace.copernicus.eu/news/2026-8-25-copernicus-dem-30m-view-service-update
24. Randolph Glacier Inventory, RGI 7.0 outlines: https://rgidata.org/
25. GLIMS glacier inventory: https://www.gtn-g.ch/data_catalogue_glims/
26. Kathmandu urban mapping and documented bare-soil confusion: https://www.mdpi.com/2072-4292/11/19/2296

**Evidence rule:** Any numeric event fact quoted from these sources must be tied to the source's own reporting date and geographic scope. Do not quietly merge estimates from different reports; published figures are not output from HabitatShift. External datasets and report maps need license/rights checks before repackaging.

---

# 17. First execution instruction (when the user starts development)

**Do not execute M0–M5 by pasting this entire roadmap as one demand to finish everything in a single Cline turn.** This is the governing specification. Begin with a separate, tightly scoped M0 prompt referencing this file and its criteria. Proceed to M1 only after M0 evidence is reviewed.

Suggested M0 opening instruction:

> Read the latest roadmap (`HabitatShift_Master_Roadmap_v1.1.md`, or `HabitatShift_Master_Roadmap.md` if saved under that canonical name) in full. You are implementing **M0 only** in a new HabitatShift repo. First prove genuine, multi-date Sentinel-2 L2A acquisition for one bounded non-disaster study area using a documented STAC API, save exact scene IDs and a reproducible manifest, calculate a valid NDVI sample on aligned/QA-masked real imagery. **Also perform two bounded Himalayan source-area scene-availability searches around 8 July 2025 and 26 August 2026, capture real scene dates and optical-visibility limits without inventing before/after damage maps**, plus a Kathmandu 2020/2025 availability check. Create a minimal proof viewer and tests, then stop with an honest M0 gate report. Do not build the final landing page or claim ML results yet. Respect scoped local permissions and do not fabricate satellite data. Create a Git checkpoint and report commands, artifacts, tests, cost/size and blockers.

**Success criterion:** at the end of M0, the project possesses **real, traced, aligned satellite evidence** for one core site plus an honest Nepal-event/Kathmandu feasibility report. At the end of M5, the goal is a visually exceptional, reproducible **five-site cross-domain atlas**; missing cloud-free scenes remain transparently incomplete rather than fictional.

---

# 18. Revision log — v1.1 (4 November 2026)

- Upgraded V1 from three India-only sites to **five study areas** across India and Nepal/Tibet, plus two distinct Himalayan disaster event views.
- Added **8 July 2025 Purepu supraglacial-lake drainage** and **26 August 2026 Langtang Lirung rock–ice collapse** as different case histories, aligned with Nepal NDRRMA and ICIMOD/ESA/UNOSAT published sources.
- Added **Kathmandu Valley urban expansion**, distinct validation and NDBI/bare-soil pitfalls.
- Added per-domain algorithms, evidence/provenance contracts and safeguards against made-up glacier volume, flood prediction, unverified infrastructure damage or urban classifier scores.
- Expanded M0 early availability checks, M1/M2 methods, M3 study-type UI and M4 five-site staged delivery; preserved the six-gate M0–M5 structure and optional worldwide M6.
- Retained **The Field Atlas** warm cartographic UI concept; added a respectful Nepal-specific origin story and event evidence navigation.
- Revised provisional 99-credit budget, acceptance criteria, risks and browser tests.

*End of revised roadmap.*
