/** Scene availability for a small custom area (discovery only).
 *
 * First, safe stage of a custom-AOI mode: it asks the local backend (which
 * queries the public Sentinel-2 L2A catalogue) which scenes exist over a small
 * box. Nothing is downloaded or processed, and the limits are enforced by the
 * server. Without the backend the page says so instead of failing silently.
 */
import { useState } from "react";
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

const PRESETS: Record<string, [number, number, number, number]> = {
  "Chilika, Odisha (≈19 km²)": [85.3, 19.7, 85.34, 19.74],
  "Kathmandu core (≈20 km²)": [85.3, 27.68, 85.34, 27.72],
};


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

export function AvailabilityPage() {
  const [bounds, setBounds] = useState<[number, number, number, number]>(PRESETS["Chilika, Odisha (≈19 km²)"]);
  const [start, setStart] = useState("2024-01-01");
  const [end, setEnd] = useState("2024-03-01");
  const [maxCloud, setMaxCloud] = useState(40);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Availability | null>(null);

  async function run(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    const [west, south, east, north] = bounds;
    const query = new URLSearchParams({
      west: String(west),
      south: String(south),
      east: String(east),
      north: String(north),
      start,
      end,
      max_cloud: String(maxCloud),
    });
    try {
      const response = await fetch(`/api/aoi/availability?${query}`);
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? `Request failed (HTTP ${response.status})`);
      }
      setResult((await response.json()) as Availability);
    } catch (caught) {
      setError(
        caught instanceof TypeError
          ? "The analysis backend is not reachable. This page needs the local backend (start.bat); the offline showcase cannot query the catalogue."
          : String((caught as Error).message)
      );
    } finally {
      setBusy(false);
    }
  }

  const setBound = (i: number, value: string) =>
    setBounds((prev) => prev.map((v, j) => (j === i ? Number(value) : v)) as [number, number, number, number]);

  return (
    <main id="main" className="availability">
      <p className="eyebrow">Custom area</p>
      <h1>Your own area</h1>
      <p className="availability-lede">
        Check which Sentinel-2 L2A scenes exist over a small box before anything is processed. Limits: 0.05–100 km², at
        most 400 days, 2015-06-23 onwards. This reads catalogue metadata only: no imagery is downloaded and no change
        is computed.
      </p>

      <form className="availability-form" onSubmit={run} aria-describedby="avail-help">
        <fieldset>
          <legend>Area (WGS84 degrees)</legend>
          <label>
            Preset
            <select
              onChange={(e) => PRESETS[e.target.value] && setBounds(PRESETS[e.target.value])}
              defaultValue="Chilika, Odisha (≈19 km²)"
            >
              {Object.keys(PRESETS).map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          {(["West", "South", "East", "North"] as const).map((label, i) => (
            <label key={label}>
              {label}
              <input type="number" step="0.001" value={bounds[i]} onChange={(e) => setBound(i, e.target.value)} required />
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Window</legend>
          <label>
            Start
            <input type="date" value={start} min="2015-06-23" onChange={(e) => setStart(e.target.value)} required />
          </label>
          <label>
            End
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} required />
          </label>
          <label>
            Max scene cloud (%)
            <input type="number" min={0} max={100} value={maxCloud} onChange={(e) => setMaxCloud(Number(e.target.value))} />
          </label>
        </fieldset>
        <button type="submit" className="toggle-btn is-active" disabled={busy} data-testid="avail-run">
          {busy ? "Searching…" : "Check availability"}
        </button>
        <p id="avail-help" className="availability-help">
          Scene-wide cloud cover is not the cloud fraction inside your box.
        </p>
      </form>

      <div role="status" aria-live="polite">
        {error && (
          <p className="availability-error" data-testid="avail-error">
            {error}
          </p>
        )}
        {result && (
          <section className="availability-result" data-testid="avail-result">
            <h2>
              {result.scenes_found} scene{result.scenes_found === 1 ? "" : "s"} found over {result.aoi.area_km2} km²
              {result.truncated_at_limit ? " (list truncated at the 100-scene limit)" : ""}
            </h2>
            {result.scenes_found > 0 && (
              <table>
                <caption className="sr-only">Sentinel-2 L2A scenes intersecting the box</caption>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Scene</th>
                    <th scope="col">Platform</th>
                    <th scope="col">Scene cloud %</th>
                  </tr>
                </thead>
                <tbody>
                  {result.scenes.map((scene) => (
                    <tr key={scene.id}>
                      <td>{scene.date}</td>
                      <td className="mono">{scene.id}</td>
                      <td>{scene.platform}</td>
                      <td>{scene.scene_cloud_percent === null ? "n/a" : scene.scene_cloud_percent.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <ul className="availability-notes">
              {result.honest_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </section>
        )}
      </div>
      <CustomAnalysis bounds={bounds} />
    </main>
  );
}
