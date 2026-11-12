# M5-G1 — Independent scientific audit

**Status:** complete — 3184/3184 independent checks pass (plus 404 backend
tests, 2837 M4-R2 findings checks, 149 M2 checks, 106 disclosure checks).
Branch `m5-release`, 2026-11-08.

Auditor script: `scripts/audit_m5_science.py` (per-check ledger in
`docs/evidence/m5/audit_m5_science_checks.json`). **The auditor imports
nothing from `backend.app`** — every recomputation (indices, deltas, masks,
threshold classes, median composites, the spatial block bootstrap, live STAC
metadata, live COG window reads) is an independent re-implementation written
from the documented spec, so a shared bug cannot hide in an imported
production function.

## 1. Scope and method

| Section | What was verified | How |
|---|---|---|
| A — Satellite source verification | All 40 unique Sentinel-2 L2A items across the 7 experiment manifests (M0 verified via its anchor-scene linkage to Coringa M1) | **Live** Earth Search STAC queries: item id ↔ acquisition date, sensor/platform, processing baseline, per-asset `raster:bands` scale/offset/nodata/native resolution, `earthsearch:boa_offset_applied`, `proj:epsg` vs analysis grid |
| B — Radiometry review | Every observation's DN→reflectance convention | Recorded-decision classification, policy-consistency rules, pixel-wise re-validation of 58 current-policy cache records, **live COG window reads** re-measuring declared vs scale-only reflectance on the real pixels |
| C — Processing verification | The full processing chain | Raster-level recomputation (indices from composites, deltas, common-valid masks, threshold classes, area arithmetic, grid alignment, output checksums), composites rebuilt bit-for-bit from the observation cache, M2 block bootstrap reproduced from the cache with the recorded seed |

## 2. A — Source verification results

- 40/40 unique items: live STAC metadata matches every recorded field
  (acquisition datetime, baseline, sensor, scale 0.0001, nodata 0, native
  GSD 10 m visible / 20 m SWIR, `proj:epsg` = analysis grid EPSG).
- Item-id-embedded dates match recorded acquisition dates (all 40).
- Processing baselines span 02.14 (2020 Coringa items) to 05.11 (2025/2026
  reprocessed items); recorded per observation.
- Grid alignment: all rasters within each study share one CRS/transform/
  signature; the raster grid equals the manifest grid (all 7 experiments).

## 3. B — Radiometry review

### 3.1 Convention classification (all 40 processed observations)

| Convention | Count | Meaning |
|---|---|---|
| `no_offset_declared` (raw DN, pre-04.00 baseline) | 8 | Coringa/Kathmandu/WG 2020 items on baseline 02.14–03.xx; catalog declares offset 0; scale-only applied |
| `offset_applied_scale_only` (scaled DN, offset baked) | 26 | `earthsearch:boa_offset_applied=true`; effective offset resolved to 0.0; **no double correction** |
| `empirical_scale_only` | 6 | The six 2025-02 Chilika-dry/Western-Ghats items from the M4 radiometry incident: declared transform measured non-physical, scale-only applied with recorded band-mean evidence |
| `declared_offset_applied` | **0** | No observation in the corpus applies the −0.1 offset; the code path exists and is exercised by tests, but no processed scene required it |

Policy-consistency assertions (all pass): no record carries both an applied
−0.1 offset and an empirical-correction marker (double-offset guard); every
empirically corrected record carries its measured evidence (verdict, failing
band means below the −0.005 physical floor, finite-pixel denominator); no
pre-04.00 record applies an offset.

### 3.2 Live product-level verification (per convention, real COG pixels)

The auditor re-read each sample item's blue band warped onto the exact
analysis grid and measured window means under both transforms:

