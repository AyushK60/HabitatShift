# HabitatShift — limitations

The complete limitation record lives with the work that produced it:

| Document | Scope |
|---|---|
| [`M1_LIMITATIONS.md`](M1_LIMITATIONS.md) | first engine: single-scene deltas, mask policy limits |
| [`M2_LIMITATIONS.md`](M2_LIMITATIONS.md) | threshold sweeps, estimator families, bootstrap assumptions |
| [`M4_R3_HANDOFF.md` §6](M4_R3_HANDOFF.md) | product/experience limits (curated top-5 selection, export caveats) |
| [`M5_LIMITATIONS.md`](M5_LIMITATIONS.md) | M5 findings: ML framing, cross-epoch assumption, bright-snow reflectance, cache orphans, deferred resolution sensitivity |

## The five statements that matter most

1. **Candidate signals only.** Every finding is a measured spectral change
   candidate. The platform does not verify environmental change, does not
   predict disasters, and does not monitor in real time.
2. **No independent ground truth exists in this project.** ML metrics are
   agreement with the ESA WorldCover v200 reference product. Agreement is
   consistency, never accuracy against reality.
3. **The curated top-5 selection is not an inventory.** Audited counts of
   unrecorded qualifying components are disclosed in-product per experiment.
4. **The radiometry convention for the 2025 Earth Search reprocessing is
   empirically validated per read** (metadata still declares an offset the
   stored DNs do not carry); the physical floor test plus the baseline guard
   are the recorded defence, and the decision evidence is stored per
   observation.
5. **Scope is five small AOIs between fixed past dates.** Generalisation
   beyond them — other regions, other years, operational use — is neither
   designed for nor claimed.
