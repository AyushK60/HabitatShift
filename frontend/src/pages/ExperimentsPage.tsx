/** Results & Experiments workspace (M3-G3, M4-R1 §11 study selector).
 *
 * The page presents every investigation's GENUINE analytical outputs and
 * labels their status honestly:
 * - "Recorded experiment" — a full hypothesis-testing run exists (today only
 *   Coringa's M2 run; served verbatim by the backend when reachable, and
 *   mirrored in the portable bundle otherwise).
 * - "Descriptive measurement" — recorded M1 outputs (threshold sweeps, period
 *   means, change areas) that describe the data without testing hypotheses.
 * - "Planned / not available" — experiments that have NOT been run; the page
 *   never invents numbers to fill them.
 *
 * Everything renders from the portable bundles, so the study selector works
 * in Showcase Mode with no Python backend.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import {
  loadRegistryJson,
  loadStudyBundle,
  type StudyBundle,
} from "../api/bundle";
import type { ExperimentSummary, Registry } from "../api/types";
import { ErrorNote, StatusChip } from "../components/ui";
import { buildStudyCharts } from "../charts/studyCharts";
import "../styles/experiments.css";

const ha = (value: number) =>
  `${Number(value).toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ha`;
const pct = (value: number) => `${(Number(value) * 100).toFixed(2)}%`;

const STUDY_ORDER = [
  "coringa_coastal",
  "chilika_wetland",
  "western_ghats_forest",
  "himalaya_purepu_2025",
  "himalaya_langtang_2026",
  "kathmandu_urban",
];

const STUDY_SHORT: Record<string, string> = {
  coringa_coastal: "Coringa",
  chilika_wetland: "Chilika",
  western_ghats_forest: "Western Ghats",
  himalaya_purepu_2025: "Himalayan 2025",
  himalaya_langtang_2026: "Himalayan 2026",
  kathmandu_urban: "Kathmandu",
};

function VerdictChip({ verdict }: { verdict: string }) {
  return (
    <span className={`verdict-chip verdict-${verdict}`}>{verdict.replace("_", " ")}</span>
  );
}

/* ------------------------------------------------- shared sub-views --- */

