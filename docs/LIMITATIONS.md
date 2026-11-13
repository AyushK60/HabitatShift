# Limitations

## The five statements that matter most

1. **Candidate signals only.** Every finding is a measured spectral change that might be real. The project does not
   verify environmental change, does not predict disasters and does not monitor in real time.
2. **No independent ground truth.** The machine learning numbers are agreement with the ESA WorldCover v200 map,
   which is another satellite product with its own errors. Agreement is consistency, not accuracy against reality.
3. **The curated top-5 list is not a full inventory.** The app shows the five largest changed patches per index and
   direction. The counts of patches not shown are disclosed per experiment, and a complete component inventory
   exists in `data/experiments/m5_inventory/`.
4. **Sentinel-2 radiometry needed care for 2025 data.** The 2025 Earth Search reprocessing declares a reflectance
   offset that its stored values do not carry. Each read is checked against a physical floor test, and the decision
   evidence is stored per observation.
5. **Small areas, fixed dates.** The studies cover a handful of small areas between fixed past dates. Other regions, other years and operational use are not claimed.

## More detail

Older limitation records are kept as written at the time:

| Document | Scope |
|---|---|
| [`archive/M1_LIMITATIONS.md`](archive/M1_LIMITATIONS.md) | first engine: single-scene differences, mask policy limits |
| [`archive/M2_LIMITATIONS.md`](archive/M2_LIMITATIONS.md) | threshold sweeps, estimator families, bootstrap assumptions |
| [`archive/M4_R3_HANDOFF.md`](archive/M4_R3_HANDOFF.md) (section 6) | product limits: curated selection, export caveats |
| [`archive/M5_LIMITATIONS.md`](archive/M5_LIMITATIONS.md) | machine learning framing, cross-epoch assumption, bright-snow reflectance, cache orphans |
