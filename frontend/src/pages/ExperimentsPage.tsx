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
      label: "M1 composite & index measurements (threshold sweeps, period means, Δ statistics)",
      kind: "descriptive",
    },
    ...(hasM2
      ? [
          {
            label: "M2 hypothesis-testing run (estimator comparison, block bootstrap, verdicts)",
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
      : { label: "Supervised classification accuracy (no independent labels exist — M2 finding)", kind: "planned" as const },
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
          Recorded M1 outputs for {bundle.study.title}
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
              The backend is not serving the recorded M2 run right now — the
              sections below render the same recorded numbers from the portable
              showcase bundle.
            </p>
          )}
          <BundleExperiments bundle={bundle} />
          <AvailabilityPanel bundle={bundle} />
        </>
      )}
    </main>
  );
}
