# M0 Nepal data feasibility — D1 (8 July 2025), D2 (26 August 2026) and Kathmandu

**What this document is.** A record of what the Element 84 Earth Search
`sentinel-2-l2a` catalogue *actually holds* over the two Nepal event source
areas and over the Kathmandu pilot window, and what that imagery can and cannot
support. It contains no estimated values and no invented scenes: every ID,
date, cloud figure and valid fraction below was produced by
`scripts/probe_event_feasibility.py`, whose raw output is
`data/cache/event_feasibility.json` (git-ignored cache; regenerate with the
command below).

**How the numbers were produced**

1. `SearchRequest` per target window using the AOI polygon from
   `studies/registry.yaml`, with `max_cloud_cover = 100 %` so that *nothing* is
   filtered out on metadata alone.
2. Every returned item was scored by footprint coverage of the AOI.
3. The best 6 candidates per window (metadata pre-rank: footprint, then global
   cloud) had their SCL window read at 20 m over the AOI, and the in-AOI *valid*
   fraction was measured with the same masking policy the pipeline uses
   (classes 0, 1, 3, 8, 9, 10 rejected).
4. A candidate counts as **usable** only when the scene footprint covers the AOI
   completely **and** the measured in-AOI valid fraction is at least `0.60`
   (`config.MIN_SCENE_VALID_FRACTION`). Candidates beyond the measurement budget
   have `aoi_valid_fraction: null` and are never counted as usable.

Run: `python scripts/probe_event_feasibility.py --max-measure 6`

Measured 2026-11-04. The cold run made **25 catalogue requests and downloaded
8,016,992 bytes** of catalogue JSON plus the SCL range reads; warm re-runs make
8 requests and download 0 bytes because catalogue responses and SCL
valid-fraction memos are reused from `data/cache/`.

> **Attribution.** Contains modified Copernicus Sentinel data, processed by ESA;
> L2A products distributed by the Element 84 Earth Search STAC catalogue
> (AWS Open Data). Event context (NDRRMA 2025 situation report, ICIMOD 2026
> reporting) is cited external literature, **not** a project measurement.

## D1 — Purepu supraglacial-lake drainage, 8 July 2025

AOI (approximate source-area window, ±2 km): `85.615–85.650 E`,
`28.300–28.330 N`, 11.41 km², MGRS tile `45RUM`.
Registry entry: `studies/registry.yaml` → `himalaya_purepu_2025`.

| Window | Catalogue items | Usable in AOI | Best measured valid fraction | Best candidate |
|---|---|---|---|---|
| `2025-04-01 → 2025-07-08` (pre-event) | 49 | 6 | **1.000** | `S2B_45RUM_20250421_0_L2A` (2025-04-21, scene cloud 2.24 %) |
| `2025-07-08 → 2025-07-31` (immediate post) | 13 | **1** | **0.632** | `S2C_45RUM_20250708_0_L2A` (2025-07-08, scene cloud 54.05 %) |
| `2025-08-01 → 2025-10-31` (post-monsoon) | 48 | 6 | **1.000** | `S2B_45RUM_20251021_0_L2A` (2025-10-21, scene cloud 0.50 %) |

Other pre-event candidates measured at full in-AOI validity:
`S2B_45RUM_20250401_0_L2A` (2025-04-01, cloud 2.95 %),
`S2B_45RUM_20250424_0_L2A` (2025-04-24, cloud 3.02 %),
`S2A_45RUM_20250401_1_L2A` (2025-04-01, cloud 3.08 %), and
`S2B_45RUM_20250404_0_L2A` (2025-04-04, valid 0.990).

Immediate post-event candidates that **fail** the validity threshold:
`S2C_45RUM_20250718_0_L2A` (0.446), `S2B_45RUM_20250723_0_L2A` (0.317),
`S2C_45RUM_20250725_0_L2A` (0.055), `S2B_45RUM_20250713_0_L2A` (0.022) and
`S2B_45RUM_20250710_1_L2A` (0.000).

Post-monsoon candidates measured at full validity besides the best one:
2025-10-26, 2025-10-25, 2025-10-11 (two items) and 2025-10-16.

**Verdict for D1.** Feasible, with an honest gap. A clean pre-event observation
exists (April 2025, full AOI validity). The only usable immediate post-event
observation is the **same-day** acquisition on 2025-07-08 whose AOI is 63.2 %
valid — every later July pass is monsoon-obscured. A fully valid post-event
observation exists only from 2025-10-21, i.e. ~3.5 months after the drainage.
Consequently a defensible comparison is *April 2025 → 21 October 2025*
("before the monsoon" vs "after the monsoon"), **not** a same-week before/after
pair. Seasonal snow-cover change over those months is a confounder of the same
size as the event itself, so nothing here supports a lake-volume or flood
claim; at most it supports a bounded observation of lake/shore appearance under
an explicitly seasonal caveat.

## D2 — Langtang Lirung rock–ice collapse, 26 August 2026

AOI (approximate source-zone window): `85.530–85.565 E`, `28.155–28.190 N`,
13.33 km², MGRS tile `45RUM`.
Registry entry: `himalaya_langtang_2026`.

