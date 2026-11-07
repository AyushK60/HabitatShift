/** Study selection experience at /workstation (M4-R1 §2).
 *
 * Selecting "Workstation" no longer drops the visitor into a specific
 * investigation: without a studyId this page presents all six processed
 * investigations and lets the visitor choose. Direct study URLs
 * (/workstation/<study_id>) continue to bypass the picker.
 *
 * Rendered from the static registry and the portable bundles, so it works
 * in Showcase Mode with no Python backend. Nothing is invented: cards show
 * the registry's recorded status and each bundle's actual acquisition dates.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  loadRegistryJson,
  loadStudyBundle,
  type StudyBundle,
} from "../api/bundle";
import type { Registry, RegistryStudy } from "../api/types";
import { ErrorNote, StatusChip } from "../components/ui";

function bundlePeriodLabel(bundle: StudyBundle | undefined): string | null {
  const periods = bundle?.experiments[0]?.summary?.periods ?? [];
  if (periods.length < 2) return null;
  return `${periods[0].anchor_date} → ${periods[1].anchor_date}`;
}

function PickerCard({
  study,
  bundle,
}: {
  study: RegistryStudy;
  bundle?: StudyBundle;
}) {
  const isEvent = Boolean(study.event_date);
  return (
    <article className={`picker-card picker-card--${bundle?.evidence_status ?? study.status}`}>
      <header className="picker-card-head">
        <span className="study-letter" aria-hidden="true">
          {study.id}
        </span>
        <div>
          <p className="study-kind">
            {study.study_type.replace(/_/g, " ")}
            {isEvent ? ` · event ${study.event_date}` : ""}
          </p>
          <h2>{study.title}</h2>
        </div>
        <StatusChip status={bundle ? bundle.evidence_status : study.status} />
      </header>
      <p className="picker-question">{study.question}</p>
      {bundle && (
        <p className="mono-label picker-dates">
          Processed acquisitions: {bundlePeriodLabel(bundle)}
          {bundle.evidence_status === "partial" ? " · seasonal pair, PARTIAL evidence" : ""}
        </p>
      )}
      <footer className="picker-foot">
        <Link
          className="button button--primary"
          to={`/workstation/${encodeURIComponent(study.study_id)}`}
        >
          {isEvent ? "Open the event investigation" : "Open the investigation"}
        </Link>
      </footer>
    </article>
  );
}

export function StudyPicker() {
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [bundles, setBundles] = useState<Record<string, StudyBundle>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const reg = await loadRegistryJson();
        if (cancelled) return;
        setRegistry(reg);
        const loaded = await Promise.all(
          reg.studies.map((study) =>
            loadStudyBundle(study.study_id)
              .then((bundle) => [study.study_id, bundle] as const)
              .catch(() => null)
          )
        );
        if (cancelled) return;
        setBundles(Object.fromEntries(loaded.filter(Boolean) as [string, StudyBundle][]));
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <main id="main" className="picker-page workstation-error">
        <ErrorNote message={`The study registry could not be loaded (${error}).`} />
      </main>
    );
  }

  return (
    <main id="main" className="picker-page">
      <header className="picker-head">
        <p className="eyebrow">Research workstation</p>
        <h1>Choose an investigation</h1>
        <p className="picker-lede">
          Six investigations across five landscapes, each rendered from its
          recorded bundle: real Sentinel-2 acquisitions, explicit masking and
          documented thresholds. Coringa is the reference investigation with the
          full experiment framework; the 2025 Himalayan event carries its
          recorded PARTIAL status.
        </p>
      </header>
      {!registry && <p className="mono-label">Loading the study registry…</p>}
      {registry && (
        <div className="picker-grid">
          {registry.studies.map((study) => (
            <PickerCard
              key={study.id}
              study={study}
              bundle={bundles[study.study_id]}
            />
          ))}
        </div>
      )}
    </main>
  );
}
