/** Study-aware chart builders (M4-G5).
 *
 * Every chart here is assembled from recorded bundle data.  Interpretation
 * strings are fixed, method-based templates — the NUMBERS inside tooltips
 * come only from the recorded points, never from these templates.
 */
import type { ReactNode } from "react";
import type {
  BundleCharts,
  BundleEstimatorPoint,
  BundleM2Charts,
  BundleThresholdSeries,
  StudyBundle,
} from "../api/bundle";
import { InteractiveChart, type ChartSeries } from "./InteractiveChart";

const PALETTE = ["#1b4f9c", "#6b7690", "#5b8bd6", "#0d1320", "#a9b4c8", "#b3261e"];

/** G10: threshold-series legends must be distinguishable.  When several
 *  estimator configurations feed the same index, the display label carries a
 *  short configuration name and the tooltip carries the full technical
 *  identifier. */
function thresholdSeriesLabel(item: BundleThresholdSeries, seen: Set<string>): string {
  const base = `Δ${item.index.toUpperCase()} decrease`;
  const configShort =
    item.estimator_id === "composite_mean"
      ? "mean composite"
      : item.estimator_id === "composite_median"
        ? "median composite"
        : item.estimator_id
          ? item.estimator_id.replace(/_/g, " ")
          : null;
  let label = configShort ? `${base} · ${configShort}` : base;
  // Safety net: if two configurations still collide, disambiguate with the
  // recorded primary threshold (a genuine configuration difference).
  if (seen.has(label)) {
    label = `${label}${item.primary_threshold != null ? ` · ±${item.primary_threshold}` : " (2)"}`;
  }
  seen.add(label);
  return label;
}

/** G10: compact axis label for an estimator point; the full recorded label
 *  stays on the point and is shown on hover/focus. */
function estimatorShortLabel(estimatorId: string): string {
  if (estimatorId === "anchor_single") return "anchor";
  if (estimatorId === "composite_mean") return "mean";
  if (estimatorId === "composite_median") return "median";
  if (estimatorId === "m0_anchor_single_scene") return "single";
  const dates = estimatorId.match(/\d{8}/g) ?? [];
  const mmdd = (date: string) => `${date.slice(4, 6)}-${date.slice(6, 8)}`;
  if (estimatorId.startsWith("loo_")) {
    const first = dates[0];
    return first ? `LOO ${mmdd(first)}` : "LOO";
  }
  if (estimatorId.startsWith("single__")) {
    const a = dates[0];
    const b = dates[1];
    return a && b ? `${mmdd(a)}×${mmdd(b)}` : "pair";
  }
  return estimatorId.length > 14 ? `${estimatorId.slice(0, 13)}…` : estimatorId;
}

/* ------------------------------------------------ threshold sensitivity --- */

export function ThresholdChart({
  series,
  context,
  guardrail,
}: {
  series: BundleThresholdSeries[];
  context: string;
  guardrail?: string | null;
}) {
  const seenLabels = new Set<string>();
  const charts: ChartSeries[] = series
    .filter((item) => item.points.length > 0)
    .map((item, position) => ({
      id: item.estimator_id ? `${item.index}:${item.estimator_id}` : item.index,
      label: thresholdSeriesLabel(item, seenLabels),
      color: PALETTE[position % PALETTE.length],
      points: item.points.map((point) => ({
        x: point.threshold,
        y: point.decrease_percent_of_common,
        facts: (
          [
            item.estimator_id
              ? (["Estimator", item.estimator_id] as [string, string])
              : null,
            ["Candidate increase", `${point.increase_percent_of_common?.toFixed(2) ?? "–"} %`],
            point.decrease_area_ha !== undefined
              ? (["Candidate decrease area", `${point.decrease_area_ha.toFixed(2)} ha`] as [string, string])
              : null,
            ["Shared-valid pixels", point.valid_pixels.toLocaleString("en-GB")],
          ] as ([string, string] | null)[]
        ).filter((fact): fact is [string, string] => fact !== null),
        interpretation:
          guardrail ??
          `At |Δ| ≥ ${point.threshold}, ${point.decrease_percent_of_common.toFixed(2)} % of the shared-valid AOI satisfies the candidate-decrease criterion. This is a candidate spectral change signal, not independently verified land-cover change.`,
      })),
    }));
  if (!charts.length) return null;
  return (
    <InteractiveChart
      series={charts}
      xLabel="Difference threshold |Δ| ≥"
      yLabel="Candidate decrease"
      xUnit="index units"
      yUnit="% of shared-valid AOI"
      context={context}
      caption={`Threshold sensitivity: candidate-decrease share of the shared-valid AOI per index. ${context}`}
      canConclude={[
        "How the candidate-change area responds as the threshold tightens; equal thresholds compare indices on the same shared-valid footprint.",
      ]}
      cannotConclude={[
        "Land-cover change verdicts, causation, or area outside the shared-valid footprint.",
      ]}
    />
  );
}

