/** Landing / Atlas - the signature editorial entry to HabitatShift.
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
import { HeroChange } from "../components/HeroChange";
import { BeforeAfter, ScoreBars, YearToggle, type Bar } from "../components/Figures";
import { StatusChip } from "../components/ui";
import "../styles/landing.css";
import "../styles/research.css";

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

interface Figures {
  imja: { area_2018_km2: number; area_2024_km2: number; growth_centre: [number, number]; size: [number, number] };
  rolpa: { area_2018_km2: number; area_2024_km2: number };
  thulagi: { area_2018_km2: number; area_2024_km2: number };
  forest: { loss_share_pct: number };
  unet: { iou: number; model_km2: number; optical_km2: number; date: string };
}
interface Row { id: string; label: string; ap: number }
interface Research {
  forest: Record<string, { counts: { base_rate: number }; rows: Row[] }>;
  lakes: { counts: { base_rate: number }; rows: Row[] };
  unet: { sets: Record<string, { unet_mean: number; otsu: number }> };
}

const pick = (rows: Row[], ids: string[], names: Record<string, string>): Bar[] =>
  ids.map((id) => {
    const r = rows.find((x) => x.id === id)!;
    return { label: names[id] ?? r.label, value: r.ap, kind: id === "prithvi" || id === "ssl4eo_rgb" ? "strong" : id === "ndvi_decrease" || id === "mndwi" ? "ref" : "plain" } as Bar;
  });

function LakeTrio({ figs }: { figs: Figures }) {
  const [v, setV] = useState<0 | 1>(0);
  const lakes = [
    { tag: "imja", name: "Imja Tsho", note: `${figs.imja.area_2018_km2.toFixed(1)} to ${figs.imja.area_2024_km2.toFixed(1)} km²`, grew: true },
    { tag: "rolpa", name: "Tsho Rolpa", note: "about the same", grew: false },
    { tag: "thulagi", name: "Thulagi", note: "about the same", grew: false },
  ];
  return (
    <figure className="trio">
      <div className="trio-grid">
        {lakes.map((l) => (
          <div key={l.tag} className="trio-cell">
            <div className="trio-frame">
              <img src={`./figures/${l.tag}_2018.jpg`} alt={`${l.name}, October 2018`} loading="lazy" />
              <img src={`./figures/${l.tag}_2024.jpg`} alt={`${l.name}, October 2024`} className="ba-top" style={{ opacity: v }} loading="lazy" />
              <img src={`./figures/${l.tag}_outline_2018.png`} alt="" aria-hidden="true" className="ba-ov" />
              <img src={`./figures/${l.tag}_outline_2024.png`} alt="" aria-hidden="true" className="ba-ov" style={{ opacity: v }} />
            </div>
            <p><b>{l.name}</b><span>{l.note}</span></p>
          </div>
        ))}
      </div>
      <figcaption><YearToggle labels={["Oct 2018", "Oct 2024"]} value={v} onChange={setV} /><span className="ba-note">White line: 2018 shore. Blue: new lake.</span></figcaption>
    </figure>
  );
}

export function LandingPage() {
  const { summary, registry, bundles, error } = useLandingData();
  const [figs, setFigs] = useState<Figures | null>(null);
  const [res, setRes] = useState<Research | null>(null);
  const [sys, setSys] = useState<{ counts: Record<string, number> } | null>(null);
  const earlierPeriod = summary?.periods?.[0];
  const laterPeriod = summary?.periods?.[1];

  useEffect(() => {
    const get = (url: string, set: (d: never) => void) =>
      fetch(url).then((r) => (r.ok ? r.json() : null)).then((d) => d && set(d as never)).catch(() => undefined);
    get("./figures/figures.json", setFigs as never);
    get("./research/v3.json", setRes as never);
    get("./system/system.json", setSys as never);
  }, []);

  return (
    <main id="main" className="landing">
      <header className="hero" data-tour="hero">
        {figs ? <HeroChange fig={figs.imja} /> : <div className="hero-empty" />}
        <div className="hero-copy">
          <h1>Is that change real, or just noise?</h1>
          <p className="lede">
            HabitatShift compares satellite pictures taken months apart and says honestly when a difference is bigger than
            the normal wobble between two scenes. This year it also tested whether AI models do the job better than simple
            formulas.
          </p>
          <div className="hero-actions">
            <button type="button" className="btn btn--fill" onClick={() => window.dispatchEvent(new Event("habitatshift:tour"))}>
              Take the 3-minute tour
            </button>
            <Link to="/research" className="btn btn--line">Open the research view</Link>
          </div>
        </div>
      </header>

      {sys && (
        <section className="ribbon" aria-label="What the project covers">
          <div><b>{sys.counts.lakes}</b><span>glacial lakes mapped across Nepal</span></div>
          <div><b>{sys.counts.training_pairs.toLocaleString("en-GB")}</b><span>radar and optical image pairs</span></div>
          <div><b>2</b><span>foundation models tested against simple formulas</span></div>
          <div><b>{sys.counts.study_areas}</b><span>study areas, from coast to glacier</span></div>
        </section>
      )}

      <section className="band-section">
        <div className="page question" data-tour="question">
          <h2>Two pictures of the same place never match exactly</h2>
          <div className="q-text">
            <p>
              Clouds, haze, sun angle and the season all change a picture. A good change test first measures that everyday
              wobble, then asks whether the change it found is bigger. If it is not, the honest answer is that the change
              cannot be told apart from noise.
            </p>
            <p>
              The question this year was whether AI models trained on millions of satellite images can do this better than
              simple formulas. Every number below is shown with its uncertainty, and every score is agreement with a
              reference product, not measured accuracy.
            </p>
          </div>
        </div>
      </section>

      <section className="page found" aria-label="What the tests found">
        {figs && res && (
          <>
            <article className="fig-row">
              <div className="fig-media">
                <BeforeAfter
                  before="./figures/forest_2021.jpg"
                  after="./figures/forest_2025.jpg"
                  overlay="./figures/forest_loss_outline.png"
                  labels={["Feb-Mar 2021", "Feb-Mar 2025"]}
                  alt="Forest in Bastar, central India"
                  note="White outlines: forest cleared 2022 to 2024"
                />
              </div>
              <div className="fig-text">
                <h3>Forest loss: a plain greenness score was as good as AI</h3>
                <p>
                  In Bastar, central India, {figs.forest.loss_share_pct}% of this 4 km window was cleared between 2022 and 2024
                  (white outlines). Each method was asked to rank cleared patches above untouched ones. A simple "did it get
                  less green" score did about as well as two AI models.
                </p>
                <ScoreBars
                  title="How well each method finds cleared patches"
                  bars={pick(res.forest.bastar_forest.rows, ["ndvi_decrease", "raw6", "prithvi", "ssl4eo_rgb"], {
                    ndvi_decrease: "Plain greenness drop", raw6: "Raw colour bands", prithvi: "AI model: Prithvi", ssl4eo_rgb: "AI model: SSL4EO",
                  })}
                  chance={res.forest.bastar_forest.counts.base_rate}
                  caption="1 is perfect. The thin line is guessing."
                />
                <Link to="/research#forest" className="more">See all forest areas</Link>
              </div>
            </article>

            <article className="fig-row fig-row--flip">
              <div className="fig-media"><LakeTrio figs={figs} /></div>
              <div className="fig-text">
                <h3>Glacial lakes: AI beat the standard water formula, and so did plain colours</h3>
                <p>
                  Imja Tsho grew toward its glacier while Tsho Rolpa and Thulagi stayed put. Radar water maps are the
                  reference. The AI model found the changed shoreline better than the standard water index, but plain colour
                  values did just as well, so the gain is not from the AI.
                </p>
                <ScoreBars
                  title="How well each method finds changed shoreline"
                  bars={pick(res.lakes.rows, ["raw6", "prithvi", "ndvi", "mndwi"], {
                    raw6: "Raw colour bands", prithvi: "AI model: Prithvi", ndvi: "Greenness index", mndwi: "Standard water index",
                  })}
                  chance={res.lakes.counts.base_rate}
                  caption="Mostly one lake changed, so the ranges are wide."
                />
                <Link to="/research#lakes" className="more">See the lake scores</Link>
              </div>
            </article>

            <article className="fig-row">
              <div className="fig-media">
                <figure className="tri">
                  <div className="tri-grid">
                    <div><img src="./figures/radar_input.jpg" alt="Radar picture of Imja Tsho; water is black" loading="lazy" /><p><b>1 Radar</b>Water shows black, in any weather</p></div>
                    <div><img src="./figures/radar_model.jpg" alt="Radar picture with the trained model's lake shaded blue" loading="lazy" /><p><b>2 Model</b>The trained model draws the lake</p></div>
                    <div><img src="./figures/radar_optical.jpg" alt="Radar picture with the optical reference lake shaded orange" loading="lazy" /><p><b>3 Optical map</b>The reference it learned from</p></div>
                  </div>
                  <figcaption>Imja Tsho, {figs.unet.date}. This lake was held out when its model was trained. Agreement {figs.unet.iou.toFixed(2)}; {figs.unet.model_km2.toFixed(1)} km² drawn against {figs.unet.optical_km2.toFixed(1)} km² in the reference.</figcaption>
                </figure>
              </div>
              <div className="fig-text">
                <h3>A small radar model can draw lakes through cloud</h3>
                <p>
                  Optical pictures fail in the monsoon; radar does not. A small model trained on 30 Nepal lakes learned to draw
                  lake outlines from radar. On lakes it never saw it agrees with the optical map better than a plain radar
                  threshold. Its area ranges hold on average but fail badly for a few lakes.
                </p>
                <ScoreBars
                  title="Agreement with the optical lake map, unseen lakes"
                  bars={[
                    { label: "Trained radar model", value: res.unet.sets.test_lakes.unet_mean, kind: "strong" },
                    { label: "Plain radar rule", value: res.unet.sets.test_lakes.otsu, kind: "plain" },
                  ]}
                  caption="1 is a perfect match."
                />
                <Link to="/research#unet" className="more">See the radar model results</Link>
              </div>
            </article>
          </>
        )}
      </section>

      <section className="page seeit" aria-labelledby="seeit-title">
        <div className="seeit-copy">
          <h2 id="seeit-title">Slide between before and after</h2>
          <p className="page-lede">Drag the handle across the Coringa mangrove delta in India. Left is earlier, right is later.</p>
          <Link to="/workstation/coringa_coastal" className="button button--primary">Open this study</Link>
          {earlierPeriod && laterPeriod && (
            <p className="mono-label seeit-meta">
              {earlierPeriod.anchor_date} to {laterPeriod.anchor_date}. Median of {earlierPeriod.observation_count} and{" "}
              {laterPeriod.observation_count} clear observations.
            </p>
          )}
        </div>
        <div className="seeit-media">
          {summary && earlierPeriod && laterPeriod ? (
            <SwipeStage
              earlier={{ src: bundlePreviewUrl(CORINGA, earlierPeriod.previews.true_colour), alt: `True-colour composite, ${earlierPeriod.anchor_date}` }}
              later={{ src: bundlePreviewUrl(CORINGA, laterPeriod.previews.true_colour), alt: `True-colour composite, ${laterPeriod.anchor_date}` }}
              aspectRatio={`${summary.grid.width} / ${summary.grid.height}`}
              showTools={false}
            />
          ) : (
            <div className="hero-media-empty" aria-live="polite">
              {error ? "Processed imagery could not be loaded." : "Loading the Coringa comparison…"}
            </div>
          )}
        </div>
      </section>

      <section className="band-section">
        <div className="studies page" id="studies" aria-labelledby="studies-title">
          <div className="section-head">
            <h2 id="studies-title">Where we looked</h2>
            <p className="section-lede">
              Coastal, forest, wetland, urban and glacial-lake studies, each with its own before and after pictures and a stated question.
            </p>
          </div>
          {!registry && !error && <p className="mono-label">Loading registry…</p>}
          {registry && (
            <div className="study-grid">
              {registry.studies.map((study) => (
                <GalleryCard key={study.study_id} study={study} bundle={bundles[study.study_id]} />
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="page nextsteps" aria-label="Where to go next">
        <Link to="/lakes"><strong>Glacial lakes</strong><span>Monthly lake area from radar, optical and the trained model, 2017 to 2026.</span></Link>
        <Link to="/experiments"><strong>Evidence</strong><span>Every graph per study area, with plain-words notes.</span></Link>
        <Link to="/availability"><strong>Scene check</strong><span>Which clear images exist for any place and date.</span></Link>
        <Link to="/system"><strong>System</strong><span>What the pipeline behind the site has processed.</span></Link>
      </section>
    </main>
  );
}
