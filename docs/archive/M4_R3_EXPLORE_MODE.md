# M4-R3 — Explore the Evidence

The public-facing experience over the HabitatShift evidence engine. Audience:
a person with no remote-sensing or GIS background. Lives inside each study
workstation as the What Changed? analysis's "Explore the Evidence" inspector
tab (integrated with — not replacing — the existing Historical / Change /
Quality views).

## Entry

- Open any study: `/#/workstation/<study_id>` → "What changed?" analysis →
  "Explore the Evidence" tab.
- Direct link to a finding:
  `/#/workstation/<study_id>?finding=<evidence_id>` (optionally
  `&view=research` for the technical record).

## What the visitor sees

1. **Overview summary** — derived only from the study's findings container:
   recorded candidate findings with decrease/increase split, the indices
   involved, the number of recorded overlapping-measurement links (and how
   many regions they touch), observation period, shared-valid footprint with
   the correct denominator wording, and the minimum mapping unit.
2. **Curated-selection disclosure** — states the top-5-per-index-direction
   rule, the recorded count, the audited count of additional qualifying
   components that were NOT recorded, and that the list is not a complete
   inventory. Counts come from `studies/selection_policy.json`, generated
   from the independent audit artifact by `scripts/build_selection_policy.py`
   (152 recorded / 1,520 qualifying / 1,368 unrecorded across all studies).
   When the artifact is unavailable, the policy text renders without counts —
   counts are never invented.
3. **Filters** — direction, index, threshold behaviour (the recorded
   persistent / moderate / sensitive categories), overlap availability, and a
   region text search. Filters only narrow the recorded list; the UI says so.
   No confidence score exists anywhere.
4. **Finding list** — grouped by index, each entry showing display id,
   direction and area.
5. **Selected finding card** — the eight guided questions:
   - What was observed? (recorded observed-measurement statement)
   - Where was it observed? (location description + centroid; region
     highlighted on the map)
   - When was it observed? (earlier/later composite periods)
   - What was measured? (mean/median Δ with units, threshold, candidate area
     with hole accounting, shared-valid denominator, share of footprint)
   - What does it mean? (cautious recorded interpretation)
   - What could explain it? (recorded possibilities incl. confounders)
   - How much evidence supports it? (observation counts, valid coverage,
     threshold behaviour in plain language with the recorded category named,
     related-measurement count)
   - What should we not conclude? (recorded limitations)
   plus clickable **Overlapping measurements** (never presented as
   independent events) and an **Open the Research Mode record →** link.
6. **Study limitations** footer.

## Map integration

Real evidence-region polygons only (GeoJSON verbatim from the records),
muted direction colours, teal highlight for the selection, hover tooltip with
the stable region identifier, click-to-select (isolated from the pixel-probe
click), fly-to on selection, Reset View for the full study area, and a
Finding-regions overlay toggle.

## Guarantees

- Every displayed value is read through the shared evidence adapter
  (`frontend/src/evidence/adapter.ts`) from the same evidence record Research
  Mode shows — one source, no recomputation.
- The selection, the URL, the map highlight and both cards all carry the
  stable content-derived `evidence_id`.
- Candidate language everywhere; a threshold-stable finding is never called
  verified change; PARTIAL studies say so prominently.
