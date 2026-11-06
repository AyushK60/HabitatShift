# M1 numerical audit — Coringa / Godavari delta

**Statement.** Every number in this document is read from the committed M1
artefacts for `coringa_coastal`:

- `data/processed/m1/coringa_coastal/summary.json`
- `data/processed/m1/coringa_coastal/summary.csv`
- `data/manifests/m1_coringa_coastal.json`

They were independently re-derived from the exported GeoTIFFs by
`scripts/audit_m1.py` (22/22 checks passed). No value here is estimated,
interpolated or copied from a model's expectation.

> **Claim boundary.** The differences below are *observed index differences at
> a stated threshold*. They are not verified deforestation, wetland loss,
> construction, glacier damage or any other land-cover/causal label.

---

## 1. Run identity

| Field | Value |
|---|---|
| Experiment | `coringa_m1` |
| Study | `coringa_coastal` — Coringa / Godavari delta, Andhra Pradesh |
| Pipeline | `0.2.0-m1`, profile `spectral_change_m1` |
| Composite | median, up to 3 observations per period |
| Min observations per pixel | 1 |
| Indices | NDVI, NDWI, MNDWI |
| Thresholds | 0.10, 0.15 (primary), 0.20 |
| Catalogue | Element 84 Earth Search, `sentinel-2-l2a` |
| Canonical run | `--offline` rebuild from cached source data |
| Engine verification | 26/26 passed |
| Independent audit | 22/22 passed |

The manifest records `http_requests: 0` and `bytes_downloaded: 0` for the
committed run because it was rebuilt offline from cached catalogue responses
and cached observation arrays. An online run produced byte-identical rasters
(see [`M1_VERIFICATION.md`](M1_VERIFICATION.md)).

---

## 2. Scenes actually used

Selection is by measured in-AOI valid fraction and proximity to the period
anchor, one scene per calendar date. All six selected scenes are MGRS tile
`44QPD`.

### Earlier period — anchor 2020-03-26

| Date | Item ID | Scene cloud | Measured AOI valid |
|---|---|---:|---:|
| 2020-03-26 | `S2A_44QPD_20200326_1_L2A` | 0.0369 % | 0.999836 |
| 2020-03-21 | `S2B_44QPD_20200321_0_L2A` | 21.0368 % | 0.795635 |
| 2020-03-31 | `S2B_44QPD_20200331_0_L2A` | 0.0903 % | 0.999782 |

### Later period — anchor 2025-03-25

| Date | Item ID | Scene cloud | Measured AOI valid |
|---|---|---:|---:|
| 2025-03-25 | `S2B_44QPD_20250325_0_L2A` | 5.0095 % | 0.957962 |
| 2025-03-30 | `S2C_44QPD_20250330_0_L2A` | 2.5912 % | 0.999879 |
| 2025-04-01 | `S2A_44QPD_20250401_1_L2A` | 2.1748 % | 0.920526 |

The earlier and later anchors are the two M0 acquisition dates, so the
single-observation reconstruction can be compared directly with M0 (§7).
The three-observation composites are a different, documented estimator.

---

## 3. Grid and AOI

| Field | Value |
|---|---|
| Analysis CRS | `EPSG:32644` (UTM 44N) |
| Resolution | 10 m |
| Raster size | 429 × 390 px (167,310 px) |
| Transform | `[10, 0, 632700, 0, −10, 1851790]` |
| Bounds (projected) | `632700, 1847890, 636990, 1851790` |
| Grid signature | `ad1601d5620e5f23` |
| Pixel area | 100 m² |
| Pixels inside AOI | 165,136 |
| Valid fraction of grid | 0.987006 |

Area cross-check:

| Method | Area |
|---|---:|
| AOI polygon, projected (`EPSG:32644`) | 16.516024 km² |
| AOI polygon, geodesic (WGS84) | 16.52181 km² |
| Rasterised pixel count × 100 m² | 16.5136 km² |
| Grid extent | 16.731 km² |

Relative differences:

- geodesic vs projected: `3.5035 × 10⁻⁴`
- raster vs projected: `1.4674 × 10⁻⁴`

The raster value differs from the polygon only by boundary rasterisation.
Hectares and square kilometres are converted from projected square metres, not
from degrees.

---

## 4. Observation counts and composite validity

