/** Landing / Atlas — the signature editorial entry to HabitatShift.
 *
 * Scientific-integrity rules baked into this page:
 * - The hero imagery is the real processed Coringa comparison; its captions
 *   print the actual acquisition dates, scene IDs and composite method from
 *   the M1 summary.
 * - The five-study gallery is driven by `studies/registry.yaml` (served
 *   verbatim by the backend); non-processed studies show their true status
 *   and an AOI window schematic drawn from their registry bounds — never
 *   fabricated imagery, metrics or dates.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, m1PreviewUrl } from "../api/client";
import type { M1Summary, Registry, RegistryStudy } from "../api/types";
import { SwipeStage } from "../components/SwipeStage";
import { ErrorNote, MonoFact, StatusChip } from "../components/ui";
import "../styles/landing.css";

const CORINGA = "coringa_coastal";

function useStudyData() {
  const [summary, setSummary] = useState<M1Summary | null>(null);
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.m1Summary(CORINGA), api.registry()])
      .then(([m1, reg]) => {
        if (!cancelled) {
          setSummary(m1);
          setRegistry(reg);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { summary, registry, error };
}

/** Schematic of a registry AOI window: real bounds, drawn as a map frame.
 *  It is explicitly a *window outline*, not imagery. */
function AoiSchematic({ study }: { study: RegistryStudy }) {
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

function formatPeriodRange(study: RegistryStudy): string | null {
  const periods = study.target_periods
    ? Object.values(study.target_periods)
    : [];
  if (!periods.length) return null;
  const starts = periods.map((p) => p.start).sort();
  const ends = periods.map((p) => p.end).sort();
  return `${starts[0]} → ${ends[ends.length - 1]}`;
}

function GalleryCard({ study }: { study: RegistryStudy }) {
  const isCoringa = study.study_id === CORINGA;
  const periodRange = formatPeriodRange(study);
  return (
    <article
      className={`study-card study-card--${study.status} ${isCoringa ? "study-card--lead" : ""}`}
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
        <StatusChip status={study.status} />
      </header>

      {isCoringa ? (
        <div className="study-card-media">
          <img
            src={m1PreviewUrl(CORINGA, "earlier_2020-03-26_true_colour.png")}
            alt="True-colour Sentinel-2 composite of the Coringa AOI, March 2020"
            loading="lazy"
          />
          <img
            src={m1PreviewUrl(CORINGA, "later_2025-03-25_true_colour.png")}
            alt="True-colour Sentinel-2 composite of the Coringa AOI, March 2025"
            loading="lazy"
          />
          <span className="study-card-media-note">
            Real processed composites · 2020-03-26 / 2025-03-25 · Sentinel-2 L2A
          </span>
        </div>
      ) : (
        <AoiSchematic study={study} />
      )}

      <p className="study-question">{study.question}</p>
      {periodRange && (
        <p className="study-period mono-label">Target windows: {periodRange}</p>
      )}
      <ul className="study-phenomena">
        {study.phenomena.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>

      <footer className="study-card-foot">
        {isCoringa ? (
          <Link className="button button--primary" to="/workstation">
            Open the investigation
          </Link>
        ) : (
          <p className="study-status-note">
            {study.status === "feasibility"
              ? "Data feasibility recorded in M0; no processed imagery is shown because none has been analysed yet."
              : "Registered study; processing is scheduled for a later milestone."}
          </p>
        )}
      </footer>
    </article>
  );
}

export function LandingPage() {
  const { summary, registry, error } = useStudyData();
  const earlierPeriod = summary?.periods?.[0];
  const laterPeriod = summary?.periods?.[1];
  const attribution =
    typeof summary?.attribution === "string"
      ? summary.attribution
      : summary?.attribution?.text;

  return (
    <main id="main">
      {/* ------------------------------------------------------------- hero */}
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Geospatial research workstation</p>
          <h1>
            Read the landscape.
            <br />
            Trace what changed.
          </h1>
          <p className="lede">
            HabitatShift investigates environmental, cryospheric-disaster and
            urban landscape change through reproducible open satellite data —
            real Sentinel-2 acquisitions, explicit masking, documented methods,
            and measurements you can re-run.
          </p>
          <div className="hero-actions">
            <Link to="/workstation" className="button button--primary">
              Explore the Atlas
            </Link>
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
                  src: m1PreviewUrl(CORINGA, earlierPeriod.previews.true_colour),
                  alt: `True-colour composite, ${earlierPeriod.anchor_date}`,
                }}
                later={{
                  src: m1PreviewUrl(CORINGA, laterPeriod.previews.true_colour),
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
                ? "Processed imagery could not be loaded. Start the backend API to view the real comparison."
                : "Loading the processed Coringa comparison…"}
            </div>
          )}
        </div>
      </section>

      {/* ----------------------------------------------------- five studies */}
      <section className="studies" id="studies" aria-labelledby="studies-title">
        <div className="section-head">
          <p className="eyebrow">Study areas</p>
          <h2 id="studies-title">Five landscapes, one standard of evidence</h2>
          <p className="section-lede">
            Statuses below are the repository's own record. Only Study A has a
            completed processed bundle today; the others state their real
            feasibility position instead of showing placeholder results.
          </p>
        </div>

        {error && <ErrorNote message={`Registry unavailable: ${error}`} />}
        {!registry && !error && <p className="mono-label">Loading registry…</p>}
        {registry && (
          <div className="study-grid">
            {registry.studies.map((study) => (
              <GalleryCard key={study.id} study={study} />
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
              Every scene ID and date is recorded in the run manifest.
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
          run from the manifests.
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
        </ul>
      </section>
    </main>
  );
}
