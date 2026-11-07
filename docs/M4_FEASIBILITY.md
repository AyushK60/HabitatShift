# M4 data feasibility — five studies, six investigations

**What this document is.** The M4-G0 gate deliverable: a recorded data-feasibility
decision for every investigation before any bulk processing. It contains no
estimated change values and no invented scenes. Every item ID, date, cloud
figure and in-AOI valid fraction was produced by the existing probe tools
(`scripts/probe_catalog.py --measure`, `scripts/probe_event_feasibility.py`)
against the Element 84 Earth Search `sentinel-2-l2a` catalogue, plus one
`cop-dem-glo-30` availability query for terrain context.

**Measurement policy (unchanged from M0).** A candidate counts as *usable* only
when its footprint fully covers the AOI **and** the measured in-AOI SCL valid
fraction (masking classes 0, 1, 3, 8, 9, 10) is at least 0.60. Probed
2026-11-07 on branch `m4-studies`.

> **Attribution.** Contains modified Copernicus Sentinel data, processed by ESA;
> L2A distributed via the Element 84 Earth Search STAC catalogue (AWS Open Data).
> DEM: Copernicus DEM GLO-30 (© ESA/DLR, via the same catalogue).

## Decision summary

| # | Investigation | Verdict | Basis |
|---|---|---|---|
| A | Coringa / Godavari delta (reference) | **PASS (existing)** | M0/M1/M2 outputs frozen; re-processed never |
| B | Chilika Lake — matched dry-season | **PASS** | Many 100 %-valid observations in both windows |
| B | Chilika Lake — seasonal sensitivity | **PASS** | Fully valid post-monsoon observations in both years |
| C | Western Ghats (Supa taluk, Kali basin) | **PASS** | Rich matched dry-season pairs both years; DEM available |
| D1 | Purepu supraglacial-lake drainage | **PARTIAL** | No clean immediate post-event pass; only same-day 63 % valid + post-monsoon |
| D2 | Langtang Lirung rock–ice collapse | **PASS (constrained)** | Usable pair exists: −14 d / +33 d, with monsoon caveats |
| E | Kathmandu Valley built-up signal | **PASS (interpretation-limited)** | Near-exact seasonal match; no independent labels → candidate signal only |

Nothing is BLOCKED. D1 is PARTIAL and will be presented as evidence-under-constraint.

---

## A — Coringa / Godavari delta (reference study)

Status: processed (M0), reproduced (M1), experimentally characterised (M2).
Existing periods 2020-03-26 → 2025-03-25, indices NDVI/NDWI/MNDWI, threshold
sensitivity, estimator comparison, block-bootstrap uncertainty. **M4 action:**
no reprocessing, no overwrite of existing runs; Coringa becomes the reference
case that validates the new bundle architecture and interactive charts.

## B — Chilika Lake, Odisha (AOI 85.30–85.36 E, 19.69–19.74 N; MGRS tile 45QUB)

Window location: southern lagoon sector near Satapada / Krushna Prasad, Puri
district (reverse-geocoded). The AOI deliberately straddles the open-water /
barrier / mudflat transition, which is where the study question lives.
AOI area 33.7 km².

Candidate observations (probe output, usable only):

- Dry season 2020 (2020-01-01 → 2020-03-31): 24+ usable items, 26 at or near
  100 % in-AOI validity, e.g. `S2B_45QUB_20200217_0_L2A` (valid 0.998),
  `S2B_45QUB_20200227_1_L2A` (1.000), `S2A_45QUB_20200313_0_L2A` (1.000).
- Dry season 2025 (2025-01-01 → 2025-03-31): 19+ usable items, e.g.
  `S2B_45QUB_20250210_0_L2A`, `S2B_45QUB_20250302_0_L2A`,
  `S2C_45QUB_20250215_0_L2A`, `S2B_45QUB_20250220_0_L2A` (all 0.99–1.00).
- Post-monsoon 2020 (2020-10-01 → 2020-12-31): fully valid items e.g.
  `S2A_45QUB_20201108_1_L2A`, `S2A_45QUB_20201208_1_L2A`, `S2B_45QUB_20201213_1_L2A`.
- Post-monsoon 2025 (2025-10-01 → 2025-12-31): fully valid items e.g.
  `S2B_45QUB_20251117_1_L2A`, `S2A_45QUB_20251114_1_L2A`, `S2B_45QUB_20251127_0_L2A`.

**Recommended experiments (both matched-season):**

1. `chilika_m4_dry` — dry-season composite pair: earlier anchor 2020-02-17,
   later anchor 2025-02-15 (day-of-year gap ≈ 2 days). Indices NDWI, MNDWI (+NDVI).
2. `chilika_m4_postmonsoon` — post-monsoon pair: earlier anchor 2020-11-08,
   later anchor 2025-11-17 (day-of-year gap ≈ 9 days). Same indices.

The two experiments *together* form the seasonal-sensitivity investigation: the
difference between dry-season and post-monsoon water-extent signals **within**
the same years bounds how much of the 2020→2025 change could be seasonal.
Seasonal amplitude is expected to dominate; results will be presented
accordingly. Risks: turbidity fronts shift NDWI/MNDWI values; open-ocean
waves/wind; shallow mixed pixels along the barrier. No hydrological-causation
claims.

## C — Western Ghats forest landscape (AOI 74.33–74.38 E, 15.13–15.17 N; tile 43PDS)