| Period | Valid pixels | Fraction of AOI | Fraction of grid | Count min | Count max | Count mean | Count median |
|---|---:|---:|---:|---:|---:|---:|---:|
| Earlier | 165,136 | 1.000000 | 0.987006 | 1 | 3 | 2.795254 | 3.0 |
| Later | 165,136 | 1.000000 | 0.987006 | 1 | 3 | 2.878367 | 3.0 |

Both composites are valid on every AOI pixel, but not every pixel has three
observations. The exported observation-count raster and preview make that
visible; the engine never fills a missing observation.

The 2,174 pixels outside the AOI are the invalid class in each change raster.

---

## 5. Index statistics on the composites

All values are on composite surface reflectance, 10 m grid. MNDWI uses 20 m
SWIR upsampled to 10 m and carries no genuine 10 m SWIR detail.

### Earlier period

| Index | Mean | Std | Min | p05 | Median | p95 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| NDVI | 0.519902 | 0.346974 | −0.728453 | −0.131679 | 0.615104 | 0.894965 | 0.965418 |
| NDWI | −0.457928 | 0.343736 | −0.902138 | −0.801254 | −0.583211 | 0.241579 | 0.774510 |
| MNDWI | −0.317975 | 0.247002 | −0.770332 | −0.568494 | −0.410061 | 0.201720 | 0.628599 |

### Later period

| Index | Mean | Std | Min | p05 | Median | p95 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| NDVI | 0.499431 | 0.336145 | −0.937198 | −0.183659 | 0.572498 | 0.865524 | 0.950216 |
| NDWI | −0.438969 | 0.340494 | −0.876637 | −0.755630 | −0.558218 | 0.305200 | 0.951493 |
| MNDWI | −0.324163 | 0.300674 | −0.827116 | −0.604197 | −0.430021 | 0.394290 | 0.677379 |

Valid count is 165,136 for every index in both periods.

---

## 6. Matched-valid change

### 6.1 Common-valid footprint

For all three indices the common-valid footprint is:

- **165,136 px**
- **1,651.36 ha**
- **16.5136 km²**
- **100.0 % of the AOI** (`common_valid_fraction_of_aoi = 1.0`)
- `suitable_for_comparison = true`

This is the footprint on which both periods have a finite index value for that
index. Percentages of decrease/increase below are relative to this footprint,
not to the full grid.

### 6.2 Difference distributions (later − earlier)

| Index | Mean | Std | Min | p05 | Median | p95 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| ΔNDVI | −0.020471 | 0.144254 | −1.328528 | −0.234398 | −0.022912 | 0.209492 | 1.191492 |
| ΔNDWI | 0.018959 | 0.139023 | −1.110745 | −0.192775 | 0.022871 | 0.208657 | 1.353161 |
| ΔMNDWI | −0.006188 | 0.154778 | −1.065322 | −0.215870 | −0.022711 | 0.274504 | 0.925330 |

### 6.3 Class counts at the primary threshold (0.15)

| Index | Decrease px | Stable px | Increase px | Invalid px |
|---|---:|---:|---:|---:|
| NDVI | 19,291 | 131,447 | 14,398 | 2,174 |
| NDWI | 12,612 | 136,279 | 16,245 | 2,174 |
| MNDWI | 21,897 | 120,599 | 22,640 | 2,174 |

Area conservation holds for every index:
`decrease + stable + increase = valid = 165,136`.

### 6.4 Threshold sensitivity

All values in hectares on the 1,651.36 ha common-valid footprint.

**NDVI**

| Threshold | Decrease ha | Decrease % of common | Increase ha | Increase % of common | Stable px |
|---:|---:|---:|---:|---:|---:|
| 0.10 | 347.71 | 21.055978 | 234.75 | 14.215556 | 106,890 |
| 0.15 | 192.91 | 11.681886 | 143.98 | 8.718874 | 131,447 |
| 0.20 | 113.45 | 6.870095 | 90.16 | 5.459742 | 144,775 |

**NDWI**

| Threshold | Decrease ha | Decrease % of common | Increase ha | Increase % of common |
|---:|---:|---:|---:|---:|
| 0.10 | 212.87 | 12.890587 | 320.69 | 19.419751 |
| 0.15 | 126.12 | 7.637341 | 162.45 | 9.837346 |
| 0.20 | 77.31 | 4.681596 | 90.59 | 5.485781 |

**MNDWI**

