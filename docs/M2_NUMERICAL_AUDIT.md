# M2 — Numerical audit

**Auditor:** `scripts/audit_m2.py` (independent of the experiment engine's
threshold/estimator code paths)
**Target run:** `20261107T102819Z_d70f3978`
**Result:** **149/149 checks passed**, machine-readable record at
`data/experiments/m2/coringa_m2/<run>/audit_m2_results.json`.

Reproduce:

```powershell
.\.venv\Scripts\python.exe scripts\audit_m2.py
```

---

## Why the checks are not circular

A check is only meaningful if the two sides come from different code or
different storage. Every audit check pairs one of:

1. **Fresh numpy expressions** — classification is re-derived with
   `valid & (delta <= -t)` style masks written directly in the audit script,
   never by importing `thresholds.classify_delta`.
2. **Independent storage** — areas are recomputed from the exported
   GeoTIFF's own affine transform (`|a·e| = 100 m²`), not from the summary's
   `pixel_area_m2` field.
3. **Independent formats** — CSV tables are parsed and compared against
   `result.json` values field by field.
4. **API layer** — the viewer summary endpoint is queried in-process and
   compared against the recorded JSON it claims to serve.

## Check inventory (149 total)

| Group | Checks | What is verified |
|---|---|---|
| 1. Threshold classes from rasters | 105 | For each of 3 indices × 5 thresholds: decrease/stable/increase pixel counts recomputed from the exported delta raster match the recorded rows; decrease area equals count × transform-derived pixel area; transform pixel area is exactly 100 m². Classes partition the valid footprint; composite mean delta recomputed from period rasters matches the recording and the frozen M1 headline (±1e-6). |
| 2. Sweep monotonicity | 6 | Recorded decrease/increase counts are non-increasing as the threshold tightens, for every index. |
| 3. Estimator arithmetic | 12 | Single pairs = 3×3; leave-one-out = 3+3; two composites per index; all estimators conserve area; the M0 estimator appears once (NDVI only). |
| 4. Bootstrap containment | 32 | Every 95 % percentile interval contains its point estimate for decrease and increase at every threshold and index; recorded iterations used == requested. |
| 5. CSV consistency | 2 | Row count == estimators × thresholds; every row's counts and mean-delta match `result.json`. |
| 6. Manifest hashes | 3 | Every artifact hash verifies; git commit recorded; software versions recorded. |
| 7. Input provenance | 3 | M1 summary hash equals the run's recorded input hash; M1 config present; cache inventory = 6 observations. |
| 8. Supervised-metric absence | 2 | No accuracy/F1/confusion-matrix/precision/recall/IoU keys anywhere in `result.json`; label status recorded as blocked. |
| 9. API agreement | 3 | `/api/experiments/coringa_m2/latest` serves the same run and identical numbers. |

## Selected frozen regressions re-verified

- Composite means reproduce the M1 headline exactly:
  NDVI −0.020471, NDWI +0.018959, MNDWI −0.006188.
- M0 ↔ M1 anchor single-scene NDVI: identical on all 158,168 shared pixels
  (max |difference| 0.0), footprint differs by 22 pixels (mask policy).
- All M0/M1 files: no modification (see `M2_VERIFICATION.md`).

## Known audit limits

- The audit reads the same exported rasters the engine used. It verifies
  internal consistency and correct arithmetic, not the correctness of the
  underlying satellite observations (that is bounded by the sensor and the
  provider's L2A processing).
- The bootstrap containment check verifies internal coherence of the
  resampling output; the assumptions themselves (block exchangeability) are
  stated and argued in `M2_UNCERTAINTY.md`, not provable from data alone.
