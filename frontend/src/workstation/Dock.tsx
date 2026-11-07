/** Compact, expandable bottom analysis dock.
 *
 * Collapsed it is one thin strip carrying the acquisition timeline summary.
 * Expanded it opens as an overlay above the strip so it never permanently
 * consumes map space. Only sections with genuine recorded data render.
 */
import { useState } from "react";
import type { ExperimentSummary, M1Summary } from "../api/types";

interface DockProps {
  summary: M1Summary;
  experiment: ExperimentSummary | null;
  experimentError: string | null;
  open: boolean;
  onToggle: () => void;
  studyId: string;
}

function Timeline({ summary }: { summary: M1Summary }) {
  return (
    <div className="dock-section dock-timeline">
      <h3>Timeline</h3>
      <div className="timeline-track">
        {summary.periods.map((period, index) => (
          <div key={period.period_id} className="timeline-node">
            <span className="timeline-dot" data-period={period.period_id} aria-hidden="true" />
            <strong>{index === 0 ? "Earlier" : "Later"}</strong>
            <span className="mono-label">{period.anchor_date}</span>
            <span className="mono-label">
              {period.observation_count} obs ·{" "}
              {(period.observation_dates ?? []).length} acquisitions
            </span>
            <span className="mono-label timeline-scenes" title={period.item_ids.join(", ")}>
              {period.item_ids[0]}
              {period.item_ids.length > 1 ? ` +${period.item_ids.length - 1}` : ""}
            </span>
          </div>
        ))}
        <div className="timeline-gap" aria-hidden="true" />
      </div>
    </div>
  );
}

