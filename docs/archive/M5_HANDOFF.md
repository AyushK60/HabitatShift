# M5 handoff

**Status: complete, ready for user review.** Branch `m5-release` (10 commits,
`7af80ac`…`e16a46b`), based on `m4-r3-experiences` @ `d892ca4`. No ML beyond
the label-gated experiments, no deployment, no external push, no M6.
Frozen M0–M4 scientific outputs untouched.

## What was delivered, gate by gate

| Gate | Commit | Outcome |
|---|---|---|
| G0 baseline | `7af80ac` | M4-R3 acceptance re-verified by execution (all suites green before any change); baseline recorded |
| G1 scientific audit | `f436d7e` | `scripts/audit_m5_science.py` — 3184 checks, no production imports; live STAC + COG verification; **one provenance defect (I1) found and corrected** with backups + root-cause fix + regression test; three limitations documented (I2–I4) |
| G2 label feasibility | `a7f78f4` | every reference source probed live; **PASS ×3, PARTIAL ×1, BLOCKED ×2**; no labels manufactured; Dynamic World excluded; JRC GSW gap recorded honestly |
| G3 supervised ML | `352375e` | 2021-epoch training imagery via the audited chain; RF with 1 km block folds; agreement-with-reference framing; per-class support gating; geographic hold-out analysis; audit 107/107 incl. bit-for-bit retraining |
| G4 K-means | `a836cf7` | two studies only, by design; clusters never interpreted as classes or change |
| G5 robustness | `a5d13d7` | MMU sensitivity (7 experiments), bootstrap block-size sensitivity, ML feature-withhold; five uncertainty categories kept separate |
| G6 integration | `04e7785` | additive ML layer in the product (Explore + Research Mode) from generated artifacts; verify 23/23 live + showcase; disclosure audit 96/96 |
| G7 reliability | `9df26b3` | pip-audit: 89 advisories found → upgraded to zero; fresh-venv reproduction of chilika_m4_dry **byte-identical**; start/stop scripts incl. duplicate guard verified; audit extended to 4111/4111 |
| G8 release prep | `e16a46b` | README + ARCHITECTURE / METHODOLOGY / RESULTS / LIMITATIONS / DATA_PROVENANCE / SETUP_GUIDE / FINAL_AUDIT with diagrams |

## Final verification state (all re-run at the end)

- pytest **404** · build clean · scientific audit **4111/4111** (live)
- findings audit **2837** · M2 audit **149** · disclosure audit **106**
- ML audits **107/107** and **96/96**
- browser suites **51 / 35 / 31 / 23** live, **17 / 23** showcase (backend stopped)
- pip-audit: **zero known vulnerabilities**
- fresh reproduction: statistics identical, 9/9 GeoTIFFs byte-identical
- start.bat / stop.bat / duplicate guard: verified

## Where the ML numbers live

`data/experiments/m5_ml/<study>/<run>/result.json` (sealed with manifests),
additively surfaced in the product via `frontend/public/studies/m5ml_findings.json`
(`habitatshift-m5ml-findings/1` containers referencing the frozen
`habitatshift-findings/2` records by SHA-256). The frozen records are
byte-identical to M4-R3.

## Honest headline

The platform now has: an independently audited processing chain (live
source-verified), label-gated Random Forests whose every metric is framed as
agreement with a reference product (never ground truth), measured
sensitivity analyses, a reproduced-from-source pipeline (byte-identical), a
security-clean dependency set, and complete documentation. The scientific
claims remain candidate spectral signals — that is the point, not a gap.

## Remaining options (not started, awaiting direction)

- GitHub push / deployment — requires explicit user approval.
- JRC Global Surface Water integration (endpoint search failed in the
  feasibility window; recorded as a future upgrade).
- Resolution-sensitivity reprocess (20 m) — available on demand.
- Complete-component inventory mode (M4-R3 suggestion).
- M6 / world-scale exploration — explicitly out of scope per the brief.
