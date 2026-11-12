# M1 limitations

This file lists what the M1 engine and the Coringa result **cannot** support.
It is deliberately blunt: the fastest way to misuse a spectral-change product
is to forget which question it did not answer.

---

## 1. Scope limits

- M1 is a two-period comparison, not a time series. Each period is summarised
  by at most three observations; inter-annual change is represented by two
  composites.
- M1 does not classify land cover, detect objects, train a model, or attribute
  cause. M2 and M3 are out of scope.
- M1 does not establish that a change is ecologically meaningful, desirable,
  degraded or permanent.
- M1 covers one small AOI (`coringa_coastal`, ~16.5 km²). Nothing here
  generalises to the Godavari delta, to other mangroves, or to the Himalaya.

---

## 2. Temporal and physical confounders

The 2020 and 2025 periods are **seasonally** matched (late March, ±30-day
anchor window). They are not physically matched:

- tidal stage at acquisition is uncontrolled and can move the water boundary
  by more than a pixel in these creeks;
- turbidity and suspended sediment change water reflectance independently of
  water extent;
- phenology, rainfall, salinity and human management differ between years;
- atmosphere, sun angle and view geometry differ; the provider L2A correction
  reduces but does not eliminate these effects;
- the three sensors used (S2A, S2B, S2C) have small inter-sensor differences.

A ΔNDVI or ΔNDWI signal can therefore reflect tide, turbidity, phenology or
atmosphere rather than a change in habitat. The engine does not correct for
these; it records the dates and scenes so a reviewer can judge them.

---

## 3. Compositing limits

- A median of two or three observations is a robust but coarse summary. It can
  suppress a real sub-period event and can blend different physical states.
- `min_observations = 1` means some pixels are represented by a single
  observation. The per-pixel count raster and count statistics expose this;
  the engine does not fill the gap.
- Compositing is done on reflectance, then indices are computed. This is the
  documented and tested choice, but it is not interchangeable with
  median-of-index.
- Selecting observations within ±30 days of an anchor reduces seasonal
  mismatch but does not remove it.
- If fewer observations are available, the run reports the limitation and
  proceeds; it does not claim the same confidence as a three-observation
  composite.

---

## 4. Masking limits

- Cloud, shadow, cirrus, saturated and nodata removal relies on the provider
  SCL product. SCL errors propagate directly.
- Thin cirrus and cloud edges can remain, especially where SCL class 10 is
  absent or misclassified.
- Terrain shadow is not independently re-derived.
- SCL class 11 (snow/ice) is accepted by the shared policy. It does not occur
  at Coringa, but a future Himalayan run must not assume this policy means
  "glacier change is validated".
- The mask is conservative in the sense that any non-finite fetched band makes
  the pixel invalid. It cannot recover information that the provider did not
  deliver.
- Masked pixels are excluded, not interpolated. Change statistics therefore
  describe the common-valid footprint, which may be a biased subset of the AOI
  when cloud patterns differ between dates. At Coringa the common-valid
  footprint happens to be 100 % of the AOI; that is a property of this run, not
  a guarantee.

---

## 5. Resolution limits

- NDVI and NDWI use 10 m bands and are genuine 10 m products.
- MNDWI, NDSI and NDBI use native 20 m SWIR (B11) resampled bilinearly to the
  10 m grid. **They contain no genuine 10 m SWIR detail.** Their effective
  resolution is 20 m, and the interpolation can create smooth gradients that
  look like fine structure but are not.
- Mixed pixels are unavoidable at 10 m in a mangrove/creek complex: a pixel can
  contain vegetation, water and mud. Index values are mixtures, not pure
  endmembers.
- Resampling continuous reflectance with bilinear interpolation and categorical
  SCL with nearest is correct policy, but neither reconstructs information
  below the source resolution.

---

## 6. Threshold and statistical limits

- The thresholds 0.10 / 0.15 / 0.20 are **candidate** index-unit thresholds
  chosen for sensitivity display, not statistically calibrated change
  detectors.
- A threshold crossing is not a significance test. No null model, no
  confidence interval, no multiple-comparison correction and no spatial
  autocorrelation adjustment is applied.
- Pixel counts are not independent samples; neighbouring pixels are strongly
  correlated. Treating `n` pixels as `n` independent observations would
  overstate confidence.