| Item (class) | declared (−0.1) mean | scale-only mean | Verdict |
|---|---|---|---|
| `S2C_45QUB_20250215_0_L2A` (empirical) | **−0.0295 (non-physical)** | +0.0705 | recorded scale-only decision correct; independently measured failing mean matches the recorded evidence |
| `S2A_44QPD_20200326_1_L2A` (offset-applied) | −0.0739 | +0.0261 | double-applying −0.1 would be non-physical; the engine's flag-based scale-only resolution is correct |
| `S2B_44QPD_20200321_0_L2A` (no-offset, baseline 02.14) | −0.0006 (hypothetical) | +0.0994 | catalog itself declares offset 0 for pre-04.00; recorded decision correct |

**Boundary-case observation (recorded, no action):** for the pre-04.00 item
`S2B_44QPD_20200321_0_L2A`, a hypothetical (never-declared, never-applied)
−0.1 transform yields a window mean of −0.0006 — *above* the −0.005
empirical floor. The empirical acceptance test alone would not have caught a
wrongly applied offset on that particular scene; the baseline guard
(`resolve_offset` hard-rejects any offset on baselines < 04.00) is what
prevents it. This is defence in depth working as designed; noted for the
record.

### 3.3 Negative-value semantics

No cached current-policy record contains negative reflectance in any band
window (0 small-negative pixels across 58 records); no stored value is at DN
scale. In the Himalayan records, a small number of SCL-valid pixels exceed
reflectance 1.0 (bright snow/ice; see §5, issue I3).

## 4. C — Processing verification results

Per experiment (Coringa M1 + six M4 investigations):

- **Indices reproduced from exported reflectance composites** with an
  independent normalised-difference implementation (max diff ≤ 1e-6; NaN
  patterns identical).
- **Deltas** reproduced as later − earlier (≤ 1e-6); **common-valid masks**
  reproduced as the period-mask intersection (exact); **threshold classes**
  reproduced at the recorded primary thresholds (exact); decrease/increase/
  stable pixel counts and areas (px × 100 m² / 10 000) match the recorded
  summaries exactly; shares use the common-valid denominator.
- **Median composites rebuilt bit-for-bit from the observation cache**
  (per-observation stored reflectance → median over ≥ min_observations →
  index) — max diff 0.0 on every band and index, all 7 experiments. This
  validates the whole chain DN → radiometry → masking → compositing → index
  from the cached evidence alone.
- **M2 spatial block bootstrap reproduced bit-for-bit** from the cached
  observations with the recorded design (seed 20260326, block 15 px, 200
  iterations, thresholds 0.05–0.25): every decrease/increase/mean-delta
  percentile matches the recorded CIs to < 1e-9.
- **Output checksums**: every manifest output file verified byte-for-byte
  (after correction I1 below).
- **Area cross-checks**: recorded projected-vs-geodesic differences are all
  < 1 %, consistent with UTM-local AOIs.

## 5. Issues found (expected / actual / evidence / root cause / impact / correction / verification)

### I1 — Stale output checksums in all six M4 manifests (found and corrected)

- **Expected:** every manifest `outputs` entry hashes to its file.
- **Actual:** 30/312 output checksums mismatched in the six M4 manifests —
  exactly `earlier/later_true_colour.png`, `earlier/later_false_colour.png`
  and `summary.json` per study; every scientific output (all GeoTIFFs) was
  clean. Coringa M1 and M0 manifests verified fully.
- **Evidence:** `scripts/audit_m5_science.py` checksum section;
  `git show 4df276e --stat` (M4-R1 G4 rewrote exactly those files).
- **Root cause:** M4-R1 G4's `scripts/regenerate_comparable_previews.py`
  re-rendered the colour PNGs with the joint two-period stretch and rewrote
  `summary.json` (stretch-provenance fields) but never refreshed the
  manifests' `outputs` sha256/bytes records.
- **Impact:** provenance drift only — presentation-layer artifacts and
  stretch metadata. No scientific number was affected: all rasters verified,
  the M4-R2 findings audit (2837 checks) and the M2 audit (149) still pass
  against the same files, and the summary's science fields are re-derived
  from the rasters by both audits.
