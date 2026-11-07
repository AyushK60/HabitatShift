/** Reusable interactive, explanatory line chart (M4-G5, refined M4-R1-G10).
 *
 * One interaction system for every analytical graph in the product:
 * - hover snaps to the NEAREST RECORDED data point (no interpolation —
 *   values that were never measured are never shown);
 * - hover shows ONLY the nearest series (vertical distance to the pointer);
 *   a "Details" control expands related series at the same x, the
 *   measurement context and the limitations;
 * - a vertical guide and an HTML overlay tooltip carry the series name, the
 *   exact x/y values with units and denominator, additional recorded facts
 *   and a plain-language interpretation.  The overlay is positioned relative
 *   to the plot container AND the viewport, flips sides when room runs out
 *   and is clamped so no explanatory text is ever clipped; it is absolutely
 *   positioned, so its appearance never shifts layout;
 * - click pins a tooltip (Esc dismisses); touch taps behave like a pin;
 * - the plot is keyboard-focusable: left/right walk the recorded points,
 *   up/down changes series at the current point, Enter pins, and the
 *   tooltip is mirrored into an aria-live region;
 * - the legend toggles series visibility.
 *
 * All displayed numbers come from the props' recorded data — this component
 * has no sample data and no hardcoded values.
 */
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import "./charts.css";

export interface ChartPoint {
  x: number;
  y: number;
  /** Optional exact label for the x value (e.g. a date). */
  label?: string;
  /** Compact axis-tick label for categorical x values; the full name stays
   *  in `label` and is shown on hover/focus. */
  shortLabel?: string;
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
  /** Treat the x axis as recorded categories (ticks at every recorded x
   *  using each point's label) instead of a numeric scale. */
  xCategorical?: boolean;
}

interface HoverState {
  /** Index into the sorted x domain (nearest recorded point). */
  pointIndex: number;
  /** Series the interaction is attached to (nearest under the pointer). */
  seriesId: string;
  pinned: boolean;
}

interface TooltipPos {
  left: number;
  top: number;
}

const MARGIN = { top: 18, right: 24, bottom: 52, left: 68 };
const TOOLTIP_GAP = 16;
const TOOLTIP_PAD = 10;

