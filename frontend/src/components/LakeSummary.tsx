/** Plain-language view of a lake: what changed in one sentence, a simple yearly chart, and the real 2018 and 2024
 *  pictures. The dense monthly chart stays on the page behind a button for readers who want it. */
import { useMemo, useState } from "react";
import { BeforeAfter } from "./Figures";

export interface MonthRow { month: string; area_km2?: number }
export interface LakeLike {
  id: string;
  name: string;
  s1_monthly: MonthRow[];
  s2_monthly: MonthRow[];
  reference: Record<string, { himag: { area_km2: number } | null }> | null;
}

export interface Year { year: number; median: number; p25: number; p75: number; n: number }

const quantile = (sorted: number[], q: number) => {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos), hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
};

export function yearly(rows: MonthRow[], minMonths: number): Year[] {
  const by = new Map<number, number[]>();
  for (const r of rows) {
    if (r.area_km2 === undefined) continue;
    const y = Number(r.month.slice(0, 4));
    by.set(y, [...(by.get(y) ?? []), r.area_km2]);
  }
  return [...by.entries()]
    .filter(([, v]) => v.length >= minMonths)
    .map(([year, v]) => {
      const s = [...v].sort((a, b) => a - b);
      return { year, median: quantile(s, 0.5), p25: quantile(s, 0.25), p75: quantile(s, 0.75), n: s.length };
    })
    .sort((a, b) => a.year - b.year);
}

export interface Summary {
  first: Year; last: Year; delta: number; pct: number; verdict: "grew" | "shrank" | "same"; clear: boolean;
}

export function summarise(radar: Year[]): Summary | null {
  if (radar.length < 2) return null;
  const first = radar[0], last = radar[radar.length - 1];
  const delta = last.median - first.median;
  const pct = (delta / first.median) * 100;
  const spread = Math.max((first.p75 - first.p25) / 2, (last.p75 - last.p25) / 2);
  const clear = Math.abs(delta) > 2 * spread && Math.abs(pct) >= 10;
  return { first, last, delta, pct, clear, verdict: !clear ? "same" : delta > 0 ? "grew" : "shrank" };
}

const IMG: Record<string, string> = { imja_tsho: "imja", tsho_rolpa: "rolpa", thulagi: "thulagi" };

const HIMAG = "#b4561f";
const OPT = "#4b556b";

