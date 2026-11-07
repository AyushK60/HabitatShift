/** Landing / Atlas — the signature editorial entry to HabitatShift.
 *
 * Scientific-integrity rules baked into this page:
 * - The hero imagery is the real processed Coringa comparison; its captions
 *   print the actual acquisition dates, scene IDs and composite method from
 *   the bundle's recorded M1 summary.
 * - The gallery is driven by the static registry copy and each study's own
 *   bundle: processed studies show their real composite previews, the two
 *   Himalayan events show their real processed source-zone context, and
 *   nothing is fabricated. Study D1 carries its recorded PARTIAL status.
 *
 * M4: the page renders from the portable bundles, so it works with the
 * Python backend stopped.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  bundlePreviewUrl,
  bundleSummary,
  loadRegistryJson,
  loadStudyBundle,
  type StudyBundle,
} from "../api/bundle";
import { useMemo } from "react";
import type { M1Summary, Registry } from "../api/types";
import { SwipeStage } from "../components/SwipeStage";
import { ErrorNote, MonoFact, StatusChip } from "../components/ui";
import "../styles/landing.css";

const CORINGA = "coringa_coastal";

function useLandingData() {
  const [summary, setSummary] = useState<M1Summary | null>(null);
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [bundles, setBundles] = useState<Record<string, StudyBundle>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [reg, coringaBundle] = await Promise.all([
          loadRegistryJson(),
          loadStudyBundle(CORINGA),
        ]);
        if (cancelled) return;
        setRegistry(reg);
        setSummary(bundleSummary(CORINGA, coringaBundle));
        setBundles({ [CORINGA]: coringaBundle });
        // Load the remaining bundles opportunistically for real gallery media.
        const others = reg.studies.filter((study) => study.study_id !== CORINGA);
        const loaded = await Promise.all(
          others.map((study) =>
            loadStudyBundle(study.study_id)
              .then((bundle) => [study.study_id, bundle] as const)
              .catch(() => null)
          )
        );
        if (cancelled) return;
        setBundles((prev) => {
          const next = { ...prev };
          for (const entry of loaded) {
            if (entry) next[entry[0]] = entry[1];
          }
          return next;
        });
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { summary, registry, bundles, error };
}

/** Schematic of a registry AOI window: real bounds, drawn as a map frame.
 *  It is explicitly a *window outline*, not imagery. */
function AoiSchematic({ study }: { study: import("../api/types").RegistryStudy }) {
  const { west, south, east, north } = study.aoi.bounds;
  const midLat = (south + north) / 2;
  const kmPerDegLon = 111.32 * Math.cos((midLat * Math.PI) / 180);
  const widthKm = (east - west) * kmPerDegLon;
  const heightKm = (north - south) * 110.57;
  const ratio = Math.min(2.2, Math.max(0.5, widthKm / heightKm));
  return (
    <div
      className="aoi-schematic"
      role="img"
      aria-label={`Schematic of the ${study.title} AOI working window (${study.aoi.approx_km} km), not satellite imagery`}
    >
      <svg viewBox="0 0 200 140" preserveAspectRatio="xMidYMid meet">
        <defs>
          <pattern id={`grid-${study.id}`} width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#d8d3c8" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="200" height="140" fill={`url(#grid-${study.id})`} />
        <rect
          x={100 - (ratio * 45)}
          y={70 - 45}
          width={ratio * 90}
          height={90}
          fill="rgba(127,171,167,0.18)"
          stroke="#193c43"
          strokeWidth="2"
          strokeDasharray="5 3"
        />
        <text x="8" y="132" fontFamily="var(--mono)" fontSize="8" fill="#56686d">
          {west.toFixed(3)}°E, {south.toFixed(3)}°N
        </text>
        <text x="192" y="14" textAnchor="end" fontFamily="var(--mono)" fontSize="8" fill="#56686d">
          {east.toFixed(3)}°E, {north.toFixed(3)}°N
        </text>
      </svg>
      <span className="aoi-schematic-note">
        AOI working window · {study.aoi.approx_km} km · {study.aoi.kind}
      </span>
    </div>
  );
}

function formatPeriodRange(study: import("../api/types").RegistryStudy): string | null {
  const periods = study.target_periods
    ? Object.values(study.target_periods)
    : [];
  if (!periods.length) return null;
  const starts = periods.map((p) => p.start).sort();
  const ends = periods.map((p) => p.end).sort();
  return `${starts[0]} → ${ends[ends.length - 1]}`;
}

/** True processed acquisition dates from the study's bundle, for the card. */
function bundlePeriodLabel(bundle: StudyBundle | undefined): string | null {
  const periods = bundle?.experiments[0]?.summary?.periods ?? [];
  if (!periods.length) return null;
  return `${periods[0].anchor_date} → ${periods[periods.length - 1].anchor_date}`;
}

/** The study's first-experiment summary with preview paths rebased to the
 *  bundled copies ("previews/<flat>.png" asset paths). */