| Threshold | Decrease ha | Decrease % of common | Increase ha | Increase % of common |
|---:|---:|---:|---:|---:|
| 0.10 | 418.89 | 25.366365 | 330.26 | 19.999273 |
| 0.15 | 218.97 | 13.259980 | 226.40 | 13.709912 |
| 0.20 | 104.10 | 6.303895 | 153.58 | 9.300213 |

(NDVI percentages are the exact values stored in the summary; NDWI/MNDWI
percentages are the exact stored values too, computed from the audited pixel
counts that the audit verifies independently.)

Counts decrease monotonically as the threshold rises, for both directions and
all three indices. That is the expected sensitivity behaviour and is checked
by the test suite.

---

## 7. M0 baseline comparison — same scenes, different estimator

The earlier and later anchor scenes are exactly the M0 scenes. Recomputing the
indices from those single observations reproduces the M0 NDVI means:

| Quantity | M0 two-scene baseline | M1 anchor reconstruction |
|---|---:|---:|
| Earlier NDVI mean (2020-03-26) | 0.533215 | 0.533161 |
| Later NDVI mean (2025-03-25) | 0.443271 | 0.443271 |
| Difference of the two anchor means | −0.089944 | −0.089890 |
| M0 pixelwise ΔNDVI mean | −0.087687 | — |
| Common-valid fraction of AOI | 0.957938 | — |

The anchor NDVI means agree to within `5.4 × 10⁻⁵` (earlier) and exactly
(later). The earlier anchor valid count is 165,109 px versus M0's 165,132 px
(23 px fewer); the difference is explained by the mask set — the M1 anchor also
requires finite SWIR1 for the multi-index band set, while the M0 mask does not.
The engine reports this as an anchor reconstruction, not a byte-identical M0
rebuild. The "difference of anchor means" row is arithmetic on the two single
observations; it is **not** the same statistic as M0's pixelwise ΔNDVI mean.

**The headline M1 ΔNDVI is −0.020471, not the M0 −0.0877.** This is not a
regression and not a silently changed M0 result. It is a different estimator:

- M0 compares **one scene per date**.
- M1 compares **median composites of up to three observations per period**.
- The later M0 scene has 5.01 % scene cloud; the M1 later composite adds two
  clearer observations (2.59 % and 2.17 %), and the earlier composite adds one
  partly cloudy and one clear observation.
- Common-valid coverage also rises from 95.79 % of the AOI (M0) to 100 %
  (M1), so the two deltas are computed over different pixel populations.

Both numbers are real outputs of their respective estimators. The M1 summary
and manifest record the composite construction so the difference is auditable
rather than hidden. M0 artefacts are unchanged.

---

## 8. Independent recomputation

`scripts/audit_m1.py` does not import the engine. It:

1. re-hashes every manifest output and checks byte sizes;
2. reads every GeoTIFF and confirms one CRS/shape/transform;
3. recomputes NDVI, NDWI and MNDWI from the exported reflectance composites
   using independently written formulas;
4. recomputes deltas, threshold counts, percentages and areas;
5. checks area conservation and the projected/geodesic/raster area
   cross-check;
6. checks scene IDs, dates and grid signature agree between summary and
   manifest.

Result: **22 checks, all passed**, maximum sampled index/delta differences
within the audit tolerances (`≤ 2 × 10⁻⁵` for index means and pixel maxima,
`≤ 10⁻⁶` for delta recomputation).

The engine's own 26 checks add grid-tag checks, observation-count checks and a
deterministic 400-pixel index sample per period/index. All sampled differences
were `0.0`.

---

## 9. What these numbers support — and what they do not

Supported:

- The six listed scenes were read, masked, composited and indexed on the
  documented grid.
- NDVI/NDWI/MNDWI composites and their differences are reproducible from the
  committed manifest and cached data.
- At threshold 0.15, the candidate directional areas are as tabulated, on a
  fully documented common-valid footprint.
- The numbers are internally consistent across summary, CSV, manifest, rasters
  and the viewer.

Not supported:

- That any specific area changed land cover.
- That NDVI decrease is mangrove loss, or NDWI/MNDWI increase is a permanent
  water gain.
- That the 2020 and 2025 conditions are physically identical apart from the
  index signal (tide, turbidity, phenology and atmosphere differ).
- Genuine 10 m detail in MNDWI.

See [`M1_LIMITATIONS.md`](M1_LIMITATIONS.md) and
[`SCIENCE_PROTOCOL.md`](SCIENCE_PROTOCOL.md).