function StudySelector({
  studies,
  active,
  onSelect,
}: {
  studies: { id: string; title: string; status: string }[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="exp-study-selector" role="group" aria-label="Investigation">
      <span className="control-label">Investigation</span>
      <div className="segmented" role="group" aria-label="Study">
        {studies.map((study) => (
          <button
            key={study.id}
            type="button"
            className={study.id === active ? "is-active" : ""}
            aria-pressed={study.id === active}
            onClick={() => onSelect(study.id)}
          >
            {STUDY_SHORT[study.id] ?? study.title}
          </button>
        ))}
      </div>
    </div>
  );
}

function AvailabilityPanel({ bundle }: { bundle: StudyBundle }) {
  const isCoringa = bundle.study_id === "coringa_coastal";
  const hasM2 = Boolean(bundle.sources?.m2_experiment);
  const rows: { label: string; kind: "experiment" | "descriptive" | "planned" }[] = [
    {
      label: "Composite & index measurements (threshold sweeps, period means, Δ statistics)",
      kind: "descriptive",
    },
    ...(hasM2
      ? [
          {
            label: "Hypothesis-testing run (estimator comparison, block bootstrap, verdicts)",
            kind: "experiment" as const,
          },
        ]
      : []),
    ...(bundle.event
      ? [
          {
            label: "Event-relative observation timeline & validity record",
            kind: "descriptive" as const,
          },
          {
            label: "Discharge volume, flood depth or damage assessment from optical data",
            kind: "planned" as const,
          },
        ]
      : []),
    ...(bundle.study_id === "chilika_wetland"
      ? [
          {
            label: "Seasonal sensitivity: matched dry-season vs matched post-monsoon pairs",
            kind: "descriptive" as const,
          },
        ]
      : []),
    ...(bundle.study_id === "kathmandu_urban"
      ? [
          {
            label: "Independent reference labels for verified urban expansion",
            kind: "planned" as const,
          },
        ]
      : []),
    !hasM2
      ? {
          label: "Full hypothesis-testing experiment run for this study",
          kind: "planned" as const,
        }
      : { label: "Supervised classification accuracy (no independent labels exist for this study)", kind: "planned" as const },
  ];
  const kindLabel = {
    experiment: "Recorded experiment",
    descriptive: "Descriptive measurement",
    planned: "Planned / not available",
  };
  return (
    <section className="exp-block" aria-labelledby="exp-availability-title">
      <p className="eyebrow">Experiment availability</p>
      <h2 id="exp-availability-title">What exists — and what does not</h2>
      <p className="exp-lede">
        Every study reports exactly what has been measured for it. Nothing is
        invented to make the sections look alike{isCoringa ? "" : " — this investigation has descriptive measurements but no hypothesis-testing run yet"}.
      </p>
      <table className="exp-table">
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              <td>
                <span className={`availability-chip availability-${row.kind}`}>
                  {kindLabel[row.kind]}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** Descriptive M1 outputs for any study, from the portable bundle. */
function BundleExperiments({ bundle }: { bundle: StudyBundle }) {
  const experiment = bundle.experiments[0];
  const summary = experiment.summary;
  const charts = buildStudyCharts(bundle, 0);
  const changeKeys = Object.keys(summary.change ?? {});
  const firstBlock = changeKeys.length ? summary.change[changeKeys[0]] : null;
  const earlier = summary.periods?.[0];
  const later = summary.periods?.[1];

  return (
    <>
      <section className="exp-block" aria-labelledby="exp-descriptive-title">
        <p className="eyebrow">Descriptive measurement</p>
        <h2 id="exp-descriptive-title">
          Recorded outputs for {bundle.study.title}
        </h2>
        <p className="exp-lede">
          Experiment <code>{experiment.experiment_id}</code> · acquisitions{" "}
          {earlier?.anchor_date} → {later?.anchor_date} ·{" "}
          {pct(Object.values(summary.change ?? {})[0]?.common_valid_fraction_of_aoi ?? 0)}{" "}
          of AOI shared-valid. These are descriptive measurements of the
          processed composites; they test no hypothesis.
        </p>
        <dl className="exp-facts">
          <div>
            <dt>Evidence status</dt>
            <dd>
              <StatusChip status={bundle.evidence_status} />
            </dd>
          </div>
          <div>
            <dt>Indices</dt>
            <dd>{Object.keys(earlier?.indices ?? {}).map((k) => k.toUpperCase()).join(", ")}</dd>
          </div>
          <div>
            <dt>Analysis grid</dt>
            <dd>
              {summary.grid.width} × {summary.grid.height} px @ {summary.grid.resolution_m} m
            </dd>
          </div>
        </dl>
      </section>

      {charts.map((spec) => (
        <section key={spec.id} className="exp-block">
          <p className="eyebrow">Interactive chart</p>
          <h2>{spec.title}</h2>
          {spec.element}
          {spec.id === "bootstrap" && (
            <p className="exp-note">
              Reading the uncertainty chart: the band is the 2.5th–97.5th
              percentile across spatial-block resamples of this AOI and grid —
              it is not a population confidence interval and not a statement
              about any other area.
            </p>
          )}
        </section>
      ))}

      {firstBlock && (
        <section className="exp-block" aria-labelledby="exp-areas-title">
          <p className="eyebrow">Descriptive measurement</p>
          <h2 id="exp-areas-title">Candidate change areas at stated thresholds</h2>
          <div className="exp-two-col">
            <table className="exp-table">
              <thead>
                <tr>
                  <th scope="col">|Δ{changeKeys[0].toUpperCase()}| ≥</th>
                  <th scope="col">lower ha</th>
                  <th scope="col">higher ha</th>
                </tr>
              </thead>
              <tbody>
                {(firstBlock.thresholds ?? [])
                  .slice()
                  .sort((a, b) => a.threshold - b.threshold)
                  .map((row) => (
                    <tr key={row.threshold}>
                      <th scope="row">{row.threshold.toFixed(2)}</th>
                      <td>{row.decrease_area_ha.toFixed(2)}</td>
                      <td>{row.increase_area_ha.toFixed(2)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <div className="exp-side">
              <h3>Reading this table</h3>
              <p className="exp-note">
                Areas are the shared-valid footprint satisfying the threshold
                criterion — candidate spectral signals with a stated cut-off,
                not verified land-cover change. The primary threshold is ±
                {firstBlock.primary_threshold}: {ha(firstBlock.primary.decrease_area_ha)}{" "}
                lower / {ha(firstBlock.primary.increase_area_ha)} higher.
              </p>
              {firstBlock.interpretation_guardrail && (
                <p className="exp-note">{firstBlock.interpretation_guardrail}</p>
              )}
            </div>
          </div>
        </section>
      )}

      <section className="exp-block" aria-labelledby="exp-limits-title">
        <p className="eyebrow">Scientific interpretation</p>
        <h2 id="exp-limits-title">What this evidence can and cannot establish</h2>
        <div className="exp-two-col">
          <ul className="exp-guardrails">
            {(bundle.interpretation?.can_conclude ?? []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <ul className="exp-guardrails">
            {(bundle.interpretation?.cannot_conclude ?? []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <ul className="exp-exports">
          <li>
            <a
              href={`/studies/${encodeURIComponent(bundle.study_id)}/bundle.json`}
              target="_blank"
              rel="noopener noreferrer"
            >
              Showcase bundle JSON (checksummed artefact copies)
            </a>
          </li>
          <li>
            <Link to="/methods">Methods, formulas and limitations</Link>
          </li>
        </ul>
      </section>
    </>
  );
}

/** Coringa's recorded M2 run, served verbatim by the backend. */
function CoringaRecordedRun({ experiment }: { experiment: ExperimentSummary }) {
  const coverage = experiment.coverage;
  return (
    <>
      <section className="exp-block">
        <p className="eyebrow">Recorded experiment</p>
        <h2>Coringa threshold sensitivity, method comparison &amp; measured uncertainty</h2>
        <p className="exp-lede">
          Recorded run <code>{experiment.run_id}</code> · generated{" "}
          {experiment.generated_utc} · fingerprint {String(experiment.fingerprint).slice(0, 16)}…
          . Every number and chart below is read from that run; no supervised
          labels were used anywhere.
        </p>
        <dl className="exp-facts">
          <div>
            <dt>Valid footprint</dt>
            <dd>
              {coverage.aoi_pixels.toLocaleString("en-GB")} AOI px ·{" "}
              {((coverage.pixel_area_m2 * coverage.aoi_pixels) / 10000).toFixed(1)} ha
            </dd>
          </div>
          <div>
            <dt>Common-valid coverage</dt>
            <dd>{pct(coverage.minimum_common_valid_fraction_of_aoi)} of AOI (all indices)</dd>
          </div>
          <div>
            <dt>Observations</dt>
            <dd>
              {coverage.periods
                .map((p) => `${p.period_id} ${p.observation_count}`)
                .join(" · ")}
            </dd>
          </div>
        </dl>
      </section>

      <section className="exp-block" aria-labelledby="exp-verdicts-title">
        <p className="eyebrow">Hypothesis verdicts</p>
        <h2 id="exp-verdicts-title">What the run set out to test</h2>
        <ul className="verdict-list">
          {experiment.hypothesis_verdicts.map((verdict) => (
            <li key={verdict.id}>
              <strong>{verdict.id}</strong>
              <VerdictChip verdict={verdict.verdict} />
              <span>{verdict.statement.split(". ").slice(1).join(". ")}</span>
            </li>
          ))}
        </ul>
      </section>
      <p className="exp-note">
        The interactive threshold-sensitivity, estimator-comparison and
        block-bootstrap charts for this recorded run are rendered in the
        analysis dock of the{" "}
        <Link to="/workstation/coringa_coastal">Coringa workstation</Link>{" "}
        (expand the dock) and in the descriptive sections below when the
        backend is offline.
      </p>
    </>
  );
}


/* ------------------------------------- complete component inventory --- */

interface InventoryExperiment {
  experiment: string;
  study_id: string;
  rule: string;
  total: number;
  matches_selection_policy: boolean;
  by_index: Record<
    string,
    Record<string, { components_total: number; components_at_or_above_mmu: number; area_ha_at_or_above_mmu: number }>
  >;
  largest: { index: string; direction: string; pixels: number; area_ha: number; mean_delta: number; lon: number; lat: number }[];
  csv: string;
}

function InventoryPanel({ studyId }: { studyId: string }) {
  const [items, setItems] = useState<InventoryExperiment[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    fetch("studies/m5_inventory.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((doc) => !cancelled && setItems(doc.experiments as InventoryExperiment[]))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);
  const mine = (items ?? []).filter((item) => item.study_id === studyId);
  if (failed || (items && mine.length === 0)) return null;
  return (
    <section className="exp-section" aria-labelledby="inventory-h">
      <h2 id="inventory-h">Complete change-component inventory</h2>
      <p className="exp-note">
        Every connected component at or above the minimum mapping unit, not just the
        curated top five shown as findings. Additive view of recorded rasters; the sealed
        findings are unchanged.
      </p>
      {mine.map((item) => (
        <div key={item.experiment} className="exp-card">
          <p className="mono-label">
            {item.experiment} · {item.total} components ·{" "}
            {item.matches_selection_policy ? "matches audited selection policy" : "differs from selection policy"}
          </p>
          <p className="exp-note">{item.rule}</p>
          <div className="exp-table-wrap">
            <table className="exp-table">
              <thead>
                <tr>
                  <th>Index</th>
                  <th>Direction</th>
                  <th>Components ≥ MMU</th>
                  <th>All components</th>
                  <th>Area ≥ MMU</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(item.by_index).flatMap(([index, dirs]) =>
                  Object.entries(dirs).map(([direction, v]) => (
                    <tr key={`${index}-${direction}`}>
                      <td>{index.toUpperCase()}</td>
                      <td>{direction}</td>
                      <td>{v.components_at_or_above_mmu}</td>
                      <td>{v.components_total}</td>
                      <td>{ha(v.area_ha_at_or_above_mmu)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <details>
            <summary>Ten largest components</summary>
            <div className="exp-table-wrap">
              <table className="exp-table">
                <thead>
                  <tr>
                    <th>Index</th>
                    <th>Direction</th>
                    <th>Pixels</th>
                    <th>Area</th>
                    <th>Mean Δ</th>
                    <th>Centroid (lon, lat)</th>
                  </tr>
                </thead>
                <tbody>
                  {item.largest.map((c, i) => (
                    <tr key={i}>
                      <td>{c.index.toUpperCase()}</td>
                      <td>{c.direction}</td>
                      <td>{c.pixels}</td>
                      <td>{ha(c.area_ha)}</td>
                      <td>{c.mean_delta.toFixed(3)}</td>
                      <td>
                        {c.lon.toFixed(4)}, {c.lat.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <p>
            <a href={item.csv} download>
              Download full component list (CSV)
            </a>
          </p>
        </div>
      ))}
    </section>
  );
}


/* ------------------------------------------- per-scene time series --- */

interface SceneSeries {
  key: string;
  study_id: string;
  experiment: string;
  scenes: { date: string; item_id: string; period: string; valid_pixels: number; mean: Record<string, number> }[];
}

function TimeSeriesPanel({ studyId }: { studyId: string }) {
  const [series, setSeries] = useState<SceneSeries[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [index, setIndex] = useState("ndvi");
  useEffect(() => {
    let cancelled = false;
    fetch("studies/m5_timeseries.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((doc) => !cancelled && setSeries(doc.studies as SceneSeries[]))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);
  const mine = (series ?? []).filter((item) => item.study_id === studyId);
  if (failed || (series && mine.length === 0)) return null;
  const indices = ["ndvi", "ndwi", "ndbi"].filter((k) =>
    mine.some((item) => item.scenes.some((sc) => sc.mean[k] !== undefined))
  );
  const active = indices.includes(index) ? index : indices[0];
  return (
    <section className="exp-section" aria-labelledby="timeseries-h">
      <h2 id="timeseries-h">The scenes behind each composite</h2>
      <p className="exp-note">
        Mean {active?.toUpperCase()} of each individual scene that fed the composites, over that scene's own
        valid pixels. This shows how much scenes within one period differ compared with the gap between the two
        periods. It is a description of 3 scenes per period, not a trend test.
      </p>
      <div className="segmented" role="group" aria-label="Index">
        {indices.map((k) => (
          <button key={k} type="button" className={k === active ? "is-active" : ""} aria-pressed={k === active} onClick={() => setIndex(k)}>
            {k.toUpperCase()}
          </button>
        ))}
      </div>
      {mine.map((item) => {
        const pts = item.scenes
          .filter((sc) => sc.mean[active] !== undefined)
          .map((sc) => ({ ...sc, t: Date.parse(sc.date), v: sc.mean[active] }));
        if (!pts.length) return null;
        const W = 640, H = 220, L = 52, R = 16, T = 14, B = 34;
        const ts = pts.map((q) => q.t), vs = pts.map((q) => q.v);
        const t0 = Math.min(...ts), t1 = Math.max(...ts);
        const pad = (Math.max(...vs) - Math.min(...vs) || 0.05) * 0.2;
        const v0 = Math.min(...vs) - pad, v1 = Math.max(...vs) + pad;
        const x = (t: number) => L + ((t - t0) / (t1 - t0 || 1)) * (W - L - R);
        const y = (v: number) => T + (1 - (v - v0) / (v1 - v0)) * (H - T - B);
        const label = `Per-scene mean ${active.toUpperCase()} for ${item.experiment}: ` +
          pts.map((q) => `${q.date} ${q.v.toFixed(3)}`).join(", ");
        return (
          <figure key={item.key} className="exp-card">
            <figcaption className="mono-label">{item.experiment}</figcaption>
            <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} style={{ width: "100%", maxWidth: 680, height: "auto" }}>
              <line x1={L} y1={T} x2={L} y2={H - B} stroke="currentColor" opacity="0.4" />
              <line x1={L} y1={H - B} x2={W - R} y2={H - B} stroke="currentColor" opacity="0.4" />
              {[v0, (v0 + v1) / 2, v1].map((v) => (
                <text key={v} x={L - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="currentColor">{v.toFixed(2)}</text>
              ))}
              {pts.map((q) => (
                <g key={q.item_id}>
                  <circle cx={x(q.t)} cy={y(q.v)} r={6} fill={q.period === "earlier" ? "#3c655d" : "#b3744e"} stroke="#18272d" strokeWidth="1" />
                  <text x={x(q.t)} y={H - B + 16} textAnchor="middle" fontSize="10" fill="currentColor">{q.date.slice(2)}</text>
                </g>
              ))}
            </svg>
            <p className="exp-note">
              <span style={{ color: "#3c655d" }}>●</span> earlier period · <span style={{ color: "#b3744e" }}>●</span> later period
            </p>
          </figure>
        );
      })}
    </section>
  );
}


/* --------------------------------------------- noise-aware threshold --- */

interface NoiseExperiment {
  experiment: string;
  study_id: string;
  framing: string;
  method: string;
  per_index: Record<
    string,
    {
      status: string;
      reason?: string;
      scenes_earlier?: number;
      scenes_later?: number;
      median_standard_error?: number;
      fixed_rule?: { decrease_pixels: number; increase_pixels: number };
      by_k?: Record<string, { fixed_rule_share_noise_supported: number | null; noise_significant_but_below_fixed_threshold: number }>;
    }
  >;
}

function NoisePanel({ studyId }: { studyId: string }) {
  const [items, setItems] = useState<NoiseExperiment[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch("studies/m6_noise.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((doc) => !cancelled && setItems(doc.experiments as NoiseExperiment[]))
      .catch(() => !cancelled && setItems([]));
    return () => {
      cancelled = true;
    };
  }, []);
  const mine = (items ?? []).filter((item) => item.study_id === studyId);
  if (mine.length === 0) return null;
  return (
    <section className="exp-section" aria-labelledby="noise-h">
      <h2 id="noise-h">Is the change bigger than the noise?</h2>
      <p className="exp-note">
        The fixed 0.15 rule is a convention. Each period is built from several scenes, so we can measure how much
        each pixel fluctuates between scenes of nearly the same date and ask whether the change is larger than that
        fluctuation. The table shows the share of fixed-rule changed pixels that pass this test.
      </p>
      {mine.map((item) => (
        <div key={item.experiment} className="exp-card">
          <p className="mono-label">{item.experiment}</p>
          <div className="exp-table-wrap">
            <table className="exp-table">
              <thead>
                <tr>
                  <th>Index</th>
                  <th>Scenes (earlier / later)</th>
                  <th>Typical noise (SE)</th>
                  <th>Changed pixels (fixed rule)</th>
                  <th>Pass noise test, 2×</th>
                  <th>Pass noise test, 3×</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(item.per_index).map(([index, r]) =>
                  r.status !== "ok" ? (
                    <tr key={index}>
                      <td>{index.toUpperCase()}</td>
                      <td colSpan={5}>Not testable: {r.reason}</td>
                    </tr>
                  ) : (
                    <tr key={index}>
                      <td>{index.toUpperCase()}</td>
                      <td>
                        {r.scenes_earlier} / {r.scenes_later}
                      </td>
                      <td>{r.median_standard_error?.toFixed(3)}</td>
                      <td>{(r.fixed_rule!.decrease_pixels + r.fixed_rule!.increase_pixels).toLocaleString()}</td>
                      {["2", "3"].map((k) => {
                        const share = r.by_k?.[k + ".0"]?.fixed_rule_share_noise_supported;
                        return <td key={k}>{share == null ? "n/a" : `${(share * 100).toFixed(1)}%`}</td>;
                      })}
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
          <p className="exp-note">{item.framing}</p>
        </div>
      ))}
    </section>
  );
}


/* -------------------------------------- independent validation panel --- */

interface ConfusionRow {
  tp: number; fp: number; fn: number; tn: number;
  precision: number | null; recall: number | null; f1: number | null;
  reference_base_rate: number | null; lift_over_chance: number | null;
}
interface ValidationResult {
  reference: { name: string; citation: string; licence: string; native_resolution_m: number };
  design: { domain: string; reference_positive: string; prediction: string };
  domain_pixels: number;
  reference_loss_pixels_in_domain: number;
  reference_loss_cells_30m_approx: number;
  predicted_decrease_pixels_in_domain: number;
  main: Record<string, ConfusionRow>;
  sensitivity_including_2020: Record<string, ConfusionRow>;
  sensitivity_one_pixel_tolerance: Record<string, ConfusionRow | string>;
  interpretation_guardrails: string[];
}

function ValidationPanel({ studyId }: { studyId: string }) {
  const [doc, setDoc] = useState<{ study_id: string; result: ValidationResult } | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch("studies/m6_validation.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => !cancelled && setDoc(d))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
  if (!doc || doc.study_id !== studyId) return null;
  const r = doc.result;
  const pct1 = (v: number | null) => (v == null ? "n/a" : `${(v * 100).toFixed(1)}%`);
  const rows: [string, ConfusionRow][] = [
    ["Main: loss 2021–2024", r.main.fixed_rule_ndvi_decrease],
    ["Including 2020", r.sensitivity_including_2020.fixed_rule_ndvi_decrease],
    ["One-pixel (30 m) tolerance", r.sensitivity_one_pixel_tolerance.fixed_rule_ndvi_decrease as ConfusionRow],
  ];
  return (
    <section className="exp-section" aria-labelledby="validation-h">
      <h2 id="validation-h">Independent check against forest-loss data</h2>
      <p className="exp-note">
        The NDVI-decrease map is compared with an independent product, <strong>{r.reference.name}</strong> (
        {r.reference.licence}), evaluated on forest pixels only. This is agreement with another satellite-derived
        product, not accuracy against ground truth.
      </p>
      <div className="exp-card">
        <div className="exp-table-wrap">
          <table className="exp-table">
            <thead>
              <tr>
                <th>Scenario</th>
                <th>Found by map (recall)</th>
                <th>Correct when flagged (precision)</th>
                <th>F1</th>
                <th>Hits / false alarms / misses</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([label, c]) => (
                <tr key={label}>
                  <td>{label}</td>
                  <td>{pct1(c.recall)}</td>
                  <td>{pct1(c.precision)}</td>
                  <td>{c.f1 == null ? "n/a" : c.f1.toFixed(2)}</td>
                  <td>
                    {c.tp} / {c.fp} / {c.fn}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="exp-note">
          Only about {r.reference_loss_cells_30m_approx} reference loss cells (30 m) fall in this {" "}
          {r.domain_pixels.toLocaleString()}-pixel forest area, so these figures are indicative, not a general accuracy
          claim. The map finds most recorded loss but also flags many pixels the reference does not call loss; NDVI
          also drops with leaf shedding and dryness, so low precision is expected.
        </p>
        <ul className="exp-note">
          {r.interpretation_guardrails.map((g) => (
            <li key={g}>{g}</li>
          ))}
        </ul>
        <p className="mono-label">{r.reference.citation}</p>
      </div>
    </section>
  );
}


/* ------------------------------------------------ monthly time series --- */

interface MonthlySeries {
  experiment: string;
  window: { start: string; end: string };
  comparison_anchors: string[];
  points: { month: string; date: string; valid_fraction: number; mean: Record<string, number> }[];
  gaps: { month: string; reason: string }[];
  model: null | {
    index: string;
    dates: string[];
    fitted: number[];
    trend_per_year: number;
    trend_ci95: [number, number];
    seasonal_amplitude: number;
    residual_sd: number;
    r_squared: number | null;
    n_months: number;
  };
  limits: string[];
}

const SERIES_OF_STUDY: Record<string, string> = {
  kathmandu_urban: "kathmandu_m4",
  western_ghats_forest: "western_ghats_m4",
};

function MonthlySeriesPanel({ studyId }: { studyId: string }) {
  const [series, setSeries] = useState<MonthlySeries | null>(null);
  const experiment = SERIES_OF_STUDY[studyId];
  useEffect(() => {
    setSeries(null);
    if (!experiment) return;
    let cancelled = false;
    fetch(`studies/m6_timeseries/${experiment}.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((doc) => !cancelled && setSeries(doc as MonthlySeries))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [experiment]);
  if (!experiment || !series || !series.model) return null;
  const idx = series.model.index;
  const pts = series.points.filter((q) => q.mean[idx] !== undefined);
  const W = 720, H = 260, L = 54, R = 16, T = 16, B = 36;
  const t = (d: string) => Date.parse(d);
  const t0 = Math.min(...pts.map((q) => t(q.date))), t1 = Math.max(...pts.map((q) => t(q.date)));
  const all = [...pts.map((q) => q.mean[idx]), ...series.model.fitted];
  const pad = (Math.max(...all) - Math.min(...all)) * 0.12 || 0.05;
  const v0 = Math.min(...all) - pad, v1 = Math.max(...all) + pad;
  const x = (ms: number) => L + ((ms - t0) / (t1 - t0 || 1)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - v0) / (v1 - v0)) * (H - T - B);
  const line = pts.map((q, i) => `${i ? "L" : "M"}${x(t(q.date)).toFixed(1)},${y(q.mean[idx]).toFixed(1)}`).join(" ");
  const fit = series.model.dates
    .map((d, i) => `${i ? "L" : "M"}${x(t(d)).toFixed(1)},${y(series.model!.fitted[i]).toFixed(1)}`)
    .join(" ");
  const anchors = series.comparison_anchors ?? [];
  // The monthly pick can differ from the anchor scene by a day or two; match the nearest within 4 days.
  const anchorPts = anchors.map((a) => {
    const near = pts
      .map((q) => ({ q, gap: Math.abs(t(q.date) - t(a)) }))
      .sort((u, v) => u.gap - v.gap)[0];
    return near && near.gap <= 4 * 86400000 ? near.q : undefined;
  });
  const diff = anchorPts[0] && anchorPts[1] ? anchorPts[1]!.mean[idx] - anchorPts[0]!.mean[idx] : null;
  const m = series.model;
  const years: number[] = [];
  for (let yr = new Date(t0).getUTCFullYear(); yr <= new Date(t1).getUTCFullYear(); yr++) years.push(yr);
  const label = `Monthly mean ${idx.toUpperCase()} for ${series.experiment}, ${pts.length} months from ${series.window.start} to ${series.window.end}`;
  return (
    <section className="exp-section" aria-labelledby="monthly-h">
      <h2 id="monthly-h">Monthly time series</h2>
      <p className="exp-note">
        One scene per month over {series.window.start} to {series.window.end}, mean {idx.toUpperCase()} over the box. A
        seasonal curve plus a linear drift is fitted so the normal yearly swing can be compared with the two-date
        difference used elsewhere. Months with no usable scene (mostly monsoon cloud) are left as gaps, not filled.
      </p>
      <figure className="exp-card">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} style={{ width: "100%", maxWidth: 760, height: "auto" }}>
          <line x1={L} y1={T} x2={L} y2={H - B} stroke="currentColor" opacity="0.4" />
          <line x1={L} y1={H - B} x2={W - R} y2={H - B} stroke="currentColor" opacity="0.4" />
          {[v0 + pad * 0.2, (v0 + v1) / 2, v1 - pad * 0.2].map((v) => (
            <text key={v} x={L - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="currentColor">{v.toFixed(2)}</text>
          ))}
          {years.map((yr) => {
            const ms = Date.UTC(yr, 0, 1);
            if (ms < t0 || ms > t1) return null;
            return (
              <g key={yr}>
                <line x1={x(ms)} y1={T} x2={x(ms)} y2={H - B} stroke="currentColor" opacity="0.12" />
                <text x={x(ms)} y={H - B + 16} textAnchor="middle" fontSize="11" fill="currentColor">{yr}</text>
              </g>
            );
          })}
          {anchors.map((a) => (
            <line key={a} x1={x(t(a))} y1={T} x2={x(t(a))} y2={H - B} stroke="#b3744e" strokeDasharray="4 3" />
          ))}
          <path d={line} fill="none" stroke="#3c655d" strokeWidth="1.4" />
          <path d={fit} fill="none" stroke="#18272d" strokeWidth="1.4" strokeDasharray="5 4" opacity="0.7" />
          {pts.map((q) => (
            <circle key={q.date} cx={x(t(q.date))} cy={y(q.mean[idx])} r={3.2} fill="#3c655d" />
          ))}
        </svg>
        <p className="exp-note">
          Solid line: monthly scenes. Dashed line: seasonal curve with drift. Orange verticals: the two dates of the
          recorded comparison.
        </p>
        <div className="exp-table-wrap">
          <table className="exp-table">
            <tbody>
              <tr>
                <th scope="row">Months with a usable scene</th>
                <td>
                  {m.n_months} ({series.gaps.length} gaps)
                </td>
              </tr>
              <tr>
                <th scope="row">Seasonal swing (amplitude)</th>
                <td>{m.seasonal_amplitude.toFixed(3)}</td>
              </tr>
              <tr>
                <th scope="row">Scatter around the curve (SD)</th>
                <td>{m.residual_sd.toFixed(3)}</td>
              </tr>
              <tr>
                <th scope="row">Drift per year (95% interval)</th>
                <td>
                  {m.trend_per_year.toFixed(4)} ({m.trend_ci95[0].toFixed(4)} to {m.trend_ci95[1].toFixed(4)})
                </td>
              </tr>
              {diff !== null && (
                <tr>
                  <th scope="row">Two-date difference used elsewhere</th>
                  <td>{diff.toFixed(3)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <ul className="exp-note">
          {series.limits.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </figure>
    </section>
  );
}

export function ExperimentsPage() {
  const [studyId, setStudyId] = useState<string>(STUDY_ORDER[0]);
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [bundles, setBundles] = useState<Record<string, StudyBundle>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [liveExperiment, setLiveExperiment] = useState<ExperimentSummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const reg = await loadRegistryJson();
        if (cancelled) return;
        setRegistry(reg);
        const ordered = STUDY_ORDER.map(
          (id) => reg.studies.find((s) => s.study_id === id)
        ).filter(Boolean) as NonNullable<ReturnType<typeof reg.studies.find>>[];
        const loaded = await Promise.all(
          ordered.map((study) =>
            loadStudyBundle(study.study_id)
              .then((bundle) => [study.study_id, bundle] as const)
              .catch(() => null)
          )
        );
        if (cancelled) return;
        setBundles(Object.fromEntries(loaded.filter(Boolean) as [string, StudyBundle][]));
      } catch (err) {
        if (!cancelled) setLoadError((err as Error).message);
      }
    })();
    // Best-effort: the recorded M2 run needs the backend; the page works
    // without it (bundle mirror) and says which mode is showing.
    api
      .experimentLatest("coringa_m2")
      .then((payload) => !cancelled && setLiveExperiment(payload))
      .catch(() => !cancelled && setLiveExperiment(null));
    return () => {
      cancelled = true;
    };
  }, []);

  const studies = useMemo(
    () =>
      STUDY_ORDER.map((id) => {
        const regStudy = registry?.studies.find((s) => s.study_id === id);
        return {
          id,
          title: regStudy?.title ?? STUDY_SHORT[id],
          status: bundles[id]?.evidence_status ?? regStudy?.status ?? "processed",
        };
      }),
    [registry, bundles]
  );

  const bundle = bundles[studyId];
  const isCoringa = studyId === "coringa_coastal";

  return (
    <main id="main" className="experiments-page">
      <header className="exp-head">
        <p className="eyebrow">Results &amp; experiments</p>
        <h1>Recorded measurements per investigation</h1>
        <p className="exp-lede">
          Choose an investigation. Each one reports only its genuine analytical
          outputs — recorded experiments where they exist, descriptive
          measurements elsewhere, and explicit gaps where an experiment has not
          been run.
        </p>
        <StudySelector studies={studies} active={studyId} onSelect={setStudyId} />
        {loadError && <ErrorNote message={`Registry unavailable: ${loadError}`} />}
      </header>

      {!bundle && !loadError && <p className="mono-label">Loading recorded outputs…</p>}

      {bundle && (
        <>
          {isCoringa && liveExperiment && <CoringaRecordedRun experiment={liveExperiment} />}
          {isCoringa && !liveExperiment && (
            <p className="exp-note">
              The backend is not serving the recorded hypothesis-testing run right now — the
              sections below render the same recorded numbers from the portable
              showcase bundle.
            </p>
          )}
          <BundleExperiments bundle={bundle} />
          <AvailabilityPanel bundle={bundle} />
          <ValidationPanel studyId={studyId} />
          <NoisePanel studyId={studyId} />
          <MonthlySeriesPanel studyId={studyId} />
          <TimeSeriesPanel studyId={studyId} />
          <InventoryPanel studyId={studyId} />
        </>
      )}
    </main>
  );
}
