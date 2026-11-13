/** Scene availability for a small custom area (discovery only).
 *
 * First, safe stage of a custom-AOI mode: it asks the local backend (which
 * queries the public Sentinel-2 L2A catalogue) which scenes exist over a small
 * box. Nothing is downloaded or processed, and the limits are enforced by the
 * server. Without the backend the page says so instead of failing silently.
 */
import { useEffect, useState } from "react";
import { Explain } from "../components/Explain";
import "../styles/availability.css";

interface Scene {
  id: string;
  date: string;
  scene_cloud_percent: number | null;
  platform: string;
}
interface Availability {
  aoi: { bounds_4326: number[]; area_km2: number };
  window: { start: string; end: string; max_scene_cloud_percent: number };
  scenes_found: number;
  truncated_at_limit: boolean;
  scenes: Scene[];
  honest_notes: string[];
}



interface RunSummary {
  run_id: string;
  area_km2: number;
  periods: { period_id: string; observation_dates: string[]; item_ids: string[]; valid_fraction: number; true_colour: string | null }[];
  change: Record<
    string,
    {
      label: string;
      threshold: number;
      common_valid_area_ha: number;
      decrease_area_ha: number;
      increase_area_ha: number;
      decrease_percent: number;
      increase_percent: number;
      delta_preview: string | null;
      guardrail?: string;
    }
  >;
  limitations: string[];
  verification_passed: boolean | null;
}
interface RunStatus {
  run_id: string;
  status: "queued" | "running" | "done" | "failed";
  error: string | null;
  stages: string[];
  summary: RunSummary | null;
}

