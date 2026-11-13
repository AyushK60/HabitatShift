/** Small figure components for the home page. All images are real data rendered by scripts/make_site_figures.py. */
import { useState } from "react";

export function YearToggle({ labels, value, onChange }: { labels: [string, string]; value: 0 | 1; onChange: (v: 0 | 1) => void }) {
  return (
    <div className="yt" role="group" aria-label="Choose date">
      {labels.map((l, i) => (
        <button key={l} type="button" className={value === i ? "on" : ""} onClick={() => onChange(i as 0 | 1)}>
          {l}
        </button>
      ))}
    </div>
  );
}

/** One image pair with a date toggle and an optional outline layer. */
export function BeforeAfter({ before, after, overlay, labels, alt, note, view, onView }: {
  before: string; after: string; overlay?: string; labels: [string, string]; alt: string; note?: string;
  /** Optional controlled date: lets a parent drive the toggle (used by the auto-rotating lake view). */
  view?: 0 | 1; onView?: (v: 0 | 1) => void;
}) {
  const [own, setOwn] = useState<0 | 1>(0);
  const v = view ?? own;
  const setV = (n: 0 | 1) => { setOwn(n); onView?.(n); };
  const [outline, setOutline] = useState(true);
  return (
    <figure className="ba">
      <div className="ba-frame">
        <img src={before} alt={`${alt}, ${labels[0]}`} loading="lazy" />
        <img src={after} alt={`${alt}, ${labels[1]}`} className="ba-top" style={{ opacity: v }} loading="lazy" />
        {overlay && <img src={overlay} alt="" aria-hidden="true" className="ba-ov" style={{ opacity: outline ? 1 : 0 }} loading="lazy" />}
      </div>
      <figcaption>
        <YearToggle labels={labels} value={v} onChange={setV} />
        {overlay && (
          <label className="ba-check">
            <input type="checkbox" checked={outline} onChange={(e) => setOutline(e.target.checked)} /> Show outlines
          </label>
        )}
        {note && <span className="ba-note">{note}</span>}
      </figcaption>
    </figure>
  );
}

export interface Bar { label: string; value: number; kind?: "strong" | "plain" | "ref" }

/** Plain horizontal bars on a 0 to 1 scale, with a chance line. */
export function ScoreBars({ title, bars, chance, caption }: { title: string; bars: Bar[]; chance?: number; caption?: string }) {
  return (
    <div className="sb" role="img" aria-label={`${title}: ${bars.map((b) => `${b.label} ${b.value.toFixed(2)}`).join(", ")}`}>
      <p className="sb-title">{title}</p>
      {bars.map((b) => (
        <div className="sb-row" key={b.label}>
          <span>{b.label}</span>
          <div className="sb-track">
            <i className={`sb-fill ${b.kind ?? "plain"}`} style={{ width: `${b.value * 100}%` }} />
            {chance !== undefined && <u className="sb-chance" style={{ left: `${chance * 100}%` }} />}
          </div>
          <b>{b.value.toFixed(2)}</b>
        </div>
      ))}
      {caption && <p className="sb-cap">{caption}</p>}
    </div>
  );
}
