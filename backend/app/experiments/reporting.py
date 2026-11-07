"""Deterministic research reporting: SVG charts and CSV summaries.

Every chart is generated from numbers that were computed by the experiment
runner in the same process.  There is no random element and no wall-clock
timestamp inside a chart, so regenerating the same run reproduces the files
byte for byte.  The SVG writer is deliberately dependency-free: it draws
axis frames, series polylines, bars and confidence whiskers with plain
string formatting, and nothing else.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Iterable, Sequence


class ReportingError(RuntimeError):
    """Raised when a chart or table cannot be produced from real results."""


def _fmt(value: float, digits: int = 4) -> str:
    """Compact fixed-precision formatting without exponent surprises."""
    text = f"{value:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class SvgCanvas:
    """Minimal deterministic SVG frame: axes, ticks, legend, series."""

    WIDTH = 900
    HEIGHT = 460
    MARGIN = {"left": 70, "right": 24, "top": 56, "bottom": 64}
    # Midnight Teal & Copper palette (matches the viewer identity).
    SERIES_COLORS = ("#4fb3a9", "#d98a5d", "#8fb3c7", "#c9a15d", "#a9836d")

    def __init__(self, title: str, subtitle: str = "") -> None:
        self.title = title
        self.subtitle = subtitle
        self.body: list[str] = []

    # -- geometry -----------------------------------------------------------
    @property
    def plot_left(self) -> int:
        return self.MARGIN["left"]

    @property
    def plot_top(self) -> int:
        return self.MARGIN["top"]

    @property
    def plot_right(self) -> int:
        return self.WIDTH - self.MARGIN["right"]

    @property
    def plot_bottom(self) -> int:
        return self.HEIGHT - self.MARGIN["bottom"]

    def x(self, value: float, lo: float, hi: float) -> float:
        if hi <= lo:
            raise ReportingError("x domain is degenerate")
        return self.plot_left + (value - lo) / (hi - lo) * (
            self.plot_right - self.plot_left
        )

    def y(self, value: float, lo: float, hi: float) -> float:
        if hi <= lo:
            raise ReportingError("y domain is degenerate")
        return self.plot_bottom - (value - lo) / (hi - lo) * (
            self.plot_bottom - self.plot_top
        )

    # -- primitives ---------------------------------------------------------
    def frame(self, x_lo: float, x_hi: float, y_lo: float, y_hi: float) -> None:
        self.body.append(
            f'<rect x="{self.plot_left}" y="{self.plot_top}" '
            f'width="{self.plot_right - self.plot_left}" '
            f'height="{self.plot_bottom - self.plot_top}" '
            f'fill="#0e2226" stroke="#3a5f63" stroke-width="1"/>'
        )

    def y_ticks(self, lo: float, hi: float, digits: int = 3) -> None:
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            value = lo + fraction * (hi - lo)
            y = self.y(value, lo, hi)
            label = _fmt(value, digits)
            self.body.append(
                f'<line x1="{self.plot_left}" y1="{y:.1f}" '
                f'x2="{self.plot_right}" y2="{y:.1f}" '
                f'stroke="#24444c" stroke-width="1" stroke-dasharray="3 4"/>'
            )
            self.body.append(
                f'<text x="{self.plot_left - 10}" y="{y + 4:.1f}" '
                f'text-anchor="end" font-size="12" fill="#9fc2c6">{label}</text>'
            )

    def caption(self, text: str) -> None:
        self.body.append(
            f'<text x="{self.MARGIN["left"]}" y="{self.HEIGHT - 12}" '
            f'font-size="11" fill="#6f949b">{_esc(text)}</text>'
        )

    def legend(self, entries: Sequence[tuple[str, str]]) -> None:
        x = self.MARGIN["left"] + 12
        y = self.MARGIN["top"] + 20
        for index, (label, color) in enumerate(entries):
            row = y + index * 18
            self.body.append(
                f'<line x1="{x}" y1="{row}" x2="{x + 26}" y2="{row}" '
                f'stroke="{color}" stroke-width="2"/>'
            )
            self.body.append(
                f'<text x="{x + 32}" y="{row + 4}" font-size="12" '
                f'fill="#cfe3e4">{_esc(label)}</text>'
            )

    def polyline(
        self,
        points: Iterable[tuple[float, float]],
        color: str,
        width: float = 2.0,
    ) -> None:
        rendered = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        self.body.append(
            f'<polyline points="{rendered}" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linejoin="round"/>'
        )

    def marker(self, x: float, y: float, color: str) -> None:
        self.body.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>'
        )

    def bar(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        color: str,
    ) -> None:
        self.body.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(width, 1.0):.1f}" '
            f'height="{max(height, 0.0):.1f}" fill="{color}"/>'
        )

    def whisker(
        self, x: float, y_lo: float, y_hi: float, color: str
    ) -> None:
        self.body.append(
            f'<line x1="{x:.1f}" y1="{y_lo:.1f}" x2="{x:.1f}" '
            f'y2="{y_hi:.1f}" stroke="{color}" stroke-width="2"/>'
        )
        for y in (y_lo, y_hi):
            self.body.append(
                f'<line x1="{x - 4:.1f}" y1="{y:.1f}" x2="{x + 4:.1f}" '
                f'y2="{y:.1f}" stroke="{color}" stroke-width="2"/>'
            )

    def titles(self) -> None:
        self.body.append(
            f'<text x="{self.WIDTH / 2}" y="24" text-anchor="middle" '
            f'font-size="16" font-weight="600" fill="#e6f1f1">'
            f'{_esc(self.title)}</text>'
        )
        if self.subtitle:
            self.body.append(
                f'<text x="{self.WIDTH / 2}" y="42" text-anchor="middle" '
                f'font-size="12" fill="#9fc2c6">{_esc(self.subtitle)}</text>'
            )

    def x_axis_label(self, label: str) -> None:
        self.body.append(
            f'<text x="{(self.plot_left + self.plot_right) / 2:.0f}" '
            f'y="{self.HEIGHT - 34}" text-anchor="middle" font-size="12" '
            f'fill="#9fc2c6">{_esc(label)}</text>'
        )

    def x_tick(self, value: float, label: str, x_lo: float, x_hi: float) -> None:
        x = self.x(value, x_lo, x_hi)
        self.body.append(
            f'<text x="{x:.1f}" y="{self.plot_bottom + 18}" '
            f'text-anchor="middle" font-size="11" fill="#9fc2c6">'
            f'{_esc(label)}</text>'
        )

    def save(self, path: Path) -> str:
        self.titles()
        content = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {self.WIDTH} {self.HEIGHT}" '
            f'width="{self.WIDTH}" height="{self.HEIGHT}" '
            'font-family="Segoe UI, Arial, sans-serif">\n'
            + "\n".join(self.body)
            + "\n</svg>\n"
        )
        path.write_text(content, encoding="utf-8")
        return content


def threshold_response_svg(
    results_by_index: dict[str, list[dict[str, Any]]],
    estimator_id: str,
    path: Path,
) -> None:
    """Write the threshold-response line chart for one estimator."""
    canvas = SvgCanvas(
        "Threshold response - candidate change fraction of common-valid area",
        f"estimator: {estimator_id}",
    )
    thresholds = sorted(
        {row["threshold"] for rows in results_by_index.values() for row in rows}
    )
    if len(thresholds) < 2:
        raise ReportingError("threshold response needs at least two thresholds")
    x_lo, x_hi = thresholds[0], thresholds[-1]
    max_fraction = max(
        max(
            max(row["decrease_percent_of_common"], row["increase_percent_of_common"])
            for row in rows
        )
        for rows in results_by_index.values()
    )
    y_hi = max(10.0, math.ceil(max_fraction / 10.0) * 10.0)
    canvas.frame(x_lo, x_hi, 0.0, y_hi)
    canvas.y_ticks(0.0, y_hi, digits=0)
    for value in thresholds:
        canvas.x_tick(value, f"{value:.2f}", x_lo, x_hi)
    canvas.x_axis_label("absolute delta threshold")
    entries: list[tuple[str, str]] = []
    for position, (index, rows) in enumerate(sorted(results_by_index.items())):
        color = canvas.SERIES_COLORS[position % len(canvas.SERIES_COLORS)]
        rows = sorted(rows, key=lambda item: item["threshold"])
        decrease = [
            (canvas.x(row["threshold"], x_lo, x_hi),
             canvas.y(row["decrease_percent_of_common"], 0.0, y_hi))
            for row in rows
        ]
        increase = [
            (canvas.x(row["threshold"], x_lo, x_hi),
             canvas.y(row["increase_percent_of_common"], 0.0, y_hi))
            for row in rows
        ]
        canvas.polyline(decrease, color)
        for x, y in decrease:
            canvas.marker(x, y, color)
        canvas.polyline(increase, color, width=1.2)
        for x, y in increase:
            canvas.marker(x, y, color)
        entries.append((f"{index}: decrease solid / increase thin", color))
    canvas.legend(entries)
    canvas.caption(
        "decrease = delta <= -threshold; increase = delta >= +threshold; "
        "fractions are of the estimator's own common-valid footprint"
    )
    canvas.save(path)


def delta_histogram_svg(
    delta: "Any",
    common: "Any",
    index: str,
    estimator_id: str,
    path: Path,
) -> dict[str, Any]:
    """Histogram of measured delta values on the common-valid footprint."""
    import numpy as np

    values = np.asarray(delta, dtype=np.float64)[common]
    if values.size == 0:
        raise ReportingError(f"{estimator_id}/{index}: empty footprint")
    bins = 48
    lo = float(values.min())
    hi = float(values.max())
    if hi <= lo:
        raise ReportingError(f"{estimator_id}/{index}: degenerate delta range")
    counts, edges = np.histogram(values, bins=bins, range=(lo, hi))
    canvas = SvgCanvas(
        f"Delta {index.upper()} distribution - measured pixel counts",
        f"estimator: {estimator_id} | n = {values.size:,} | "
        f"mean = {_fmt(float(values.mean()))} | std = {_fmt(float(values.std()))}",
    )
    peak = int(counts.max())
    canvas.frame(lo, hi, 0.0, float(peak))
    canvas.y_ticks(0.0, float(peak), digits=0)
    for edge, label in ((lo, _fmt(lo, 2)), (0.0, "0"), (hi, _fmt(hi, 2))):
        if lo <= edge <= hi:
            canvas.x_tick(edge, label, lo, hi)
    canvas.x_axis_label(f"delta {index}")
    bar_width = (canvas.plot_right - canvas.plot_left) / bins
    for position, count in enumerate(counts):
        if count <= 0:
            continue
        x = canvas.plot_left + position * bar_width
        height = count / peak * (canvas.plot_bottom - canvas.plot_top)
        zero_inside = edges[position] <= 0.0 <= edges[position + 1]
        color = "#d98a5d" if zero_inside else "#4fb3a9"
        canvas.bar(x, canvas.plot_bottom - height, bar_width, height, color)
    x_zero = canvas.x(0.0, lo, hi)
    canvas.body.append(
        f'<line x1="{x_zero:.1f}" y1="{canvas.plot_top}" '
        f'x2="{x_zero:.1f}" y2="{canvas.plot_bottom}" '
        f'stroke="#e6f1f1" stroke-width="1" stroke-dasharray="5 4"/>'
    )
    canvas.caption(
        "bins are equal-width over the measured min..max; the dashed line "
        "marks delta = 0 (no change); copper bars straddle zero"
    )
    canvas.save(path)
    return {
        "bins": bins,
        "range_min": lo,
        "range_max": hi,
        "counts": [int(item) for item in counts],
        "edges": [float(item) for item in edges],
    }


def estimator_comparison_svg(
    results: list[dict[str, Any]],
    index: str,
    threshold: float,
    path: Path,
) -> None:
    """Mean delta and candidate-change fraction for every estimator, one index."""
    rows = sorted(
        (item for item in results if item["index"] == index),
        key=lambda item: (item["family"], item["estimator_id"]),
    )
    if not rows:
        raise ReportingError(f"no estimator results for index {index}")
    canvas = SvgCanvas(
        f"Estimator comparison at threshold {threshold:.2f} - {index.upper()}",
        "bar height = candidate-change fraction (% of common-valid); "
        "colour = family",
    )
    family_colors = {
        "composite": "#4fb3a9",
        "anchor_single": "#d98a5d",
        "single_pairs": "#8fb3c7",
        "leave_one_out": "#c9a15d",
        "m0_single_scene": "#a9836d",
    }
    slot = (canvas.plot_right - canvas.plot_left) / len(rows)
    bar_width = slot * 0.62
    peak_fraction = max(
        max(
            row["primary"]["decrease_percent_of_common"],
            row["primary"]["increase_percent_of_common"],
        )
        for row in rows
    )
    y_hi = max(10.0, math.ceil(peak_fraction / 10.0) * 10.0)
    canvas.frame(0.0, float(len(rows)), 0.0, y_hi)
    canvas.y_ticks(0.0, y_hi, digits=0)
    for position, row in enumerate(rows):
        x = canvas.plot_left + position * slot + (slot - bar_width) / 2
        color = family_colors.get(row["family"], "#8fb3c7")
        decrease_height = (
            row["primary"]["decrease_percent_of_common"] / y_hi
            * (canvas.plot_bottom - canvas.plot_top)
        )
        canvas.bar(x, canvas.plot_bottom - decrease_height, bar_width / 2 - 1,
                   decrease_height, color)
        increase_height = (
            row["primary"]["increase_percent_of_common"] / y_hi
            * (canvas.plot_bottom - canvas.plot_top)
        )
        canvas.bar(
            x + bar_width / 2 + 1,
            canvas.plot_bottom - increase_height,
            bar_width / 2 - 1,
            increase_height,
            "#5d4436" if color == "#d98a5d" else "#7d4f38",
        )
        label = row["estimator_id"]
        if label.startswith("single__"):
            label = "single__" + label[8:24] + "…"
        canvas.body.append(
            f'<text x="{x + bar_width / 2:.1f}" '
            f'y="{canvas.plot_bottom + 16}" text-anchor="end" '
            f'font-size="9" fill="#9fc2c6" '
            f'transform="rotate(-52 {x + bar_width / 2:.1f} '
            f'{canvas.plot_bottom + 16})">{_esc(label)}</text>'
        )
    canvas.body.append(
        f'<text x="{canvas.plot_right - 8}" y="{canvas.plot_top + 20}" '
        f'text-anchor="end" font-size="12" fill="#cfe3e4">left bar: decrease'
        f'</text>'
    )
    canvas.body.append(
        f'<text x="{canvas.plot_right - 8}" y="{canvas.plot_top + 36}" '
        f'text-anchor="end" font-size="12" fill="#cfe3e4">right bar: increase'
        f'</text>'
    )
    canvas.caption(
        "every bar is computed from the same index formula and threshold rule; "
        "differences are observation-selection effects"
    )
    canvas.save(path)


def bootstrap_svg(
    bootstrap: dict[str, Any],
    index: str,
    path: Path,
) -> None:
    """Block-bootstrap intervals per threshold beside the point estimate."""
    if not bootstrap.get("enabled"):
        raise ReportingError("bootstrap is disabled; no chart available")
    rows = sorted(bootstrap["thresholds"], key=lambda item: item["threshold"])
    lo = min(
        min(row["decrease_fraction_ci95"]["p2_5"],
            row["increase_fraction_ci95"]["p2_5"])
        for row in rows
    )
    hi = max(
        max(row["decrease_fraction_ci95"]["p97_5"],
            row["increase_fraction_ci95"]["p97_5"])
        for row in rows
    )
    pad = 0.05 * (hi - lo) if hi > lo else 0.01
    y_lo = max(0.0, lo - pad)
    y_hi = hi + pad
    canvas = SvgCanvas(
        f"Spatial block bootstrap - {index.upper()} change fractions",
        f"block {bootstrap['block_size_px']} px "
        f"({bootstrap['block_size_m']:.0f} m) | "
        f"{bootstrap['iterations_used']} resamples | seed "
        f"{bootstrap['seed']} | whiskers = 95% percentile interval",
    )
    thresholds = [row["threshold"] for row in rows]
    x_lo, x_hi = thresholds[0], thresholds[-1]
    canvas.frame(x_lo, x_hi, y_lo, y_hi)
    canvas.y_ticks(y_lo, y_hi, digits=3)
    for value in thresholds:
        canvas.x_tick(value, f"{value:.2f}", x_lo, x_hi)
    canvas.x_axis_label("absolute delta threshold")
    for row in rows:
        x = canvas.x(row["threshold"], x_lo, x_hi)
        dec = row["decrease_fraction_ci95"]
        canvas.whisker(
            x,
            canvas.y(dec["p2_5"], y_lo, y_hi),
            canvas.y(dec["p97_5"], y_lo, y_hi),
            "#d98a5d",
        )
        canvas.marker(x, canvas.y(dec["p50"], y_lo, y_hi), "#d98a5d")
        inc = row["increase_fraction_ci95"]
        canvas.whisker(
            x,
            canvas.y(inc["p2_5"], y_lo, y_hi),
            canvas.y(inc["p97_5"], y_lo, y_hi),
            "#4fb3a9",
        )
        canvas.marker(x, canvas.y(inc["p50"], y_lo, y_hi), "#4fb3a9")
    canvas.legend([("decrease fraction", "#d98a5d"), ("increase fraction", "#4fb3a9")])
    canvas.caption(
        "intervals describe resampling variability of an area fraction for "
        "this AOI and grid only; they are not population confidence intervals"
    )
    canvas.save(path)


def write_summary_csv(
    path: Path,
    results: list[dict[str, Any]],
) -> int:
    """One row per estimator x threshold with area conservation columns."""
    fields = [
        "estimator_id",
        "family",
        "index",
        "threshold",
        "common_valid_pixels",
        "decrease_pixels",
        "stable_pixels",
        "increase_pixels",
        "valid_area_ha",
        "decrease_area_ha",
        "stable_area_ha",
        "increase_area_ha",
        "decrease_percent_of_common",
        "stable_percent_of_common",
        "increase_percent_of_common",
        "delta_mean",
        "delta_std",
        "delta_p50",
        "area_conservation_ok",
        "suitable_for_comparison",
    ]
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            for row in result["thresholds"]:
                writer.writerow(
                    {
                        "estimator_id": result["estimator_id"],
                        "family": result["family"],
                        "index": result["index"],
                        "threshold": f"{row['threshold']:.2f}",
                        "common_valid_pixels": row["valid_pixels"],
                        "decrease_pixels": row["decrease_pixels"],
                        "stable_pixels": row["stable_pixels"],
                        "increase_pixels": row["increase_pixels"],
                        "valid_area_ha": f"{row['valid_area_ha']:.4f}",
                        "decrease_area_ha": f"{row['decrease_area_ha']:.4f}",
                        "stable_area_ha": f"{row['stable_area_ha']:.4f}",
                        "increase_area_ha": f"{row['increase_area_ha']:.4f}",
                        "decrease_percent_of_common": f"{row['decrease_percent_of_common']:.6f}",
                        "stable_percent_of_common": f"{row['stable_percent_of_common']:.6f}",
                        "increase_percent_of_common": f"{row['increase_percent_of_common']:.6f}",
                        "delta_mean": f"{result['delta_stats']['mean']:.6f}",
                        "delta_std": f"{result['delta_stats']['std']:.6f}",
                        "delta_p50": f"{result['delta_stats']['quantiles']['p50']:.6f}",
                        "area_conservation_ok": row["area_conservation"]["ok"],
                        "suitable_for_comparison": result["suitable_for_comparison"],
                    }
                )
                count += 1
    return count


def write_sensitivity_csv(
    path: Path,
    primary_results: dict[str, list[dict[str, Any]]],
) -> int:
    """Primary composite estimator: the threshold sensitivity table."""
    fields = [
        "index",
        "threshold",
        "decrease_area_ha",
        "increase_area_ha",
        "stable_area_ha",
        "valid_area_ha",
        "decrease_percent_of_common",
        "increase_percent_of_common",
        "area_conservation_ok",
    ]
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, rows in sorted(primary_results.items()):
            for row in sorted(rows, key=lambda item: item["threshold"]):
                writer.writerow(
                    {
                        "index": index,
                        "threshold": f"{row['threshold']:.2f}",
                        "decrease_area_ha": f"{row['decrease_area_ha']:.4f}",
                        "increase_area_ha": f"{row['increase_area_ha']:.4f}",
                        "stable_area_ha": f"{row['stable_area_ha']:.4f}",
                        "valid_area_ha": f"{row['valid_area_ha']:.4f}",
                        "decrease_percent_of_common": f"{row['decrease_percent_of_common']:.6f}",
                        "increase_percent_of_common": f"{row['increase_percent_of_common']:.6f}",
                        "area_conservation_ok": row["area_conservation"]["ok"],
                    }
                )
                count += 1
    return count