/** Bounded change analysis for the box above: same engine as the recorded studies. */
function CustomAnalysis({ bounds }: { bounds: [number, number, number, number] }) {
  const [earlier, setEarlier] = useState("2020-03-31");
  const [later, setLater] = useState("2025-03-29");
  const [state, setState] = useState<RunStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function start(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setState(null);
    setBusy(true);
    const [west, south, east, north] = bounds;
    const query = new URLSearchParams({
      west: String(west), south: String(south), east: String(east), north: String(north), earlier, later,
    });
    try {
      const response = await fetch(`/api/aoi/run?${query}`, { method: "POST" });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? `Request failed (HTTP ${response.status})`);
      }
      const { run_id } = (await response.json()) as { run_id: string };
      for (;;) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const poll = await fetch(`/api/aoi/run/${run_id}`);
        if (!poll.ok) throw new Error(`Status check failed (HTTP ${poll.status})`);
        const status = (await poll.json()) as RunStatus;
        setState(status);
        if (status.status === "done" || status.status === "failed") break;
      }
    } catch (caught) {
      setError(
        caught instanceof TypeError
          ? "The analysis backend is not reachable. This needs the local backend (start.bat)."
          : String((caught as Error).message)
      );
    } finally {
      setBusy(false);
    }
  }

  const summary = state?.summary;
  return (
    <section className="availability-result" aria-labelledby="custom-run-h">
      <h2 id="custom-run-h">Run a change analysis on this box</h2>
      <p className="availability-lede">
        Runs the same engine as the recorded studies on the box above: about 0.2 to 6 km², two dates at least 90 days
        apart, one run at a time, roughly a minute or two. The result is descriptive: there is no reference data for your
        area, so treat it as a first look, not a measurement.
      </p>
      <form className="availability-form" onSubmit={start}>
        <fieldset>
          <legend>Two seasons to compare</legend>
          <label>
            Earlier date
            <input type="date" value={earlier} min="2015-08-01" onChange={(e) => setEarlier(e.target.value)} required />
          </label>
          <label>
            Later date
            <input type="date" value={later} onChange={(e) => setLater(e.target.value)} required />
          </label>
        </fieldset>
        <button type="submit" className="toggle-btn is-active" disabled={busy} data-testid="custom-run">
          {busy ? "Running…" : "Run analysis"}
        </button>
      </form>
      <div role="status" aria-live="polite">
        {error && <p className="availability-error">{error}</p>}
        {state && state.status !== "done" && state.status !== "failed" && (
          <p>Working… completed steps: {state.stages.length ? state.stages.join(", ") : "starting"}</p>
        )}
        {state?.status === "failed" && <p className="availability-error">Run failed: {state.error}</p>}
        {summary && (
          <div data-testid="custom-result">
            <h3>
              Result for {summary.area_km2} km²{" "}
              {summary.verification_passed === false ? "(some internal checks failed)" : "(internal checks passed)"}
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
              {summary.periods.map((p) =>
                p.true_colour ? (
                  <figure key={p.period_id} style={{ margin: 0 }}>
                    <img src={p.true_colour} alt={`True colour, ${p.period_id}`} style={{ width: "100%", imageRendering: "auto" }} />
                    <figcaption className="mono">
                      {p.period_id} · {p.observation_dates.join(", ")}
                    </figcaption>
                  </figure>
                ) : null
              )}
              {Object.entries(summary.change).map(([key, c]) =>
                c.delta_preview ? (
                  <figure key={key} style={{ margin: 0 }}>
                    <img src={c.delta_preview} alt={`Change map ${c.label}`} style={{ width: "100%", imageRendering: "pixelated" }} />
                    <figcaption className="mono">Δ {c.label} (later − earlier)</figcaption>
                  </figure>
                ) : null
              )}
            </div>
            <table>
              <caption className="sr-only">Changed area at the fixed threshold</caption>
              <thead>
                <tr>
                  <th scope="col">Index</th>
                  <th scope="col">Threshold</th>
                  <th scope="col">Decrease</th>
                  <th scope="col">Increase</th>
                  <th scope="col">Compared area</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(summary.change).map(([key, c]) => (
                  <tr key={key}>
                    <td>{c.label}</td>
                    <td>±{c.threshold}</td>
                    <td>
                      {c.decrease_area_ha.toFixed(2)} ha ({c.decrease_percent.toFixed(2)}%)
                    </td>
                    <td>
                      {c.increase_area_ha.toFixed(2)} ha ({c.increase_percent.toFixed(2)}%)
                    </td>
                    <td>{c.common_valid_area_ha.toFixed(1)} ha</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="availability-notes">
              {summary.limitations.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

type SeasonId = "winter" | "spring" | "monsoon" | "autumn";
const SEASONS: { id: SeasonId; label: string; hint: string }[] = [
  { id: "winter", label: "Winter", hint: "Dec to Feb. Usually clear" },
  { id: "spring", label: "Spring", hint: "Mar to May. Some haze" },
  { id: "monsoon", label: "Monsoon", hint: "Jun to Sep. Mostly cloud" },
  { id: "autumn", label: "Autumn", hint: "Oct to Nov. Usually clear" },
];
const YEARS = Array.from({ length: new Date().getFullYear() - 2017 + 1 }, (_, i) => new Date().getFullYear() - i);

/** Date range for a season. Winter spans the turn of the year, so "Winter 2025" is Dec 2024 to Feb 2025. */
function seasonRange(year: number, season: SeasonId): [string, string] {
  const today = new Date().toISOString().slice(0, 10);
  const r: Record<SeasonId, [string, string]> = {
    winter: [`${year - 1}-12-01`, `${year}-02-28`],
    spring: [`${year}-03-01`, `${year}-05-31`],
    monsoon: [`${year}-06-01`, `${year}-09-30`],
    autumn: [`${year}-10-01`, `${year}-11-30`],
  };
  const [a, b] = r[season];
  return [a < "2015-06-23" ? "2015-06-23" : a, b > today ? today : b];
}

const SPOTS: { name: string; hint: string; bounds: [number, number, number, number]; year: number; season: SeasonId }[] = [
  { name: "Imja Tsho", hint: "Glacial lake, Nepal", bounds: [86.89, 27.88, 86.97, 27.92], year: 2024, season: "autumn" },
  { name: "Chilika lagoon", hint: "Wetland, Odisha", bounds: [85.3, 19.7, 85.34, 19.74], year: 2024, season: "winter" },
  { name: "Kathmandu core", hint: "Urban growth, Nepal", bounds: [85.3, 27.68, 85.34, 27.72], year: 2024, season: "winter" },
  { name: "Bastar forest", hint: "Forest loss, Chhattisgarh", bounds: [81.1, 19.18, 81.18, 19.24], year: 2025, season: "winter" },
  { name: "Coringa delta", hint: "Mangroves, Andhra Pradesh", bounds: [82.28, 16.78, 82.36, 16.84], year: 2025, season: "winter" },
];

const SEARCH_URL = "https://earth-search.aws.element84.com/v1/search";

/** Ask the local backend first; when it is not running, ask the public STAC catalogue directly (metadata only). */
async function lookup(bounds: number[], start: string, end: string, maxCloud: number): Promise<Availability> {
  const [west, south, east, north] = bounds;
  try {
    const query = new URLSearchParams({ west: String(west), south: String(south), east: String(east), north: String(north), start, end, max_cloud: String(maxCloud) });
    const response = await fetch(`/api/aoi/availability?${query}`);
    if (response.ok && (response.headers.get("content-type") ?? "").includes("json")) return (await response.json()) as Availability;
    if (response.status >= 400 && response.status < 500 && response.status !== 404) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail ?? `Request failed (HTTP ${response.status})`);
    }
  } catch (caught) {
    if (!(caught instanceof TypeError)) throw caught;
  }
  const response = await fetch(SEARCH_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      collections: ["sentinel-2-l2a"], bbox: bounds, datetime: `${start}T00:00:00Z/${end}T23:59:59Z`, limit: 100,
      query: { "eo:cloud_cover": { lte: maxCloud } }, sortby: [{ field: "properties.datetime", direction: "asc" }],
    }),
  });
  if (!response.ok) throw new Error(`The public scene catalogue answered HTTP ${response.status}.`);
  const doc = await response.json();
  const kmPerLon = 111.32 * Math.cos((((south + north) / 2) * Math.PI) / 180);
  const scenes: Scene[] = (doc.features ?? []).map((f: { id: string; properties: Record<string, unknown> }) => ({
    id: f.id, date: String(f.properties.datetime).slice(0, 10), platform: String(f.properties.platform ?? "sentinel-2"),
    scene_cloud_percent: typeof f.properties["eo:cloud_cover"] === "number" ? (f.properties["eo:cloud_cover"] as number) : null,
  }));
  return {
    aoi: { bounds_4326: bounds, area_km2: Math.round((east - west) * kmPerLon * (north - south) * 110.57 * 10) / 10 },
    window: { start, end, max_scene_cloud_percent: maxCloud }, scenes_found: scenes.length, truncated_at_limit: scenes.length >= 100, scenes,
    honest_notes: [
      "Looked up directly from the public Earth Search catalogue; this page did not need the analysis backend.",
      "Scene-wide cloud cover is not the cloud fraction inside your box.",
    ],
  };
}

function cloudClass(cloud: number | null): "clear" | "part" | "cloudy" {
  if (cloud === null) return "part";
  return cloud <= 10 ? "clear" : cloud <= 40 ? "part" : "cloudy";
}

function SceneTimeline({ result }: { result: Availability }) {
  const W = 880, H = 150, L = 36, R = 12, T = 12, B = 30;
  const t0 = Date.parse(result.window.start), t1 = Math.max(Date.parse(result.window.end), t0 + 864e5);
  const x = (d: string) => L + ((Date.parse(d) - t0) / (t1 - t0)) * (W - L - R);
  const ticks = 5;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="scene-timeline" role="img" aria-label={`${result.scenes_found} scenes over time; taller bars are clearer`}>
      {[0, 50, 100].map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={T + (1 - v / 100) * (H - T - B)} y2={T + (1 - v / 100) * (H - T - B)} className="st-grid" />
          <text x={L - 6} y={T + (1 - v / 100) * (H - T - B) + 4} textAnchor="end" className="st-tick">{v}%</text>
        </g>
      ))}
      {Array.from({ length: ticks + 1 }, (_, i) => {
        const date = new Date(t0 + ((t1 - t0) * i) / ticks);
        return <text key={i} x={L + (i / ticks) * (W - L - R)} y={H - 8} textAnchor="middle" className="st-tick">{date.toISOString().slice(0, 10)}</text>;
      })}
      {result.scenes.map((s) => {
        const clear = 100 - (s.scene_cloud_percent ?? 50);
        const h = Math.max(3, (clear / 100) * (H - T - B));
        return <rect key={s.id} x={x(s.date) - 3} y={H - B - h} width={6} height={h} rx={2} className={`st-bar st-${cloudClass(s.scene_cloud_percent)}`}><title>{`${s.date}: ${s.scene_cloud_percent === null ? "cloud n/a" : `${s.scene_cloud_percent.toFixed(0)}% cloud`}`}</title></rect>;
      })}
    </svg>
  );
}

