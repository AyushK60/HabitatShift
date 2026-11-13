# M5-G2 — Machine-learning label feasibility

**Status:** complete. **Method:** every candidate reference source was
probed live (windowed COG reads over each study's actual AOI), not assumed.
Measured class coverage per AOI is recorded below. **Decisions: PASS for
Kathmandu (multi-class), Western Ghats (binary forest/vegetation), Chilika
(binary water/land); PARTIAL for Coringa; BLOCKED for both Himalayan
investigations.**

## 0. Framing — what "reference labels" mean here

The only class inventories with full spatial coverage of the study AOIs are
themselves **products of other classification systems** (ESA WorldCover,
Global Mangrove Watch). They are authoritative, widely used, and documented,
but they are **not independent ground truth**: their own methodologies have
error structures of the same kind as anything we would train. Consequently:

- Every supervised experiment in M5 is framed as **agreement with a named
  reference product**, never as accuracy against ground truth.
- Confusion matrices, per-class precision/recall/F1, macro-F1, balanced
  accuracy and IoU are computed against **held-out reference labels from
  geographically separated blocks** of the same product — this measures
  how reproducibly the classifier reproduces the reference, nothing more.
- Where the reference disagrees with the physical evidence (e.g. Coringa
  mangrove extent below), the disagreement is recorded, not resolved by
  picking whichever agrees.
- Dynamic World was evaluated and **excluded as a label source**: it is a
  near-real-time model output with per-pixel probabilities, i.e. agreement
  with it would be model-to-model agreement twice over.

## 1. Reference sources investigated

| Source | Version / epoch | Resolution | Coverage | Licensing | Measured access |
|---|---|---|---|---|---|
| **ESA WorldCover** v200 | 2021 epoch (S2 2021 composites) | 10 m, EPSG:4326, 3°×3° COG tiles | Global | CC-BY 4.0 (`© ESA WorldCover project 2022`); attribution required | **Live windowed reads verified** over every AOI (`esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/…`) |
| **Global Mangrove Watch** v3.0 | 11 epochs 1996–2020 (2020 used) | 10 m, EPSG:4326, 1° COG tiles (NxxEyy naming) | Global mangrove latitudes | CC-BY 4.0 (Bunting et al. 2022) | **Live windowed reads verified** at Coringa via the NASA MAAP STAC catalog (`s3://nasa-maap-data-store/…/GMW_N17E082_2020_v3.tif`) |
| JRC Global Surface Water | v1.4/v1.5 (to 2021/2024) | 30 m | Global | CC-BY 4.0 | Considered and preferred for water labels in principle (observation-based), but **no working download endpoint could be established during the feasibility window** (404 on all documented URL patterns). Chilika water labels therefore use WorldCover classes 80/90 instead; GSW remains a recommended future upgrade and is recorded here honestly. |
| Dynamic World | near-real-time | 10 m | Global | CC-BY 4.0 | **Excluded as labels** (model output, not reference). Could serve only as an external comparison product. |
| Independently interpreted reference imagery | — | — | — | — | Evaluated as the only route to *true* independent labels. Rejected for M5: a defensible interpreted sample requires trained human analysts and a documented QA protocol; manufacturing a small AI-interpreted sample would not survive review and would manufacture precisely the independence the protocol forbids claiming. |

### Known limitations carried into every experiment

- **Reference-product error:** WorldCover's own stated accuracies vary by
  class (built-up higher; cropland/grassland lower); we inherit exactly that
  error structure as our label noise.
- **Temporal mismatch to application epochs:** labels are the 2021 epoch.
  The M5 design (§3) trains on 2021-epoch Sentinel-2 imagery fetched at the
  same AOIs, then applies the frozen classifier to the existing 2020 and
  2025 composites. Class definitions are fixed; the assumption that class
  spectra are stable across 2020→2021→2025 (sensor S2A/B/C, Sen2Cor
  versions) is a **documented limitation**, not a verified fact.
- **Resolution:** labels native 10 m; SWIR features are native 20 m upsampled
  on the 10 m grid — no misleading "native 10 m SWIR" claims (the index
  registry's existing `native_resolution_m` convention is reused verbatim).

## 2. Measured label coverage per AOI (live reads, pixel counts)

Class codes are WorldCover v200: 10 tree, 20 shrub, 30 grass, 40 cropland,
50 built-up, 60 bare, 70 snow/ice, 80 permanent water, 90 herbaceous wetland,
95 mangrove.

| AOI | Measured histogram (AOI window) | Interpretation |
|---|---|---|
| **Kathmandu** (85.305–85.325 E, 27.695–27.715 N) | 50 built-up 50 374 · 40 cropland 2 849 · 30 grass 1 745 · 10 tree 1 611 · 60 bare 751 · 80 water 270 (57 600 px) | All four target classes present. Built-up dominates (87.5 %) — imbalance documented; water is rare (0.5 %) and retained with explicit uncertainty. |
| **Western Ghats** (74.33–74.38 E, 15.13–15.17 N) | 10 tree 275 716 · 30 grass 10 486 · 40 cropland 1 798 (288 000 px) | Binary forest/vegetation vs other is feasible; ~96 % tree — imbalance documented. |
| **Coringa** (82.245–82.285 E, 16.71–16.745 N) | 40 cropland 111 128 · 10 tree 49 885 · 80 water 25 460 · 90 wetland 4 650 · 50 built-up 4 362 · 95 mangrove 284 · … (193 090 px) | Vegetation/water classes fine. Mangrove extent is **thin and source-disagreeing**: WorldCover 95 = 284 px in-AOI, while GMW 2020 = **13 px** in the same window (GMW shows 267 120 mangrove px in the surrounding 0.35° window — the mangroves sit largely outside/north of the AOI). Verdict PARTIAL: no mangrove-supervised experiment; vegetation/water experiment permitted with the disagreement recorded. |
| **Chilika** (85.3–85.36 E, 19.69–19.74 N) | 80 water 418 978 · 40 cropland 9 967 · 90 wetland 3 055 (432 000 px) | Binary water/land feasible; 97 % water — imbalance documented, minority land class retained with uncertainty. |
| **Purepu** (Himalaya 2025) | 60 bare 51 375 · 70 snow/ice 96 781 · 80 water 1 794 · 30 grass 14 · 100 moss/lichen 1 236 | Labels exist but see verdict below — BLOCKED by design. |
| **Langtang** (Himalaya 2026) | 70 snow/ice 145 091 · 60 bare 22 638 · 100 moss/lichen 8 063 · 30 grass 426 · 80 water 182 | Same — BLOCKED by design. |

## 3. Decisions

| Investigation | Verdict | Supervised experiment (if any) |
|---|---|---|
| **Kathmandu Valley** | **PASS** | Multi-class Random Forest: built-up / vegetation (10+30+40) / bare (60) / water (80), trained on 2021-epoch imagery at the same AOI, spatially blocked train/val/test; metrics framed as agreement with WorldCover. This directly complements the NDBI change experiment (built-up confusion was a recorded M4 interpretation theme). |
| **Western Ghats** | **PASS** | Binary Random Forest: forest/vegetation (10+30) vs other, same design; complements the NDVI/NDWI change experiment (deforestation is the recorded candidate signal). |
| **Coringa** | **PARTIAL** | Binary vegetation/water Random Forest permitted. **No mangrove-supervised experiment**: the two authoritative mangrove inventories disagree within the AOI (WC 95 = 284 px vs GMW 2020 = 13 px), so no mangrove labels are manufactured and GMW 2020 is carried as a recorded external reference overlay only. The mathematical analysis (NDVI/NDWI/MNDWI change + M2 experiments) remains the Coringa evidence. |
| **Chilika** | **PASS** | Binary water/land Random Forest, same design; complements the NDWI/MNDWI water experiments (the M4 "water-to-land flip" incident showed exactly why an independent-ish water reference is valuable). |
| **Purepu (Himalaya 2025)** | **BLOCKED** | Per protocol: Himalayan investigations stay on their scientific questions (glacier-lake / snow-ice change). No land-cover classifier is forced onto them; labels exist but would add no defensible information and would invite class-name overreach on PARTIAL-evidence imagery. |
| **Langtang (Himalaya 2026)** | **BLOCKED** | Same, plus the study's recorded optical-only/seasonal limitations. |

## 4. Consequences for M5-G3

- Supervised Random Forests are implemented for **Kathmandu, Western Ghats,
  Chilika**, and **Coringa (vegetation/water only)**.
- Training imagery is **fetched at the 2021 label epoch** through the existing
  engine (new M5 manifests; frozen M4 outputs untouched).
- Every reported metric is labelled "agreement with <reference product>",
  with class imbalance, reference-error inheritance and the cross-epoch
  application assumption recorded in `M5_LIMITATIONS.md`.
- If any experiment's held-out reference labels prove insufficient (e.g. a
  class with < 100 test pixels), its metrics are **not reported**; the
  experiment is downgraded and recorded, never dressed up.
