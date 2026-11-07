# M4-R2 Evidence Record Schema

**Status:** M4-R2 G4 deliverable. Defines the versioned evidence records
carried by every finding. Implementation: `scripts/generate_findings.py`
writing schema `habitatshift-findings/2`; each finding carries an embedded
Evidence Record of schema `habitatshift-evidence-record/1`.

## Versioning

- Container: `habitatshift-findings/2` — a strictly additive evolution of
  `habitatshift-findings/1`. Every /1 field keeps its name, type and meaning;
  the /2 additions are per-finding `evidence_id`, `hole_pixel_count`,
  interior rings in `geometry_wgs84`, and the embedded `evidence` record.
- Record: `habitatshift-evidence-record/1` with an integer `schema_version`
  inside `identification`.
- Rule: measurement-bearing fields never change meaning across versions. A
  changed threshold convention, MMU or geometry rule is a new schema version,
  not a silent edit.

## Stable identification

`evidence_id` is content-derived and stable across regenerations:

```
ev-<experiment_id>-<index>-<dec|inc>-<centroid_utm_x_m>-<centroid_utm_y_m>
```

e.g. `ev-kathmandu_m4-ndbi-inc-333838-3066494`. It survives re-ordering and
top-K reshuffles as long as the region itself persists; the positional
`display_id` ("Region 03") remains the UI label only. Both views (Explore the
Evidence and Research Mode) reference findings by `evidence_id`.

## Record layout

Structured measurements live in `finding.evidence`; the deterministic
explanatory text stays in `finding.interpretation` and belongs to the record
by reference (`geometry_wgs84_ref`, `confounding_factors`). Numbers are never
duplicated into prose for computation — prose interpolates them for display
only.

| Group | Key fields |
|---|---|
| `identification` | `evidence_id`, `finding_id`, `display_id`, `schema_version`, `study_id`, `experiment_id`, `finding_type` (`threshold-connected-region`), `candidate_direction`, `evidence_status` (incl. `partial` for D1) |
| `source_observations` | earlier/later `item_ids` (scene IDs), `observation_dates`, `anchor_date`, `composite_method`, `observation_count`, `valid_pixels`, `aoi_pixels`, `valid_fraction`; `dataset` (collection, provider, license, processing level, attribution); `study_aoi` (bounds, area, pixels) |
| `input_measurements` | index, label, formula, bands, native band resolution + resolution note, `delta_definition` (`I_later − I_earlier`), `threshold`, `threshold_rule` (`|ΔI| ≥ t` inclusive), delta raster path + sha256, valid-mask path + sha256, `analysis_grid` (CRS, resolution, size, transform, pixel area) |
| `spatial_measurements` | `pixel_count`, `area_ha` + area units/convention, `mean_delta`, `median_delta`, `valid_pixel_denominator`, `share_of_common_valid_percent`, `hole_pixel_count`, centroids (UTM + WGS84), geometry reference |
| `evidence_quality` | earlier/later valid fractions, `shared_valid_fraction_of_aoi`, `observation_support` (counts + minimum required), `masking_and_cloud_limitations` (study's recorded limitations), `threshold_sensitivity` (computed G6 evaluation — see below), `confounding_factors` (deterministic study-specific list) |
| `relationships` | `overlap_rule` + `links[]`: every same-experiment finding whose equal-area UTM polygon overlaps this one by ≥ 10 % of the smaller region. `relation` is `same-direction-overlap` (multiple measurements of one candidate change — not independent events) or `opposite-direction-overlap` (different candidate signals in the same area, e.g. vegetation vs water). Cross-index only (same-index components are disjoint by construction); strongest overlap first, max 8 links. Nothing is merged or discarded. |
| `method_provenance` | `algorithm`, `algorithm_version` (pipeline version), `parameters` (threshold, MMU px + ha, top-K, connectivity), `input_hashes` (delta + mask sha256), `source_experiment_run` (experiment id, run timestamp, pipeline verification result), `git_commit`, `software` (numpy/rasterio/scipy/pyproj versions), `generated_utc`, `output_checksum` |
| interpretation (by reference) | `finding.interpretation`: title, location, observation period, observed measurement, meaning, explanations, evidence strength, cannot-conclude, source |

## Threshold sensitivity (descriptive, never a score)

`evidence_quality.threshold_sensitivity` records, per finding, the
containing component's behaviour at t ± 0.05 (max-overlap tracking) and a
transparent descriptive label with its exact rule:

- **spatially persistent across tested thresholds** — ≥ 80 % of the region's
  pixels remain candidates at t + 0.05 and the component stays within 2× at
  both neighbours;
- **threshold-sensitive** — < 50 % retained at t + 0.05, or the component
  grows beyond 3× / shrinks below ⅓× at a neighbour;
- **moderately threshold-sensitive** — everything in between.

A threshold-stable label is **not** a verified-change statement; it says the
candidate footprint is robust to the threshold choice. The sensitivity
evaluation does not consider observation-selection variability, reference-data
uncertainty or classification uncertainty — those are different uncertainty
sources and are not claimed to be covered.

## Honesty rules

1. **No invented values.** Any field the pipeline cannot supply is `null`
   with an explanatory `status` string (e.g. `threshold_sensitivity.result`
   is `null` until G6 computes it). Nothing is estimated or defaulted.
2. **Sealed checksums.** Each record's `output_checksum` is the SHA-256 of
   the canonical JSON of its whole finding with the checksum field null —
   any later edit of any measurement invalidates it. The independent audit
   (`scripts/audit_findings_m4r2.py`) re-verifies every checksum.
3. **Geometry completeness.** `geometry_wgs84` is a full GeoJSON Polygon:
   ring 0 is the component exterior; interior rings are the masked pixels
   enclosed by the component (`hole_pixel_count` records their total area in
   pixels). The analytical `pixel_count`/`area_ha` exclude holes and remain
   the measurement of record; display renders the holes as holes.
4. **Separation of concerns.** Structured numbers (`evidence`) and
   explanatory text (`interpretation`) are separate; neither is the source
   of the other.

## Relationship to the recorded legacy fields

`pixel_count`, `area_ha`, `mean_delta`, `median_delta`,
`share_of_common_valid_percent`, `common_valid_pixels`, `threshold`,
`input_raster`, `valid_mask` remain the flat fields consumed by the
frontend and bundles; `evidence` carries the same values plus provenance and
quality context. The two are written in one pass from the same computation
and sealed together by the checksum.