function SpotMap({ bounds }: { bounds: [number, number, number, number] }) {
  const [w, s, e, n] = bounds;
  const km = (e - w) * 111.32 * Math.cos((((s + n) / 2) * Math.PI) / 180);
  const kmv = (n - s) * 110.57;
  const r = Math.min(1, Math.max(0.35, km / kmv));
  const bw = r >= 1 ? 84 : 84 * r, bh = r >= 1 ? 84 / r : 84;
  return (
    <svg viewBox="0 0 120 100" className="spot-map" aria-hidden="true">
      <defs><pattern id="sg" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M12 0H0V12" fill="none" className="sg-line" /></pattern></defs>
      <rect width="120" height="100" fill="url(#sg)" />
      <rect x={60 - bw / 2} y={50 - bh / 2} width={bw} height={bh} className="sg-box" />
      <text x="4" y="96" className="sg-label">{w.toFixed(2)}E {s.toFixed(2)}N</text>
    </svg>
  );
}

export function AvailabilityPage() {
  const [spot, setSpot] = useState(0);
  const [bounds, setBounds] = useState<[number, number, number, number]>(SPOTS[0].bounds);
  const [year, setYear] = useState(SPOTS[0].year);
  const [season, setSeason] = useState<SeasonId | "custom">(SPOTS[0].season);
  const [start, setStart] = useState(seasonRange(SPOTS[0].year, SPOTS[0].season)[0]);
  const [end, setEnd] = useState(seasonRange(SPOTS[0].year, SPOTS[0].season)[1]);
  const [maxCloud, setMaxCloud] = useState(40);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Availability | null>(null);
  // The first answer is a real lookup for the default place, shown as an example until the visitor runs their own.
  const [isExample, setIsExample] = useState(true);

  function applySeason(y: number, s: SeasonId) {
    const [a, b] = seasonRange(y, s);
    setYear(y); setSeason(s); setStart(a); setEnd(b);
  }

  function pick(i: number) {
    setSpot(i);
    setBounds(SPOTS[i].bounds);
    applySeason(SPOTS[i].year, SPOTS[i].season);
    setResult(null);
    setError(null);
    setIsExample(false);
  }

  useEffect(() => {
    let cancelled = false;
    const [a, b] = seasonRange(SPOTS[0].year, SPOTS[0].season);
    lookup(SPOTS[0].bounds, a, b, 40).then((r) => { if (!cancelled) setResult((cur) => cur ?? r); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  async function run(event: React.FormEvent) {
    event.preventDefault();
    setIsExample(false);
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await lookup(bounds, start, end, maxCloud));
    } catch (caught) {
      setError(caught instanceof TypeError ? "Could not reach the scene catalogue. Check the internet connection and try again." : String((caught as Error).message));
    } finally {
      setBusy(false);
    }
  }

  const setBound = (i: number, value: string) =>
    setBounds((prev) => prev.map((v, j) => (j === i ? Number(value) : v)) as [number, number, number, number]);
  const clearScenes = result ? result.scenes.filter((s) => cloudClass(s.scene_cloud_percent) === "clear").length : 0;
  const grade: "good" | "ok" | "low" = clearScenes >= 6 ? "good" : clearScenes >= 3 ? "ok" : "low";

  return (
    <main id="main" className="availability scenecheck">
      <header className="page-head">
        <h1>Scene check</h1>
        <p className="page-lede">
          Can satellites actually see this place? Clouds block the pictures, especially in the monsoon. Before you trust a
          change map, check here that enough clear photos exist.
        </p>
      </header>

      <aside className="scene-why">
        <b>Why check first?</b>
        <p>
          A change map compares two pictures. If those pictures are cloudy, the map shows cloud, not change. This page only
          looks up the public photo list. Nothing is downloaded and no change is computed.
        </p>
      </aside>

      <form className="scene-form" data-tour="scene-form" onSubmit={run}>
        <div className="scene-where">
          <h2 className="scene-step"><i>1</i>Pick a place</h2>
          <div className="spot-grid" role="radiogroup" aria-label="Place">
            {SPOTS.map((s, i) => (
              <button key={s.name} type="button" role="radio" aria-checked={spot === i} className={`spot${spot === i ? " is-on" : ""}`} onClick={() => pick(i)}>
                <strong>{s.name}</strong>
                <span>{s.hint}</span>
              </button>
            ))}
          </div>
          <details className="scene-custom">
            <summary>Use my own box (degrees)</summary>
            <div className="scene-coords">
              {(["West", "South", "East", "North"] as const).map((label, i) => (
                <label key={label}>
                  {label}
                  <input type="number" step="0.001" value={bounds[i]} onChange={(e) => setBound(i, e.target.value)} required />
                </label>
              ))}
            </div>
          </details>
          <SpotMap bounds={bounds} />
        </div>

        <div className="scene-when">
          <h2 className="scene-step"><i>2</i>Pick a season</h2>
          <label className="scene-year">Year
            <select value={year} onChange={(e) => applySeason(Number(e.target.value), season === "custom" ? "autumn" : season)}>
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </label>
          <div className="season-grid" role="radiogroup" aria-label="Season">
            {SEASONS.map((s) => (
              <button key={s.id} type="button" role="radio" aria-checked={season === s.id} className={`season${season === s.id ? " is-on" : ""}`} onClick={() => applySeason(year, s.id)}>
                <strong>{s.label}</strong>
                <span>{s.hint}</span>
              </button>
            ))}
          </div>
          <details className="scene-custom">
            <summary>Exact dates and cloud limit</summary>
            <div className="scene-dates">
              <label>From<input type="date" value={start} min="2015-06-23" onChange={(e) => { setStart(e.target.value); setSeason("custom"); }} required /></label>
              <label>To<input type="date" value={end} onChange={(e) => { setEnd(e.target.value); setSeason("custom"); }} required /></label>
            </div>
            <label className="scene-cloud">
              Skip photos cloudier than <b>{maxCloud}%</b>
              <input type="range" min={5} max={100} step={5} value={maxCloud} onChange={(e) => setMaxCloud(Number(e.target.value))} />
            </label>
          </details>
          <h2 className="scene-step"><i>3</i>See the answer</h2>
          <button type="submit" className="button button--primary" disabled={busy} data-testid="avail-run">
            {busy ? "Searching…" : "Check this place and season"}
          </button>
        </div>
      </form>

      <div role="status" aria-live="polite">
        {error && <p className="availability-error" data-testid="avail-error">{error}</p>}
        {result && (
          <section className="scene-result" data-testid="avail-result">
            {isExample && <p className="scene-example">Example answer for {SPOTS[0].name}, autumn {SPOTS[0].year}. Pick anything above and press the button to check your own.</p>}
            <div className={`scene-answer is-${grade}`}>
              <p className="scene-headline">
                {grade === "good" ? `Yes, satellites can see ${SPOTS[spot].name} clearly.`
                  : grade === "ok" ? "Partly. There are a few clear photos."
                  : "Not really. Too few clear photos."}
              </p>
              <p className="scene-meaning">
                {grade === "good" ? "A change map for this season should rest on solid pictures."
                  : grade === "ok" ? "A change map is possible but rests on few photos. Treat it as a rough guide."
                  : "A change map here would be weak. Try a drier season (winter or autumn) or allow more cloud."}
              </p>
              <div className="scene-summary">
                <p className="scene-big"><b>{clearScenes}</b> clear photo{clearScenes === 1 ? "" : "s"}<span> (10% cloud or less)</span></p>
                <p className="scene-big"><b>{result.scenes_found}</b> in total<span> over {result.aoi.area_km2} km²{result.truncated_at_limit ? ", list cut at 100" : ""}</span></p>
              </div>
            </div>
            <div className="plate">
              <SceneTimeline result={result} />
              <p className="scene-legend"><i className="st-clear" />Clear <i className="st-part" />Some cloud <i className="st-cloudy" />Cloudy. Taller bar means clearer scene.</p>
              <Explain
                plain="Each bar is one time a satellite photographed the place. A tall bar means a clear photo you can use; a short bar means cloud got in the way. Empty stretches mean no photo, often because of monsoon cloud."
                technical={<>Sentinel-2 L2A items from Earth Search for the box and window. The percentage is scene-wide cloud cover, not the cloud fraction inside the box.</>}
              />
            </div>
            {result.scenes_found > 0 && (
              <details className="scene-table">
                <summary>All {result.scenes_found} scenes</summary>
                <table>
                  <caption className="sr-only">Sentinel-2 L2A scenes intersecting the box</caption>
                  <thead><tr><th scope="col">Date</th><th scope="col">Scene</th><th scope="col">Platform</th><th scope="col">Scene cloud %</th></tr></thead>
                  <tbody>
                    {result.scenes.map((scene) => (
                      <tr key={scene.id}>
                        <td>{scene.date}</td><td className="mono">{scene.id}</td><td>{scene.platform}</td>
                        <td>{scene.scene_cloud_percent === null ? "n/a" : scene.scene_cloud_percent.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}
            <ul className="availability-notes">{result.honest_notes.map((note) => <li key={note}>{note}</li>)}</ul>
          </section>
        )}
      </div>
      <CustomAnalysis bounds={bounds} />
    </main>
  );
}
