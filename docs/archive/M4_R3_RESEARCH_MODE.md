# M4-R3 — Research Mode

The technical investigation experience over the HabitatShift evidence
engine. Audience: technical users, students, professors, supervisors and
reviewers. It exposes the real computational foundation of each finding —
it is not the public explanation with harder words. Lives in the workstation
as the What Changed? analysis's "Research Mode" inspector tab.

## Opening a record

- Select a finding in Explore the Evidence → "Open the Research Mode record →".
- Click a region on the map → Research Mode tab.
- Direct link: `/#/workstation/<study_id>?finding=<evidence_id>&view=research`.

## What the record shows (per selected evidence_id)

1. **Identification** — display id, finding type, candidate direction,
   evidence status, study/experiment, container schema
   (`habitatshift-evidence-record/1`), checksum-sealed.
2. **Mathematical method** — only the operations actually recorded for this
   finding: the index definition with its bands and the band-resolution
   note (e.g. NDBI from SWIR/NIR; 20 m-native bands upsampled to the 10 m
   grid), `ΔI = I_later − I_earlier` with the record's own delta
   definition, the candidate-selection inequality (`ΔNDBI ≤ −0.15` /
   `ΔNDVI ≥ +t`, inclusive), what the threshold controls, the component
   pipeline (`threshold candidate mask → 4-connected components → MMU
   filter → top-K selection`) with the explicit curated-selection caveat,
   and the shared-valid denominator. Collapsible; no unrelated formulas.
3. **Source observations** — scene IDs, observation dates, composite
   method, dataset collection.
4. **Input measurements** — index formula, bands, delta definition,
   threshold, analysis grid (CRS, resolution, m²/px), delta-raster and
   valid-mask sha256 prefixes.
5. **Spatial measurements** — pixel count, area (ha), mean/median Δ, valid
   denominator, share of footprint, enclosed holes — with a levels note
   separating region summary / per-pixel values / study-wide summaries.
6. **Evidence quality** — shared-valid fraction, observation support,
   masking and cloud limitations.
7. **Threshold sensitivity** — the recorded label with its exact recorded
   rules, primary threshold, and the t ± 0.05 neighbours table (component
   pixels, retained fraction, growth factor). Explicitly a transparency
   category, not a confidence score.
8. **Relationships** — the recorded overlap rule plus clickable links to
   related evidence records (same/opposite-direction overlap, indices,
   overlap %). Opening one selects it **without leaving Research Mode**
   (§4.5); multiple measurements of one geography are labelled as not
   independent events.
9. **Method provenance** — algorithm + version, parameters, git commit,
   software versions, generation time, sealed output checksum.
10. **Exports** — verbatim record JSON and a deterministic
    `section,field,value` CSV (`evidenceRecordToCsv` in the shared
    adapter), both client-side and available offline in Showcase Mode.

## Guarantees

- Same payload as Explore the Evidence: one `selectedEvidenceId`, one
  `BundleFinding`, zero recomputation. The suite verifies UI numbers equal
  the record numbers (area, mean Δ, denominator, sensitivity neighbours)
  to the recorded display precision.
- Fields the pipeline cannot supply stay `unavailable` — never invented.
- Working without the Python backend is verified by the showcase suite
  (17/17 with the backend stopped), including exports and deep links.