/* -------------------------------------------------- pre/post index means --- */

export function PrePostMeansChart({
  charts,
  eventDate,
  studyId,
}: {
  charts: BundleCharts;
  eventDate?: string;
  studyId: string;
}) {
  const indices = [...new Set(charts.period_index_means.map((row) => row.index))];
  const periods = charts.period_index_means;
  const labels = [...new Set(periods.map((row) => row.anchor_date))];
  const context =
    `Recorded per-period mean index values on the shared analysis grid. ` +
    (eventDate
      ? `Event date ${eventDate}; both composites bracket the event seasonally. `
      : "") +
    `Study ${studyId}.`;
  const seriesList = indices
    .map((index, position) => {
      const points = labels.map((label) => {
        const row = periods.find(
          (item) => item.index === index && item.anchor_date === label
        );
        return row
          ? {
              x: labels.indexOf(label),
              label,
              y: row.mean,
              facts: [
                ["Valid pixels", row.valid_count.toLocaleString("en-GB")],
                ["Valid fraction", `${(row.valid_fraction * 100).toFixed(1)} %`],
              ] as [string, string][],
              interpretation:
                index === "ndbi"
                  ? `NDBI mean ${row.mean.toFixed(3)} for ${label}. NDBI is a candidate built-up spectral signal, not a building detector; bare soil and dry riverbeds can raise it.`
                  : eventDate
                    ? `Mean ${index.toUpperCase()} ${row.mean.toFixed(3)} for the ${label} composite (${Math.abs(daysBetween(label, eventDate))} days ${daysBetween(label, eventDate) >= 0 ? "after" : "before"} the event). Seasonal snow/ice evolution confounds same-season comparisons.`
                    : `Mean ${index.toUpperCase()} ${row.mean.toFixed(3)} for the ${label} composite of ${row.valid_count.toLocaleString("en-GB")} valid pixels.`,
            }
          : null;
      });
      return {
        id: index,
        label: index.toUpperCase(),
        color: PALETTE[position % PALETTE.length],
        points: points.filter((point): point is NonNullable<typeof point> => point !== null),
      };
    })
    .filter((series) => series.points.length > 0);
  if (!seriesList.length) return null;
  const fmtDate = (value: number) => labels[Math.round(value)] ?? String(value);
  return (
    <InteractiveChart
      series={seriesList}
      xLabel="Composite period (anchor date)"
      yLabel="Mean index value"
      context={context}
      caption={`Per-period mean index values. ${context}`}
      formatX={fmtDate}
      xCategorical
      canConclude={[
        "The recorded mean index level of each period's composite and how many valid observations back it.",
      ]}
      cannotConclude={[
        "Per-pixel change (see the map layers), or any cause of a difference between periods.",
      ]}
    />
  );
}

function daysBetween(dateA: string, dateB: string): number {
  return Math.round(
    (Date.parse(dateA) - Date.parse(dateB)) / 86400000
  );
}

/* ------------------------------------------- coringa: estimator comparison --- */

export function EstimatorChart({
  points,
  index,
  context,
}: {
  points: BundleEstimatorPoint[];
  index: string;
  context: string;
}) {
  const rows = points
    .filter((point) => point.index === index && point.delta_mean !== null)
    .slice()
    .sort((a, b) => a.family.localeCompare(b.family) || a.estimator_id.localeCompare(b.estimator_id));
  if (rows.length < 2) return null;
  const series: ChartSeries = {
    id: "estimators",
    label: `Δ${index.toUpperCase()} mean per estimator`,
    color: PALETTE[0],
    points: rows.map((row, position) => ({
      x: position,
      label: row.label,
      shortLabel: estimatorShortLabel(row.estimator_id),
      y: row.delta_mean as number,
      facts: (
        [
          ["Family", row.family],
          ["Estimator", row.estimator_id],
          ["Shared-valid pixels", row.common_valid_pixels.toLocaleString("en-GB")],
          row.decrease_percent_of_common !== null
            ? (["Candidate decrease at primary threshold", `${row.decrease_percent_of_common.toFixed(2)} %`] as [string, string])
            : null,
        ] as ([string, string] | null)[]
      ).filter((fact): fact is [string, string] => fact !== null),
      interpretation:
        "Each point is one recorded estimator (different observation selections) on its own shared-valid footprint. Differences between estimators are observation-selection effects for this AOI and grid — not measurement error bars.",
    })),
  };
  const fmtTick = (value: number) => rows[Math.round(value)]?.family ?? String(value);
  return (
    <InteractiveChart
      series={[series]}
      xLabel="Estimator (observation selection)"
      yLabel="Mean Δ value"
      context={context}
      caption={`Estimator comparison for Δ${index.toUpperCase()}. ${context}`}
      formatX={fmtTick}
      xCategorical
      canConclude={[
        "How much the recorded mean difference moves when the observation selection changes.",
      ]}
      cannotConclude={["Any population-level confidence interval."]}
    />
  );
}