function useCardSummary(studyId: string, bundle?: StudyBundle): M1Summary | null {
  return useMemo(
    () => (bundle ? bundleSummary(studyId, bundle) : null),
    [studyId, bundle]
  );
}

function GalleryCard({
  study,
  bundle,
}: {
  study: import("../api/types").RegistryStudy;
  bundle?: StudyBundle;
}) {
  const isCoringa = study.study_id === CORINGA;
  const periodRange = bundlePeriodLabel(bundle) ?? formatPeriodRange(study);
  const status = bundle ? bundle.evidence_status : study.status;
  const processed = Boolean(bundle);
  const summary = useCardSummary(study.study_id, bundle);
  const earlierPreview = summary?.periods?.[0]?.previews?.true_colour;
  const laterPreview = summary?.periods?.[1]?.previews?.true_colour;
  const mediaNote = bundle
    ? `Real processed composites · ${bundlePeriodLabel(bundle)} · Sentinel-2 L2A`
    : undefined;

  return (
    <article
      className={`study-card study-card--${status} ${isCoringa ? "study-card--lead" : ""}`}
      data-study-id={study.study_id}
    >
      <header className="study-card-head">
        <span className="study-letter" aria-hidden="true">
          {study.id}
        </span>
        <div>
          <p className="study-kind">
            {study.study_type.replace(/_/g, " ")}
            {study.event_date ? ` · event ${study.event_date}` : ""}
          </p>
          <h3>{study.title}</h3>
        </div>
        <StatusChip status={status} />
      </header>

      {processed && earlierPreview && laterPreview ? (
        <div className="study-card-media">
          <img
            src={bundlePreviewUrl(study.study_id, earlierPreview)}
            alt={`True-colour Sentinel-2 composite of the ${study.title} earlier period`}
            loading="lazy"
          />
          <img
            src={bundlePreviewUrl(study.study_id, laterPreview)}
            alt={`True-colour Sentinel-2 composite of the ${study.title} later period`}
            loading="lazy"
          />
          <span className="study-card-media-note">{mediaNote}</span>
        </div>
      ) : (
        <AoiSchematic study={study} />
      )}

      <p className="study-question">{study.question}</p>
      {periodRange && (
        <p className="study-period mono-label">
          {processed ? "Processed acquisitions" : "Target windows"}: {periodRange}
        </p>
      )}
      {bundle?.evidence_status === "partial" && (
        <p className="study-period mono-label">
          PARTIAL: no clean immediate post-event observation exists; the processed
          pair is seasonal and explicitly caveated.
        </p>
      )}
      <ul className="study-phenomena">
        {study.phenomena.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>

      <footer className="study-card-foot">
        {processed ? (
          <Link
            className="button button--primary"
            to={`/workstation/${encodeURIComponent(study.study_id)}`}
          >
            {isCoringa
              ? "Open the reference investigation"
              : study.event_date
                ? "Open the event investigation"
                : "Open the investigation"}
          </Link>
        ) : (
          <p className="study-status-note">
            {study.status === "feasibility"
              ? "Data feasibility recorded; no processed imagery is shown because none has been analysed yet."
              : "Registered study; processing is scheduled for a later milestone."}
          </p>
        )}
      </footer>
    </article>
  );
}

export function LandingPage() {
  const { summary, registry, bundles, error } = useLandingData();
  const earlierPeriod = summary?.periods?.[0];
  const laterPeriod = summary?.periods?.[1];
  const attribution = summary
    ? typeof summary.attribution === "string"
      ? summary.attribution
      : (summary.attribution?.text ?? "")
    : "";

  return (
    <main id="main">
      {/* ------------------------------------------------------------- hero */}
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Geospatial research platform</p>
          <h1>
            Read the landscape.
            <br />
            Trace what changed.
          </h1>
          <p className="lede">
            HabitatShift investigates coastal, wetland, forest, cryospheric-disaster
            and urban landscape change through reproducible open satellite data —
            real Sentinel-2 acquisitions, explicit masking, documented methods,
            and measurements you can re-run.
          </p>
          <div className="hero-actions">
            {/* M4-R1 §2: the Atlas action presents the study gallery here on
                the landing page instead of dropping the visitor into a
                specific investigation. The hash router owns location.hash, so
                the anchor is handled as a controlled smooth scroll. */}
            <a
              href="#studies"
              className="button button--primary"
              onClick={(event) => {
                event.preventDefault();
                document
                  .getElementById("studies")
                  ?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
            >
              Explore the Atlas
            </a>
            <Link to="/methods" className="button button--secondary">
              Read the Methods
            </Link>
          </div>
          {summary && (
            <dl className="hero-facts">
              <MonoFact label="Study sensor" value="Sentinel-2 MSI L2A" />
              <MonoFact
                label="Analysis grid"
                value={`${summary.grid.width} × ${summary.grid.height} px @ ${summary.grid.resolution_m} m`}
              />
              <MonoFact label="Analysis CRS" value={summary.grid.crs} />
              <MonoFact
                label="Engine verification"
                value={`${summary.verification.check_count}/${summary.verification.check_count} checks passed`}
              />
            </dl>
          )}
        </div>

        <div className="hero-media">
          {summary && earlierPeriod && laterPeriod ? (
            <>
              <SwipeStage
                earlier={{
                  src: bundlePreviewUrl(CORINGA, earlierPeriod.previews.true_colour),
                  alt: `True-colour composite, ${earlierPeriod.anchor_date}`,
                }}
                later={{
                  src: bundlePreviewUrl(CORINGA, laterPeriod.previews.true_colour),
                  alt: `True-colour composite, ${laterPeriod.anchor_date}`,
                }}
                aspectRatio={`${summary.grid.width} / ${summary.grid.height}`}
                showTools={false}
              />
              <div className="hero-media-caption">
                <span className="mono-label">
                  Coringa / Godavari delta · {earlierPeriod.anchor_date} →{" "}
                  {laterPeriod.anchor_date} · median composites of{" "}
                  {earlierPeriod.observation_count} / {laterPeriod.observation_count}{" "}
                  valid observations
                </span>
                <span className="mono-label hero-scenes">
                  Earlier scenes: {earlierPeriod.item_ids.join(" · ")}
                </span>
                <span className="mono-label hero-scenes">
                  Later scenes: {laterPeriod.item_ids.join(" · ")}
                </span>
                {attribution && (
                  <span className="mono-label hero-attr">{attribution}</span>
                )}
              </div>
            </>
          ) : (
            <div className="hero-media-empty" aria-live="polite">
              {error
                ? "Processed imagery could not be loaded. Build the showcase bundles with `python scripts/build_showcase_bundles.py` and reload."
                : "Loading the processed Coringa comparison…"}
            </div>
          )}
        </div>
      </section>

      {/* ----------------------------------------------------- five studies */}
      <section className="studies" id="studies" aria-labelledby="studies-title">
        <div className="section-head">
          <p className="eyebrow">Study areas</p>
          <h2 id="studies-title">Five landscapes, six investigations, one standard of evidence</h2>
          <p className="section-lede">
            Statuses below are the repository's own record. Every card that links
            to an investigation shows real processed composites from its bundle;
            the 2025 Himalayan event carries its recorded PARTIAL status instead
            of a cleaner story.
          </p>
        </div>

        {error && <ErrorNote message={`Registry unavailable: ${error}`} />}
        {!registry && !error && <p className="mono-label">Loading registry…</p>}
        {registry && (
          <div className="study-grid">
            {registry.studies.map((study) => (
              <GalleryCard
                key={study.id}
                study={study}
                bundle={bundles[study.study_id]}
              />
            ))}
          </div>
        )}
      </section>

      {/* ------------------------------------------------------- narrative */}
      <section className="method-strip" aria-labelledby="method-title">
        <div className="section-head">
          <p className="eyebrow">How evidence is made</p>
          <h2 id="method-title">Acquisition → masking → evidence</h2>
        </div>
        <ol className="method-steps">
          <li>
            <h3>Acquisition</h3>
            <p>
              Scenes are discovered on the Sentinel-2 L2A STAC catalogue and
              read as windowed COG byte ranges — never whole-scene downloads.
              Every scene ID and date is recorded in the run manifest, and the
              radiometric DN convention of every scene is validated against the
              pixels actually read.
            </p>
          </li>
          <li>
            <h3>Masking</h3>
            <p>
              Cloud, cloud shadow, cirrus, saturated and nodata pixels are
              excluded with the scene classification layer. Masked pixels are
              never interpolated; validity is carried through every product.
            </p>
          </li>
          <li>
            <h3>Evidence</h3>
            <p>
              Indices, composites and difference maps are computed on one
              co-registered grid, thresholded at stated values, and checked by
              an independent audit before anything reaches this interface.
            </p>
          </li>
        </ol>
        <p className="method-note">
          The result is a workstation where a reviewer can trace any displayed
          number back to a scene, a mask and a formula — or reproduce the whole
          run from the manifests. Completed studies are explorable as portable
          bundles even when no processing backend is running.
        </p>
      </section>

      {/* ---------------------------------------------------- credibility */}
      <section className="credibility" aria-label="Why the results can be trusted">
        <ul>
          <li>
            <strong>Open data.</strong> Copernicus Sentinel-2 L2A, free and
            open with attribution.
          </li>
          <li>
            <strong>Documented scenes.</strong> Every acquisition date and
            scene ID is in the manifests, not in a caption's memory.
          </li>
          <li>
            <strong>Repeatable.</strong> Fixed thresholds, recorded seeds and
            grid signatures; runs are verified by an independent audit script.
          </li>
          <li>
            <strong>Honest limits.</strong> Where evidence is partial — the 2025
            Rasuwa event's monsoon gap, Kathmandu's missing reference labels —
            the interface says so instead of papering over it.
          </li>
        </ul>
      </section>
    </main>
  );
}