export function InteractiveChart({
  series,
  height = 320,
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
  xCategorical = false,
}: InteractiveChartProps) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const plotRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<HoverState | null>(null);
  const [focusIndex, setFocusIndex] = useState<number | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [tooltipPos, setTooltipPos] = useState<TooltipPos | null>(null);

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

  /** Union of all recorded x values of visible series, sorted. */
  const xValues = useMemo(() => {
    const set = new Set<number>();
    for (const item of visible) for (const p of item.points) set.add(p.x);
    return [...set].sort((a, b) => a - b);
  }, [visible]);

  /** Categorical tick descriptors: one per recorded x, short label for the
   *  axis, full label kept for hover/focus. */
  const categoricalTicks = useMemo(() => {
    if (!xCategorical) return null;
    const byX = new Map<number, { short: string; full: string }>();
    for (const x of xValues) {
      let short = "";
      let full = "";
      for (const item of visible) {
        const point = item.points.find((p) => p.x === x);
        if (!point) continue;
        if (!short) short = point.shortLabel ?? point.label ?? fmtX(x);
        if (!full) full = point.label ?? fmtX(x);
        if (short && full) break;
      }
      if (!short) short = fmtX(x);
      if (!full) full = fmtX(x);
      byX.set(x, { short, full });
    }
    return byX;
  }, [xCategorical, xValues, visible, fmtX]);

  /** Long categorical labels are rotated so adjacent ticks stay readable. */
  const rotateTicks = useMemo(() => {
    if (!categoricalTicks) return false;
    return [...categoricalTicks.values()].some((tick) => tick.short.length > 6);
  }, [categoricalTicks]);

  // Rotated categorical tick labels need extra room below the plot so they
  // never collide with the x-axis title.
  const marginBottom = MARGIN.bottom + (rotateTicks ? 38 : 0);
  const plotWidth = Math.max(40, width - MARGIN.left - MARGIN.right);
  const plotHeight = Math.max(40, height - MARGIN.top - marginBottom);

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

  /** Nearest recorded x AND nearest series under the pointer. */
  const pickNearest = useCallback(
    (clientX: number, clientY: number): { pointIndex: number; seriesId: string } | null => {
      if (!domain || !xValues.length || !plotRef.current) return null;
      const rect = plotRef.current.getBoundingClientRect();
      const px = clientX - rect.left;
      const py = clientY - rect.top;
      let best = 0;
      let bestDist = Infinity;
      xValues.forEach((x, index) => {
        const dist = Math.abs(scaleX(x) - px);
        if (dist < bestDist) {
          best = index;
          bestDist = dist;
        }
      });
      const activeX = xValues[best];
      let seriesId = "";
      let seriesDist = Infinity;
      for (const item of visible) {
        const point = item.points.find((p) => p.x === activeX);
        if (!point) continue;
        const dist = Math.abs(scaleY(point.y) - py);
        if (dist < seriesDist) {
          seriesId = item.id;
          seriesDist = dist;
        }
      }
      if (!seriesId) seriesId = visible[0]?.id ?? "";
      return { pointIndex: best, seriesId };
    },
    [domain, xValues, scaleX, scaleY, visible]
  );

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== "mouse") return;
    if (hover?.pinned) return;
    // Pointer events over the tooltip (e.g. the details toggle) bubble here;
    // they must not re-pick the nearest point or series.
    if ((event.target as Element | null)?.closest?.(".ichart-tooltip")) return;
    const picked = pickNearest(event.clientX, event.clientY);
    if (!picked) {
      setHover(null);
      return;
    }
    setHover((prev) =>
      prev &&
      prev.pointIndex === picked.pointIndex &&
      prev.seriesId === picked.seriesId
        ? prev
        : { ...picked, pinned: false }
    );
  };

  const onPointerLeave = () => {
    if (!hover?.pinned) setHover(null);
  };

  const onClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const picked = pickNearest(event.clientX, event.clientY);
    if (!picked) return;
    setHover((prev) =>
      prev?.pinned && prev.pointIndex === picked.pointIndex && prev.seriesId === picked.seriesId
        ? null
        : { ...picked, pinned: true }
    );
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!xValues.length) return;
    const current = focusIndex ?? hover?.pointIndex ?? 0;
    const seriesAt = (index: number) =>
      visible.filter((item) => item.points.some((p) => p.x === xValues[index]));
    switch (event.key) {
      case "ArrowRight":
        setFocusIndex(Math.min(xValues.length - 1, current + 1));
        event.preventDefault();
        break;
      case "ArrowLeft":
        setFocusIndex(Math.max(0, current - 1));
        event.preventDefault();
        break;
      case "ArrowDown":
      case "ArrowUp": {
        const rows = seriesAt(current);
        if (rows.length > 1) {
          const at = (index: number) => (index % rows.length + rows.length) % rows.length;
          const currentAt = Math.max(0, rows.findIndex((item) => item.id === hover?.seriesId));
          const next = rows[at(currentAt + (event.key === "ArrowDown" ? 1 : -1))];
          setHover((prev) => ({ pointIndex: current, seriesId: next.id, pinned: prev?.pinned ?? false }));
        }
        event.preventDefault();
        break;
      }
      case "Home":
        setFocusIndex(0);
        event.preventDefault();
        break;
      case "End":
        setFocusIndex(xValues.length - 1);
        event.preventDefault();
        break;
      case "Enter":
      case " ": {
        const rows = seriesAt(current);
        const seriesId =
          rows.find((item) => item.id === hover?.seriesId)?.id ?? rows[0]?.id ?? "";
        setHover((prev) =>
          prev?.pinned && prev.pointIndex === current && prev.seriesId === seriesId
            ? null
            : { pointIndex: current, seriesId, pinned: true }
        );
        event.preventDefault();
        break;
      }
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

  // A new point or series collapses the details section again.
  useEffect(() => {
    setExpanded(false);
  }, [hover?.pointIndex, hover?.seriesId, focusIndex]);

  // Scrolling (or viewport changes) re-runs the tooltip placement so the
  // overlay is re-clamped against the visible viewport — a pinned tooltip
  // must stay readable while the user scrolls the chart.
  const [placementTick, setPlacementTick] = useState(0);
  useEffect(() => {
    const onScroll = () => setPlacementTick((tick) => tick + 1);
    window.addEventListener("scroll", onScroll, { capture: true, passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll, { capture: true });
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  const activeIndex = hover?.pointIndex ?? focusIndex ?? null;
  const activeX = activeIndex !== null ? xValues[activeIndex] : null;

  /** All visible series that have a recorded point at the active x. */
  const activeRows = useMemo(() => {
    if (activeX === null) return [] as { series: ChartSeries; point: ChartPoint }[];
    const rows: { series: ChartSeries; point: ChartPoint }[] = [];
    for (const item of visible) {
      const point = item.points.find((p) => p.x === activeX);
      if (point) rows.push({ series: item, point });
    }
    return rows;
  }, [activeX, visible]);

  const activeRow =
    activeRows.find((row) => row.series.id === hover?.seriesId) ?? activeRows[0] ?? null;
  const relatedRows = activeRow
    ? activeRows.filter((row) => row.series.id !== activeRow.series.id)
    : [];

  const guidePx = activeX !== null ? scaleX(activeX) : 0;
  const activePointY = activeRow ? scaleY(activeRow.point.y) : MARGIN.top + plotHeight / 2;

  // Tooltip placement (M4-R1-G10): the overlay is measured after render and
  // positioned relative to the plot container and the viewport — flipped to
  // the left of the guide when the right side lacks room, clamped inside the
  // plot and the visible viewport so no text is ever clipped.  The effect
  // runs before paint, so the move is never seen mid-frame.
  useLayoutEffect(() => {
    const tip = tooltipRef.current;
    const plot = plotRef.current;
    if (!tip || !plot) {
      setTooltipPos(null);
      return;
    }
    const tw = tip.offsetWidth;
    const th = tip.offsetHeight;
    let left = guidePx + TOOLTIP_GAP;
    if (left + tw > width - MARGIN.right) {
      left = guidePx - TOOLTIP_GAP - tw;
    }
    // Horizontal clamp: never cross the plot edges.
    left = Math.min(Math.max(left, TOOLTIP_PAD), Math.max(TOOLTIP_PAD, width - tw - TOOLTIP_PAD));
    // Vertical: anchor just above the active point, then clamp inside the
    // plot and the viewport.
    let top = activePointY - 12;
    const maxTopPlot = height - th - TOOLTIP_PAD;
    if (top > maxTopPlot) top = activePointY - th - TOOLTIP_GAP;
    top = Math.min(Math.max(top, TOOLTIP_PAD), Math.max(TOOLTIP_PAD, maxTopPlot));
    const rect = plot.getBoundingClientRect();
    if (rect) {
      const viewportBottom = window.innerHeight - 8;
      const overflowBottom = rect.top + top + th - viewportBottom;
      if (overflowBottom > 0) {
        top = Math.max(TOOLTIP_PAD, top - overflowBottom);
      }
      const viewportTop = 8;
      if (rect.top + top < viewportTop) {
        top = Math.max(TOOLTIP_PAD, viewportTop - rect.top);
      }
    }
    setTooltipPos((prev) =>
      prev && prev.left === left && prev.top === top ? prev : { left, top }
    );
  }, [guidePx, activePointY, activeX, hover?.seriesId, expanded, width, height, hover?.pinned, placementTick]);

  const yTicks = niceTicks(domain?.yMin ?? 0, domain?.yMax ?? 1, 5);

  if (!domain) {
    return (
      <div className="ichart ichart--empty" ref={wrapRef}>
        <p className="mono-label">No recorded data points for this chart.</p>
      </div>
    );
  }

  const tickXText = (x: number): string => {
    if (categoricalTicks) {
      const tick = categoricalTicks.get(x);
      if (tick) return tick.short;
    }
    return fmtX(x);
  };

  return (
    <figure className="ichart" ref={wrapRef as unknown as React.Ref<HTMLDivElement>}>
      <div
        className="ichart-plot"
        ref={plotRef}
        tabIndex={0}
        role="application"
        aria-label={`${caption}. Use left and right arrows to move between recorded data points, up and down to change series, Enter to pin the explanation.`}
        onPointerMove={onPointerMove}
        onPointerLeave={onPointerLeave}
        onClick={onClick}
        onKeyDown={onKeyDown}
      >
        <div className="ichart-svg">
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
                <text x={MARGIN.left - 8} y={scaleY(tick) + 3.5} className="ichart-tick" textAnchor="end">
                  {fmtY(tick)}
                </text>
              </g>
            ))}
            {(xCategorical ? xValues : niceTicks(domain.xMin, domain.xMax, 5)).map((tick) => {
              const tickPx = scaleX(tick);
              const tickText = tickXText(tick);
              if (rotateTicks) {
                const tickY = height - marginBottom + 20;
                return (
                  <text
                    key={`x${tick}`}
                    x={tickPx}
                    y={tickY}
                    className="ichart-tick ichart-tick-x"
                    textAnchor="end"
                    transform={`rotate(-38 ${tickPx} ${tickY})`}
                  >
                    {tickText}
                  </text>
                );
              }
              return (
                <text
                  key={`x${tick}`}
                  x={tickPx}
                  y={height - marginBottom + 20}
                  className="ichart-tick ichart-tick-x"
                  textAnchor="middle"
                >
                  {tickText}
                </text>
              );
            })}
            {activeX !== null && (
              <line
                x1={guidePx}
                x2={guidePx}
                y1={MARGIN.top}
                y2={height - marginBottom}
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
                    const isActive =
                      activeX !== null &&
                      point.x === activeX &&
                      item.id === activeRow?.series.id;
                    return (
                      <g key={i}>
                        {isActive && (
                          <circle
                            cx={scaleX(point.x)}
                            cy={scaleY(point.y)}
                            r={9}
                            className="ichart-halo"
                            fill={item.color}
                          />
                        )}
                        <circle
                          cx={scaleX(point.x)}
                          cy={scaleY(point.y)}
                          r={isActive ? 4.5 : 2.8}
                          className={`ichart-dot${isActive ? " is-active" : ""}`}
                          fill={item.color}
                          stroke={isActive ? "#18272d" : "none"}
                          strokeWidth={1.5}
                        />
                      </g>
                    );
                  })}
                </g>
              );
            })}
            <text x={MARGIN.left + plotWidth / 2} y={height - 6} className="ichart-axis" textAnchor="middle">
              {xLabel}
            </text>
            <text
              x={14}
              y={MARGIN.top + plotHeight / 2}
              className="ichart-axis"
              textAnchor="middle"
              transform={`rotate(-90 14 ${MARGIN.top + plotHeight / 2})`}
            >
              {yLabel}
            </text>
          </svg>
        </div>

        {activeRow && (
          <div
            ref={tooltipRef}
            className={`ichart-tooltip${expanded ? " is-expanded" : ""}`}
            style={{
              left: tooltipPos?.left ?? -9999,
              top: tooltipPos?.top ?? -9999,
              visibility: tooltipPos ? "visible" : "hidden",
            }}
            role="status"
          >
            <div className="ichart-tooltip-row">
              <span className="ichart-swatch" style={{ background: activeRow.series.color }} aria-hidden="true" />
              <strong>{activeRow.series.label}</strong>
              <span className="mono-label ichart-value">
                {activeRow.point.label ?? fmtX(activeRow.point.x)}
                {xUnit ? ` ${xUnit}` : ""}
              </span>
              <span className="mono-label ichart-value">
                → {fmtY(activeRow.point.y)}
                {yUnit ? ` ${yUnit}` : ""}
              </span>
              {activeRow.point.facts?.map(([label, value]) => (
                <span key={label} className="mono-label ichart-fact">
                  {label}: {value}
                </span>
              ))}
              {activeRow.point.interpretation && (
                <span className="ichart-interpretation">{activeRow.point.interpretation}</span>
              )}
            </div>
            <button
              type="button"
              className="ichart-details-toggle"
              aria-expanded={expanded}
              onClick={(event) => {
                event.stopPropagation();
                setExpanded((prev) => !prev);
              }}
            >
              {expanded ? "Hide details ▴" : "Details ▾"}
            </button>
            {expanded && (
              <div className="ichart-details">
                {relatedRows.length > 0 && (
                  <>
                    <h4>Other series at this x value</h4>
                    {relatedRows.map(({ series: item, point }) => (
                      <div key={item.id} className="ichart-tooltip-row ichart-related">
                        <span className="ichart-swatch" style={{ background: item.color }} aria-hidden="true" />
                        <span className="mono-label">
                          {item.label}: {fmtY(point.y)}
                          {yUnit ? ` ${yUnit}` : ""}
                          {point.label ? ` · ${point.label}` : ""}
                        </span>
                      </div>
                    ))}
                  </>
                )}
                <h4>Measurement context</h4>
                <p className="mono-label ichart-context">{context}</p>
                {cannotConclude && cannotConclude.length > 0 && (
                  <>
                    <h4>Limitations</h4>
                    <p className="mono-label ichart-limitations">{cannotConclude.join(" ")}</p>
                  </>
                )}
              </div>
            )}
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
              title={item.label}
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
