import { useEffect, useMemo, useState } from "react";
import { Explain } from "../components/Explain";
import { LakeGlance, LakeStory } from "../components/LakeSummary";

interface Change {
  delta_km2: number;
  threshold_km2: number;
  exceeds_noise: boolean;
}
interface MonthRow {
  month: string;
  n: number;
  excluded: Record<string, number>;
  area_km2?: number;
  min_km2?: number;
  max_km2?: number;
  se_km2?: number;
  change_vs_previous?: Change | null;
}
interface ModelRow extends MonthRow {
  lo_km2?: number;
  hi_km2?: number;
  fills_optical_gap?: boolean;
}
interface ModelSeries {
  interval: { alpha: number; relative_half_width_q: number };
  months: ModelRow[];
}
interface OrbitInfo {
  scenes: number;
  basis: string;
  q25_contrast_db: number;
  usable: boolean;
}
interface ReferenceYear {
  himag: { area_km2: number } | null;
  s1: { median_km2?: number; difference_vs_himag_pct?: number; months: number };
  s2: { median_km2?: number; difference_vs_himag_pct?: number; months: number };
}
interface Lake {
  id: string;
  name: string;
  note: string;
  seed: { seed_area_km2: number; seed_elevation_m: number };
  s1_orbits: Record<string, OrbitInfo>;
  scene_counts: { s1: number; s2: number };
  s1_monthly: MonthRow[];
  s2_monthly: MonthRow[];
  unet?: ModelSeries | null;
  reference: Record<string, ReferenceYear> | null;
}
interface Bundle {
  reference: string | null;
  lakes: Lake[];
}

const REASONS: Record<string, string> = {
  orbit_cannot_see_lake: "radar orbit cannot see the lake (layover)",
  lake_not_dark: "lake not dark (ice, wind or melt)",
  lake_not_covered: "lake outside the scene",
  cloudy: "cloud over the lake",
  cloudy_scene: "scene too cloudy (shadow and haze)",
  frozen_season: "frozen season (radar shows the lake not dark)",
  frozen: "ice on the lake surface (fully or partly frozen)",
  error: "download or processing error",
};

const TEAL = "#1b4f9c";
const COPPER = "#6b7690";
const MODEL = "#5b8bd6";

function monthTime(month: string): number {
  const [y, m] = month.split("-").map(Number);
  return Date.UTC(y, m - 1, 15);
}

function countReasons(rows: MonthRow[]): [string, number][] {
  const total: Record<string, number> = {};
  for (const row of rows) for (const [k, v] of Object.entries(row.excluded)) total[k] = (total[k] ?? 0) + v;
  return Object.entries(total).sort((a, b) => b[1] - a[1]);
}

