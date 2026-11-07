/** Reusable interactive, explanatory line chart (M4-G5).
 *
 * One interaction system for every analytical graph in the product:
 * - hover snaps to the NEAREST RECORDED data point (no interpolation —
 *   values that were never measured are never shown);
 * - a vertical guide and a floating tooltip carry the series name, the exact
 *   x/y values with units, the measurement context (denominator, method)
 *   and a plain-language interpretation of what the value can and cannot
 *   mean;
 * - click pins a tooltip (Esc dismisses); touch taps behave like a pin;
 * - the plot is keyboard-focusable: arrow keys walk the recorded points,
 *   with the tooltip mirrored into an aria-live region;
 * - the legend toggles series visibility; tooltips never shift layout.
 *
 * All displayed numbers come from the props' recorded data — this component
 * has no sample data and no hardcoded values.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./charts.css";

export interface ChartPoint {
  x: number;
  y: number;
  /** Optional exact label for the x value (e.g. a date). */
  label?: string;
  /** Extra measured facts shown in the tooltip (already formatted). */
  facts?: [string, string][];
  /** Per-point plain-language interpretation (recorded, not generated). */
  interpretation?: string;
}

export interface ChartSeries {
  id: string;
  label: string;
  color: string;
  points: ChartPoint[];
  /** Grouped in the tooltip header when several series share an x value. */
  dashed?: boolean;
}

export interface InteractiveChartProps {
  series: ChartSeries[];
  height?: number;
  xLabel: string;
  yLabel: string;
  /** Units strings used in the tooltip ("index units", "% of AOI", ...). */
  xUnit?: string;
  yUnit?: string;
  /** Study/measurement context line shown in every tooltip. */
  context: string;
  /** What can be concluded (shown under the chart). */
  canConclude?: string[];
  /** What cannot be concluded (shown under the chart). */
  cannotConclude?: string[];
  /** Accessible table caption. */
  caption: string;
  /** Formatting helpers (default: reasonable numeric formats). */
  formatX?: (value: number) => string;
  formatY?: (value: number) => string;
}

interface HoverState {
  /** Index into the sorted x domain (nearest recorded point). */
  pointIndex: number;
  pinned: boolean;
}

const MARGIN = { top: 14, right: 18, bottom: 40, left: 56 };

