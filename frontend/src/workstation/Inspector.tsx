/** Research inspector — the right-hand analytical rail of the workstation.
 *
 * Sections: layer legend & meaning, acquisition context, pixel probe
 * (server-measured full-resolution values) and the ROI tool (also
 * full-resolution server-side, explicitly labelled).
 */
import type { G0Quality, M1Summary, PixelSample, RoiResult } from "../api/types";
import type { StudyBundle } from "../api/bundle";
import type { AssetResolver, LayerSpec } from "./layers";
import { layerLegend, qualityExplanation } from "./layers";
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

export type InspectorTab = "legend" | "context" | "pixel" | "roi";

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

/** Measured coverage accounting with the correct denominators (M3 §8).
 *  Percentages of AOI use AOI pixels; the masked count is stated against the
 *  rectangular raster-grid footprint. */
function QualityCoverage({ quality }: { quality: G0Quality | null }) {
  const coverage = quality?.coverage;
  const px = (value: number | undefined) =>
    value === undefined ? "n/a" : value.toLocaleString("en-GB");
  const pctOfAoi = (pixels: number | undefined) =>
    coverage && pixels !== undefined
      ? `${((pixels / coverage.aoi_pixels) * 100).toFixed(1)}% of AOI`
      : "";
  const uniform = coverage?.uniform_common ?? false;
  return (
    <div className="quality-coverage">
      <h4 className="insp-subheading">Measured coverage</h4>
      <Facts
        rows={[
          ["AOI pixels", px(coverage?.aoi_pixels)],
          ["Grid pixels (rectangular footprint)", px(coverage?.grid_pixels)],
          [
            "Earlier valid",
            `${px(coverage?.earlier_valid_pixels)} ${pctOfAoi(coverage?.earlier_valid_pixels)}`,
          ],
          [
            "Later valid",
            `${px(coverage?.later_valid_pixels)} ${pctOfAoi(coverage?.later_valid_pixels)}`,
          ],
          [
            "Shared valid (both periods)",
            `${px(coverage?.common_valid_pixels)} ${pctOfAoi(coverage?.common_valid_pixels)}`,
          ],
          ["Masked or outside grid", px(coverage?.masked_pixels)],
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
        The AOI ({px(coverage?.aoi_pixels)} px) is the hand-chosen study window;
        the exported rasters cover a slightly larger rectangular grid (
        {px(coverage?.grid_pixels)} px). The {px(coverage?.masked_pixels)}-pixel
        difference between those footprints is masked/outside-AOI — it is not
        cloud damage. SCL flags do not record a per-pixel masking cause, so no
        specific cause is claimed anywhere.
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

export function Inspector({
  summary,
  studyId,
  resolver,
  layer,
  quality,
  bundle,
  live,
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