function AreaChart({ lake }: { lake: Lake }) {
  const W = 760;
  const H = 320;
  const L = 52;
  const R = 16;
  const T = 14;
  const B = 34;
  const all = [...lake.s1_monthly, ...lake.s2_monthly, ...(lake.unet?.months ?? [])].filter((r) => r.area_km2 !== undefined);
  const refs = Object.entries(lake.reference ?? {}).filter(([, v]) => v.himag);
  if (!all.length) return <p className="exp-note">No usable months for this lake.</p>;
  const t0 = Math.min(...all.map((r) => monthTime(r.month)), ...refs.map(([y]) => Date.UTC(+y, 6, 1)));
  const t1 = Math.max(...all.map((r) => monthTime(r.month)));
  // Axis follows the monthly values, not single-scene extremes, so one odd scene cannot flatten the chart.
  const hi = Math.max(...all.map((r) => r.area_km2!), ...refs.map(([, v]) => v.himag!.area_km2));
  const lo = Math.min(...all.map((r) => r.area_km2!), ...refs.map(([, v]) => v.himag!.area_km2));
  const pad = Math.max((hi - lo) * 0.12, 0.02);
  const v0 = Math.max(0, lo - pad);
  const v1 = hi + pad;
  const x = (t: number) => L + ((t - t0) / (t1 - t0 || 1)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - v0) / (v1 - v0)) * (H - T - B);
  const years: number[] = [];
  for (let yr = new Date(t0).getUTCFullYear(); yr <= new Date(t1).getUTCFullYear(); yr++) years.push(yr);
  const label = `Monthly area of ${lake.name} from radar and optical scenes, in square kilometres`;
  const series = (rows: MonthRow[], color: string, dx: number) =>
    rows
      .filter((r) => r.area_km2 !== undefined)
      .map((r) => {
        const cx = x(monthTime(r.month)) + dx;
        const flagged = r.change_vs_previous?.exceeds_noise;
        return (
          <g key={r.month}>
            {r.min_km2 !== undefined && r.max_km2 !== undefined && r.n > 1 && (
              <line x1={cx} x2={cx} y1={y(Math.max(r.min_km2, v0))} y2={y(Math.min(r.max_km2, v1))} stroke={color} strokeWidth="1.2" opacity="0.5" />
            )}
            <circle cx={cx} cy={y(r.area_km2!)} r={flagged ? 4 : 2.6} fill={color} stroke={flagged ? "#18272d" : "none"} strokeWidth="1.4" />
          </g>
        );
      });
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} style={{ width: "100%", maxWidth: 820, height: "auto" }}>
      <line x1={L} y1={T} x2={L} y2={H - B} stroke="currentColor" opacity="0.4" />
      <line x1={L} y1={H - B} x2={W - R} y2={H - B} stroke="currentColor" opacity="0.4" />
      {[v0 + pad * 0.3, (v0 + v1) / 2, v1 - pad * 0.3].map((v) => (
        <text key={v} x={L - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="currentColor">
          {v.toFixed(2)}
        </text>
      ))}
      <text x={12} y={T + 8} fontSize="11" fill="currentColor">
        km²
      </text>
      {years.map((yr) => {
        const ms = Date.UTC(yr, 0, 1);
        if (ms < t0 || ms > t1) return null;
        return (
          <g key={yr}>
            <line x1={x(ms)} y1={T} x2={x(ms)} y2={H - B} stroke="currentColor" opacity="0.12" />
            <text x={x(ms)} y={H - B + 16} textAnchor="middle" fontSize="11" fill="currentColor">
              {yr}
            </text>
          </g>
        );
      })}
      {series(lake.s2_monthly, COPPER, 2)}
      {series(lake.s1_monthly, TEAL, -2)}
      {(lake.unet?.months ?? [])
        .filter((r) => r.area_km2 !== undefined)
        .map((r) => {
          const cx = x(monthTime(r.month)) + 5;
          return (
            <g key={`m${r.month}`}>
              {r.lo_km2 !== undefined && r.hi_km2 !== undefined && (
                <line x1={cx} x2={cx} y1={y(Math.max(r.lo_km2, v0))} y2={y(Math.min(r.hi_km2, v1))} stroke={MODEL} strokeWidth="1" opacity="0.14" />
              )}
              <circle cx={cx} cy={y(r.area_km2!)} r="2.6" fill={r.fills_optical_gap ? MODEL : "none"} stroke={MODEL} strokeWidth="1.3" />
            </g>
          );
        })}
      {refs.map(([yr, v]) => (
        <g key={yr}>
          <rect
            x={x(Date.UTC(+yr, 6, 1)) - 4.5}
            y={y(v.himag!.area_km2) - 4.5}
            width="9"
            height="9"
            transform={`rotate(45 ${x(Date.UTC(+yr, 6, 1))} ${y(v.himag!.area_km2)})`}
            fill="#18272d"
          />
        </g>
      ))}
    </svg>
  );
}

