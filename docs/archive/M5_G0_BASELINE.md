# M5-G0 baseline record

**Date:** 2026-11-08. **Branch:** `m5-release` (created from `m4-r3-experiences`
@ `d892ca4`), working tree clean at checkpoint. Frozen M0–M4 outputs under
`data/` were not modified.

## M4-R3 acceptance precondition

`M4_R3_HANDOFF.md` records M4-R3 as complete: both research experiences
(Explore the Evidence, Research Mode) delivered over the sealed evidence
records with one shared read path, plus G0–G7 gates, disclosure audit, and
visual QA. This was re-verified by execution rather than trusting the
handoff (results below).

## Baseline battery (all re-run on this branch, before any M5 change)

| Check | Command | Result |
|---|---|---|
| Backend tests | `python -m pytest` | **403 passed**, 0 failed (18.2 s) |
| Frontend production build | `npm run build` (tsc + vite) | clean |
| M4-R2 findings audit (evidence-record integrity, all 7 containers) | `python scripts/audit_findings_m4r2.py` | **2837 passed, 0 failed** (coringa_m1, chilika_m4_dry, chilika_m4_postmonsoon, western_ghats_m4, himalaya_purepu_2025_m4, himalaya_langtang_2026_m4, kathmandu_m4) |
| M2 independent numerical audit | `python scripts/audit_m2.py` | **149/149** |
| M4-R3 disclosure audit | `python scripts/audit_m4r3_disclosure.py` | **106/106** |
| `verify_m4_r3.mjs` (browser, backend up) | 35 passed, 0 failed |
| `verify_m4.mjs` (browser, backend up) | 51 passed, 0 failed |
| `verify_m2_experiments.mjs` (browser, backend up) | 31 passed, 0 failed |
| `verify_m4_showcase.mjs` (browser, **backend stopped**) | **17 passed, 0 failed** |

All six investigation bundles (`data/findings/*.json` — Kathmandu, Western
Ghats, Coringa, Chilika dry, Chilika post-monsoon, Purepu, Langtang) are
covered by the 2837-check M4-R2 audit with per-container totals.

## Startup / shutdown scripts

- `start.bat --nopause`: verified — dependency + build checks OK, duplicate
  detection consulted, picked a free port (preferred 8098 was transiently
  occupied at that moment; it started on 8100), served the app, wrote
  `.runtime` records.
- `stop.bat --nopause`: verified — stopped exactly its managed pid (21724),
  removed runtime records, explicitly reported an unrelated port-8100
  listener as "not ours and left untouched", and the server was confirmed
  down (connection refused). No unrelated process was touched.

## Notes for M5

- The investigation set is: Kathmandu Valley, Western Ghats, Coringa,
  Chilika (dry + post-monsoon experiments), Purepu (PARTIAL), Langtang
  (optical-only limitations). Himalayan investigations stay on their
  scientific questions; no forced land-cover ML there.
- The M4 radiometry incident doc (`M4_radiometry_incident.md`) is the entry
  point for the M5-G1 radiometry review.
- Evidence-record inventory boundary for ML feasibility: the 152 sealed
  records are findings, not labels; no region is a label.
