/** Research inspector — the right-hand analytical rail of the workstation.
 *
 * Sections: layer legend & meaning, the "What am I looking at?" layer guide
 * (M4-R1 §15.5), guided findings (§15.3), acquisition context, pixel probe
 * (server-measured full-resolution values) and the ROI tool.
 */
import { useState } from "react";
import type { G0Quality, M1Summary, PixelSample, RoiResult } from "../api/types";
import type { BundleFindings, StudyBundle } from "../api/bundle";
import {
  buildEvidenceOverview,
  mlRecordForExperiment,
  type MlContainer,
  type MlFindingsIndex,
  evidenceRecordToCsv,
  findingByEvidenceId,
  formatPercent,
  relatedFindingsFor,
  selectionForExperiment,
  sensitivityKey,
  sensitivityPlainLanguage,
  thresholdSensitivity,
  formatHa,
  type SelectionPolicy,
} from "../evidence/adapter";
import type { Analysis, AssetResolver, LayerSpec } from "./layers";
import { layerGuide, layerLegend, qualityExplanation } from "./layers";
import type { RoiBox } from "./MapCompare";

interface InspectorProps {
  summary: M1Summary;
  studyId: string;
  resolver: AssetResolver;
  layer: LayerSpec;
  quality: G0Quality | null;
  bundle: StudyBundle;
  /** True when the live backend serves this study's frozen M1 outputs. */
  live: boolean;
  analysis: Analysis;
  findings: BundleFindings | null;
  /** Stable content-derived evidence_id of the selected finding (M4-R3). */
  selectedEvidenceId: string | null;
  onSelectFinding: (evidenceId: string | null) => void;
  /** Select a record while staying in Research Mode (§4.5 related links). */
  onSelectRecord: (evidenceId: string | null) => void;
  /** Open the Research Mode record for the same evidence_id. */
  onOpenResearch: () => void;
  /** Generated top-five selection disclosure; null when unavailable. */
  selectionPolicy: SelectionPolicy | null;
  /** M5 additive ML reference index; null when unavailable. */
  mlFindings: MlFindingsIndex | null;
  pixel: PixelSample | null;
  pixelError: string | null;
  pixelLoading: boolean;
  cursor: [number, number] | null;
  roiMode: boolean;
  roiBox: RoiBox | null;
  roiResult: RoiResult | null;
  roiError: string | null;
  roiLoading: boolean;
  onToggleRoi: () => void;
  tab: InspectorTab;
  onTabChange: (tab: InspectorTab) => void;
}

export type InspectorTab =
  | "legend"
  | "guide"
  | "findings"
  | "evidence"
  | "context"
  | "pixel"
  | "roi";

const REFLECTANCE_LABELS: Record<string, string> = {
  blue_B02: "B02 blue",
  green_B03: "B03 green",
  red_B04: "B04 red",
  nir_B08: "B08 NIR",
  swir1_B11: "B11 SWIR¹",
};