| Window | Catalogue items | Usable in AOI | Best measured valid fraction | Best candidate |
|---|---|---|---|---|
| `2026-06-01 → 2026-08-26` (pre-event) | 43 | 2 | **0.793** | `S2B_45RUM_20260615_0_L2A` (2026-06-15, scene cloud 18.42 %) |
| `2026-08-26 → 2026-09-30` (post-event) | 17 | 2 | **1.000** | `S2C_45RUM_20260928_0_L2A` (2026-09-28, scene cloud 1.59 %) |
| `2026-10-01 → 2026-12-15` (late season) | 18 | 6 | **1.000** | `S2B_45RUM_20261026_0_L2A` (2026-10-26, scene cloud 0.04 %) |

The tightest usable pair available: **`S2C_45RUM_20260812_0_L2A`** (2026-08-12,
14 days before the event, in-AOI valid 0.707) → **`S2C_45RUM_20260928_0_L2A`**
(2026-09-28, 33 days after, in-AOI valid 1.000). A second post-event option is
`S2B_45RUM_20260916_0_L2A` (0.791). Most September passes fail:
`S2C_45RUM_20260918_0_L2A` (0.167), `S2C_45RUM_20260921_0_L2A` (0.030),
`S2C_45RUM_20260908_0_L2A` (0.000) and `S2A_45RUM_20260920_0_L2A` (0.000).

**Verdict for D2.** Feasible as an observational pair, 14 days before and 33
days after the event. Both dates fall in the monsoon/early post-monsoon period,
so residual cloud, snow-cover evolution and terrain shadow remain confounders;
the 33-day post-event gap also allows further snow settling and debris
reworking. This supports a documented optical change observation at the source
zone — not a debris-volume estimate, not a flood-routing claim, and not the
InSAR deformation field that only radar can provide.

## E — Kathmandu Valley urban pilot (2020 / 2025 availability)

AOI: `85.305–85.325 E`, `27.695–27.715 N`, 4.37 km², MGRS tile `45RUL`.
Registry entry: `studies/registry.yaml` → `kathmandu_urban` (status
`feasibility`; no urban index is computed in M0).

| Window | Catalogue items | Usable in AOI | Best measured valid fraction | Best candidate |
|---|---|---|---|---|
| `2020-01-01 → 2020-05-31` | 122 | 6 | **1.000** | `S2B_45RUL_20200210_1_L2A` (2020-02-10, scene cloud 0.03 %) |
| `2025-01-01 → 2025-05-31` | 69 | 6 | **1.000** | `S2B_45RUL_20250111_0_L2A` (2025-01-11, scene cloud 0.0005 %) |

The best seasonally matched pair is **`S2B_45RUL_20200331_1_L2A`** (2020-03-31,
cloud 0.07 %, valid 1.000) → **`S2A_45RUL_20250329_0_L2A`** (2025-03-29, cloud
0.003 %, valid 1.000): a two-day day-of-year gap with full AOI validity on both
dates. A January pair with a 30-day seasonal gap is equally valid
(`2020-02-10` → `2025-01-11`).

**Verdict for E.** Availability is not the constraint: both windows contain
many fully valid observations, and a near-exact seasonal match exists.
Interpretation is the constraint, not data. The 2.2 × 2.2 km window mixes
roofs, roads, construction sites, bare soil and riverbed material; dry-season
bare soil and active construction can mimic a built-up spectral signature.
M0 records availability only — NDBI or any built-up index must be presented as
a *candidate* signal with a bare-soil negative control in the same panel, never
as a building label.

## What this evidence does *not* support

- No event cause, magnitude, volume, discharge, dam-failure mode or damage claim.
- No claim that the 2025 and 2026 events share a mechanism: the registry keeps
  them as two distinct investigations (`event_mechanism` differs, and a registry
  test enforces it).
- No "clean instant before/after" narrative for D1 — the honest pair is
  seasonal.
- No urban change, population or economic claim for Kathmandu.
- No widening of an AOI to chase a cleaner scene without re-recording the AOI
  rationale and re-running this probe.

## Consequences for M0 acceptance and M4

- The roadmap's M0 gate asks for exact scene candidates and visibility limits for
  **both** events: satisfied above — 2 event storylines × 3 windows, with exact
  IDs and dates and explicit cloud/validity limits.
- A cloudy/blocked Himalayan pair would have been an acceptable M0 result; in
  fact both events have at least one usable pre- and one usable post-event
  observation, with D1 requiring a seasonal caveat.
- M4 must render these as evidence-under-constraint: per-event tabs, the exact
  acquisition dates, the measured valid fraction, and a visible statement of the
  temporal gap between observations.
- The AOI centres are approximate (±2 km) and have not been snapped to a
  verified shoreline or detachment scar; M4 must not present them as official
  event footprints.
- External context (NDRRMA 2025 situation report, ICIMOD 2026 reporting, UNOSAT
  polygon availability/rights) is cited as literature only. No UNOSAT product is
  redistributed here, and no registered service is required by the pipeline.
