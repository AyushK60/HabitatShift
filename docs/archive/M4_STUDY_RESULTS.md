# M4 study results — six investigations, recorded numbers only

Every number below is copied from a stored artefact (`data/processed/m4/*/summary.json`,
`data/manifests/m4_*.json`). Nothing is re-derived for this document. The
interactive workstation shows the same values from the showcase bundles.

Attribution: contains modified Copernicus Sentinel data, processed by ESA
(Element 84 Earth Search STAC catalogue, AWS Open Data). DEM: Copernicus
GLO-30 (ESA/DLR). Event context: NDRRMA 2025 and ICIMOD 2026 reporting,
cited literature.

---

## Study A — Coringa / Godavari delta (reference; unchanged)

Frozen M0/M1/M2 outputs; not reprocessed. The M4 audit re-verified the M2
experiment: **149/149 audit checks passed**. Coringa is the reference case
that validated the bundle architecture, the interactive charts and the live
pixel/ROI enhancement.

## Study B — Chilika Lake (two experiments)

**B1 `chilika_m4_dry` — matched dry season.** Period composites
2020-02-17/12/22 → 2025-02-15/10/20 (3 observations each, all usable items
validity 0.98–1.00). Common-valid footprint: **100.0 % of AOI**. Means:
NDWI 0.454 → 0.515, MNDWI 0.759 → 0.779, NDVI −0.311 → −0.405. Candidate
change at |Δ| ≥ 0.15 (NDWI): **4.20 % of shared-valid** lower / 22.34 % higher
(146.09 ha / 777.89 ha of the 3,373 ha window).

**B2 `chilika_m4_postmonsoon` — matched post-monsoon.** 2020-11-08/03/13 →
2025-11-17/14/12. Common-valid **100.0 %**. Means: NDWI 0.520 → 0.496,
MNDWI 0.748 → 0.740. Candidate change at |Δ| ≥ 0.15 (NDWI): 11.51 % lower /
3.60 % higher (388.10 ha / 121.70 ha).

**Reading.** Both matched seasons show broadly similar water signals between
2020 and 2025; the differences that exist are modest and redistributive. The
pair of experiments *is* the seasonal-sensitivity investigation: nothing in
either supports a permanent-wetland-loss claim, and the window (main lagoon
near Satapada) is not the seasonally exposed margin. During processing, an
apparent 2020→2025 "water-to-land flip" was diagnosed as a radiometry
artifact (see `docs/M4_radiometry_incident.md`) and corrected before any
result was accepted.

## Study C — Western Ghats forest (Supa taluk, Uttara Kannada, Karnataka)

`western_ghats_m4`: 2020-02-19/14/24 → 2025-02-22/17/27 (matched dry season,
3-day day-of-year gap). Common-valid **100.0 %**. Means: NDVI 0.799 → 0.809,
NDWI −0.715 → −0.727. Candidate change at |Δ| ≥ 0.15 (NDVI): **0.14 % lower /
0.38 % higher** (3.45 ha / 8.99 ha of 2,377 ha).

**Reading.** The matched-season NDVI signal is essentially stable across the
five years at this window. DEM context (Copernicus GLO-30, item
`Copernicus_DSM_COG_10_N15_00_E074_00_DEM`): elevation 607.3–975.6 m (mean
724.5 m) — terrain context for topographic-shadow interpretation only; the
DEM is not a co-registered input to the indices. No deforestation claim is
possible or made from these numbers.

## Study D1 — Purepu supraglacial-lake drainage, 8 July 2025 (PARTIAL)

`himalaya_purepu_2025_m4`: earlier 2025-04-21/18/24 (pre-monsoon), later
2025-10-21/18/25 (post-monsoon). Common-valid **100.0 %**. Means: NDSI 0.291 →
0.704, NDWI −0.028 → 0.067, NDVI 0.004 → −0.060. Candidate change at |Δ| ≥
0.15 (NDSI): 1.63 % lower / 20.07 % higher (55.04 ha / 676.80 ha of 3,373 ha).

**Reading under constraint.** The only usable post-event July observation is
the same-day pass (`S2C_45RUM_20250708_0_L2A`, in-AOI validity 0.632); every
later July pass fails validity (recorded in the bundle's event timeline). The
defensible processed comparison is April → October, and the dominant signal —
a large NDSI increase — is **seasonal snow accumulation**, a confounder of the
same order as any event signal. Nothing here supports discharged volume,
flood depth, mechanism or damage claims. Lake surface area is not
discharged-water volume.

## Study D2 — Langtang Lirung rock–ice collapse, 26 August 2026

`himalaya_langtang_2026_m4`: earlier 2026-08-12 (−14 days, single usable
observation, validity 0.685 of AOI), later 2026-09-28/10-01/10-03 (+33 days
and after). Common-valid **70.3 % of AOI**. Means: NDSI −0.085 → 0.868, NDWI
−0.138 → 0.068, NDVI 0.111 → −0.060. Candidate change at |Δ| ≥ 0.15 (NDSI):
0.07 % lower / 119.89 % higher (0.47 ha / 843.46 ha of the common-valid area).

**Reading under constraint.** The pre-event observation is monsoon-limited
(one usable scene), and the 33-day post-event gap allows further snowfall and
debris reworking. The dominant recorded difference is seasonal snow-cover
evolution; the investigation supports a documented optical change observation
at the source zone — not a debris volume, not flood routing, and no InSAR
claim (radar findings stay external, cited literature). Presented explicitly
as a rock–ice collapse with a cascading debris-laden flood — **not** a
conventional GLOF.

## Study E — Kathmandu Valley urban pilot

`kathmandu_m4`: 2020-03-31/04-02/03-26 → 2025-03-29/30/27 (matched pre-monsoon
season, 2-day day-of-year gap). Common-valid **100.0 %**. Means: NDBI 0.092 →
0.130, NDVI 0.199 → 0.163, NDWI −0.257 → −0.232. Candidate change at |Δ| ≥
0.15 (NDBI): 1.17 % lower / 8.86 % higher (3.95 ha / 29.84 ha of 437 ha).

**Reading.** A candidate built-up spectral signal increase coincides with a
candidate vegetation-signal decrease — the expected direction of the study
question. NDBI is a spectral feature, **not** a building detector: bare soil,
construction sites and dry riverbed material inside the window can produce the
same signal. No independent reference labels exist (M2 finding), so no
classifier performance and no "hectares of new buildings" statement is
permitted or produced.
