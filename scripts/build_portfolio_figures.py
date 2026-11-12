"""Build report figures (static SVG) from recorded artifacts only.

Reads frontend/public/studies/*.json bundles, m5ml_findings.json and
data/experiments/m5_gsw/*/result.json. Computes nothing new: every plotted
value is copied from a recorded artifact. Output: docs/figures/*.svg
"""
from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"
TEAL, COPPER, INK, MUTED, GRID = "#1f4b55", "#c4733f", "#1c2b30", "#6b7b80", "#d9d6cd"
FONT = "font-family=\"IBM Plex Sans, Segoe UI, Arial, sans-serif\""

# ml experiment id -> (bundle dir, label, primary index, primary class)
STUDY_MAP = {
    "kathmandu_m4": ("kathmandu_urban", "Kathmandu", "ndbi", "built_up"),
    "western_ghats_m4": ("western_ghats_forest", "Western Ghats", "ndvi", "forest_vegetation"),
    "chilika_m4_dry": ("chilika_wetland", "Chilika (dry)", "mndwi", "water"),
    "chilika_m4_postmonsoon": ("chilika_wetland", "Chilika (post-monsoon)", "mndwi", "water"),
    "coringa_m1": ("coringa_coastal", "Coringa", "ndvi", "vegetation"),
}