/** Highest value any chart for this lake needs, rounded up to a clean axis top. */
export function chartTop(lakes: LakeLike[]): number {
  const peak = Math.max(...lakes.map((l) => Math.max(
    ...yearly(l.s1_monthly, 6).map((r) => r.p75),
    ...yearly(l.s2_monthly, 2).map((o) => o.median),
    ...Object.values(l.reference ?? {}).filter((v) => v.himag).map((v) => v.himag!.area_km2),
  ))) * 1.08;
  return [0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find((s) => s >= peak) ?? Math.ceil(peak);
}

/** Yearly lake area. Pass `top` so several cards share one axis and sizes compare honestly. */
export function YearChart({ lake, compact = false, top: sharedTop }: { lake: LakeLike; compact?: boolean; top?: number }) {
  const radar = useMemo(() => yearly(lake.s1_monthly, 6), [lake]);
  const optical = useMemo(() => yearly(lake.s2_monthly, 2), [lake]);
  const himag = Object.entries(lake.reference ?? {}).filter(([, v]) => v.himag).map(([y, v]) => ({ year: Number(y), v: v.himag!.area_km2 }));
  const [hover, setHover] = useState<number | null>(null);
  if (!radar.length) return <p className="exp-note">Not enough radar months for a yearly view.</p>;
  const W = compact ? 340 : 900, H = compact ? 190 : 300;
  const L = compact ? 34 : 52, R = compact ? 34 : 44, T = 14, B = compact ? 26 : 32;
  const years = [...radar.map((r) => r.year), ...optical.map((o) => o.year), ...himag.map((h) => h.year)];
  const y0 = Math.min(...years), y1 = Math.max(...years);
  const top = sharedTop ?? chartTop([lake]);
  const x = (yr: number) => L + ((yr - y0) / (y1 - y0 || 1)) * (W - L - R);
  const y = (v: number) => T + (1 - v / top) * (H - T - B);
  const ticks = [0, top / 2, top];
  const xTicks = compact ? [y0, Math.round((y0 + y1) / 2), y1] : Array.from({ length: y1 - y0 + 1 }, (_, i) => y0 + i);
  const band = radar.map((r) => `${x(r.year)},${y(r.p75)}`).join(" ") + " " + [...radar].reverse().map((r) => `${x(r.year)},${y(r.p25)}`).join(" ");
  const last = radar[radar.length - 1];
  const s = compact ? 1 : 1.25;
  const shown = hover !== null ? radar.find((r) => r.year === hover) : null;
  const shownOpt = hover !== null ? optical.find((o) => o.year === hover) : null;
  return (
    <figure className={`yc${compact ? " yc--compact" : ""}`}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${lake.name}: yearly lake area from radar, ${radar[0].year} to ${last.year}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="yc-grid" />
            <text x={L - 6} y={y(t) + 4} textAnchor="end" className="yc-tick">{t}</text>
          </g>
        ))}
        <text x={L - 6} y={8} textAnchor="end" className="yc-unit">km²</text>
        {xTicks.map((yr) => (
          <text key={yr} x={x(yr)} y={H - 7} textAnchor="middle" className="yc-tick">{compact ? yr : `'${String(yr).slice(2)}`}</text>
        ))}
        <polygon points={band} className="yc-band" />
        <polyline points={radar.map((r) => `${x(r.year)},${y(r.median)}`).join(" ")} className="yc-line" />
        {optical.map((o) => (
          <path key={o.year} d={`M${x(o.year) - 4 * s},${y(o.median) + 3.5 * s} l${4 * s},${-7.5 * s} l${4 * s},${7.5 * s} z`} fill="#fff" stroke={OPT} strokeWidth="1.6" />
        ))}
        {himag.map((h) => (
          <path key={h.year} d={`M${x(h.year)},${y(h.v) - 6 * s} l${6 * s},${6 * s} l${-6 * s},${6 * s} l${-6 * s},${-6 * s} z`} fill={HIMAG} stroke="#fff" strokeWidth="1" />
        ))}
        {radar.map((r) => (
          <circle key={r.year} cx={x(r.year)} cy={y(r.median)} r={hover === r.year ? 6 : compact ? 3.2 : 4} className={`yc-dot${hover === r.year ? " is-on" : ""}`} />
        ))}
        {!compact && radar.map((r) => (
          <rect key={`h${r.year}`} x={x(r.year) - 18} y={T} width="36" height={H - T - B} fill="transparent"
                onPointerEnter={() => setHover(r.year)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(r.year)} onBlur={() => setHover(null)}
                tabIndex={0} aria-label={`${r.year}: ${r.median.toFixed(2)} square kilometres`} />
        ))}
        <text x={x(last.year) + 9} y={y(last.median) + 4} className="yc-end">{last.median.toFixed(1)}</text>
      </svg>
      {!compact && (
        <p className="yc-read" aria-live="polite">
          {shown
            ? `${shown.year}: radar ${shown.median.toFixed(2)} km² (typical months ${shown.p25.toFixed(2)} to ${shown.p75.toFixed(2)}, from ${shown.n} months)${shownOpt ? `; optical ${shownOpt.median.toFixed(2)} km²` : ""}`
            : "Hover a year for its value."}
        </p>
      )}
      <figcaption className="yc-key">
        <span><i className="k-line" />Radar{compact ? "" : ", yearly median"}</span>
        {!compact && <span><i className="k-band" />Normal month-to-month range</span>}
        <span><svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M1,11 L6,2 L11,11 z" fill="#fff" stroke={OPT} strokeWidth="1.4" /></svg>Optical</span>
        <span><svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M6,0 L12,6 L6,12 L0,6 z" fill={HIMAG} /></svg>Published outline{compact ? "" : " (Hi-MAG)"}</span>
      </figcaption>
    </figure>
  );
}

