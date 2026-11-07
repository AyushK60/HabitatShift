# M4-R1 handoff

**Status:** complete, ready for user review. Branch `m4-studies`, based on
the M4 baseline `dd8f13e` (verified before any change: 313 pytest / 39+10
browser checks). M5 not started. No deployment, no external push.

M4-R1 delivered the user-review corrections (brief §1–§14) **plus** the
additional guided-interpretation feature (brief §15, "What Changed?").
Diagnosis with measured reproduction evidence for every reported issue:
`docs/M4_R1_DIAGNOSIS.md`. Fix-by-fix verification record:
`docs/M4_R1_VISUAL_QA.md`.

---

## 1. What M4-R1 delivered

1. **Navigation (G1):** "Explore the Atlas" opens the study gallery;
   `/workstation` presents a study-selection experience (all six
   investigations, honest statuses) instead of forcing Coringa; direct
   study URLs unchanged.
2. **Gallery (G1):** uniform 3-column/2-row editorial grid (tablet 2-col,
   mobile 1-col), consistent card heights and 4:3 media, lead card keeps
   its copper identity without breaking the rhythm.
3. **Map reliability (G3):** the later map is never orphaned again (the
   cell stays mounted; CSS hides it) — fixes the blank later image and the
   swipe "stop responding" after tab switches. Opacity mode composites on
   the primary map (true endpoints, genuine 50 % blend, live pan/zoom,
   zero image reloads while dragging).
4. **Quality accounting (G2):** outside-AOI pixels are reported separately
   from masked-inside-AOI pixels, with correct denominators, for all six
   investigations; validity layers clarify "observation validity ≠ image
   quality".
5. **Imagery comparison (G4):** one joint two-period stretch for the
   colour composites of all M4 studies (Kathmandu's ~15 % brightness
   mismatch removed), provenance records updated, bundles rebuilt; native
   resolution shown beside the imagery with an honest "10 m cannot resolve
   buildings" note. Coringa's frozen reference untouched.
6. **Fit Entire Study Area (G5):** one control restores the complete AOI
   extent, synchronized across both maps.
7. **Experiments selector (G6):** all six investigations selectable; every
   section labelled Recorded experiment / Descriptive measurement /
   Planned — not available; works without backend.
8. **What Changed? (G7+G8, brief §15):** findings generated from the frozen
   Δ-rasters (connected components, MMU 25 px, true grid geometry → WGS84,
   full audit trail per finding, deterministic study-specific templates)
   and embedded in the bundles; a fourth workstation view renders the
   regions as subdued overlays with a guided findings panel (overview,
   per-index groups, interpretation cards with measurement, meaning,
   explanations, evidence strength, cannot-conclude, source rasters);
   click-to-select in both directions; Reset View; "What am I looking at?"
   layer guide; PARTIAL framing preserved for D1/D2; showcase-mode safe.
9. **Regression suite (G9):** 9 new M4-R1 browser checks (quality
   accounting, map lifecycle, opacity endpoints, What Changed?, layer
   guide, fit control, resolution tag) + 11-check showcase suite (incl.
   no-backend What Changed?) + 50 findings-integrity pytest tests.
   Suite-harness fixes: cwd-independent evidence paths, exact-match
   locators, NDBI-guardrail user-flow check.

## 2. Verification results (all re-runnable)

| Check | Result |
|---|---|
| Backend tests (`python -m pytest`) | **363 passed** (313 + 50 findings tests) |
| Browser suite with backend (`node tools/visual/verify_m4.mjs`) | **49 passed, 0 failed** |
| Showcase suite without backend (`node tools/visual/verify_m4_showcase.mjs`) | **11 passed, 0 failed** |
| Production build (`cd frontend && npm run build`) | clean |
| Bundle integrity tests after findings embedding | 21/21 (in the pytest total) |

Screenshots and machine results: `docs/evidence/m4-r1/`,
`docs/evidence/m4/m4_browser_results.json`,
`docs/evidence/m4/showcase_no_backend_results.json`.

## 3. Running it

