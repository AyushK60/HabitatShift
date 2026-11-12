# Version 2 changes

Everything is additive: recorded study outputs and sealed records are untouched.

## Science

| Change | Where | Check |
|---|---|---|
| Noise-aware change test (change vs scene-to-scene noise) | `scripts/run_noise_aware_threshold.py`, `data/experiments/m6_noise/` | recomputed fixed-rule counts equal the sealed manifests (test) |
| Independent validation, Western Ghats vs Hansen forest loss | `scripts/run_validation_hansen.py`, `data/experiments/m6_validation/` | confusion matrix sums to the evaluated pixels (test) |
| Monthly time series with seasonal fit, Kathmandu and Western Ghats | `scripts/run_time_series.py`, `data/experiments/m6_timeseries/` | one scene per month, bounded values (test) |
| 20 m resolution sensitivity for all studies with a 10 m run | `scripts/run_m5_resolution_sensitivity.py` | 10 m side equals the recorded manifest (test) |
| JRC GSW vs WorldCover water cross-check, complete component inventory | `data/experiments/m5_gsw/`, `m5_inventory/` | tests |

## Product

- "Your own area" page: bounded change analysis for a drawn box (`backend/app/pipeline/custom_run.py`).
- Experiments page: noise test, validation, monthly series, scenes behind each composite, complete inventory.
- Sharper maps: bicubic enlargement for colour composites, crisp pixels for data layers (display only).
- Study report and provenance export, guided tour, scene availability check.
- Plain-language wording replaces internal milestone labels; a "Why this project exists" section on the landing page.

## Repository

- Build-history documents moved to `docs/archive/`; audit scripts moved to `verification/`.
- Line endings normalised so diffs show real changes only.

## Not done

- Ground-truth validation (only other satellite products are used).
- Radar (Sentinel-1) flood mapping, the natural follow-up to the original motivation.
- Hosted deployment, push, demo video.
- Time series for the other studies (the script runs for any configured study; monsoon-heavy areas will have many gaps).
- Retraining with GSW labels (would alter sealed results).
