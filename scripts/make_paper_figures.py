"""Draw the figures for the version 3 paper (docs/paper/v3/figures) from recorded outputs.

    python scripts/make_paper_figures.py
PNG at 300 dpi (used by LaTeX and the HTML preview) and SVG. PDF output is not used because matplotlib's PDF backend
needs fontTools, whose compiled module is blocked by this machine's application-control policy. Nothing here computes a new result.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402

ROOT = config.PROJECT_ROOT
OUT = ROOT / "docs" / "paper" / "v3" / "figures"
V3 = json.loads((ROOT / "frontend" / "public" / "research" / "v3.json").read_text())
CV = json.loads((config.DATA_DIR / "experiments" / "v3_unet" / "cv.json").read_text())

INK, BLUE, GREY, LIGHT = "#0d1320", "#1b4f9c", "#8da6cf", "#c9d3e3"
KIND_COLOUR = {"model": BLUE, "bands": GREY, "index": INK}
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#55617a", "axes.linewidth": 0.8, "svg.fonttype": "none"})


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


def dots(ax, rows, base_rate, title):
    rows = list(reversed(rows))
    for i, r in enumerate(rows):
        c = KIND_COLOUR[r["kind"]]
        if r.get("ap_ci"):
            ax.plot(r["ap_ci"], [i, i], color=c, alpha=0.35, lw=3, solid_capstyle="round")
        ax.plot(r["ap"], i, "o", color=c, ms=6)
        ax.text(1.02, i, f"{r['ap']:.2f}", va="center", fontsize=8, transform=ax.get_yaxis_transform())
    ref = next(r for r in rows if r["is_reference"])
    ax.axvline(ref["ap"], color=INK, ls="--", lw=1)
    ax.axvline(base_rate, color="#a9b4c8", ls=":", lw=1)
    ax.set_yticks(range(len(rows)), [r["label"] for r in rows])
    ax.set_xlim(0, 1)
    ax.set_xlabel("average precision")
    ax.set_title(title, loc="left", fontsize=9.5, fontweight="bold")


def fig_forest() -> None:
    fig, axes = plt.subplots(1, 5, figsize=(7.2, 2.7), sharex=True, sharey=True)
    order = ["ndvi_decrease", "raw6", "prithvi", "ssl4eo_rgb", "ndvi", "ndwi", "indices5"]
    short = {"Kodagu and Wayanad": "Kodagu", "Shivalik foothills": "Shivalik"}
    for i, (ax, (key, f)) in enumerate(zip(axes, V3["forest"].items())):
        rows = [next(r for r in f["rows"] if r["id"] == k) for k in order]
        name = f["title"].split(",")[0]
        dots(ax, rows, f["counts"]["base_rate"], f"{short.get(name, name)}" + chr(10) + f"n = {f['counts']['positives']}")
        ax.title.set_fontsize(8)
        ax.set_xticks([0, 0.5, 1])
        ax.set_xlabel("")
        for tx in ax.texts:
            tx.set_fontsize(6.5)
        if i:
            ax.tick_params(axis="y", left=False)
    fig.supxlabel("average precision", fontsize=8.5)
    fig.tight_layout()
    save(fig, "fig_forest_ap")


def fig_lakes() -> None:
    fig, ax = plt.subplots(figsize=(4.6, 2.5))
    dots(ax, V3["lakes"]["rows"], V3["lakes"]["counts"]["base_rate"], "Three Nepal lakes (44 positive patches)")
    fig.tight_layout()
    save(fig, "fig_lakes_ap")


def fig_placebo() -> None:
    methods = ["ndvi", "ndwi", "mndwi", "ndbi", "indices5", "raw6", "prithvi", "ssl4eo_rgb"]
    names = {"ndvi": "NDVI", "ndwi": "NDWI", "mndwi": "MNDWI", "ndbi": "NDBI", "indices5": "5 indices", "raw6": "6 bands",
             "prithvi": "Prithvi", "ssl4eo_rgb": "SSL4EO"}
    values: dict[str, list[float]] = {m: [] for m in methods}
    for f in sorted((config.DATA_DIR / "experiments" / "v3_fm").glob("*/noise_check.json")):
        d = json.loads(f.read_text())
        for m in methods:
            v = d["methods"].get(m, {}).get("placebo_false_alarm", {}).get("3.0")
            if v is not None:
                values[m].append(100 * v)
    fig, ax = plt.subplots(figsize=(5.0, 2.5))
    for i, m in enumerate(methods):
        kind = "model" if m in ("prithvi", "ssl4eo_rgb") else "bands" if m == "raw6" else "index"
        v = values[m]
        ax.plot([i] * len(v), v, "o", color=KIND_COLOUR[kind], alpha=0.55, ms=5)
        ax.plot([i - 0.28, i + 0.28], [np.median(v)] * 2, color=INK, lw=1.4)
    ax.set_xticks(range(len(methods)), [names[m] for m in methods], rotation=30, ha="right")
    ax.set_ylabel("false alarms at z > 3 (%)")
    ax.set_title("Placebo test, twelve areas (each dot one area; bar is the median)", loc="left", fontsize=9, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig_placebo")


def fig_coverage() -> None:
    e = CV["conformal"]["alpha_0.1"]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.4), gridspec_kw={"width_ratios": [1, 1.4]})
    folds = [e["per_fold"][str(k)]["coverage"] * 100 for k in range(5)]
    axes[0].bar(range(1, 6), folds, color=GREY, width=0.6)
    axes[0].axhline(90, color=INK, ls="--", lw=1)
    axes[0].set_xlabel("fold of six held-out lakes")
    axes[0].set_ylabel("coverage (%)")
    axes[0].set_ylim(0, 105)
    axes[0].set_title("By fold", loc="left", fontsize=9.5, fontweight="bold")
    lakes = sorted(e["per_lake"].values())
    axes[1].bar(range(len(lakes)), [v * 100 for v in lakes], color=[BLUE if v >= 0.8 else "#b3261e" for v in lakes], width=0.8)
    axes[1].axhline(90, color=INK, ls="--", lw=1)
    axes[1].set_xlabel("lakes, sorted")
    axes[1].set_ylim(0, 105)
    axes[1].set_title("By lake (red: more than 10 points short)", loc="left", fontsize=9.5, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig_coverage")


def fig_qualitative() -> None:
    pub = ROOT / "frontend" / "public"

    def comp(name: str, overlays: list[str], size: int = 700) -> Image.Image:
        base = Image.open(pub / "figures" / name).convert("RGBA")
        for o in overlays:
            base.alpha_composite(Image.open(pub / "figures" / o))
        w, h = base.size
        side = min(w, h)
        base = base.crop(((w - side) // 2, int(h * 0.30), (w + side) // 2, int(h * 0.30) + int(side * 0.55)))
        return base.convert("RGB").resize((size, int(size * base.height / base.width)))

    a = comp("imja_2018.jpg", ["imja_outline_2018.png"])
    b = comp("imja_2024.jpg", ["imja_outline_2018.png", "imja_outline_2024.png"])
    panels = [Image.open(pub / "figures" / n).convert("RGB").resize((470, 470)) for n in ("radar_input.jpg", "radar_model.jpg", "radar_optical.jpg")]
    fig = plt.figure(figsize=(7.0, 4.2))
    gs = fig.add_gridspec(2, 6, height_ratios=[0.85, 1])
    top = [fig.add_subplot(gs[0, 0:3]), fig.add_subplot(gs[0, 3:6])]
    bottom = [fig.add_subplot(gs[1, i:i + 2]) for i in (0, 2, 4)]
    for ax in top + bottom:
        ax.axis("off")
    top[0].imshow(a); top[0].set_title("(a) Oct 2018, with the 2018 shore", loc="left", fontsize=9)
    top[1].imshow(b); top[1].set_title("(b) Oct 2024: shore and lake gained", loc="left", fontsize=9)
    for ax, im, t in zip(bottom, panels, ["(c) Sentinel-1 VV", "(d) U-Net lake (held out)", "(e) optical reference"]):
        ax.imshow(im); ax.set_title(t, loc="left", fontsize=9)
    fig.tight_layout()
    save(fig, "fig_imja")


def main() -> None:
    fig_forest(); fig_lakes(); fig_placebo(); fig_coverage(); fig_qualitative()


if __name__ == "__main__":
    main()
