# M4 radiometry incident: the 2025 Earth Search DN convention

**Status:** diagnosed and fixed during M4-G1; all M4 results use the corrected
convention; the frozen Coringa M0–M2 artefacts were verified unaffected.

## What happened

The first Western Ghats run produced a physically impossible result: the 2025
composite was valid (SCL 100 %) but yielded usable NDVI on only 2.3 % of
pixels. The Chilika dry-season run showed a dramatic 2020→2025 "water-to-land
flip" — which, on inspection, was the same artifact.

## Diagnosis (measured, not assumed)

Direct windowed reads of the source COGs showed:

| Item | baseline | `boa_offset_applied` | B02 DN (window) | with declared −0.1 | scale-only |
|---|---|---|---|---|---|
| `S2B_43PDS_20250222_0_L2A` | 05.11 | false | mean 167 | **−0.083 (impossible)** | 0.017 ✓ |
| `S2B_45QUB_20250210_0_L2A` | 05.11 | false | mean 935 | **−0.007 (impossible)** | 0.094 ✓ |
| `S2C_45QUB_20250215_0_L2A` | 05.11 | false | mean 705 | **−0.030 (impossible)** | 0.071 ✓ |
| `S2B_45QUB_20251117_1_L2A` | 05.11 | true | mean 583 | 0.058 ✓ (scale-only) | — |
| `S2B_44QPD_20250325_0_L2A` | 05.11 | true | mean 830 | 0.083 ✓ (scale-only) | — |

BOA reflectance of any daytime natural surface is non-negative in the window
mean; a mean below −0.005 is only reachable by applying an offset that does
not match the stored DNs. Conclusion: the 2025-reprocessed baseline-05.11
items store `DN = reflectance × 10000` **without** the baked +1000 offset,
while their metadata still declares −0.1 with
`earthsearch:boa_offset_applied: false`. The engine's documented policy
(trust the flag, else apply the declared offset) therefore double-corrected
these items. No authoritative per-product offset is exposed by the
catalogue's metadata assets (checked `granule_metadata.xml`,
`tileinfo_metadata.json`, `raster:bands`).

Which runs were affected: every processed observation that resolved to the
declared −0.1 offset — all three 2025-02 Chilika dry observations, all three
2025-02 Western Ghats observations. Which were not: Coringa M0/M1/M2 (their
2025 scenes carry `boa_offset_applied: true` and were always processed
scale-only; the 2020 scenes predate baseline 04.00), the Chilika
post-monsoon 2025 observations, and the Kathmandu 2025 observations
(flag-true).

## The fix (backend/app/acquisition/assets.py, engine.py, composite.py)

1. **Empirical acceptance test.** After converting DNs with the declared
   convention, any band whose window mean falls below the physical floor
   (−0.005) rejects the transform. The scale-only alternative is then applied
   and must itself be plausible; if neither convention is plausible the
   observation is refused outright (`RadiometryError`) rather than guessed.
2. **Provenance.** Every corrected record's `source` string carries a
   deterministic marker, and the measured evidence (which bands failed, their
   means, finite-pixel counts) is stored per observation in the run manifest
   and in the showcase bundles (`radiometry_evidence`).
3. **Cache safety.** Observation cache keys now embed a radiometry policy
   version (`RADIOMETRY_POLICY_VERSION`), so no record written under the old
   policy can ever be silently reused; cache loads re-validate the stored
   radiometry against the recorded decision and discard any record whose
   cached reflectance fails the physical-plausibility check.
4. **Tests.** `backend/tests/test_m4_radiometry.py` (8 tests) pins the
   rejection, the scale-only fallback, the hard-refusal path, cache round-trip
   of corrected records, and the corrupt-cache discard.

## Aftermath

All four G1 studies and both G2 investigations were re-run under the
corrected policy. The corrected results are physically coherent (e.g. Chilika
2025 dry season reads as water again, matching 2020), and every affected
observation carries its correction evidence in the manifest. The lesson is
recorded in the Methods page: radiometric conventions are validated against
the pixels actually read, never trusted from metadata alone.