**AOI selection rationale (not arbitrary).** The window lies in Supa taluk,
Uttara Kannada district, Karnataka (reverse-geocoded) — a forested block of the
Kali River basin in the central Western Ghats. Selection criteria and how each
was met: historical imagery (dozens of fully valid dry-season scenes in 2020);
recent imagery (dozens in 2025, including S2C); cloud suitability (dry-season
in-AOI validity 1.000 on many dates in both years); geographic relevance
(high-rainfall evergreen/semi-evergreen forest landscape, strong terrain);
suitable comparison periods (matched dry season minimises phenology gaps);
processing feasibility (bounded 23.8 km² window, tile 43PDS consistently
delivered). Copernicus GLO-30 DEM is catalogued over the window
(`Copernicus_DSM_COG_10_N15_00_E074_00_DEM`).

Candidate observations (usable, examples):

- 2020 (2020-01-01 → 2020-04-30): `S2B_43PDS_20200219_0/1_L2A` (valid 1.000),
  `S2A_43PDS_20200125_0/1_L2A`, `S2A_43PDS_20200315_1_L2A`, `S2B_43PDS_20200330_0/1_L2A` —
  all 1.000.
- 2025 (2025-01-01 → 2025-04-30): `S2B_43PDS_20250222_0_L2A` (1.000),
  `S2B_43PDS_20250304_0_L2A` (1.000), `S2C_43PDS_20250207_0_L2A` (1.000),
  `S2A_43PDS_20250331_1_L2A` (1.000). Rejected examples recorded honestly:
  `S2B_43PDS_20250103_0_L2A` (0.595), `S2C_43PDS_20250418_0_L2A` (0.268).

**Recommended experiment:** `western_ghats_m4` — earlier anchor 2020-02-19,
later anchor 2025-02-22 (day-of-year gap 3 days). Indices NDVI (+ NDWI), with
DEM-derived elevation/slope context for terrain-shadow interpretation and
south-facing vs north-facing summarisation where materially helpful. Risks:
topographic shadow at 10 m, phenological dry-season leaf drop, plantation vs
natural forest confusion. No deforestation claim from NDVI reduction.

## D1 — Purepu supraglacial-lake drainage, 8 July 2025 (tile 45RUM)

Full probe tables in `docs/M0_HIMALAYAN_DATA_FEASIBILITY.md` (reproduced and
still current; the M0 cache re-serves these responses). Summary:

- Pre-event (fully valid): `S2B_45RUM_20250421_0_L2A` (2025-04-21, cloud 2.24 %).
- Immediate post-event: only `S2C_45RUM_20250708_0_L2A` — **same-day**, in-AOI
  valid 0.632; all other July passes fail (0.000–0.446).
- Post-monsoon (fully valid): `S2B_45RUM_20251021_0_L2A` (2025-10-21, cloud 0.50 %).

**Verdict PARTIAL.** No clean immediate post-event observation exists; the only
defensible processed comparison is *April 2025 → 21 October 2025* (before vs
after the monsoon), with the same-day July acquisition presented as a
limited-coverage context view, not a difference baseline. Seasonal snow-cover
change is a confounder of the same order as the event signal. Outputs: per-date
NDWI/MNDWI water-surface signals and observation-support layers under explicit
seasonal caveats. **Never claimed:** discharged volume, flood depth, discharge,
causal mechanism, casualties. Lake area is not discharged-water volume.

## D2 — Langtang Lirung rock–ice collapse, 26 August 2026 (tile 45RUM)

From the same M0 probe (unchanged):

- Tightest usable pair: `S2C_45RUM_20260812_0_L2A` (2026-08-12, −14 days,
  valid 0.707) → `S2C_45RUM_20260928_0_L2A` (2026-09-28, +33 days, valid 1.000).
- Second post-event option: `S2B_45RUM_20260916_0_L2A` (valid 0.791).
- Failing September passes recorded honestly (0.000–0.167).

**Verdict PASS (constrained).** A documented optical change observation at the
source zone is supported. Presented as a rock–ice collapse investigation —
**not** a conventional GLOF, not a debris-volume estimate, not flood routing,
and without InSAR (radar-only literature such as published Sentinel-1 InSAR
analyses stays external, cited, clearly labelled).

## E — Kathmandu Valley urban pilot (AOI 85.305–85.325 E, 27.695–27.715 N; tile 45RUL)

From the M0 probe (unchanged):

- Best seasonally matched pair: `S2B_45RUL_20200331_1_L2A` (2020-03-31,
  cloud 0.07 %, valid 1.000) → `S2A_45RUL_20250329_0_L2A` (2025-03-29,
  cloud 0.003 %, valid 1.000) — a two-day day-of-year gap.

**Verdict PASS (interpretation-limited).** Data availability is not the
constraint; interpretation is. NDBI, NDVI, NDWI and composites will be computed;
NDBI is presented as a *candidate built-up signal* only, with a bare-soil
negative-control panel (riverbed/exposed-soil areas inside the window) and no
classifier accuracy figures (no independent labels — M2 finding stands).
No "urban expansion in hectares of new buildings" claims.

---

## Cross-cutting risks recorded before processing

1. **D1 seasonal confounding** dominates; every D1 chart carries the caveat.
2. **Monsoon cloud** (D1/D2) limits pairs to the specific dates above.
3. **Turbidity** (B) and **terrain shadow** (C) are documented interpretation
   limits, not processing defects.
4. **E has no independent labels**; the supervised-classification path stays
   blocked and no accuracy figure will be produced.
5. Processing budget stays bounded: ≤ 3 observations per period composite,
   bounded AOI windows, windowed COG reads (existing M1 policy).

## Gate decision

Proceed to M4-G1 (Chilika, Western Ghats, Kathmandu) and M4-G2 (D1, D2) with
the scene selections above. Stop conditions re-checked before each run: any
investigation whose measured validity collapses below the pipeline thresholds
at processing time is recorded PARTIAL/BLOCKED rather than forced.