/* ------------------------------------------------ coringa: bootstrap CIs --- */

export function BootstrapChart({
  bootstrap,
  index,
  primaryThreshold,
  context,
}: {
  bootstrap: Record<string, import("../api/bundle").BundleBootstrap>;
  index: string;
  primaryThreshold: number;
  context: string;
}) {
  const payload = bootstrap[index];
  if (!payload?.thresholds?.length) return null;
  const series: ChartSeries[] = [
    {
      id: "decrease",
      label: "Candidate decrease",
      color: PALETTE[1],
      points: payload.thresholds.map((row) => ({
        x: row.threshold,
        y: row.decrease_fraction * 100,
        facts: [
          [
            "Block-bootstrap 95% range",
            `${(row.decrease_fraction_ci95.p2_5 * 100).toFixed(2)}–${(row.decrease_fraction_ci95.p97_5 * 100).toFixed(2)} %`,
          ],
          ["Bootstrap median", `${(row.decrease_fraction_ci95.p50 * 100).toFixed(2)} %`],
        ] as [string, string][],
        interpretation:
          "The resampling range is spatial-block-bootstrap variability for this AOI and grid — it is NOT a population confidence interval.",
      })),
    },
    {
      id: "increase",
      label: "Candidate increase",
      color: PALETTE[2],
      points: payload.thresholds.map((row) => ({
        x: row.threshold,
        y: row.increase_fraction * 100,
        facts: [
          [
            "Block-bootstrap 95% range",
            `${(row.increase_fraction_ci95.p2_5 * 100).toFixed(2)}–${(row.increase_fraction_ci95.p97_5 * 100).toFixed(2)} %`,
          ],
        ] as [string, string][],
        interpretation:
          "Resampling variability for this AOI and grid, not a population confidence interval.",
      })),
    },
  ];
  return (
    <InteractiveChart
      series={series}
      xLabel="Difference threshold |Δ| ≥"
      yLabel="Candidate change share"
      xUnit="index units"
      yUnit="% of shared-valid AOI"
      context={`${context} ${payload.iterations_used} resamples of ${payload.block_size_px} px spatial blocks; primary threshold ±${primaryThreshold}.`}
      caption={`Block-bootstrap uncertainty for Δ${index.toUpperCase()}. ${context}`}
      canConclude={[
        "How stable the recorded change fractions are under spatial block resampling of this AOI.",
      ]}
      cannotConclude={["A population confidence interval, or variability beyond this AOI and grid."]}
    />
  );
}

/* -------------------------------------------------------- study assembly --- */

export interface StudyChartSpec {
  id: string;
  title: string;
  element: ReactNode;
}

export function buildStudyCharts(bundle: StudyBundle, experimentIndex: number): StudyChartSpec[] {
  const specs: StudyChartSpec[] = [];
  const studyId = bundle.study_id;
  const isCoringa = studyId === "coringa_coastal";
  const experiment = bundle.experiments[experimentIndex] ?? bundle.experiments[0];
  const guardrail = Object.values(experiment.summary.change ?? {})[0]?.interpretation_guardrail;
  const context =
    `${bundle.study.title} · Sentinel-2 L2A · composites ${experiment.summary.periods
      .map((period) => period.anchor_date)
      .join(" vs ")}.`;

  const thresholdSeries: BundleThresholdSeries[] = isCoringa
    ? (bundle.sources?.m2_experiment as BundleM2Charts | null)?.threshold_series ?? bundle.charts.threshold_series
    : bundle.charts.threshold_series;
  const threshold = ThresholdChart({
    series: thresholdSeries,
    context,
    guardrail: isCoringa ? null : guardrail,
  });
  if (threshold) {
    specs.push({
      id: "thresholds",
      title: "Threshold sensitivity",
      element: threshold,
    });
  }

  specs.push({
    id: "means",
    title: bundle.event ? "Observations relative to the event" : "Period index means",
    element: (
      <PrePostMeansChart
        charts={bundle.charts}
        eventDate={bundle.event?.event_date}
        studyId={studyId}
      />
    ),
  });

  const m2 = bundle.sources?.m2_experiment as BundleM2Charts | null;
  if (m2) {
    const indices = [...new Set(m2.estimator_comparison.map((row) => row.index))];
    const estimatorElement =
      indices.length > 0
        ? EstimatorChart({ points: m2.estimator_comparison, index: indices[0], context })
        : null;
    if (estimatorElement) {
      specs.push({ id: "estimators", title: "Estimator comparison", element: estimatorElement });
    }
    const bootstrapElement = BootstrapChart({
      bootstrap: m2.bootstrap,
      index: indices[0] ?? "ndvi",
      primaryThreshold: 0.15,
      context,
    });
    if (bootstrapElement) {
      specs.push({ id: "bootstrap", title: "Uncertainty (block bootstrap)", element: bootstrapElement });
    }
  }
  return specs;
}