- **Correction:** (a) `scripts/repair_m4_output_checksums.py` refreshed the
  30 drifted records, with pre-repair manifest backups in
  `docs/evidence/m5/backup_manifests_before_checksum_repair/` and an
  outputs-only diff verification (no other manifest key changed);
  (b) the regeneration script now refreshes bytes/sha256 for every artifact
  it rewrites, so the drift cannot recur; (c) new regression test
  `backend/tests/test_manifest_output_checksums.py` walks all manifests and
  fails on any future drift.
- **Verification:** M5 audit re-run: 3184/3184; pytest 404 passed (incl. the
  new test); all prior audits unchanged.

### I2 — Superseded-policy cache records retained on disk (found, documented)

- **Expected:** the observation cache contains only records loadable under
  the current radiometry policy.
- **Actual:** 6 orphan records written under the pre-fix (declared-offset)
  policy remain in `data/cache/observations/`, alongside their corrected
  siblings. They store non-physical reflectance (e.g. blue mean −0.0833).
- **Evidence:** cache keys embed `RADIOMETRY_POLICY_VERSION`
  (`2026-11-07-empirical-boa-1`), so the engine cannot load the orphans; each
  orphan has a corrected sibling with the same grid signature and item.
- **Impact:** none at runtime (policy-versioned keys + load-time
  re-validation); disk-hygiene and audit-clarity only.
- **Correction:** none applied to the cache (deleting data is riskier than
  the risk it removes; the load path provably discards them). The auditor
  now classifies them explicitly and verifies each has a corrected sibling.
- **Verification:** B2 section: 58 current-policy records plausible, 6
  orphans with verified siblings.

### I3 — Reflectance above 1.0 on bright snow/ice pixels (found, documented as a limitation)

- **Expected:** BOA reflectance of natural surfaces is ≤ 1.
- **Actual:** in the two Himalayan studies, a small number of SCL-valid
  (snow/ice class 11) pixels carry reflectance up to ~1.66 (blue).
- **Evidence:** cache re-validation, 845 130 pixels > 1.0 across cached
  windows, all at SCL-valid bright-snow/cloud pixels.
- **Root cause:** Sen2Cor BOA over very bright snow/steep terrain plus
  sub-pixel cloud contamination; class 11 is deliberately accepted by the
  cryosphere mask policy.
- **Impact:** bounded — index algebra keeps values interpretable (|index| > 1
  → NaN), and the affected pixels are a small minority; no correction
  invented. Carried into `M5_LIMITATIONS.md` as a known measurement
  limitation for the Himalayan studies.
- **Verification:** B2 asserts any >1.0 value stays within
  bright-target magnitude (< 3.0) and reports the counts.

### I4 — Duplicate cache records with differing band sets (found, documented)

- **Expected:** one cache record per (item, grid, policy).
- **Actual:** several items (all Purepu, some others) have two records with
  different `band_keys` (4-band fetch from an earlier index set, 5-band
  later), pixel-identical on shared bands.
- **Impact:** none for results (the engine's composite path always uses the
  record matching the run's band request); a trap for naive cache consumers,
  which this audit script now handles explicitly (band-coverage matching).
- **Correction:** auditor selection hardened; production untouched.

## 6. Frozen outputs preserved

No frozen scientific result was modified. The only writes to pre-existing
artifacts were the 30 checksum-record updates of correction I1 (outputs-only,
backed up, verified) — files whose bytes themselves were already the M4-R1
G4 artifacts in git-ignored local storage with git-tracked manifests.
`data/findings/*`, all GeoTIFFs, the M2 experiment results, showcase bundles
and their checksums are untouched.

## 7. Reproduce

```bash
python scripts/audit_m5_science.py          # 3184 checks (network for live sections)
python scripts/repair_m4_output_checksums.py  # idempotent; verifies outputs-only
pytest backend/tests/test_manifest_output_checksums.py
```