function Facts({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="insp-facts">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Measured coverage accounting with the correct denominators (M3 §8,
 *  M4-R1 §4). Outside-AOI pixels and masked-inside-AOI pixels are distinct
 *  quantities and are never merged into one number. */
function QualityCoverage({ quality }: { quality: G0Quality | null }) {
  const coverage = quality?.coverage;
  const px = (value: number | undefined) =>
    value === undefined ? "n/a" : value.toLocaleString("en-GB");
  const pctOfAoi = (pixels: number | undefined) =>
    coverage && pixels !== undefined
      ? `${((pixels / coverage.aoi_pixels) * 100).toFixed(1)}% of AOI`
      : "";
  const uniform = coverage?.uniform_common ?? false;
  // Derived with pure display arithmetic from the recorded counts; the two
  // footprint differences are kept separate (M4-R1 §4).
  const aoi = coverage?.aoi_pixels;
  const grid = coverage?.grid_pixels;
  const common = coverage?.common_valid_pixels;
  const outsideAoi = coverage?.outside_aoi_pixels ??
    (aoi !== undefined && grid !== undefined ? Math.max(0, grid - aoi) : undefined);
  const maskedInsideAoi = coverage?.masked_inside_aoi_pixels ??
    (aoi !== undefined && common !== undefined ? Math.max(0, aoi - common) : undefined);
  const earlierInvalidInside =
    aoi !== undefined && coverage?.earlier_valid_pixels !== undefined
      ? Math.max(0, aoi - coverage.earlier_valid_pixels)
      : undefined;
  const laterInvalidInside =
    aoi !== undefined && coverage?.later_valid_pixels !== undefined
      ? Math.max(0, aoi - coverage.later_valid_pixels)
      : undefined;
  return (
    <div className="quality-coverage">
      <h4 className="insp-subheading">Measured coverage</h4>
      <Facts
        rows={[
          ["AOI pixels (study window)", px(coverage?.aoi_pixels)],
          ["Grid pixels (rectangular raster footprint)", px(coverage?.grid_pixels)],
          ["Outside AOI, inside grid footprint", `${px(outsideAoi)} (not observations)`],
          [
            "Earlier valid inside AOI",
            `${px(coverage?.earlier_valid_pixels)} ${pctOfAoi(coverage?.earlier_valid_pixels)}`,
          ],
          [
            "Later valid inside AOI",
            `${px(coverage?.later_valid_pixels)} ${pctOfAoi(coverage?.later_valid_pixels)}`,
          ],
          [
            "Earlier-invalid inside AOI",
            `${px(earlierInvalidInside)} ${pctOfAoi(earlierInvalidInside)}`,
          ],
          [
            "Later-invalid inside AOI",
            `${px(laterInvalidInside)} ${pctOfAoi(laterInvalidInside)}`,
          ],
          [
            "Shared valid (both periods)",
            `${px(coverage?.common_valid_pixels)} ${pctOfAoi(coverage?.common_valid_pixels)}`,
          ],
          [
            "Masked inside AOI (≥1 period unusable)",
            `${px(maskedInsideAoi)} ${pctOfAoi(maskedInsideAoi)}`,
          ],
        ]}
      />
      {uniform ? (
        <p className="insp-note insp-meaning">
          Earlier, later and shared valid are byte-identical masks for this
          study: every one of the {px(coverage?.aoi_pixels)} AOI pixels is a
          usable observation in both periods, so shared valid = earlier ∧ later
          is the same footprint by construction. Identical validity maps are
          the expected scientific result here, not a rendering fault. The
          observation-count layers are where genuine per-pixel variation lives.
        </p>
      ) : (
        <p className="insp-note insp-meaning">
          Coverage is partial: some AOI pixels are missing in at least one
          period. Only the shared-valid intersection enters the difference
          maps; masked pixels are never filled.
        </p>
      )}
      <p className="insp-note">
        Two different footprint differences appear above and are kept separate:
        the {px(outsideAoi)} pixels outside the AOI but inside the rectangular
        grid are simply not part of the study window (not cloud damage), while
        the {px(maskedInsideAoi)} masked-inside-AOI pixels were excluded by the
        SCL quality flags in at least one period. SCL flags do not record a
        per-pixel masking cause, so no specific cause is claimed anywhere.
      </p>
    </div>
  );
}

function PixelProbe({
  pixel,
  error,
  loading,
}: {
  pixel: PixelSample | null;
  error: string | null;
  loading: boolean;
}) {
  if (loading) return <p className="insp-note">Sampling full-resolution rasters…</p>;
  if (error) return <p className="insp-note insp-error">{error}</p>;
  if (!pixel) {
    return (
      <p className="insp-note">
        Click anywhere on the map to read the measured values at that pixel.
        Values are sampled server-side from the full-resolution GeoTIFFs — never
        from the preview images.
      </p>
    );
  }
  if (pixel.status === "outside_grid") {
    return (
      <p className="insp-note">
        This location is outside the analysis grid ({pixel.utm.epsg}). The
        rasters cover the rectangular footprint shown by the copper AOI frame.
      </p>
    );
  }
  return (
    <div className="pixel-probe">
      <p className="mono-label probe-coords">
        {pixel.query.lon.toFixed(5)}°E, {pixel.query.lat.toFixed(5)}°N · UTM{" "}
        {pixel.utm.x.toFixed(0)}, {pixel.utm.y.toFixed(0)} · pixel{" "}
        {pixel.pixel.col}, {pixel.pixel.row} · {pixel.resolution_m} m
      </p>
      {pixel.periods?.map((period) => (
        <div key={period.period_id} className="probe-period">
          <h4>
            {period.period_id === "earlier" ? "Earlier" : "Later"} ·{" "}
            {period.anchor_date}
          </h4>
          <p className="mono-label">
            {period.valid
              ? `Valid observation · ${period.observation_count} obs behind this pixel`
              : "Masked at this pixel — no measured composite value"}
          </p>
          {period.valid && period.reflectance && (
            <table className="probe-table">
              <tbody>
                {Object.entries(period.reflectance).map(([band, value]) => (
                  <tr key={band}>
                    <th>{REFLECTANCE_LABELS[band] ?? band}</th>
                    <td>{value === null ? "n/a" : value.toFixed(4)}</td>
                  </tr>
                ))}
                {Object.entries(period.indices).map(([key, value]) => (
                  <tr key={key} className="probe-index">
                    <th>{key.toUpperCase()}</th>
                    <td>{value === null ? "n/a" : value.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
      {pixel.common_valid && (
        <p className="mono-label probe-delta">
          {Object.entries(pixel.common_valid)
            .filter(([key]) => key.endsWith("_delta"))
            .map(([key, value]) => {
              const index = key.replace("_delta", "");
              return typeof value === "number"
                ? `Δ${index.toUpperCase()} ${value >= 0 ? "+" : ""}${value.toFixed(4)}`
                : `Δ${index.toUpperCase()} masked`;
            })
            .join(" · ")}
        </p>
      )}
      <p className="mono-label probe-source">Source: {pixel.source}</p>
    </div>
  );
}

function RoiPanel({
  roiMode,
  roiBox,
  roiResult,
  roiError,
  roiLoading,
  onToggle,
}: {
  roiMode: boolean;
  roiBox: RoiBox | null;
  roiResult: RoiResult | null;
  roiError: string | null;
  roiLoading: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="roi-panel">
      <div className="roi-actions">
        <button
          type="button"
          className={roiMode ? "toggle-btn is-active" : "toggle-btn"}
          aria-pressed={roiMode}
          onClick={onToggle}
        >
          {roiMode ? "Cancel drawing (Esc)" : "Draw ROI on map"}
        </button>
        {roiBox && !roiMode && (
          <span className="mono-label">
            {roiBox.west.toFixed(4)}°E–{roiBox.east.toFixed(4)}°E ·{" "}
            {roiBox.south.toFixed(4)}°N–{roiBox.north.toFixed(4)}°N
          </span>
        )}
      </div>
      {roiLoading && <p className="insp-note">Measuring ROI window server-side…</p>}
      {roiError && <p className="insp-note insp-error">{roiError}</p>}
      {roiResult && (
        <div className="roi-result">
          <p className="mono-label roi-source">{roiResult.source}</p>
          <p className="mono-label">
            Window {roiResult.window_px.width} × {roiResult.window_px.height} px
            @ {roiResult.resolution_m} m
          </p>
          {Object.entries(roiResult.indices).map(([key, block]) =>
            block.delta_stats ? (
              <div key={key} className="roi-block">
                <h4>{key.toUpperCase()} · later − earlier</h4>
                <table className="probe-table">
                  <tbody>
                    <tr>
                      <th>Common-valid px</th>
                      <td>{block.common_valid_pixels.toLocaleString("en-GB")}</td>
                    </tr>
                    <tr>
                      <th>Mean Δ</th>
                      <td>{block.delta_stats.mean.toFixed(4)}</td>
                    </tr>
                    <tr>
                      <th>5th–95th pct</th>
                      <td>
                        {block.delta_stats.p05.toFixed(3)} –{" "}
                        {block.delta_stats.p95.toFixed(3)}
                      </td>
                    </tr>
                    <tr>
                      <th>
                        Candidate decrease @ ±{block.primary_threshold}
                      </th>
                      <td>
                        {block.decrease_area_ha.toFixed(2)} ha
                      </td>
                    </tr>
                    <tr>
                      <th>Candidate increase @ ±{block.primary_threshold}</th>
                      <td>{block.increase_area_ha.toFixed(2)} ha</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : null
          )}
          <p className="insp-note">
            ROI thresholds reuse each index's recorded primary threshold; the
            window is measured from the same frozen GeoTIFFs as the stored
            study. Nothing here rewrites the scientific artefacts.
          </p>
        </div>
      )}
    </div>
  );
}

/** Explore the Evidence (M4-R3 §3) — the public-facing guided experience
 *  over the same evidence records Research Mode reads. Everything renders
 *  from the recorded findings payload through the shared adapter; no value
 *  is recomputed and no confidence score is invented. */
function ExploreFindingsPanel({
  findings,
  selectedId,
  onSelect,
  onOpenResearch,
  selectionPolicy,
  mlContainer,
}: {
  findings: BundleFindings | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onOpenResearch: () => void;
  selectionPolicy: SelectionPolicy | null;
  /** M5 additive ML reference experiment; null when unavailable. */
  mlContainer: MlContainer | null;
}) {
  const [filterDirection, setFilterDirection] = useState<"all" | "decrease" | "increase">("all");
  const [filterIndex, setFilterIndex] = useState<string>("all");
  const [filterSensitivity, setFilterSensitivity] = useState<string>("all");
  const [filterOverlap, setFilterOverlap] = useState<"all" | "with" | "without">("all");
  const [search, setSearch] = useState("");

  if (!findings) {
    return (
      <p className="insp-note">
        No findings file is recorded for this experiment. A finding appears
        only when a connected candidate region meets the documented minimum
        mapping unit at the recorded thresholds — none is ever invented.
      </p>
    );
  }
  const overview = buildEvidenceOverview(
    findings,
    selectionForExperiment(selectionPolicy, findings.experiment_id)
  );
  const selected = selectedId
    ? findingByEvidenceId(findings, selectedId) ?? null
    : null;
  const indicesOrder = [...new Set(findings.findings.map((f) => f.index))];

  const matches = findings.findings.filter((finding) => {
    if (filterDirection !== "all" && finding.direction !== filterDirection) return false;
    if (filterIndex !== "all" && finding.index !== filterIndex) return false;
    if (filterOverlap === "with" && (finding.evidence?.relationships?.links?.length ?? 0) === 0) return false;
    if (filterOverlap === "without" && (finding.evidence?.relationships?.links?.length ?? 0) > 0) return false;
    if (filterSensitivity !== "all") {
      const sensitivity = finding.evidence?.evidence_quality as
        | { threshold_sensitivity?: { label?: string } }
        | undefined;
      if (sensitivityKey(sensitivity?.threshold_sensitivity?.label) !== filterSensitivity) return false;
    }
    if (search.trim()) {
      const needle = search.trim().toLowerCase();
      const haystack = [
        finding.display_id,
        finding.interpretation.title,
        finding.interpretation.location,
      ].join(" ").toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    return true;
  });
  const filtersActive =
    filterDirection !== "all" ||
    filterIndex !== "all" ||
    filterSensitivity !== "all" ||
    filterOverlap !== "all" ||
    search.trim() !== "";

  return (
    <div className="findings-panel explore-panel">
      <h3 className="insp-heading">Explore the Evidence</h3>
      {overview.findings_total === 0 ? (
        <p className="insp-note insp-meaning">
          {overview.no_finding_statement ??
            "No defensible candidate region was identified for this comparison."}
        </p>
      ) : (
        <p className="insp-note insp-meaning">
          {overview.findings_total} recorded candidate findings:{" "}
          {overview.by_direction.decrease} candidate decrease,{" "}
          {overview.by_direction.increase} candidate increase, measured with{" "}
          {overview.indices.map((index) => `Δ${index.toUpperCase()}`).join(", ")}.
          These are candidate spectral signals from satellite measurements —
          not confirmed environmental events.
        </p>
      )}
      <dl className="insp-facts">
        <div>
          <dt>Observation period</dt>
          <dd>
            {overview.observation_period.earlier} → {overview.observation_period.later} (
            {findings.periods.earlier.composite_method} composites)
          </dd>
        </div>
        <div>
          <dt>Shared-valid footprint</dt>
          <dd>
            {overview.common_valid_pixels.toLocaleString("en-GB")} px ·{" "}
            {formatPercent(overview.common_valid_fraction_of_aoi, 1)} of AOI
          </dd>
        </div>
        <div>
          <dt>Overlapping measurements</dt>
          <dd>
            {overview.relationship_link_count} recorded links across{" "}
            {overview.findings_with_relationships} regions — separate
            measurements of one geography, never independent events
          </dd>
        </div>
        <div>
          <dt>Minimum mapping unit</dt>
          <dd>
            {overview.method.minimum_mapping_unit_px} px (
            {overview.method.minimum_mapping_unit_ha} ha) · smaller clusters
            are never reported
          </dd>
        </div>
      </dl>

      {overview.evidence_status === "partial" && (
        <p className="insp-note insp-guardrail partial-note">
          <strong>PARTIAL evidence.</strong> This investigation has restricted
          or incomplete observations — read the study limitations below and
          the per-finding cards before interpreting anything here.
        </p>
      )}
      {/* Curated-selection disclosure (M4-R3 §5). Counts come from the
          generated policy artifact (audited); wording never implies the
          recorded list is a complete inventory. */}
      <p className="insp-note insp-guardrail selection-disclosure">
        <strong>Curated selection.</strong>{" "}
        {overview.selection
          ? `The recorded rule keeps the largest ${overview.method.max_regions_per_index_direction} components per index and direction. This experiment records ${overview.selection.recorded_findings} findings; ${overview.selection.components_at_or_above_mmu_unrecorded_top5_cap} additional qualifying components met the minimum mapping unit but were not recorded and have no evidence records. `
          : "The recorded rule keeps the largest components per index and direction (exact counts unavailable offline). "}
        This list is not a complete inventory of every qualifying region.
      </p>
      {mlContainer && (
        <div className="ml-block" data-testid="explore-ml-block">
          <p className="insp-note insp-guardrail ml-plain">
            <strong>Additional ML reference experiment.</strong>{" "}
            {mlContainer.ml_record.plain_language}
          </p>
          <dl className="insp-facts">
            <div className="fact-row">
              <dt>Reference labels</dt>
              <dd>
                {mlContainer.ml_record.reference.dataset} ({mlContainer.ml_record.reference.epoch} epoch)
              </dd>
            </div>
            <div className="fact-row">
              <dt>Agreement (held-out test blocks)</dt>
              <dd>
                {(mlContainer.ml_record.evaluation.overall_agreement * 100).toFixed(1)} % with the
                reference product — not independent ground truth
              </dd>
            </div>
            <div className="fact-row">
              <dt>Status</dt>
              <dd>Model output against reference labels — never a measured observation</dd>
            </div>
          </dl>
        </div>
      )}
      {!mlContainer && (
        <p className="insp-note mono-label">
          ML reference experiment: no record is available for this study.
        </p>
      )}
      <p className="insp-note mono-label">
        Categories: candidate increase / candidate decrease / little measurable
        difference / insufficient evidence. "Insufficient evidence" is exactly
        what an empty list means.
      </p>

      {/* ---------------------------------------------- filters (§3.5) --- */}
      {overview.findings_total > 0 && (
        <div className="explore-filters" role="group" aria-label="Findings filters">
          <div className="explore-filter-row">
            <span className="control-label">Direction</span>
            <div className="segmented" role="group" aria-label="Direction filter">
              {(["all", "decrease", "increase"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  className={filterDirection === value ? "is-active" : ""}
                  aria-pressed={filterDirection === value}
                  onClick={() => setFilterDirection(value)}
                >
                  {value === "all" ? "All" : value === "decrease" ? "Decrease" : "Increase"}
                </button>
              ))}
            </div>
          </div>
          <div className="explore-filter-row">
            <span className="control-label">Index</span>
            <div className="segmented" role="group" aria-label="Index filter">
              <button
                type="button"
                className={filterIndex === "all" ? "is-active" : ""}
                aria-pressed={filterIndex === "all"}
                onClick={() => setFilterIndex("all")}
              >
                All
              </button>
              {indicesOrder.map((index) => (
                <button
                  key={index}
                  type="button"
                  className={filterIndex === index ? "is-active" : ""}
                  aria-pressed={filterIndex === index}
                  onClick={() => setFilterIndex(index)}
                >
                  {index.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div className="explore-filter-row">
            <span className="control-label">Threshold behaviour</span>
            <div className="segmented" role="group" aria-label="Threshold-sensitivity filter">
              {[
                ["all", "All"],
                ["persistent", "Persistent"],
                ["moderate", "Moderate"],
                ["sensitive", "Sensitive"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={filterSensitivity === value ? "is-active" : ""}
                  aria-pressed={filterSensitivity === value}
                  onClick={() => setFilterSensitivity(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="explore-filter-row">
            <span className="control-label">Related</span>
            <div className="segmented" role="group" aria-label="Overlap filter">
              {(
                [
                  ["all", "All"],
                  ["with", "Has overlapping measurements"],
                  ["without", "No overlaps"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={filterOverlap === value ? "is-active" : ""}
                  aria-pressed={filterOverlap === value}
                  onClick={() => setFilterOverlap(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="explore-filter-row">
            <label className="control-label" htmlFor="explore-region-search">
              Region
            </label>
            <input
              id="explore-region-search"
              type="search"
              className="explore-search"
              placeholder="Search region name or description…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <p className="mono-label explore-filter-count">
            Showing {matches.length} of {overview.findings_total} recorded
            findings
            {filtersActive && (
              <>
                {" · "}
                <button
                  type="button"
                  className="insp-link"
                  onClick={() => {
                    setFilterDirection("all");
                    setFilterIndex("all");
                    setFilterSensitivity("all");
                    setFilterOverlap("all");
                    setSearch("");
                  }}
                >
                  Clear filters
                </button>
              </>
            )}
          </p>
        </div>
      )}

      {/* ---------------------------------------- filtered finding list --- */}
      {indicesOrder.map((index) => {
        const entries = matches.filter((f) => f.index === index);
        if (entries.length === 0) return null;
        const stats = findings.indices[index];
        return (
          <div key={index} className="finding-group">
            <h4 className="insp-subheading">
              Δ{index.toUpperCase()} @ |Δ| ≥ {stats?.threshold ?? entries[0].threshold} ·{" "}
              {entries.length} regions
            </h4>
            <ul className="finding-list">
              {entries.map((finding) => (
                <li key={finding.evidence_id}>
                  <button
                    type="button"
                    className={
                      finding.evidence_id === selectedId
                        ? "finding-entry is-selected"
                        : "finding-entry"
                    }
                    aria-pressed={finding.evidence_id === selectedId}
                    onClick={() =>
                      onSelect(finding.evidence_id === selectedId ? null : finding.evidence_id)
                    }
                  >
                    <span className="finding-arrow" data-direction={finding.direction}>
                      {finding.direction === "decrease" ? "▼" : "▲"}
                    </span>
                    <span className="finding-name">
                      {finding.display_id} · {finding.direction}
                    </span>
                    <span className="mono-label finding-area">
                      {finding.area_ha.toFixed(2)} ha
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      {matches.length === 0 && overview.findings_total > 0 && (
        <p className="insp-note">
          No recorded finding matches these filters. Filters only narrow the
          recorded list — they never add regions.
        </p>
      )}

      {/* --------------------------------- selected finding card (§3.4) --- */}
      {selected && (
        <article className="finding-detail" aria-live="polite">
          <h4 className="insp-heading">{selected.interpretation.title}</h4>
          <h5 className="insp-question">What was observed?</h5>
          <p className="insp-note">{selected.interpretation.observed_measurement}</p>
          <h5 className="insp-question">Where was it observed?</h5>
          <p className="insp-note">
            {selected.interpretation.location} The region is highlighted on the
            map ({selected.centroid_lonlat[0].toFixed(4)}°E,{" "}
            {selected.centroid_lonlat[1].toFixed(4)}°N).
          </p>
          <h5 className="insp-question">When was it observed?</h5>
          <p className="insp-note">{selected.interpretation.observation_period}</p>
          <h5 className="insp-question">What was measured?</h5>
          {(() => {
            const sp = selected.evidence.spatial_measurements as Record<string, unknown>;
            const pixels = Number(sp.pixel_count);
            const holes = Number(sp.hole_pixel_count ?? 0);
            return (
              <Facts
                rows={[
                  ["Measured signal", `Δ${selected.index.toUpperCase()} · mean ${Number(sp.mean_delta).toFixed(3)}, median ${Number(sp.median_delta).toFixed(3)} (index units)`],
                  ["Threshold", `|Δ${selected.index.toUpperCase()}| ≥ ${selected.threshold}`],
                  ["Candidate area", `${formatHa(Number(sp.area_ha))} from ${pixels.toLocaleString("en-GB")} pixels${holes > 0 ? ` (${holes.toLocaleString("en-GB")} masked px enclosed as holes)` : ""}`],
                  ["Denominator", `${Number(sp.valid_pixel_denominator).toLocaleString("en-GB")} shared-valid pixels — the area share below is of this footprint, not the whole map`],
                  ["Share of footprint", `${sp.share_of_common_valid_percent} %`],
                ]}
              />
            );
          })()}
          <h5 className="insp-question">What does it mean?</h5>
          <p className="insp-note insp-meaning">{selected.interpretation.meaning}</p>
          <h5 className="insp-question">What could explain it?</h5>
          <ul className="insp-note">
            {selected.interpretation.explanations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <h5 className="insp-question">How much evidence supports it?</h5>
          {(() => {
            const q = selected.evidence.evidence_quality as Record<string, any>;
            const support = q.observation_support as Record<string, number> | undefined;
            const sensitivity = thresholdSensitivity(selected.evidence);
            const linkCount = selected.evidence.relationships?.links?.length ?? 0;
            return (
              <Facts
                rows={[
                  [
                    "Observations",
                    `${support?.earlier_observations ?? "?"} earlier / ${support?.later_observations ?? "?"} later satellite acquisitions in the composites`,
                  ],
                  [
                    "Valid coverage",
                    `${formatPercent(Number(q.shared_valid_fraction_of_aoi) || 0, 1)} of the study area shared-valid for this comparison`,
                  ],
                  [
                    "Threshold behaviour",
                    sensitivity
                      ? `${sensitivityPlainLanguage(sensitivity.label)} (recorded category: ${sensitivity.label})`
                      : "Sensitivity not recorded for this finding",
                  ],
                  [
                    "Related measurements",
                    linkCount > 0
                      ? `${linkCount} overlapping ${linkCount === 1 ? "measurement" : "measurements"} of the same geography (not independent events)`
                      : "No overlapping measurement recorded",
                  ],
                ]}
              />
            );
          })()}
          <h5 className="insp-question">What should we not conclude?</h5>
          <ul className="insp-note insp-guardrail">
            {selected.interpretation.cannot_conclude.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {(() => {
            const links = relatedFindingsFor(findings, selected);
            if (links.length === 0) return null;
            return (
              <>
                <h5 className="insp-question">Overlapping measurements</h5>
                <p className="insp-note">
                  Other indices flag parts of the same area. These are separate
                  measurements of one geography — not independent events. Open
                  one to see its record:
                </p>
                <ul className="insp-note">
                  {links.map((link) => (
                    <li key={link.finding.evidence_id}>
                      <button
                        type="button"
                        className="insp-link"
                        onClick={() => onSelect(link.finding.evidence_id)}
                      >
                        {link.finding.display_id} (Δ{link.finding.index.toUpperCase()}{" "}
                        {link.finding.direction})
                      </button>{" "}
                      — {link.relation === "same-direction-overlap" ? "same-direction candidate signal" : "opposite-direction candidate signal"} ·{" "}
                      {link.overlap_percent_of_smaller.toFixed(0)}% overlap
                    </li>
                  ))}
                </ul>
              </>
            );
          })()}
          <p className="insp-note mono-label">
            Evidence record: {selected.evidence_id} · Source:{" "}
            {selected.interpretation.source.input_raster} ·{" "}
            {selected.interpretation.source.method}
          </p>
          <button type="button" className="insp-link" onClick={onOpenResearch}>
            Open the Research Mode record →
          </button>
        </article>
      )}

      {findings.limitations.length > 0 && (
        <>
          <h4 className="insp-subheading">Study limitations</h4>
          <ul className="insp-note insp-guardrail">
            {findings.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/** Research Mode: the full versioned evidence record for the selected
 *  finding (M4-R2 G7). Same record as the Findings view — both render from
 *  the same payload entry and carry the same evidence_id. */
function EvidenceRecordPanel({
  findings,
  selectedId,
  onSelect,
  onOpenExplore,
  mlContainer,
}: {
  findings: BundleFindings | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onOpenExplore: () => void;
  /** M5 additive ML reference experiment; null when unavailable. */
  mlContainer: MlContainer | null;
}) {
  const [showMethods, setShowMethods] = useState(true);
  if (!findings) {
    return (
      <p className="insp-note">
        No findings file is recorded for this experiment, so there is no
        evidence record to display.
      </p>
    );
  }
  const selected = selectedId
    ? findingByEvidenceId(findings, selectedId) ?? null
    : null;
  if (!selected) {
    return (
      <div className="evidence-record">
        <h3 className="insp-heading">Research Mode</h3>
        <p className="insp-note">
          Select a finding in Explore the Evidence (or click a region on the
          map) to open its full technical record. Every mapped region carries
          one sealed record: identification, mathematical method, source
          observations, input measurements, spatial measurements, evidence
          quality, threshold sensitivity, relationships, method provenance and
          exports.
        </p>
        <p className="insp-note mono-label">
          Container schema: {findings.schema} · {findings.overview.findings_total} records
        </p>
      </div>
    );
  }
  const ev = selected.evidence;
  const im = ev.input_measurements as Record<string, any>;
  const sp = ev.spatial_measurements as Record<string, any>;
  const q = ev.evidence_quality as Record<string, any>;
  const prov = ev.method_provenance as Record<string, any>;
  const so = ev.source_observations as Record<string, any>;
  const grid = im.analysis_grid as Record<string, any>;
  const sensitivity = q.threshold_sensitivity as Record<string, any>;
  const neighbours = (sensitivity?.neighbours ?? {}) as Record<
    string,
    {
      component_pixels: number;
      retained_fraction_of_region: number;
      component_growth_factor: number;
    }
  >;
  const links =
    (ev.relationships as {
      links?: {
        with_evidence_id: string;
        relation: string;
        indices: string[];
        overlap_percent_of_smaller: number;
      }[];
    })?.links ?? [];
  const overlapRule = (ev.relationships as { overlap_rule?: string })
    ?.overlap_rule;
  const nameOf = (evidenceId: string) => {
    const other = findings.findings.find((f) => f.evidence_id === evidenceId);
    return other ? other.display_id : evidenceId;
  };

  // Mathematical method (§4.2) — only the operations actually recorded for
  // this finding; every line is read from the record or the container.
  const IUP = selected.index.toUpperCase();
  const dirTerm =
    selected.direction === "decrease" ? "decrease" : "increase";
  const selectionRule =
    selected.direction === "decrease"
      ? `Δ${IUP} ≤ −${selected.threshold}`
      : `Δ${IUP} ≥ +${selected.threshold}`;
  const params = prov.parameters as Record<string, any> | undefined;

  const download = (payload: string, mime: string, extension: string) => {
    const blob = new Blob([payload], { type: mime });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${selected.evidence_id}.${extension}`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="evidence-record">
      <h3 className="insp-heading">Research Mode</h3>
      <p className="insp-note mono-label">
        {ev.schema} · {selected.evidence_id} · checksum-sealed
      </p>
      <button type="button" className="insp-link" onClick={onOpenExplore}>
        ← Back to the Explore the Evidence card
      </button>

      <h4 className="insp-subheading">Identification</h4>
      <Facts
        rows={[
          [
            "Finding",
            `${ev.identification.display_id} (${ev.identification.finding_type})`,
          ],
          ["Candidate direction", ev.identification.candidate_direction],
          ["Evidence status", ev.identification.evidence_status],
          [
            "Study / experiment",
            `${ev.identification.study_id} / ${ev.identification.experiment_id}`,
          ],
        ]}
      />

      <h4 className="insp-subheading">Mathematical method</h4>
      <button
        type="button"
        className="insp-link methods-toggle"
        aria-expanded={showMethods}
        onClick={() => setShowMethods((prev) => !prev)}
      >
        {showMethods ? "Hide method definitions" : "Show method definitions"}
      </button>
      {showMethods && (
        <div
          className="math-block"
          aria-label="Mathematical method for this finding"
        >
          <div className="math-line">
            {IUP} = {String(im.formula)}
          </div>
          <div className="math-legend">
            {IUP} is computed from Sentinel-2 bands{" "}
            {(im.bands as string[])?.join(", ")} (
            {im.band_resolution_note ??
              `native ${im.native_band_resolution_m} m bands`}
            ); the index is dimensionless and bounded by its formula.
          </div>
          <div className="math-line">
            Δ{IUP} = {IUP}_later − {IUP}_earlier
          </div>
          <div className="math-legend">
            {String(im.delta_definition)} Analysis grid: {grid.crs} @{" "}
            {grid.resolution_m} m.
          </div>
          <div className="math-line">
            Candidate selection: {selectionRule} (inclusive)
          </div>
          <div className="math-legend">
            The threshold t = {selected.threshold} controls how strong the
            per-pixel difference must be before a pixel counts as candidate{" "}
            {dirTerm}. It is applied on the shared-valid mask — pixels invalid
            in either period are never evaluated.
          </div>
          <div className="math-legend">
            Candidate pixels are grouped by {String(prov.algorithm)} with{" "}
            {params?.connectivity ?? 4}-connectivity. Components smaller than
            the minimum mapping unit ({params?.minimum_mapping_unit_px} px ={" "}
            {params?.minimum_mapping_unit_ha ?? "—"} ha) are discarded; per
            index and direction the largest{" "}
            {params?.max_regions_per_index_direction} components are recorded
            (a curated selection — additional qualifying components are not
            recorded and have no evidence records).
          </div>
          <div className="math-legend">
            Denominator:{" "}
            {Number(sp.valid_pixel_denominator).toLocaleString("en-GB")}{" "}
            shared-valid pixels — the share below is measured against this
            footprint, not the whole AOI.
          </div>
        </div>
      )}

      <h4 className="insp-subheading">Source observations</h4>
      <Facts
        rows={[
          [
            "Earlier scenes",
            ((so.earlier as Record<string, any>).item_ids as string[])?.join(
              ", "
            ) ?? "unavailable",
          ],
          [
            "Earlier dates",
            ((so.earlier as Record<string, any>)
              .observation_dates as string[])?.join(", "),
          ],
          [
            "Later scenes",
            ((so.later as Record<string, any>).item_ids as string[])?.join(
              ", "
            ) ?? "unavailable",
          ],
          [
            "Later dates",
            ((so.later as Record<string, any>).observation_dates as string[])?.join(
              ", "
            ),
          ],
          ["Dataset", (so.dataset as Record<string, any>).collection],
        ]}
      />

      <h4 className="insp-subheading">Input measurements</h4>
      <Facts
        rows={[
          ["Index", `${im.index_label} — ${im.formula}`],
          [
            "Bands",
            [
              (im.bands as string[])?.join(" + "),
              im.band_resolution_note ?? "",
            ]
              .filter(Boolean)
              .join(" · "),
          ],
          ["Delta definition", im.delta_definition],
          ["Threshold", `|Δ| ≥ ${im.threshold} (inclusive)`],
          [
            "Analysis grid",
            `${grid.crs} @ ${grid.resolution_m} m (${grid.pixel_area_m2} m²/px)`,
          ],
          [
            "Delta raster",
            `${im.input_raster} · sha256 ${String(im.input_raster_sha256).slice(0, 16)}…`,
          ],
          [
            "Valid mask",
            `${im.valid_mask} · sha256 ${String(im.valid_mask_sha256).slice(0, 16)}…`,
          ],
        ]}
      />

      <h4 className="insp-subheading">Spatial measurements</h4>
      <Facts
        rows={[
          ["Pixel count", `${Number(sp.pixel_count).toLocaleString("en-GB")} px`],
          ["Area", `${sp.area_ha} ha (${sp.area_units})`],
          ["Mean / median Δ", `${sp.mean_delta} / ${sp.median_delta}`],
          [
            "Valid denominator",
            `${Number(sp.valid_pixel_denominator).toLocaleString("en-GB")} px shared-valid`,
          ],
          ["Share of footprint", `${sp.share_of_common_valid_percent} %`],
          [
            "Enclosed holes",
            `${sp.hole_pixel_count} masked px inside the outline`,
          ],
        ]}
      />
      <p className="insp-note mono-label">
        Levels: the values above are the region summary recorded in the
        spatial_measurements section of this evidence record. Per-pixel Δ values are not part of the record (probe
        them with the Pixel Probe where the live backend serves the study).
        Study-wide summaries (indices table, shared-valid footprint) belong to
        the findings container shown in Explore the Evidence.
      </p>

      <h4 className="insp-subheading">Evidence quality</h4>
      <Facts
        rows={[
          [
            "Shared-valid of AOI",
            `${((Number(q.shared_valid_fraction_of_aoi) || 0) * 100).toFixed(1)} %`,
          ],
          [
            "Observation support",
            `${(q.observation_support as Record<string, any>).earlier_observations} earlier / ${(q.observation_support as Record<string, any>).later_observations} later observations`,
          ],
        ]}
      />
      {((q.masking_and_cloud_limitations as string[] | undefined) ?? []).length >
        0 && (
        <ul className="insp-note insp-guardrail">
          {((q.masking_and_cloud_limitations as string[]) ?? []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}

      <h4 className="insp-subheading">Threshold sensitivity</h4>
      <p className="insp-note mono-label">
        Recorded label: {sensitivity.label} — {sensitivity.label_rules}
      </p>
      <p className="insp-note">
        Primary threshold t = {selected.threshold}; the recorded neighbours
        re-evaluate the same rule at t ± {sensitivity.neighbour_delta}. This
        is a transparency category with recorded rules — not a confidence
        score and not a verification statement.
      </p>
      <table className="sensitivity-table">
        <thead>
          <tr>
            <th scope="col">Threshold</th>
            <th scope="col">Component px</th>
            <th scope="col">Retained</th>
            <th scope="col">Growth</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(neighbours).map(([key, row]) => (
            <tr key={key}>
              <th scope="row">
                {key.replace("t_minus", "t − ").replace("t_plus", "t + ")}
              </th>
              <td>{Number(row.component_pixels).toLocaleString("en-GB")}</td>
              <td>{(row.retained_fraction_of_region * 100).toFixed(1)} %</td>
              <td>×{Number(row.component_growth_factor).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4 className="insp-subheading">Relationships</h4>
      {overlapRule && (
        <p className="insp-note mono-label">Rule: {overlapRule}</p>
      )}
      {links.length === 0 ? (
        <p className="insp-note">
          No overlapping measurement recorded for this region.
        </p>
      ) : (
        <>
          <p className="insp-note">
            Multiple measurements of one geography are not automatically
            independent environmental events. Open a related record without
            leaving Research Mode:
          </p>
          <ul className="insp-note">
            {links.map((link) => (
              <li key={link.with_evidence_id}>
                <button
                  type="button"
                  className="insp-link"
                  onClick={() => onSelect(link.with_evidence_id)}
                >
                  {nameOf(link.with_evidence_id)}
                </button>{" "}
                (
                {link.indices
                  .map((index) => `Δ${index.toUpperCase()}`)
                  .join(", ")}{" "}
                · {link.relation} ·{" "}
                {link.overlap_percent_of_smaller.toFixed(0)} % of the smaller
                region)
              </li>
            ))}
          </ul>
        </>
      )}

      {mlContainer ? (
        <div className="ml-block" data-testid="research-ml-block">
          <h4 className="insp-subheading">ML reference experiment (additive)</h4>
          <Facts
            rows={[
              ["Model", String(mlContainer.ml_record.model.type)],
              ["Trees / seed", `${String(mlContainer.ml_record.model.params.n_estimators)} / ${String(mlContainer.ml_record.model.params.random_state)}`],
              ["Reference", `${mlContainer.ml_record.reference.dataset} · ${mlContainer.ml_record.reference.epoch} epoch · ${mlContainer.ml_record.reference.license}`],
              ["Split", `${mlContainer.ml_record.split_design.method} (${mlContainer.ml_record.split_design.block_px} px blocks; train ${mlContainer.ml_record.split_design.train_px} / validation ${mlContainer.ml_record.split_design.validation_px} / test ${mlContainer.ml_record.split_design.test_px} px)`],
              ["Overall agreement", `${(mlContainer.ml_record.evaluation.overall_agreement * 100).toFixed(1)} %`],
              ["Macro-F1 (supported classes)", mlContainer.ml_record.evaluation.macro_f1_supported_classes === null ? "not reported" : mlContainer.ml_record.evaluation.macro_f1_supported_classes.toFixed(3)],
              ["Balanced accuracy", mlContainer.ml_record.evaluation.balanced_accuracy.toFixed(3)],
            ]}
          />
          <table className="ml-eval-table">
            <thead>
              <tr>
                <th>Class</th>
                <th>Test support</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>F1</th>
                <th>IoU</th>
              </tr>
            </thead>
            <tbody>
              {mlContainer.ml_record.evaluation.class_order.map((name) => {
                const row = mlContainer.ml_record.evaluation.per_class[name];
                return (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>{row.support}</td>
                    {row.metrics_reported ? (
                      <>
                        <td>{(row.precision ?? 0).toFixed(3)}</td>
                        <td>{(row.recall ?? 0).toFixed(3)}</td>
                        <td>{(row.f1 ?? 0).toFixed(3)}</td>
                        <td>{row.iou === null ? "—" : row.iou.toFixed(3)}</td>
                      </>
                    ) : (
                      <td colSpan={4} className="ml-gated">not reported — support below the {mlContainer.ml_record.evaluation.support_floor}-px floor</td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="insp-note mono-label">{mlContainer.ml_record.evaluation.framing}</p>
          <Facts
            rows={[
              ["Features", mlContainer.ml_record.features.list.join(", ")],
              ["Resolution note", mlContainer.ml_record.features.resolution_note],
              ["Application epochs", Object.values(mlContainer.ml_record.application).map((app) => `${app.date}: ${Object.entries(app.predicted_fractions).map(([cls, frac]) => `${cls} ${(frac * 100).toFixed(1)} %`).join(", ")}`).join(" · ")],
              ["Geographic stability", mlContainer.ml_record.geographic_stability.agreement_range ? `agreement ${mlContainer.ml_record.geographic_stability.agreement_range[0].toFixed(3)}-${mlContainer.ml_record.geographic_stability.agreement_range[1].toFixed(3)} across held-out blocks` : "not available"],
              ["Label gate", mlContainer.label_gate],
            ]}
          />
          <ul className="insp-note">
            {mlContainer.ml_record.interpretation_guardrails.map((g) => (
              <li key={g}>{g}</li>
            ))}
            {mlContainer.limitations.map((l) => (
              <li key={l}>Limitation: {l}</li>
            ))}
          </ul>
          <p className="insp-note mono-label">
            The mathematical records on this page are untouched; this block is
            additive provenance from {mlContainer.references.mathematical_findings_container.path}.
          </p>
        </div>
      ) : (
        <h4 className="insp-subheading">ML reference experiment: no record available</h4>
      )}

      <h4 className="insp-subheading">Method provenance</h4>
      <Facts
        rows={[
          ["Algorithm", String(prov.algorithm)],
          ["Engine version", String(prov.algorithm_version)],
          [
            "Parameters",
            `t = ${selected.threshold}, MMU ${(prov.parameters as Record<string, any>).minimum_mapping_unit_px} px, connectivity ${(prov.parameters as Record<string, any>).connectivity}, top-${(prov.parameters as Record<string, any>).max_regions_per_index_direction}`,
          ],
          ["Git commit", String(prov.git_commit).slice(0, 12)],
          [
            "Software",
            Object.entries(prov.software as Record<string, string>)
              .map(([k, v]) => `${k} ${v}`)
              .join(", "),
          ],
          ["Generated", String(prov.generated_utc ?? "—")],
          ["Output checksum", `${String(prov.output_checksum).slice(0, 16)}…`],
        ]}
      />

      <h4 className="insp-subheading">Exports</h4>
      <p className="insp-note">
        Download this sealed record verbatim — the export contains exactly the
        recorded fields, including provenance and checksums.
      </p>
      <div className="evidence-exports">
        <button
          type="button"
          className="insp-link"
          onClick={() =>
            download(
              JSON.stringify(selected.evidence, null, 2),
              "application/json",
              "json"
            )
          }
        >
          Download record JSON
        </button>
        <button
          type="button"
          className="insp-link"
          onClick={() =>
            download(
              evidenceRecordToCsv(selected.evidence),
              "text/csv",
              "csv"
            )
          }
        >
          Download record CSV
        </button>
      </div>

      <h4 className="insp-subheading">Interpretation</h4>
      <p className="insp-note">
        The plain-language interpretation for this record is the Explore the
        Evidence card — same evidence_id, same numbers, no separate
        computation.
      </p>
      <button type="button" className="insp-link" onClick={() => onSelect(null)}>
        Clear selection
      </button>
    </div>
  );
}

/** "What am I looking at?" — plain-language guide to the selected layer. */
function LayerGuidePanel({
  layer,
  summary,
  resolver,
}: {
  layer: LayerSpec;
  summary: M1Summary;
  resolver: AssetResolver;
}) {
  const guide = layerGuide(layer, summary);
  const legend = layerLegend(layer);
  return (
    <div className="layer-guide">
      <h3 className="insp-heading">What am I looking at?</h3>
      <Facts
        rows={[
          ["Layer", layer.label],
          ["Type", guide.kind],
          ["Band composition", guide.composition ?? "Not a band composite"],
          [
            "Native resolution",
            `${summary.grid.resolution_m} m per pixel (${summary.grid.crs})`,
          ],
        ]}
      />
      {legend.file && (
        <img
          className="insp-legend-img"
          src={resolver.previewUrl(legend.file)}
          alt={`Colour legend for ${layer.label}`}
        />
      )}
      {legend.swatches && (
        <div className="insp-swatches">
          {legend.swatches.map((swatch) => (
            <span key={swatch.label} className="insp-swatch">
              <span
                className="swatch-chip"
                style={{ background: swatch.color }}
                aria-hidden="true"
              />
              {swatch.label}
            </span>
          ))}
        </div>
      )}
      <h4 className="insp-subheading">What the values represent</h4>
      <p className="insp-note">{guide.values}</p>
      <h4 className="insp-subheading">How to read the colours</h4>
      <p className="insp-note">{guide.reading}</p>
      <h4 className="insp-subheading">What this layer cannot establish</h4>
      <p className="insp-note insp-guardrail">{guide.cannotEstablish}</p>
    </div>
  );
}

export function Inspector({
  summary,
  studyId,
  resolver,
  layer,
  quality,
  bundle,
  live,
  analysis,
  findings,
  selectedEvidenceId,
  onSelectFinding,
  onSelectRecord,
  onOpenResearch,
  selectionPolicy,
  mlFindings,
  pixel,
  pixelError,
  pixelLoading,
  cursor,
  roiMode,
  roiBox,
  roiResult,
  roiError,
  roiLoading,
  onToggleRoi,
  tab,
  onTabChange,
}: InspectorProps) {
  const legend = layerLegend(layer);
  const earlier = summary.periods?.[0];
  const later = summary.periods?.[1];
  const worstCommon = Math.min(
    ...Object.values(summary.change ?? {}).map((block) =>
      Number(block.common_valid_fraction_of_aoi ?? 0)
    )
  );

  const tabs: { id: InspectorTab; label: string }[] = [
    { id: "guide", label: "Guide" },
    { id: "legend", label: "Legend" },
    ...(analysis === "what_changed"
      ? ([
          { id: "findings", label: "Evidence" },
          { id: "evidence", label: "Research" },
        ] as { id: InspectorTab; label: string }[])
      : []),
    { id: "context", label: "Scenes" },
    { id: "pixel", label: "Probe" },
    { id: "roi", label: "ROI" },
  ];

  return (
    <aside className="inspector" aria-label="Research inspector">
      <div className="insp-tabs" role="tablist" aria-label="Inspector sections">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? "insp-tab is-active" : "insp-tab"}
            onClick={() => onTabChange(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="insp-body">
        {tab === "legend" && (
          <>
            <h3 className="insp-heading">{layer.label}</h3>
            {legend.file && (
              <img
                className="insp-legend-img"
                src={resolver.previewUrl(legend.file)}
                alt={`Colour legend for ${layer.label}`}
              />
            )}
            {legend.swatches && (
              <div className="insp-swatches">
                {legend.swatches.map((swatch) => (
                  <span key={swatch.label} className="insp-swatch">
                    <span
                      className="swatch-chip"
                      style={{ background: swatch.color }}
                      aria-hidden="true"
                    />
                    {swatch.label}
                  </span>
                ))}
              </div>
            )}
            <p className="insp-note">{legend.note}</p>
            {/* M4-R1 §8: native spatial resolution beside the imagery. */}
            <p className="insp-note mono-label">
              Analysis grid: {summary.grid.resolution_m} m/px ·{" "}
              {summary.grid.crs}. Sentinel-2 visible/NIR bands are natively
              10 m, SWIR bands 20 m (resampled to this grid). A 10 m pixel does
              not resolve individual buildings, trees or field boundaries. No
              higher-resolution reference imagery is integrated — the detail
              limit shown is the genuine limit of the open data.
            </p>
            {layer.kind === "quality" && (
              <>
                <p className="insp-note insp-meaning">
                  {qualityExplanation(layer)}
                </p>
                <QualityCoverage quality={quality} />
              </>
            )}
            {layer.kind === "change" && summary.change?.[layer.index]?.interpretation_guardrail && (
              <p className="insp-note insp-guardrail">
                {summary.change[layer.index].interpretation_guardrail}
              </p>
            )}
            <p className="insp-note mono-label cursor-line">
              {cursor
                ? `Cursor: ${cursor[0].toFixed(5)}°E, ${cursor[1].toFixed(5)}°N`
                : "Cursor coordinates appear here as you move over the map."}
            </p>
          </>
        )}

        {tab === "guide" && (
          <LayerGuidePanel layer={layer} summary={summary} resolver={resolver} />
        )}

        {tab === "findings" && (
          <ExploreFindingsPanel
            findings={findings}
            selectedId={selectedEvidenceId}
            onSelect={onSelectFinding}
            onOpenResearch={onOpenResearch}
            selectionPolicy={selectionPolicy}
            mlContainer={
              findings ? mlRecordForExperiment(mlFindings, findings.experiment_id) : null
            }
          />
        )}

        {tab === "evidence" && (
          <EvidenceRecordPanel
            findings={findings}
            selectedId={selectedEvidenceId}
            onSelect={onSelectRecord}
            onOpenExplore={() => onTabChange("findings")}
            mlContainer={
              findings ? mlRecordForExperiment(mlFindings, findings.experiment_id) : null
            }
          />
        )}

        {tab === "context" && (
          <>
            <h3 className="insp-heading">Acquisition &amp; processing</h3>
            <Facts
              rows={[
                ["Sensor", "Sentinel-2 MSI Level-2A"],
                ["Composite method", `${earlier?.composite_method ?? "?"} of valid observations`],
                ["Earlier window", (earlier?.observation_dates ?? []).join(", ")],
                ["Later window", (later?.observation_dates ?? []).join(", ")],
                [
                  "Valid coverage",
                  `${((worstCommon ?? 0) * 100).toFixed(1)}% of AOI common-valid`,
                ],
                ["Analysis CRS", `${summary.grid.crs} @ ${summary.grid.resolution_m} m`],
                ["Grid signature", summary.grid.signature],
                [
                  "Engine verification",
                  `${summary.verification.check_count} checks ${
                    summary.verification.all_passed ? "passed" : "FAILED"
                  }`,
                ],
              ]}
            />
            <h4 className="insp-subheading">Source scenes</h4>
            <Facts
              rows={[
                ["Earlier", (earlier?.item_ids ?? []).join(", ")],
                ["Later", (later?.item_ids ?? []).join(", ")],
              ]}
            />
            <h4 className="insp-subheading">Provenance</h4>
            <ul className="insp-links">
              {live ? (
                <>
                  <li>
                    <a href={`/api/m1/study/${studyId}/manifest`} target="_blank" rel="noopener noreferrer">
                      Run manifest (scenes, hashes, formulas)
                    </a>
                  </li>
                  <li>
                    <a href={`/api/m1/study/${studyId}`} target="_blank" rel="noopener noreferrer">
                      Study summary JSON
                    </a>
                  </li>
                </>
              ) : (
                <>
                  <li>
                    <a
                      href={`studies/${encodeURIComponent(studyId)}/bundle.json`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Showcase bundle JSON (checksummed artefact copies)
                    </a>
                  </li>
                  <li className="mono-label">
                    Experiment config: {bundle.experiments[0]?.config_path} · sha256{" "}
                    {(bundle.experiments[0]?.config_sha256 ?? "").slice(0, 16)}…
                  </li>
                </>
              )}
              <li>
                <a href="/methods">Methods &amp; limitations</a>
              </li>
            </ul>
            {bundle.dem_context?.available && (
              <>
                <h4 className="insp-subheading">Terrain context (DEM)</h4>
                <Facts
                  rows={[
                    ["DEM", `${bundle.dem_context.collection} · ${bundle.dem_context.item_id}`],
                    [
                      "Elevation range",
                      `${bundle.dem_context.elevation_min_m}–${bundle.dem_context.elevation_max_m} m (mean ${bundle.dem_context.elevation_mean_m} m)`,
                    ],
                  ]}
                />
                <p className="insp-note">{bundle.dem_context.role}</p>
              </>
            )}
            {bundle.event && (
              <>
                <h4 className="insp-subheading">
                  Event context · {bundle.event.event_date}
                </h4>
                <p className="insp-note">{bundle.event.event_mechanism}</p>
                <Facts
                  rows={bundle.event.observation_gaps.map((gap) => [
                    "Observation gap",
                    gap.statement,
                  ])}
                />
                <ul className="insp-note">
                  {bundle.event.known_unprocessed_observations.map((observation) => (
                    <li key={observation.item_id ?? observation.date}>
                      <span className="mono-label">
                        {observation.date} · {observation.item_id} ·{" "}
                        {observation.in_aoi_valid_fraction !== undefined
                          ? `${(observation.in_aoi_valid_fraction * 100).toFixed(1)}% valid · `
                          : ""}
                      </span>
                      {observation.status}
                    </li>
                  ))}
                </ul>
                <p className="insp-note insp-guardrail">{bundle.event.insar_note}</p>
                <ul className="insp-note">
                  {bundle.event.external_references.map((reference) => (
                    <li key={reference.title}>
                      {reference.title} — {reference.role}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {bundle.interpretation?.cannot_conclude?.length > 0 && (
              <>
                <h4 className="insp-subheading">What this evidence cannot establish</h4>
                <ul className="insp-note insp-guardrail">
                  {bundle.interpretation.cannot_conclude.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </>
            )}
            <p className="insp-note">
              {typeof summary.attribution === "string"
                ? summary.attribution
                : summary.attribution?.text}
            </p>
          </>
        )}

        {tab === "pixel" && (
          <>
            <h3 className="insp-heading">Pixel probe</h3>
            <PixelProbe pixel={pixel} error={pixelError} loading={pixelLoading} />
          </>
        )}

        {tab === "roi" && (
          <>
            <h3 className="insp-heading">Region of interest</h3>
            <RoiPanel
              roiMode={roiMode}
              roiBox={roiBox}
              roiResult={roiResult}
              roiError={roiError}
              roiLoading={roiLoading}
              onToggle={onToggleRoi}
            />
          </>
        )}
      </div>
    </aside>
  );
}