def svg(w: int, h: int, body: str, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{escape(title)}" {FONT}><rect width="{w}" height="{h}" fill="#fbfaf6"/>{body}</svg>')


def text(x, y, s, size=12, fill=INK, anchor="start", weight="400"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{escape(str(s))}</text>')


def rect(x, y, w, h, fill):
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(w, 0):.2f}" height="{h:.2f}" fill="{fill}"/>'


def line(x1, y1, x2, y2, stroke, width=1):
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{stroke}" stroke-width="{width}"/>'


def load():
    path = ROOT / "frontend/public/studies/m5ml_findings.json"
    return json.loads(path.read_text(encoding="utf-8"))["experiments"]


def fig_agreement(ml) -> str:
    rows = []
    for eid, (_, label, _, _) in STUDY_MAP.items():
        r = ml[eid]["ml_record"]
        ev, folds = r["evaluation"], r["geographic_stability"]["folds"]
        ag = [f["overall_agreement"] for f in folds if f.get("available")]
        rows.append((label, ev["overall_agreement"], ev["macro_f1_supported_classes"], min(ag), max(ag)))
    W, H, L, R, T = 820, 90 + 62 * len(rows), 200, 40, 62
    pw = W - L - R

    def x(v):
        return L + v * pw

    b = text(24, 28, "Random Forest agreement with ESA WorldCover (test blocks)", 16, INK, weight="600")
    b += text(24, 48, "Agreement with a reference product, not ground-truth accuracy. Whisker = range over geographic hold-out folds.", 11, MUTED)
    for t in (0, .25, .5, .75, 1):
        b += line(x(t), T, x(t), H - 34, GRID) + text(x(t), H - 18, f"{t:.2f}", 10, MUTED, "middle")
    for i, (lab, ag, f1, lo, hi) in enumerate(rows):
        y = T + 14 + i * 62
        b += text(L - 12, y + 22, lab, 12, INK, "end")
        b += rect(L, y, x(ag) - L, 18, TEAL) + text(x(max(ag, hi)) + 8, y + 13, f"{ag:.3f}", 11, INK)
        b += rect(L, y + 22, x(f1) - L, 14, COPPER) + text(x(f1) + 6, y + 33, f"{f1:.3f}", 11, INK)
        b += line(x(lo), y + 9, x(hi), y + 9, INK, 1.5)
        for v in (lo, hi):
            b += line(x(v), y + 4, x(v), y + 14, INK, 1.5)
    b += rect(W - 260, H - 14, 10, 10, TEAL) + text(W - 245, H - 5, "overall agreement", 10, MUTED)
    b += rect(W - 130, H - 14, 10, 10, COPPER) + text(W - 115, H - 5, "macro-F1 (supported)", 10, MUTED)
    return svg(W, H, b, "Random Forest agreement by study")


def fig_two_methods(ml) -> str:
    cache, rows = {}, []
    for eid, (bd, label, idx, cls) in STUDY_MAP.items():
        if bd not in cache:
            cache[bd] = json.loads((ROOT / f"frontend/public/studies/{bd}/bundle.json").read_text(encoding="utf-8"))
        bundle = cache[bd]
        exp = next((e for e in bundle["experiments"] if e["experiment_id"] == eid), None)
        charts = (exp or {}).get("charts") or bundle["charts"]
        series = next(s for s in charts["threshold_series"] if s["index"] == idx)
        pt = next(p for p in series["points"] if abs(p["threshold"] - series["primary_threshold"]) < 1e-9)
        net = pt["increase_percent_of_common"] - pt["decrease_percent_of_common"]
        shift = ml[eid]["ml_record"]["math_baseline_comparison"]["predicted_fraction_shift"][cls] * 100
        rows.append((label, net, shift, idx.upper(), series["primary_threshold"]))
    W, H, L, R, T = 880, 120 + 64 * len(rows), 270, 60, 84
    lim = max(max(abs(r[1]), abs(r[2])) for r in rows)
    lim = max(5, (int(lim / 5) + 1) * 5)
    mid, half = L + (W - L - R) / 2, (W - L - R) / 2

    def x(v):
        return mid + v / lim * half

    b = text(24, 28, "Two methods, one question: direction of change", 16, INK, weight="600")
    b += text(24, 48, "Different quantities (index-change share vs predicted class-share change, in %/percentage points): compare direction, not magnitude.", 11, MUTED)
    b += text(24, 64, "Agreement in direction is consistency, never corroboration; neither is verified change.", 11, MUTED)
    b += line(mid, T, mid, H - 40, INK)
    for t in (-lim, -lim / 2, lim / 2, lim):
        b += line(x(t), T, x(t), H - 40, GRID) + text(x(t), H - 24, f"{t:+.0f}", 10, MUTED, "middle")
    for i, (lab, v1, v2, idx, thr) in enumerate(rows):
        y = T + 8 + i * 64
        b += text(L - 12, y + 26, f"{lab} ({idx}, ±{thr})", 12, INK, "end")
        for off, v, col in ((0, v1, TEAL), (24, v2, COPPER)):
            x0, x1 = sorted((mid, x(v)))
            b += rect(x0, y + off, max(x1 - x0, 1), 18, col)
            b += text(x(v) + (6 if v >= 0 else -6), y + off + 13, f"{v:+.2f}", 11, INK, "start" if v >= 0 else "end")
    b += rect(24, H - 14, 10, 10, TEAL) + text(40, H - 5, "math: net share of pixels beyond threshold (increase - decrease), % of common-valid", 10, MUTED)
    b += rect(W - 250, H - 14, 10, 10, COPPER) + text(W - 235, H - 5, "RF: predicted class-share shift (pp)", 10, MUTED)
    return svg(W, H, b, "Mathematical vs Random Forest direction of change")


def fig_gsw() -> str:
    studies = [("chilika_dry", "Chilika (dry)"), ("chilika_postmonsoon", "Chilika (post-monsoon)"), ("coringa", "Coringa")]
    data = {s: json.loads((ROOT / f"data/experiments/m5_gsw/{s}/result.json").read_text(encoding="utf-8")) for s, _ in studies}
    W, H, L, T = 820, 340, 90, 90
    ph = H - T - 50
    b = text(24, 28, "Water reference products: ESA WorldCover vs JRC Global Surface Water", 16, INK, weight="600")
    b += text(24, 48, "Water overlap (IoU) by GSW occurrence threshold. Reference-vs-reference consistency, not accuracy.", 11, MUTED)
    ths = [10, 25, 50, 75]
    gw = (W - L - 30) / len(studies)

    def y(v):
        return T + ph * (1 - v)

    for t in (0, .25, .5, .75, 1):
        b += line(L, y(t), W - 30, y(t), GRID) + text(L - 8, y(t) + 4, f"{t:.2f}", 10, MUTED, "end")
    shades = ["#9fc3c9", "#5f9aa4", TEAL, "#123037"]
    for gi, (s, lab) in enumerate(studies):
        gx = L + gi * gw + 14
        bw = (gw - 40) / len(ths)
        for ti, row in enumerate(data[s]["results_by_gsw_threshold"]):
            v = row["water_overlap_iou"]
            bx = gx + ti * bw
            b += rect(bx, y(v), bw - 6, y(0) - y(v), shades[ti]) + text(bx + (bw - 6) / 2, y(v) - 4, f"{v:.2f}", 10, INK, "middle")
        b += text(gx + (gw - 40) / 2, H - 26, lab, 12, INK, "middle")
        b += text(gx + (gw - 40) / 2, H - 10, f"WorldCover water share {data[s]['worldcover_water_fraction'] * 100:.1f}%", 10, MUTED, "middle")
    for ti, t in enumerate(ths):
        b += rect(W - 330 + ti * 80, 62, 10, 10, shades[ti]) + text(W - 316 + ti * 80, 71, f"occ >= {t}%", 10, MUTED)
    return svg(W, H, b, "WorldCover vs JRC GSW water overlap")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ml = load()
    for name, content in (("fig1_rf_agreement.svg", fig_agreement(ml)),
                          ("fig2_two_methods_direction.svg", fig_two_methods(ml)),
                          ("fig3_water_reference_crosscheck.svg", fig_gsw())):
        (OUT / name).write_text(content, encoding="utf-8")
        print("wrote", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
