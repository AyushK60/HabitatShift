# M4-R2 Method Protocol — formal mathematical definitions of the Evidence Engine

**Status:** M4-R2 G1 deliverable. This document records the mathematical rules
behind every "What Changed?" finding, and confirms that the existing
implementation matches them. No calculation was changed in G1.

Implementation of record: `scripts/generate_findings.py` (schema
`habitatshift-findings/1`) reading the frozen M1/M4 rasters produced by
`backend/app/pipeline/engine.py`.

---

## 1. Difference measurement

For two aligned observations on the same analysis grid:

```
ΔI(p) = I_later(p) − I_earlier(p)
```

- `p` is one pixel of the shared analysis grid (10 m Sentinel-2 grid in the
  study's local UTM CRS; pixel area 100 m²).
- `I` is the recorded spectral index (registry: `backend/app/indices/spectral.py`).
- Earlier and later composites are built on the identical grid and window
  (`backend/app/pipeline/engine.py`, `compute_change_layers`), so the
  subtraction is a per-pixel alignment with no reprojection at this stage.

**Convention check (G1):** `ndvi.difference(later, earlier)` computes
`later − earlier`. The delta rasters written as `delta_<index>.tif` carry the
GeoTIFF description `delta_later_minus_earlier`. Verified, unchanged.

## 2. Threshold rule (candidate change classes)

For a recorded primary threshold `t > 0` (all studies record `t = 0.15`):

```
C(p) = candidate decrease   if ΔI(p) ≤ −t
C(p) = candidate increase   if ΔI(p) ≥ +t
C(p) = below threshold      if |ΔI(p)| < t
```

Boundary convention: both directions are **inclusive** of the threshold value
(`<=` / `>=` in `scripts/generate_findings.py:302-303`). This matches the
M4-R1 recorded rule `|Δ| ≥ t` and the brief's piecewise definition. The
sign of ΔI is never silently reversed: `decrease` always means the later
composite reads lower in the index than the earlier composite.

## 3. Validity conditions

A pixel may only become a candidate change pixel when it is a valid
observation in **both** periods:

```
common(p) = valid_earlier(p) ∧ valid_later(p)
          ∧ isfinite(I_earlier(p)) ∧ isfinite(I_later(p))
          ∧ isfinite(ΔI(p))
```

- `valid_<period>` is the SCL-derived observation-validity mask of that
  period's composite (clouds masked, never interpolated;
  `backend/app/preprocess/masks.py`). AOI membership is tracked separately
  from observation validity, so a pixel outside the AOI is never counted as a
  masked observation inside the AOI (distinction established in M4-R1 G2).
- The on-disk delta raster is already `NaN` where `common` is false
  (`engine.py` writes `np.where(common, delta, nan)`), so the candidate mask
  in `generate_findings.py` (`usable = common & isfinite(delta)`) is doubly
  guarded.
- The **valid denominator** — `common_valid_pixels` — is recorded per index
  in each `summary.json` change block and in every finding
  (`common_valid_pixels`). All percentages (`share_of_common_valid_percent`)
  are relative to this denominator, never to the full AOI.

NoData semantics: the delta GeoTIFF uses NaN as NoData; the common-valid mask
GeoTIFF is uint8 with nodata 0. Both are respected on read.

## 4. Index registry and interpretation discipline

| Index | Formula | Bands | Native res. |
|-------|---------|-------|-------------|
| NDVI  | (NIR − Red) / (NIR + Red)       | B8, B4   | 10 m |
| NDWI  | (Green − NIR) / (Green + NIR)   | B3, B8   | 10 m |
| MNDWI | (Green − SWIR1) / (Green + SWIR1) | B3, B11 | 20 m |
| NDSI  | (Green − SWIR1) / (Green + SWIR1) | B3, B11 | 20 m |
| NDBI  | (SWIR1 − NIR) / (SWIR1 + NIR)   | B11, B8  | 20 m |

**MNDWI / NDSI duplication rule.** MNDWI and NDSI are mathematically
identical on identical inputs (Green + SWIR1). The registry records this
explicitly, and NDSI is gated to cryosphere study profiles. No experiment in
the current set uses both indices (Coringa/Chilika use MNDWI; the Himalaya
studies use NDSI), so no finding set ever presents the same measurement twice
as independent evidence. This rule is enforced structurally: if a future
profile requested both, the evidence layer must label them as one measurement
with two interpretations, not two findings.

**Index-specific interpretation.** The sign of ΔI is never given a universal
environmental meaning. Interpretation is study-specific and deterministic
(`generate_findings.py::_template`):

- Negative NDVI difference → *candidate vegetation-index decrease* (canopy
  change, water-level/turbidity differences, or illumination — study-specific).
- Positive NDVI difference → *candidate vegetation-index increase*.
- Negative NDWI/MNDWI difference → *candidate water-index decrease under the
  selected definition* (exposed lakebed, tidal state, turbidity).
- Positive NDBI difference → *candidate stronger built-up-related spectral
  signal* — explicitly not a building detector (10 m pixels cannot resolve
  buildings).
- NDSI differences → *snow/ice-related spectral signal*, never read as a
  verified collapse footprint.

Each finding carries the study's recorded `cannot_conclude` guardrails and,
where applicable (D1 Purepu 2025), the `PARTIAL` evidence status is inherited
from the frozen summary and restated in the interpretation.

## 5. Spatial finding extraction

1. Candidate mask: `usable ∧ (Δ ≤ −t ∨ Δ ≥ t)`, split per direction.
2. Connected components: `scipy.ndimage.label` with the 3×3 cross structuring
   element — **4-connectivity** (verified: `CONNECTIVITY_STRUCTURE` has zero
   diagonal).
3. Minimum mapping unit: components smaller than **25 pixels** are discarded.
   On the 10 m grid (100 m²/pixel) this is **0.25 ha**; all six studies use
   the same 10 m grid, so the MMU is a consistent physical area across
   studies (audited in G3).
4. Selection: the top **5** components per index × direction by pixel count,
   ties broken by centroid row then column — fully deterministic.
5. Geometry: `rasterio.features.shapes` on the component mask with the
   delta raster's own affine transform (true grid geometry, pixel-aligned,
   UTM CRS), then projected to WGS84 with pyproj for display only. No
   hand-drawn or simplified polygons are used anywhere in the measurement
   chain.
6. Area: `pixel_count × 100 m²` on the projected analysis grid, reported in
   hectares. Areas are **not** measured from the WGS84 display polygons.

One connected component yields exactly one polygon; multi-ring outputs are
rejected (the code takes the single ring from `shapes` for a connected mask).

## 6. What a finding is — and is not

A finding is a **threshold-defined candidate region** with a full audit
trail (threshold, pixel count, measured area, mean/median Δ, common-valid
denominator, acquisition periods, recorded limitations, deterministic
interpretation). It is not a classification, not a land-cover label, and not
a significance-tested change. Adjacent pixels inside one component are not
independent observations; no p-value or confidence score is computed.

M4-R2 G4 upgrades each record to the versioned Evidence Record schema
(`docs/M4_R2_EVIDENCE_SCHEMA.md`) without changing any measurement.

## 7. Change-control rules for this milestone

- Frozen M1/M4 rasters are inputs of record; findings are regenerated from
  them, never from preview imagery or display geometry.
- Existing results are only regenerated after an independently demonstrated
  error, with the previous outputs preserved and the issue documented
  (`docs/M4_R2_FINDINGS_AUDIT.md`).
- Thresholds, MMU, connectivity and region caps are recorded constants; any
  change to them is a new schema version, never a silent edit.