function LakeView({ lake, reference }: { lake: Lake; reference: string | null }) {
  const flags = useMemo(() => {
    const out: { sensor: string; month: string; change: Change }[] = [];
    for (const [sensor, rows] of [["Radar", lake.s1_monthly], ["Optical", lake.s2_monthly]] as const)
      for (const r of rows) if (r.change_vs_previous?.exceeds_noise) out.push({ sensor, month: r.month, change: r.change_vs_previous });
    return out.sort((a, b) => a.month.localeCompare(b.month));
  }, [lake]);
  const s1Months = lake.s1_monthly.filter((r) => r.area_km2 !== undefined).length;
  const s2Months = lake.s2_monthly.filter((r) => r.area_km2 !== undefined).length;
  const refRows = Object.entries(lake.reference ?? {}).filter(([, v]) => v.himag);
  return (
    <>
      <section className="exp-block">
        <p className="eyebrow">{lake.name}</p>
        <h2>Every month, in detail</h2>
        <p className="exp-lede">{lake.note}</p>
        <figure className="exp-card">
          <AreaChart lake={lake} />
          <p className="exp-note">
            <span style={{ color: TEAL }}>●</span> Radar (Sentinel-1), {s1Months} months &nbsp;
            <span style={{ color: COPPER }}>●</span> Optical (Sentinel-2), {s2Months} months &nbsp;
            {lake.unet && (
              <>
                <span style={{ color: MODEL }}>●</span> Radar U-Net (trained model), model output; filled dots are months with
                no optical value, the bar is a conformal {Math.round((1 - lake.unet.interval.alpha) * 100)}% interval.{" "}
              </>
            )}
            <span>◆</span> Hi-MAG reference outline (annual). Thin lines run from the smallest to the largest scene in the
            month. A ringed dot is a month-to-month change larger than 3 times the combined standard error. Months with no
            usable scene are left empty, not filled.
          </p>
        </figure>
        <Explain
          plain="Each dot is one month of lake area. Radar works through cloud, so it fills the monsoon months where optical pictures are missing. Where both exist they should sit on top of each other. A ringed dot is a jump bigger than the normal wobble."
          technical="Radar: Sentinel-1 RTC, Lee-filtered VV, Otsu water threshold on gentle slopes, patches touching a DEM-flat seed, usable orbits only, monthly median with standard error. Optical: MNDWI and NIR rule on clear, ice-free scenes. Purple is the trained U-Net with a conformal interval."
        />
      </section>

      <section className="exp-block">
        <p className="eyebrow">Check against a reference</p>
        <h2>Agreement with Hi-MAG</h2>
        {refRows.length ? (
          <div className="exp-table-wrap">
            <table className="exp-table">
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Hi-MAG (km²)</th>
                  <th>Radar median, Jun-Oct</th>
                  <th>Optical median, Jun-Oct</th>
                </tr>
              </thead>
              <tbody>
                {refRows.map(([yr, v]) => (
                  <tr key={yr}>
                    <td>{yr}</td>
                    <td>{v.himag!.area_km2.toFixed(2)}</td>
                    <td>
                      {v.s1.median_km2 !== undefined
                        ? `${v.s1.median_km2.toFixed(2)} (${v.s1.difference_vs_himag_pct! > 0 ? "+" : ""}${v.s1.difference_vs_himag_pct}%)`
                        : "no usable months"}
                    </td>
                    <td>
                      {v.s2.median_km2 !== undefined
                        ? `${v.s2.median_km2.toFixed(2)} (${v.s2.difference_vs_himag_pct! > 0 ? "+" : ""}${v.s2.difference_vs_himag_pct}%)`
                        : "no usable months"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="exp-note">No Hi-MAG outline was found within 500 m of this lake for 2016 or 2017.</p>
        )}
        <p className="exp-note">
          {reference ?? "Reference"}: another satellite product at 30 m. This is agreement with a reference, not accuracy.
        </p>
      </section>

      <section className="exp-block">
        <p className="eyebrow">What was left out, and why</p>
        <h2>Gaps and exclusions</h2>
        <div className="exp-table-wrap">
          <table className="exp-table">
            <thead>
              <tr>
                <th>Radar orbit</th>
                <th>Scenes checked</th>
                <th>Lake vs surroundings (dB, lower quartile)</th>
                <th>Used</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(lake.s1_orbits).map(([k, o]) => (
                <tr key={k}>
                  <td>{k}</td>
                  <td>{o.scenes}</td>
                  <td>{o.q25_contrast_db}</td>
                  <td>{o.usable ? "yes" : "no: lake not visible"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="exp-note">
          {([["Radar", lake.s1_monthly], ["Optical", lake.s2_monthly]] as const).map(([name, rows]) => (
            <li key={name}>
              <strong>{name}:</strong>{" "}
              {countReasons(rows)
                .map(([k, v]) => `${v} scenes, ${REASONS[k] ?? k}`)
                .join("; ") || "nothing excluded"}
            </li>
          ))}
        </ul>
      </section>

      <section className="exp-block">
        <p className="eyebrow">Change larger than noise</p>
        <h2>Months that stand out</h2>
        {flags.length ? (
          <ul className="exp-note">
            {flags.map((f) => (
              <li key={`${f.sensor}${f.month}`}>
                {f.month} ({f.sensor}): {f.change.delta_km2 > 0 ? "+" : ""}
                {f.change.delta_km2.toFixed(3)} km², more than 3 × combined SE ({f.change.threshold_km2.toFixed(3)} km²)
              </li>
            ))}
          </ul>
        ) : (
          <p className="exp-note">No month-to-month change exceeds 3 times the combined standard error.</p>
        )}
        <p className="exp-note">
          The standard error comes from the scatter between scenes in a month. It does not include the threshold choice or
          the difference between radar and optical, which is why the two sensors can sit apart.
        </p>
      </section>
    </>
  );
}

export function LakesPage() {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  // `selected` null = nothing chosen: the page cycles through the lakes, 5 s on Oct 2018 then 5 s on Oct 2024 each.
  const [selected, setSelected] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    fetch("lakes/lakes.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Bundle>;
      })
      .then(setBundle)
      .catch((e) => setError(String(e)));
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (mq) {
      setReduced(mq.matches);
      const on = () => setReduced(mq.matches);
      mq.addEventListener("change", on);
      return () => mq.removeEventListener("change", on);
    }
  }, []);
  const rotating = selected === null && !reduced && !!bundle && bundle.lakes.length > 0;
  useEffect(() => {
    if (!rotating || paused) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 5000);
    return () => window.clearInterval(id);
  }, [rotating, paused]);
  const n = bundle?.lakes.length ?? 0;
  const shown = selected ?? (n ? bundle!.lakes[Math.floor(tick / 2) % n].id : "");
  const lake = bundle?.lakes.find((l) => l.id === shown);
  const view: 0 | 1 | undefined = rotating ? ((tick % 2) as 0 | 1) : undefined;
  const pick = (id: string) => { setSelected((cur) => (cur === id ? null : id)); setTick(0); };
  return (
    <main id="main" className="exp-page page">
      <header className="exp-header">
        <h1>Are Nepal's glacial lakes growing?</h1>
        <p className="exp-lede">
          Three lakes followed from 2017 to 2026 with satellite radar, which sees through monsoon cloud. Each card says in one
          line whether the lake changed. Click a lake for its before and after pictures, a yearly chart and, further down, the
          full monthly detail.
        </p>
      </header>
      {error && <p className="exp-note">The lake results could not be loaded ({error}).</p>}
      {!bundle && !error && <p className="mono-label">Loading…</p>}
      {bundle && (
        <>
          <div
            onPointerEnter={() => setPaused(true)} onPointerLeave={() => setPaused(false)}
            onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}
          >
            <p className="rot-hint" aria-live="off">
              {selected ? "Showing the lake you picked. Click it again to go back to the slideshow."
                : reduced ? "Pick a lake below."
                : paused ? "Slideshow paused while you look. Click a lake to keep it."
                : "Slideshow: each lake shows Oct 2018, then Oct 2024. Click a lake to hold it."}
            </p>
            <LakeGlance lakes={bundle.lakes} active={shown} auto={rotating} onPick={pick} />
            {lake && <LakeStory lake={lake} note={lake.note} view={view} onView={rotating ? (v) => setTick((t) => t - (t % 2) + v) : undefined} />}
          </div>
          {lake && selected && (
            <details className="lake-more">
              <summary>Monthly detail, checks and exclusions</summary>
              <LakeView lake={lake} reference={bundle.reference} />
            </details>
          )}
        </>
      )}
    </main>
  );
}