function IndexDistributions({ summary, experiment }: { summary: M1Summary; experiment: ExperimentSummary | null }) {
  const [index, setIndex] = useState("ndvi");
  const indices = Object.keys(summary.periods?.[0]?.indices ?? {});
  const chart = experiment?.artifacts.charts[`delta_histogram_${index}`];
  return (
    <div className="dock-section">
      <h3>Index distributions</h3>
      <div className="dock-index-switch" role="group" aria-label="Index">
        {indices.map((key) => (
          <button
            key={key}
            type="button"
            className={key === index ? "chip is-active" : "chip"}
            onClick={() => setIndex(key)}
          >
            {key.toUpperCase()}
          </button>
        ))}
      </div>
      <table className="dock-table">
        <thead>
          <tr>
            <th scope="col">Period</th>
            <th scope="col">mean</th>
            <th scope="col">p05</th>
            <th scope="col">p50</th>
            <th scope="col">p95</th>
          </tr>
        </thead>
        <tbody>
          {summary.periods.map((period) => {
            const stats = period.indices?.[index]?.stats;
            if (!stats) return null;
            return (
              <tr key={period.period_id}>
                <th scope="row">
                  {period.period_id === "earlier" ? "Earlier" : "Later"}
                </th>
                <td>{stats.mean.toFixed(3)}</td>
                <td>{stats.quantiles?.p05?.toFixed(3) ?? "–"}</td>
                <td>{stats.quantiles?.p50?.toFixed(3) ?? "–"}</td>
                <td>{stats.quantiles?.p95?.toFixed(3) ?? "–"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {chart && (
        <img
          className="dock-chart"
          src={chart}
          alt={`Recorded ${index.toUpperCase()} difference histogram`}
          loading="lazy"
        />
      )}
      {!experiment && (
        <p className="mono-label">
          Recorded histogram appears when the experiment run is loaded.
        </p>
      )}
    </div>
  );
}

function ChangeAreas({ summary }: { summary: M1Summary }) {
  const [index, setIndex] = useState<string>(
    Object.keys(summary.change ?? {})[0] ?? "ndvi"
  );
  const block = summary.change?.[index];
  const keys = Object.keys(summary.change ?? {});
  if (!block) return null;
  return (
    <div className="dock-section">
      <h3>Change areas</h3>
      <div className="dock-index-switch" role="group" aria-label="Change index">
        {keys.map((key) => (
          <button
            key={key}
            type="button"
            className={key === index ? "chip is-active" : "chip"}
            onClick={() => setIndex(key)}
          >
            Δ{key.toUpperCase()}
          </button>
        ))}
      </div>
      <table className="dock-table">
        <thead>
          <tr>
            <th scope="col">|Δ| ≥</th>
            <th scope="col">lower ha</th>
            <th scope="col">unchanged ha</th>
            <th scope="col">higher ha</th>
          </tr>
        </thead>
        <tbody>
          {(block.thresholds ?? [])
            .slice()
            .sort((a, b) => a.threshold - b.threshold)
            .map((row) => (
              <tr key={row.threshold}>
                <th scope="row">{row.threshold.toFixed(2)}</th>
                <td>{row.decrease_area_ha.toFixed(2)}</td>
                <td>
                  {((Number(row.stable_pixels ?? 0) * Number(block.pixel_area_m2 ?? 0)) / 10000).toFixed(2)}
                </td>
                <td>{row.increase_area_ha.toFixed(2)}</td>
              </tr>
            ))}
        </tbody>
      </table>
      <p className="mono-label">
        {index.toUpperCase()} at the primary threshold ±{block.primary_threshold}:{" "}
        {block.primary.decrease_area_ha.toFixed(2)} ha lower /{" "}
        {block.primary.increase_area_ha.toFixed(2)} ha higher on{" "}
        {(block.common_valid_fraction_of_aoi * 100).toFixed(1)}% common-valid
        support. Candidate spectral signals, not land-cover verdicts.
      </p>
    </div>
  );
}

function Uncertainty({ experiment, experimentError }: { experiment: ExperimentSummary | null; experimentError: string | null }) {
  if (!experiment) {
    return (
      <div className="dock-section">
        <h3>Uncertainty</h3>
        <p className="mono-label">{experimentError ?? "Loading recorded uncertainty…"}</p>
      </div>
    );
  }
  const index = experiment.config.indices[0];
  const bootstrap = experiment.bootstrap?.[index];
  const atPrimary = bootstrap?.thresholds?.find(
    (row) => Math.abs(row.threshold - experiment.config.primary_threshold) < 1e-9
  );
  const pct = (value: number) => `${(value * 100).toFixed(2)}%`;
  return (
    <div className="dock-section">
      <h3>Uncertainty · {index.toUpperCase()}</h3>
      {atPrimary ? (
        <table className="dock-table">
          <tbody>
            <tr>
              <th scope="row">Candidate decrease</th>
              <td>
                {pct(atPrimary.decrease_fraction)} · block-bootstrap 95% range{" "}
                {pct(atPrimary.decrease_fraction_ci95.p2_5)}–
                {pct(atPrimary.decrease_fraction_ci95.p97_5)}
              </td>
            </tr>
            <tr>
              <th scope="row">Candidate increase</th>
              <td>
                {pct(atPrimary.increase_fraction)} · 95% range{" "}
                {pct(atPrimary.increase_fraction_ci95.p2_5)}–
                {pct(atPrimary.increase_fraction_ci95.p97_5)}
              </td>
            </tr>
          </tbody>
        </table>
      ) : (
        <p className="mono-label">No recorded bootstrap row at the primary threshold.</p>
      )}
      <p className="mono-label">
        Resampling variability of change-area fractions for this AOI and grid
        ({bootstrap?.iterations_used} resamples, {bootstrap?.block_size_px} px
        blocks) — not a population confidence interval.
      </p>
      <a href="/experiments" className="dock-link">
        Open the full experiments workspace →
      </a>
    </div>
  );
}

export function Dock({ summary, experiment, experimentError, open, onToggle }: Omit<DockProps, "studyId">) {
  return (
    <section className={`dock ${open ? "is-open" : ""}`} aria-label="Analysis dock">
      {open && (
        <div className="dock-panel">
          <Timeline summary={summary} />
          <IndexDistributions summary={summary} experiment={experiment} />
          <ChangeAreas summary={summary} />
          <Uncertainty experiment={experiment} experimentError={experimentError} />
        </div>
      )}
      <div className="dock-bar">
        <button
          type="button"
          className="dock-toggle"
          aria-expanded={open}
          onClick={onToggle}
        >
          <span className="dock-chevron" aria-hidden="true">
            {open ? "▾" : "▴"}
          </span>
          Analysis dock
        </button>
        <span className="mono-label dock-summary">
          {summary.periods
            .map(
              (period) =>
                `${period.period_id === "earlier" ? "Earlier" : "Later"} ${period.anchor_date} (${period.observation_count} obs)`
            )
            .join("  →  ")}
        </span>
        <span className="mono-label dock-hint">
          {open ? "Expanded — the map stays usable; collapse for full height" : "Expand for distributions, change areas and uncertainty"}
        </span>
      </div>
    </section>
  );
}