- Percentages are of the common-valid footprint, not of the AOI. When the
  footprint is smaller than the AOI, percentages can look larger than the
  AOI-relative share.
- Changing the threshold changes the area substantially. The sensitivity table
  is provided precisely so no single number is presented as *the* answer.

---

## 7. Area limits

- Areas are planimetric on `EPSG:32644`, using a constant 100 m² pixel. UTM
  scale distortion at this AOI is small but nonzero.
- The rasterised AOI differs from the polygon by boundary rasterisation
  (relative difference `1.47 × 10⁻⁴` here).
- Surface area on sloping terrain is not modelled; this coastal AOI is
  effectively flat, but the method would understate area on slopes.
- Hectare and square-kilometre values are conversions from projected square
  metres, not independently surveyed areas.
- The geodesic cross-check validates order of magnitude and projection
  behaviour; it is not a cadastral measurement.

---

## 8. Radiometry limits

- Surface reflectance is the provider L2A product. No independent atmospheric
  correction, BRDF correction or adjacency correction is performed.
- The scale/offset policy handles the baseline-04.00 offset trap and
  `boa_offset_applied`, and cross-baseline items are tested. It still depends
  on catalogue metadata being correct.
- Negative reflectance is treated as invalid rather than clipped. That is
  honest, but it removes pixels near the noise floor.
- Water reflectance is low and sensitive to sun glint, turbidity and bottom
  reflectance in shallow creeks. NDWI/MNDWI differences over water should be
  read with that in mind.

---

## 9. Alignment and reprojection limits

- Every input is warped once onto one documented grid. This prevents mixed
  grids, but it does not guarantee sub-pixel co-registration between dates.
- A systematic half-pixel shift would appear as edge-concentrated difference
  signal. The engine does not estimate or correct such a shift.
- Bilinear resampling of 20 m SWIR to 10 m smooths spatial detail; nearest
  resampling of SCL preserves class codes but can produce blocky masks.
- The grid signature is a configuration fingerprint, not a geodetic accuracy
  statement.

---

## 10. Reproducibility limits

- The committed run is reproducible offline from cached catalogue responses
  and observation arrays. It is not a guarantee that a fresh network run years
  later will select the same scenes: the catalogue can change, and cache
  entries can be absent.
- Byte-identical GeoTIFFs were demonstrated on the same software stack. A
  different GDAL/rasterio/NumPy version, or a different CPU/libm, can change
  compression bytes or last-bit floating-point results.
- Timestamps, duration fields and HTTP counters naturally differ between runs;
  they are not part of the scientific result.
- The manifest records software versions so a mismatch is visible.

---

## 11. API and viewer limits

- The API is read-only, unauthenticated and bound to localhost for this study.
  It is not a deployment-ready service.
- The viewer shows stored artefacts; it performs no science in the browser.
- The M1 viewer is a minimal extension of the M0 proof viewer, not the M3
  product UI.
- Legends are fixed per index so periods are comparable; they are not
  automatically stretched to each period's distribution.
- A screenshot of the browser verification could not be captured because the
  browser tool requires a visible desktop tab. The verification evidence is
  DOM/network based; no image is claimed.

---

## 12. Interpretation guardrail

The following sentences are **not** supported by this work:

- "192.91 ha of mangrove was lost."
- "143.98 ha of wetland was restored."
- "MNDWI increase proves permanent water gain."
- "NDVI decrease is deforestation."
- "The delta is degrading."
- "Glacier area changed" (NDSI is a tested primitive only, not interpreted).
- "Urban expansion occurred" (NDBI is a tested primitive only, not
  interpreted).

Supported sentences look like:

- "At a candidate threshold of |ΔNDVI| ≥ 0.15, 192.91 ha of the 1,651.36 ha
  common-valid footprint had a lower later-period NDVI and 143.98 ha had a
  higher later-period NDVI, using a median composite of up to three
  observations per period."
- "This is an observed spectral difference. Tidal stage, turbidity, phenology
  and atmosphere are uncontrolled and could contribute to the signal."

See [`SCIENCE_PROTOCOL.md`](SCIENCE_PROTOCOL.md) for the claim rules that apply
to every M1 output.
