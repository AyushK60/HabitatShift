/** Horizontal dot-and-interval plot: one row per method, a dot for the score and a bar for its 95% interval.
 *  Every value is printed on the row, so hovering only highlights; nothing floats over the data. A dashed line marks
 *  the baseline the others are compared with. */
import { useState } from "react";

export interface DotRow {
  id: string;
  label: string;
  value: number;
  interval?: [number, number] | null;
  kind: "index" | "bands" | "model";
  note?: string;
  isBaseline?: boolean;
}

const KIND_LABEL = { index: "Spectral index", bands: "Raw bands", model: "Foundation model" } as const;
const ROW_H = 38;
const LABEL_W = 210;
const VALUE_W = 64;

export function DotPlot({ rows, baselineLabel, chanceLevel, caption, domain = [0, 1] }: {
  rows: DotRow[];
  baselineLabel: string;
  chanceLevel?: number;
  caption: string;
  domain?: [number, number];
}) {
  const [active, setActive] = useState<string | null>(null);
  const width = 760;
  const plotW = width - LABEL_W - VALUE_W - 12;
  const x = (v: number) => LABEL_W + ((v - domain[0]) / (domain[1] - domain[0])) * plotW;
  const height = rows.length * ROW_H + 34;
  const base = rows.find((r) => r.isBaseline);
  const ticks = [0, 0.25, 0.5, 0.75, 1].filter((t) => t >= domain[0] && t <= domain[1]);
  const shown = rows.find((r) => r.id === active);
  return (
    <figure className="dotplot">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={caption}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={6} y2={rows.length * ROW_H + 6} className="dp-grid" />
            <text x={x(t)} y={rows.length * ROW_H + 24} textAnchor="middle" className="dp-tick">{t.toFixed(2)}</text>
          </g>
        ))}
        {chanceLevel !== undefined && (
          <g>
            <line x1={x(chanceLevel)} x2={x(chanceLevel)} y1={6} y2={rows.length * ROW_H + 6} className="dp-chance" />
            <text x={x(chanceLevel) + 4} y={rows.length * ROW_H + 24} className="dp-chance-label">chance</text>
          </g>
        )}
        {base && (
          <line x1={x(base.value)} x2={x(base.value)} y1={6} y2={rows.length * ROW_H + 6} className="dp-baseline" />
        )}
        {rows.map((row, i) => {
          const cy = 6 + i * ROW_H + ROW_H / 2;
          const on = active === row.id;
          return (
            <g
              key={row.id}
              className={`dp-row dp-${row.kind}${on ? " is-on" : ""}${row.isBaseline ? " is-baseline" : ""}`}
              onPointerEnter={() => setActive(row.id)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(row.id)}
              onBlur={() => setActive(null)}
              tabIndex={0}
              role="listitem"
              aria-label={`${row.label}: ${row.value.toFixed(2)}${row.interval ? `, 95% interval ${row.interval[0].toFixed(2)} to ${row.interval[1].toFixed(2)}` : ""}`}
            >
              <rect x={0} y={cy - ROW_H / 2} width={width} height={ROW_H} className="dp-hit" />
              <text x={0} y={cy + 4.5} className="dp-label">{row.label}</text>
              {row.interval && (
                <line x1={x(row.interval[0])} x2={x(row.interval[1])} y1={cy} y2={cy} className="dp-bar" />
              )}
              <circle cx={x(row.value)} cy={cy} r={6} className="dp-dot" />
              <text x={width} y={cy + 4.5} textAnchor="end" className="dp-value">{row.value.toFixed(2)}</text>
            </g>
          );
        })}
      </svg>
      <div className="dp-legend">
        <span className="dp-key dp-key-model">Foundation model</span>
        <span className="dp-key dp-key-bands">Raw bands</span>
        <span className="dp-key dp-key-index">Spectral index</span>
        <span className="dp-key dp-key-base">Dashed line: {baselineLabel}</span>
      </div>
      <p className="dp-readout" aria-live="polite">
        {shown
          ? `${shown.label} (${KIND_LABEL[shown.kind]}): ${shown.value.toFixed(2)}${
              shown.interval ? `, plausible range ${shown.interval[0].toFixed(2)} to ${shown.interval[1].toFixed(2)}` : ""
            }${shown.note ? `. ${shown.note}` : ""}`
          : "Hover or tab to a row for its range."}
      </p>
    </figure>
  );
}
