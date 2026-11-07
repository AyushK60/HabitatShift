/** Research inspector — the right-hand analytical rail of the workstation.
 *
 * Sections: layer legend & meaning, the "What am I looking at?" layer guide
 * (M4-R1 §15.5), guided findings (§15.3), acquisition context, pixel probe
 * (server-measured full-resolution values) and the ROI tool.
 */
import type { G0Quality, M1Summary, PixelSample, RoiResult } from "../api/types";
import type { BundleFindings, StudyBundle } from "../api/bundle";
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
  selectedFindingId: string | null;
  onSelectFinding: (id: string | null) => void;
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

export type InspectorTab = "legend" | "guide" | "findings" | "context" | "pixel" | "roi";

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

/** Guided "What Changed?" findings panel (M4-R1 §15.3/§15.6). Everything
 *  renders from the recorded findings payload — same numbers as the map. */
function FindingsPanel({
  findings,
  selectedId,
  onSelect,
}: {
  findings: BundleFindings | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  if (!findings) {
    return (
      <p className="insp-note">
        No findings file is recorded for this experiment. A finding appears
        only when a connected candidate region meets the documented minimum
        mapping unit at the recorded thresholds — none is ever invented.
      </p>
    );
  }
  const { overview, method, periods } = findings;
  const selected = findings.findings.find((f) => f.id === selectedId) ?? null;
  const indicesOrder = [...new Set(findings.findings.map((f) => f.index))];
  return (
    <div className="findings-panel">
      <h3 className="insp-heading">What changed here?</h3>
      {overview.findings_total === 0 ? (
        <p className="insp-note insp-meaning">
          {overview.no_finding_statement ??
            "No defensible candidate region was identified for this comparison."}
        </p>
      ) : (
        <p className="insp-note insp-meaning">
          {overview.findings_total} defensible mapped regions:{" "}
          {overview.by_direction.decrease} candidate decrease,{" "}
          {overview.by_direction.increase} candidate increase, across{" "}
          {overview.signal_types.join(", ")}. Every region is a connected
          component of the recorded difference map at its stated threshold —
          not a confirmed environmental change.
        </p>
      )}
      <dl className="insp-facts">
        <div>
          <dt>Observation period</dt>
          <dd>
            {periods.earlier.anchor_date} → {periods.later.anchor_date} (
            {periods.earlier.composite_method} composites)
          </dd>
        </div>
        <div>
          <dt>Shared-valid footprint</dt>
          <dd>
            {findings.common_valid_pixels.toLocaleString("en-GB")} px ·{" "}
            {(findings.common_valid_fraction_of_aoi * 100).toFixed(1)}% of AOI
          </dd>
        </div>
        <div>
          <dt>Minimum mapping unit</dt>
          <dd>
            {method.minimum_mapping_unit_px} px ({method.minimum_mapping_unit_ha}{" "}
            ha) · smaller clusters are never reported
          </dd>
        </div>
      </dl>
      <p className="insp-note mono-label">
        Categories: candidate increase / candidate decrease / little measurable
        difference / insufficient evidence. All mapped regions here are
        <strong> candidates</strong>; "insufficient evidence" is exactly what
        an empty list means.
      </p>

      {indicesOrder.map((index) => {
        const entries = findings.findings.filter((f) => f.index === index);
        const stats = findings.indices[index];
        return (
          <div key={index} className="finding-group">
            <h4 className="insp-subheading">
              Δ{index.toUpperCase()} @ |Δ| ≥ {stats?.threshold ?? entries[0].threshold} ·{" "}
              {entries.length} regions
            </h4>
            <ul className="finding-list">
              {entries.map((finding) => (
                <li key={finding.id}>
                  <button
                    type="button"
                    className={
                      finding.id === selectedId
                        ? "finding-entry is-selected"
                        : "finding-entry"
                    }
                    aria-pressed={finding.id === selectedId}
                    onClick={() => onSelect(finding.id === selectedId ? null : finding.id)}
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

      {selected && (
        <article className="finding-detail" aria-live="polite">
          <h4 className="insp-heading">{selected.interpretation.title}</h4>
          <Facts
            rows={[
              ["Location", selected.interpretation.location],
              ["Observation period", selected.interpretation.observation_period],
              ["Observed measurement", selected.interpretation.observed_measurement],
            ]}
          />
          <p className="insp-note insp-meaning">{selected.interpretation.meaning}</p>
          <h4 className="insp-subheading">What could explain it?</h4>
          <ul className="insp-note">
            {selected.interpretation.explanations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <h4 className="insp-subheading">How strong is the evidence?</h4>
          <p className="insp-note">{selected.interpretation.evidence_strength}</p>
          <h4 className="insp-subheading">What cannot be concluded?</h4>
          <ul className="insp-note insp-guardrail">
            {selected.interpretation.cannot_conclude.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="insp-note mono-label">
            Source: {selected.interpretation.source.input_raster} ·{" "}
            {selected.interpretation.source.method}
          </p>
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
  selectedFindingId,
  onSelectFinding,
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
    { id: "legend", label: "Layer & legend" },
    { id: "guide", label: "What am I looking at?" },
    ...(analysis === "what_changed"
      ? ([{ id: "findings", label: "Findings" }] as { id: InspectorTab; label: string }[])
      : []),
    { id: "context", label: "Acquisition" },
    { id: "pixel", label: "Pixel probe" },
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
          <FindingsPanel
            findings={findings}
            selectedId={selectedFindingId}
            onSelect={onSelectFinding}
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
                      href={`/studies/${encodeURIComponent(studyId)}/bundle.json`}
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
