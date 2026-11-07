# M4-R2 Findings Audit — independent verification record

**Status:** M4-R2 G2 + G3 deliverable. All 152 recorded findings were
re-derived from the frozen rasters by an audit implementation that shares no
code with the production generator (`scripts/audit_findings_m4r2.py` vs
`scripts/generate_findings.py`).

**Result: 1614 / 1614 independent checks passed, 0 failed.**

Machine-readable output: `docs/evidence/m4-r2/findings_audit_results.json`.

---

## 1. Audit method (independence)

The audit deliberately re-implements, rather than imports:

| Step | Production | Audit |
|------|-----------|-------|
| Candidate mask | numpy comparisons in `generate_findings.py` | same rule re-stated with plain numpy on freshly read rasters |
| Component labelling | `scipy.ndimage.label`, 4-connectivity | independent iterative flood fill (`collections.deque`), 4-connectivity |
| Region stats | production loop | recomputed from rasters per component |
| Geometry checks | `rasterio.features.shapes` + pyproj | recorded WGS84 rings round-tripped back to the grid; shapely validity; shoelace areas; vertex grid alignment |
| Denominator | recorded `common_valid_pixels` | recounted from the `common_valid_*.tif` mask |

Checks per finding: direction, pixel count, mean Δ, median Δ, `area_ha`
arithmetic, `share_of_common_valid_percent` arithmetic (at the recorded 4-dp
precision), single-ring Polygon structure, closed ring, shapely validity,
exterior-ring area consistency, grid alignment of every vertex (≤ 0.05 px,
allowing for the recorded 6-dp WGS84 rounding), centroid consistency.
Per index: common-valid denominator recount, decrease/increase pixel totals,
finding-count vs recomputed top-K regions. Per experiment: unique IDs,
overview-total consistency.

## 2. Numerical agreement

Every recorded value reproduces exactly:

- candidate mask pixel totals per index × direction (7 experiments);
- all 152 pixel counts, mean/median Δ (≤ 1e-6 index units), areas, shares;
- all 7 × per-index common-valid denominators (recounted from masks);
- component selection: recorded findings are exactly the top-5 components
  (≥ 25 px) per index × direction under the recorded deterministic order.

## 3. Geometry validation (G3)

- **Grid:** all six studies analyse on a 10 m Sentinel-2 grid in the local
  UTM CRS — Coringa EPSG:32644, Chilika/Kathmandu/Purepu/Langtang EPSG:32645,
  Western Ghats EPSG:32643. Pixel area 100 m² everywhere.
- **Transforms:** every recorded polygon vertex round-trips onto the raster
  grid to within 0.05 px (residual is purely the recorded 6-dp WGS84
  rounding, ≈ 0.1 m ≈ 0.004 px).
- **Geometry validity:** all 152 rings are closed, shapely-valid, single
  exterior polygons.
- **CRS conversion:** UTM → WGS84 (pyproj, always-xy); round-trip verified.
- **Area method:** analytical areas are `pixel_count × 100 m²` on the
  projected grid — never measured in latitude/longitude. Independently
  confirmed by shoelace areas on the round-tripped UTM rings.
- **AOI containment:** no finding vertex falls outside its delta raster /
  analysis-window bounds; components derive from the shared-valid mask,
  which is itself inside the AOI.

### 3.1 Display-geometry simplification (documented, preserved measurement)

The recorded `geometry_wgs84` is the **exterior ring** of the component.
127 of 152 components enclose interior holes — masked (invalid) pixels fully
surrounded by candidate pixels — totalling **51,050 pixels (510.50 ha
equivalent in outline terms)**. The recorded `pixel_count`, `area_ha` and all
statistics exclude these holes and are therefore correct; the display
outline includes them visually. This is a display simplification of the same
kind the brief anticipates: the original analytical measurement is preserved
separately and is the number of record. G4 records the hole pixels per
finding explicitly so the simplification is traceable per record.

## 4. Minimum mapping unit interpretation (G3)

- 25 px = **0.25 ha** on every study's 10 m grid — the MMU is a consistent
  physical area across all investigations; no cross-study scaling error
  exists. (SWIR-derived indices — MNDWI, NDSI, NDBI — use 20 m native bands
  upsampled onto the same 10 m analysis grid; their effective information
  content is coarser, which is a resolution caveat recorded in the index
  registry, not an MMU inconsistency.)
- The MMU discards components < 25 px; no finding below it exists (verified).

## 5. Missing / unrecorded candidates (documented selection, not an error)

The generator records the top 5 components per index × direction. The audit
counts every component ≥ 25 px:

| Experiment | Recorded | Components ≥ MMU | Not recorded (top-5 cap) |
|---|---|---|---|
| coringa_m1 | 30 | 686 | 656 |
| chilika_m4_dry | 30 | 294 | 264 |
| chilika_m4_postmonsoon | 30 | 230 | 200 |
| western_ghats_m4 | 11 | 13 | 2 |
| himalaya_purepu_2025_m4 | 20 | 139 | 119 |
| himalaya_langtang_2026_m4 | 12 | 63 | 51 |
| kathmandu_m4 | 19 | 95 | 76 |
| **Total** | **152** | **1520** | **1368** |

The unrecorded components are smaller, lower-ranked regions of the same
masks. This is the recorded, deterministic `max_regions_per_index_direction =
5` selection rule — a completeness boundary of the product, not a numerical
error. It is stated here so nobody mistakes the 152 findings for an
exhaustive inventory.

## 6. Audit-log issues raised and resolved during G2

Three initial audit failures were **audit bugs**, corrected after diagnosis;
no recorded value changed:

1. share tolerance ignored the recorded 4-dp rounding;
2. a malformed shapely `is_ring` check on polygons;
3. tie-order matching compared recorded findings by ascending UTM northing
   against recomputed regions by ascending row (opposite orders), which
   mispaired two equal-size Kathmandu regions (Region 03/04, 108 px each)
   and produced a false mean/median mismatch. With production-order matching
   both reproduce exactly.

One genuine characteristic was discovered (§3.1) and documented rather than
"fixed silently": the exterior-ring display geometry encloses component
holes. No existing number was modified.

## 7. Verdict

Every displayed finding is derived from genuine processed data, reproduces
exactly under independent recomputation, sits on the true raster grid, and
carries a correct projected-grid area. The previous outputs were preserved;
nothing required regeneration on numerical grounds.