```powershell
cd frontend && npm run build        # already built; emits frontend/dist
cd ..
python -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port 8098
# open http://127.0.0.1:8098/   (any static server on frontend/dist = showcase)
```

Regeneration pipelines (rarely needed):

```powershell
python scripts/regenerate_comparable_previews.py   # joint-stretch colour previews (M4 studies only)
python scripts/generate_findings.py                # What-Changed findings → data/findings/
python scripts/build_showcase_bundles.py           # rebuild website bundles (re-hashes assets)
```

Order matters: previews → findings → bundles.

## 4. Map of the M4-R1 code

```
frontend/src/workstation/StudyPicker.tsx     /workstation study-selection experience
frontend/src/workstation/MapCompare.tsx      map lifecycle fix, opacity composition, findings overlay,
                                             fit/focus actions, resolution tag
frontend/src/workstation/Inspector.tsx       coverage accounting, FindingsPanel, LayerGuidePanel
frontend/src/workstation/layers.ts           Analysis + what_changed pool, layerGuide()
frontend/src/pages/WorkstationPage.tsx       study-selector routing (keyed remount), What-Changed wiring
frontend/src/pages/ExperimentsPage.tsx       study selector + truthful availability panel
frontend/src/pages/LandingPage.tsx           Atlas CTA → gallery scroll
frontend/src/api/bundle.ts                   findings types + FeatureCollection adapter
scripts/generate_findings.py                 findings generation (schema habitatshift-findings/1)
scripts/regenerate_comparable_previews.py    joint-stretch preview re-render
scripts/build_showcase_bundles.py            embeds findings per experiment
backend/tests/test_m4_r1_findings.py         50 findings-integrity tests
tools/visual/verify_m4.mjs                   49-check browser suite (incl. 9 M4-R1 checks)
tools/visual/verify_m4_showcase.mjs          11-check no-backend suite
docs/M4_R1_DIAGNOSIS.md                      G0 root causes with measured evidence
docs/M4_R1_VISUAL_QA.md                      fix-by-fix verification record
docs/evidence/m4-r1/                         screenshots
```

## 5. Git checkpoints

| Commit | Gate |
|---|---|
| `9a4218d` | M4-R1 G0 baseline verified + all issues diagnosed |
| `682e968` | G1 navigation + gallery |
| `fa66bd8` | G3 map lifecycle + opacity composition |
| `876bef0` | G2 quality accounting |
| `4df276e` | G4 joint stretch + resolution transparency |
| `8d96839` | G5 Fit Entire Study Area |
| `01a722e` | G6 Experiments study selector |
| `fed49a1` | G7 findings generation pipeline |
| `fe0b7c2` | G8 What Changed? workstation experience |
| (this commit) | G9 regression suites, visual QA, handoff docs |

## 6. Honest limitations

- **Kathmandu's detail limit is the data**, not the rendering: 10 m
  Sentinel-2 over a ≈2×2.3 km AOI. The interface now labels this instead
  of hiding it; no paid/licensed imagery was introduced (would need
  approval per §8).
- **Findings are candidate signals.** The MMU (25 px) and recorded
  thresholds bound what becomes a finding; seasonal/tidal/snow confounders
  are stated per study in every interpretation card. D1 keeps its recorded
  PARTIAL framing throughout.
- **Findings do not exist for experiments without defensible regions** —
  the panel then says exactly that (an empty list means "insufficient
  evidence", never an invented polygon).
- The **previews were regenerated** for the M4 studies (joint stretch,
  provenance updated); analytical rasters, indices, thresholds and the
  Coringa frozen reference are untouched.
- The one-frame stale-render fix (keyed remount) also resets
  analysis/inspector state on study switches — intentional; it is what
  prevents cross-study state leakage.
- The in-app-browser session used during QA observed the same behaviour as
  the Playwright suites; no additional platform-specific issues are known.

Stop after M4-R1. M5 not started. The user will personally review the
corrected website before accepting M4.

**Primary objective preserved:** all existing scientific outputs, study
bundles, comparison modes, charts and quality functions remain operational
(verified by the full suites), while navigation, maps, opacity, image
presentation and interpretation are now dependable for a non-expert
visitor.