export function InteractiveChart({
  series,
  height = 240,
  xLabel,
  yLabel,
  xUnit = "",
  yUnit = "",
  context,
  canConclude,
  cannotConclude,
  caption,
  formatX,
  formatY,
}: InteractiveChartProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<HoverState | null>(null);
  const [focusIndex, setFocusIndex] = useState<number | null>(null);

  useEffect(() => {
    const element = wrapRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const next = Math.max(280, Math.floor(entries[0].contentRect.width));
      setWidth(next);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const visible = useMemo(
    () => series.filter((item) => !hidden.has(item.id)),
    [series, hidden]
  );

  const domain = useMemo(() => {
    const xs: number[] = [];
    const ys: number[] = [];
    for (const item of visible) {
      for (const point of item.points) {
        xs.push(point.x);
        ys.push(point.y);
      }
    }
    if (!xs.length) return null;
    const padY = (Math.max(...ys) - Math.min(...ys)) * 0.08 || 0.1;
    return {
      xMin: Math.min(...xs),
      xMax: Math.max(...xs),
      yMin: Math.min(...ys) - padY,
      yMax: Math.max(...ys) + padY,
    };
  }, [visible]);

  const fmtX = formatX ?? ((v: number) => Number.isInteger(v) ? String(v) : v.toFixed(2));
  const fmtY = formatY ?? ((v: number) => Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2));

  const plotWidth = Math.max(40, width - MARGIN.left - MARGIN.right);
  const plotHeight = Math.max(40, height - MARGIN.top - MARGIN.bottom);

  const scaleX = useCallback(
    (x: number) => {
      if (!domain) return MARGIN.left;
      const t = domain.xMax === domain.xMin ? 0.5 : (x - domain.xMin) / (domain.xMax - domain.xMin);
      return MARGIN.left + t * plotWidth;
    },
    [domain, plotWidth]
  );
  const scaleY = useCallback(
    (y: number) => {
      if (!domain) return MARGIN.top;
      const t = domain.yMax === domain.yMin ? 0.5 : (y - domain.yMin) / (domain.yMax - domain.yMin);
      return MARGIN.top + (1 - t) * plotHeight;
    },
    [domain, plotHeight]
  );

  /** Union of all recorded x values of visible series, sorted. */
  const xValues = useMemo(() => {
    const set = new Set<number>();
    for (const item of visible) for (const p of item.points) set.add(p.x);
    return [...set].sort((a, b) => a - b);
  }, [visible]);

  const pointIndexFromClientX = useCallback(
    (clientX: number): number | null => {
      if (!domain || !xValues.length || !wrapRef.current) return null;
      const rect = wrapRef.current.getBoundingClientRect();
      const px = clientX - rect.left;
      let best = 0;
      let bestDist = Infinity;
      xValues.forEach((x, index) => {
        const dist = Math.abs(scaleX(x) - px);
        if (dist < bestDist) {
          best = index;
          bestDist = dist;
        }
      });
      return best;
    },
    [domain, xValues, scaleX]
  );

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== "mouse") return;
    if (hover?.pinned) return;
    const index = pointIndexFromClientX(event.clientX);
    if (index === null) {
      setHover(null);
      return;
    }
    setHover({ pointIndex: index, pinned: false });
  };

  const onPointerLeave = () => {
    if (!hover?.pinned) setHover(null);
  };

  const onClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const index = pointIndexFromClientX(event.clientX);
    if (index === null) return;
    setHover((prev) =>
      prev?.pinned && prev.pointIndex === index ? null : { pointIndex: index, pinned: true }
    );
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!xValues.length) return;
    const current = focusIndex ?? hover?.pointIndex ?? 0;
    switch (event.key) {
      case "ArrowRight":
        setFocusIndex(Math.min(xValues.length - 1, current + 1));
        event.preventDefault();
        break;
      case "ArrowLeft":
        setFocusIndex(Math.max(0, current - 1));
        event.preventDefault();
        break;
      case "Home":
        setFocusIndex(0);
        event.preventDefault();
        break;
      case "End":
        setFocusIndex(xValues.length - 1);
        event.preventDefault();
        break;
      case "Enter":
      case " ":
        setHover((prev) =>
          prev?.pinned && prev.pointIndex === current
            ? null
            : { pointIndex: current, pinned: true }
        );
        event.preventDefault();
        break;
      case "Escape":
        setHover(null);
        setFocusIndex(null);
        event.preventDefault();
        break;
      default:
        return;
    }
  };

  useEffect(() => {
    if (!hover?.pinned) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setHover(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hover?.pinned]);

  if (!domain) {
    return (
      <div className="ichart ichart--empty" ref={wrapRef}>
        <p className="mono-label">No recorded data points for this chart.</p>
      </div>
    );
  }

  const activeIndex = hover?.pointIndex ?? focusIndex ?? null;
  const activeX = activeIndex !== null ? xValues[activeIndex] : null;
  const activeRows =
    activeX === null
      ? []
      : visible
          .map((item) => {
            const point = item.points.find((p) => p.x === activeX);
            return point ? { series: item, point } : null;
          })
          .filter((row): row is { series: ChartSeries; point: ChartPoint } => row !== null);

  // Tooltip placement: flip to the left of the guide when near the right edge.
  const guidePx = activeX !== null ? scaleX(activeX) : 0;
  const tooltipLeft =
    guidePx > width * 0.62 ? guidePx - 12 : guidePx + 12;
  const tooltipAlign = guidePx > width * 0.62 ? "right" : "left";

  const yTicks = niceTicks(domain.yMin, domain.yMax, 4);
  const xTicks = niceTicks(domain.xMin, domain.xMax, 5);

  return (
    <figure className="ichart" ref={wrapRef}>
      <div
        className="ichart-plot"
        tabIndex={0}
        role="application"
        aria-label={`${caption}. Use arrow keys to move between recorded data points; press Enter to pin the explanation.`}
        onPointerMove={onPointerMove}
        onPointerLeave={onPointerLeave}
        onClick={onClick}
        onKeyDown={onKeyDown}
      >
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-hidden={false}
        >
          {yTicks.map((tick) => (
            <g key={`y${tick}`}>
              <line
                x1={MARGIN.left}
                x2={width - MARGIN.right}
                y1={scaleY(tick)}
                y2={scaleY(tick)}
                className="ichart-gridline"
              />
              <text x={MARGIN.left - 8} y={scaleY(tick) + 3} className="ichart-tick" textAnchor="end">
                {fmtY(tick)}
              </text>
            </g>
          ))}
          {xTicks.map((tick) => (
            <text
              key={`x${tick}`}
              x={scaleX(tick)}
              y={height - MARGIN.bottom + 18}
              className="ichart-tick"
              textAnchor="middle"
            >
              {fmtX(tick)}
            </text>
          ))}
          {activeX !== null && (
            <line
              x1={guidePx}
              x2={guidePx}
              y1={MARGIN.top}
              y2={height - MARGIN.bottom}
              className="ichart-guide"
            />
          )}
          {visible.map((item) => {
            const path = item.points
              .map((point, i) => `${i === 0 ? "M" : "L"}${scaleX(point.x)},${scaleY(point.y)}`)
              .join(" ");
            return (
              <g key={item.id}>
                <path
                  d={path}
                  fill="none"
                  stroke={item.color}
                  strokeWidth={2}
                  strokeDasharray={item.dashed ? "5 4" : undefined}
                />
                {item.points.map((point, i) => {
                  const isActive = activeX !== null && point.x === activeX;
                  return (
                    <circle
                      key={i}
                      cx={scaleX(point.x)}
                      cy={scaleY(point.y)}
                      r={isActive ? 4.5 : 2.6}
                      className={`ichart-dot${isActive ? " is-active" : ""}`}
                      fill={item.color}
                      stroke={isActive ? "#18272d" : "none"}
                      strokeWidth={1.5}
                    />
                  );
                })}
              </g>
            );
          })}
          <text x={MARGIN.left + plotWidth / 2} y={height - 4} className="ichart-axis" textAnchor="middle">
            {xLabel}
          </text>
          <text
            x={12}
            y={MARGIN.top + plotHeight / 2}
            className="ichart-axis"
            textAnchor="middle"
            transform={`rotate(-90 12 ${MARGIN.top + plotHeight / 2})`}
          >
            {yLabel}
          </text>
        </svg>

        {activeRows.length > 0 && (
          <div
            className="ichart-tooltip"
            style={{
              left: tooltipLeft,
              top: Math.min(
                height - MARGIN.bottom - 40 - activeRows.length * 14,
                MARGIN.top + 8
              ),
              textAlign: tooltipAlign,
            }}
            role="status"
          >
            {activeRows.map(({ series: item, point }) => (
              <div key={item.id} className="ichart-tooltip-row">
                <span className="ichart-swatch" style={{ background: item.color }} aria-hidden="true" />
                <strong>{item.label}</strong>
                <span className="mono-label">
                  {point.label ?? fmtX(point.x)}
                  {xUnit ? ` ${xUnit}` : ""} → {fmtY(point.y)}
                  {yUnit ? ` ${yUnit}` : ""}
                </span>
                {point.facts?.map(([label, value]) => (
                  <span key={label} className="mono-label ichart-fact">
                    {label}: {value}
                  </span>
                ))}
                {point.interpretation && (
                  <span className="ichart-interpretation">{point.interpretation}</span>
                )}
              </div>
            ))}
            <span className="mono-label ichart-context">{context}</span>
            {hover?.pinned && (
              <span className="mono-label ichart-pin-hint">Pinned — press Esc to dismiss</span>
            )}
          </div>
        )}
      </div>

      {series.length > 1 && (
        <div className="ichart-legend" role="group" aria-label="Series visibility">
          {series.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`ichart-legend-item${hidden.has(item.id) ? " is-off" : ""}`}
              aria-pressed={!hidden.has(item.id)}
              onClick={() =>
                setHidden((prev) => {
                  const next = new Set(prev);
                  if (next.has(item.id)) {
                    next.delete(item.id);
                  } else if (visible.length > 1) {
                    next.add(item.id);
                  }
                  return next;
                })
              }
            >
              <span className="ichart-swatch" style={{ background: item.color }} aria-hidden="true" />
              {item.label}
            </button>
          ))}
        </div>
      )}

      <figcaption className="ichart-caption">
        {canConclude && canConclude.length > 0 && (
          <span>
            <strong>Can be read:</strong> {canConclude.join(" ")}
          </span>
        )}
        {cannotConclude && cannotConclude.length > 0 && (
          <span>
            <strong>Cannot be read:</strong> {cannotConclude.join(" ")}
          </span>
        )}
      </figcaption>

      {/* Screen-reader table of the recorded points (never rendered visually). */}
      <table className="visually-hidden">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Series</th>
            <th scope="col">{xLabel}{xUnit ? ` (${xUnit})` : ""}</th>
            <th scope="col">{yLabel}{yUnit ? ` (${yUnit})` : ""}</th>
          </tr>
        </thead>
        <tbody>
          {series.flatMap((item) =>
            item.points.map((point, i) => (
              <tr key={`${item.id}-${i}`}>
                <th scope="row">{item.label}</th>
                <td>{point.label ?? fmtX(point.x)}</td>
                <td>{fmtY(point.y)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </figure>
  );
}

function niceTicks(min: number, max: number, count: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    return [min];
  }
  const span = max - min;
  const step = Math.pow(10, Math.floor(Math.log10(span / count)));
  const err = (span / count) / step;
  const factor = err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1;
  const niceStep = step * factor;
  const ticks: number[] = [];
  for (let value = Math.ceil(min / niceStep) * niceStep; value <= max + 1e-9; value += niceStep) {
    ticks.push(Number(value.toFixed(10)));
  }
  return ticks.length ? ticks : [min, max];
}