function Sentence({ lake, s }: { lake: LakeLike; s: Summary }) {
  const verb = s.verdict === "grew" ? "grew" : s.verdict === "shrank" ? "shrank" : "stayed about the same size";
  return (
    <p className="ls-sentence">
      <b>{lake.name}</b> {verb}
      {s.verdict !== "same" && (
        <>
          {" "}from <b>{s.first.median.toFixed(1)}</b> to <b>{s.last.median.toFixed(1)} km²</b> ({s.pct > 0 ? "+" : ""}{Math.round(s.pct)}%)
        </>
      )}
      {" "}between {s.first.year} and {s.last.year}, measured by radar.
      {s.verdict === "same" && ` Typical yearly area was ${s.first.median.toFixed(1)} km² at the start and ${s.last.median.toFixed(1)} km² at the end, which is within normal month-to-month variation.`}
    </p>
  );
}

/** Three lakes in one row so the difference is visible at a glance. */
export function LakeGlance({ lakes, active, onPick, auto = false }: { lakes: LakeLike[]; active: string; onPick: (id: string) => void; auto?: boolean }) {
  const top = chartTop(lakes);
  return (
    <div className="glance" data-tour="lake-chart">
      {lakes.map((lake) => {
        const radar = yearly(lake.s1_monthly, 6);
        const s = summarise(radar);
        return (
          <button key={lake.id} type="button" className={`glance-card${lake.id === active ? (auto ? " is-on is-auto" : " is-on") : ""}`} onClick={() => onPick(lake.id)} aria-pressed={lake.id === active && !auto}>
            <h3>{lake.name}</h3>
            {s && (
              <p className={`glance-big is-${s.verdict}`}>
                {s.verdict === "same" ? "No clear change" : `${s.pct > 0 ? "+" : ""}${Math.round(s.pct)}%`}
                <span>{s.first.year} to {s.last.year}, by radar</span>
              </p>
            )}
            <YearChart lake={lake} compact top={top} />
          </button>
        );
      })}
    </div>
  );
}

/** The selected lake: sentence, real pictures, simple yearly chart. */
export function LakeStory({ lake, note, view, onView }: { lake: LakeLike; note: string; view?: 0 | 1; onView?: (v: 0 | 1) => void }) {
  const radar = useMemo(() => yearly(lake.s1_monthly, 6), [lake]);
  const s = summarise(radar);
  const tag = IMG[lake.id];
  return (
    <section className="ls">
      <div className="ls-text">
        <h2>{lake.name}</h2>
        {s && <Sentence lake={lake} s={s} />}
        <p className="ls-note">{note}</p>
        {s && !s.clear && s.verdict === "same" && (
          <p className="ls-note">A change is only reported when it is clearly bigger than the normal month-to-month spread.</p>
        )}
      </div>
      <div className="ls-media">
        {tag && (
          <BeforeAfter
            before={`./figures/${tag}_2018.jpg`}
            after={`./figures/${tag}_2024.jpg`}
            overlay={`./figures/${tag}_outline_2024.png`}
            labels={["Oct 2018", "Oct 2024"]}
            alt={lake.name}
            view={view}
            onView={onView}
            note="White line: 2018 shore. Blue: lake gained since."
          />
        )}
      </div>
      <div className="ls-chart">
        <h3>Lake area by year</h3>
        <YearChart lake={lake} />
        <p className="ls-note" style={{ marginTop: "0.8rem" }}>Radar is the main measure. The optical triangles can sit lower because optical pictures miss water that is muddy, icy or in shadow, and in cloudy months they are missing altogether.</p>
      </div>
    </section>
  );
}
