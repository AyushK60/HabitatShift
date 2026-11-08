# HabitatShift — final audit (end of M5)

**Branch `m5-release` (base `m4-r3-experiences` @ `d892ca4`), 2026-11-08.**
No deployment, no external push. This ledger lists every verification that
was executed at the end of M5, with its result.

## 1. Verification battery (final state, upgraded dependency set)

| Check | Result |
|---|---|
| Backend tests (`pytest`) | **404 passed** (project venv AND fresh venv from requirements alone) |
| Frontend production build (tsc + vite) | clean |
| M5 independent scientific audit (`audit_m5_science.py`, live) | **4111 passed, 0 failed** |
| M4-R2 findings audit (`audit_findings_m4r2.py`) | **2837 passed, 0 failed** |
| M2 numerical audit (`audit_m2.py`) | **149/149** |
| M4-R3 disclosure audit (`audit_m4r3_disclosure.py`) | **106/106** |
| M5-ML reproducibility audit (`audit_m5_ml.py`) | **107/107** (bit-for-bit retraining) |
| M5-ML disclosure audit (`audit_m5ml_disclosure.py`) | **96/96** (negation-aware claim scan) |
| `verify_m4.mjs` (browser) | 51/51 |
| `verify_m4_r3.mjs` (browser, incl. 4 viewports) | 35/35 |
| `verify_m2_experiments.mjs` (browser) | 31/31 |
| `verify_m5_ml.mjs` (browser, live) | 23/23 |
| `verify_m4_showcase.mjs` (backend stopped) | 17/17 |
| `verify_m5_ml.mjs` (backend stopped) | 23/23 |
| `pip-audit` on pinned requirements | **zero known vulnerabilities** (89 found before the M5-G7 upgrades) |
| Fresh-environment reproduction (`reproduce_m5_fresh.py`) | change statistics identical; 9/9 GeoTIFFs **byte-identical** |
| `start.bat` / duplicate guard / `stop.bat` isolation | verified (§ M5_G7_RELIABILITY.md) |

## 2. Issues found during M5 and their disposition

| # | Issue | Found by | Disposition |
|---|---|---|---|
| I1 | 30 stale output checksums in the six M4 manifests (M4-R1 G4 preview regeneration never refreshed provenance) | M5-G1 audit | **Corrected**: backups + outputs-only repair + root-cause fix in the regeneration script + regression test (`test_manifest_output_checksums.py`) |
| I2 | 6 superseded-policy cache records on disk (non-physical reflectance) | M5-G1 audit | Documented; provably unloadable (policy-versioned keys + load-time re-validation); corrected siblings verified |
| I3 | Reflectance > 1.0 on bright Himalayan snow/ice pixels (max ~1.66 blue) | M5-G1 audit | Documented limitation (SCL class 11 is deliberately valid); index algebra bounds the effect; no invented correction |
| I4 | Duplicate cache records with differing band sets | M5-G1 audit | Documented; auditors match records by band coverage |
| I5 | verify_m4_r3 regression: ML evaluation table shared the `sensitivity-table` selector | browser suite | Fixed (dedicated `ml-eval-table` class); suite back to 35/35 |
| I6 | 89 dependency advisories (starlette/requests/Pillow/pytest) | pip-audit (M5-G7) | Upgraded to fixed versions; re-audit clean; full battery re-verified |
| I7 | Audit experiment-extraction crashed on the new M5-ML training manifests (`study` as string) | M5-G7 re-run | Fixed; the audit ledger now also live-verifies the 2021 training items (3184 → 4111 checks) |

## 3. What was deliberately NOT done

- No push to GitHub, no deployment, no public exposure, no purchases — per
  the brief, awaiting explicit user approval.
- No M6 / world-scale exploration started.
- No mangrove labels manufactured for Coringa (source disagreement recorded).
- No supervised ML for the Himalayan studies (label gate BLOCKED by design).
- No resolution-sensitivity reprocess (deferred with recorded rationale).
- Frozen M0–M4 scientific outputs untouched (the only writes were the I1
  checksum-record repairs, outputs-only, backed up, verified).

## 4. Acceptance criteria check (brief §12)

1. Scientific chain independently audited — ✅ 4111 checks, no production imports.
2. Radiometry and source-data conventions verified — ✅ live, per asset class.
3. ML feasibility assessed for all six investigations — ✅ PASS×3 / PARTIAL×1 / BLOCKED×2.
4. Supervised models only where labels justify — ✅ 4 studies, 1 partial-scoped.
5. Geographically independent validation — ✅ 1 km block folds + 3-fold hold-out ranges.
6. ML compared with mathematical baselines — ✅ recorded per study, disagreements kept.
7. Uncertainty and limitations documented — ✅ five separate categories, never one score.
8. Explore + Research Mode consistent — ✅ one adapter, one artifact, verified 23+23.
9. All existing study bundles reproducible — ✅ audits + byte-identical fresh reproduction.
10. Portable Showcase works — ✅ 17+23 checks with the backend stopped.
11. Startup/shutdown scripts safe — ✅ duplicate guard + pid isolation verified.
12. Fresh-environment reproduction succeeds — ✅ fresh venv, byte-identical rasters.
13. Documentation and GitHub-ready materials complete — ✅ see the doc map in the README.
