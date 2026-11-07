# M2 — Independent label feasibility audit

**Study:** `coringa_coastal` (Coringa / Godavari delta, Andhra Pradesh)
**Periods:** earlier 2020-03 window, later 2025-03 window, Sentinel-2 L2A, 10 m grid EPSG:32644
**Question for this audit:** can genuinely independent reference labels be
obtained and validated for supervised evaluation (Part E of the M2 plan), or
must the supervised path remain blocked?

**Verdict: BLOCKED for change evaluation.** No candidate source provides
labels that are simultaneously (a) independent of our index-threshold
pipeline, (b) temporally valid for the 2025 period, and (c) geometrically and
semantically compatible with a 10 m change study. A supervised Random Forest
accuracy number for *change* cannot be produced honestly in M2, so none is
reported. This follows the required fallback (Part E4): the baseline
experiments stand on their own and the ML interface is documented, not faked.

---

## 1. What an admissible label source must satisfy

For the M2 study to claim supervised evaluation, labels must:

| Requirement | Why |
|---|---|
| Independent of the candidate models | Labels derived from an NDVI/NDWI/MNDWI threshold would benchmark the threshold against itself (circularity). |
| Cover the later (2025) period for change evaluation | Change labels must exist in both periods; a 2020-only label set can at most support single-date presence modelling. |
| Geometry compatible with the 429 × 390 @ 10 m grid | Coarser labels force resampling that dominates pixel-level agreement. |
| Licence permits research use and redistribution of derived artefacts | Manifest and evidence screenshots must be publishable. |
| Documented class definitions and known quality | So per-class precision/recall means something. |
| Spatially referenceable sampling design | Needed for spatially separated train/test splits without leakage. |

## 2. Candidate sources examined

### 2.1 ESA WorldCover — **rejected for this study**
- Versions: **WorldCover 2020 (v100)** and **WorldCover 2021 (v200)** only.
  No epoch exists for 2022–2025.
- v200 is an improved algorithm, so v100 vs v200 differences conflate
  algorithm change with land-cover change; neither version covers 2025.
- Validated overall accuracy ≈ 75% (v100) with class-dependent errors;
  mangrove/tree classes are among the weaker ones in coastal mosaics.
- Even the 2021 product leaves a 4-year gap to our 2025 imagery; using it as
  "truth" for 2025 assumes the very persistence the study is trying to test.
- Verdict: usable as *context* only; not admissible as independent change
  ground truth.

### 2.2 Dynamic World (Google) — **rejected as ground truth**
- Model-generated near-real-time probabilities, not observations. Agreement
  with another classifier (ours) is not independent accuracy.
- Roadmap M2 item 9 allows "Dynamic World model agreement only when GEE
  availability/registration is legitimately solved" — and explicitly forbids
  conflating agreement with accuracy. GEE access is not solved in this
  environment, so even the agreement comparison cannot be produced in M2.

### 2.3 Global Mangrove Watch (GMW) — **the closest candidate; still insufficient**
- GMW v3.0 (Bunting et al. 2022, Zenodo record 6894273) provides annual
  mangrove-presence rasters 1996–2020 at ~25–30 m nominal resolution, CC-BY
  4.0, estimated accuracy ≈ 87.4% (95% CI 86.2–88.6%).
- A newer platform layer claims epochs beyond 2020, but it is not an
  archived, versioned, citable product with documented accuracy; building a
  benchmark on it would violate the provenance requirements.
- Even the 2020 epoch offers only **binary mangrove presence for the earlier
  period**: no water class, no 2025 epoch, 25 m resolution (2.5× coarser than
  the analysis grid), and accuracy that already saturates below what a
  change-evaluation claim would need.
- A single-period RF presence classifier trained on GMW 2020 would be
  feasible in a later milestone, but it validates *presence mapping*, not
  *change detection*, and cannot validate any M2 threshold.

### 2.4 National / regional Indian datasets
- Bhuvan LULC (NRSC) is 1:50k-scale vector mapping at 56 m/15 m epochs with
  class schemes that do not separate mangrove sub-classes reliably; licence
  and redistribution terms are restrictive; no 2025 epoch.
- No state-level 10 m mangrove inventory with open licensing was found.

### 2.5 Hand-digitised local labels — **rejected for M2**
- Digitising polygons over the *same Sentinel-2 imagery* the models use makes
  the labels non-independent by construction (same sensor, same masking, and
  the analyst sees the index patterns).
- One small AOI cannot support spatially separated train/val/test regions of
  the kind Part E3 requires.

## 3. Consequences for M2

1. **No supervised accuracy result is claimed anywhere in M2.** The result
   JSON contains no accuracy/F1/confusion-matrix keys, and a test asserts
   that stays true.
2. The experiment config records `labels.status: blocked` with an empty
   `labels.paths`; the runner never silently substitutes a proxy label set.
3. The research package consists of the threshold-sensitivity study, the
   estimator comparison, and the measured uncertainty analysis — all of which
   need no labels.
4. **What would unblock supervised evaluation** (future milestones):
   - an independent 2025-era label product with documented accuracy and
     licence (e.g., a future WorldCover-style epoch, or a validated national
     inventory), or
   - a field/campaign label set for the AOI with a documented sampling
     design, or
   - at minimum: GMW-based single-period presence labels plus a *separate*
     change-reference source for the 2025 period.
5. Until then, cross-site transfer and ML benchmarking stay out of scope, as
   Part E3 requires for a single small labelled region.

## 4. Sources consulted

- ESA WorldCover product pages and data access (esa-worldcover.org; GEE
  catalogue entries `ESA/WorldCover/v100`, `ESA/WorldCover/v200`).
- Zanaga et al. 2022 (WorldCover v200) and Tsendbazar et al. 2021 (v100
  validation).
- Bunting et al. 2022, *Global Mangrove Extent Change 1996–2020*, Remote
  Sensing; GMW v3.0 archive (Zenodo record 6894273); GEE community catalog
  GMW entry.
- Dynamic World documentation (Google, `GOOGLE/DYNAMICWORLD/V1`).
