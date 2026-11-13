"""Render the real-data figures used on the home page into frontend/public/figures/.

Everything is drawn from files the pipeline already produced:
  * Sentinel-2 scenes cached in data/fm/<study>/scenes (true colour, one stretch shared by each before/after pair)
  * radar water frequency maps (data/fm/lake_*/radar_water_*.npy) for the lake outlines and the area that changed
  * Hansen forest-loss rasters for the forest-loss outlines
  * one radar / optical training pair and the held-out cross-validation model for the radar U-Net panel
Run:  python scripts/make_site_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import config  # noqa: E402
from backend.app.segmentation import data as D  # noqa: E402
from backend.app.segmentation.train import predict_tile  # noqa: E402
from backend.app.segmentation.unet import UNet  # noqa: E402

FM = config.DATA_DIR / "fm"
OUT = config.PROJECT_ROOT / "frontend" / "public" / "figures"
BLUE = (70, 140, 255)
WHITE = (255, 255, 255)


def scene(study: str, item: str) -> np.ndarray:
    return np.load(FM / study / "scenes" / f"{item}.npz")["refl"]


def median_scene(study: str, items: list[str]) -> np.ndarray:
    return np.nanmedian(np.stack([scene(study, i) for i in items]), axis=0)


def stretch(pair: list[np.ndarray]) -> tuple[float, float]:
    cat = np.concatenate([p[[2, 1, 0]].reshape(3, -1) for p in pair], axis=1)
    return float(np.nanpercentile(cat, 1)), float(np.nanpercentile(cat, 99.3))


def rgb_image(refl: np.ndarray, lo: float, hi: float, scale: int = 2) -> Image.Image:
    v = np.clip((np.nan_to_num(refl[[2, 1, 0]], nan=lo) - lo) / (hi - lo), 0, 1) ** (1 / 1.25)
    im = Image.fromarray((v.transpose(1, 2, 0) * 255).astype("uint8"))
    return im.resize((im.width * scale, im.height * scale), Image.LANCZOS)


def smooth_up(mask: np.ndarray, scale: int = 2) -> np.ndarray:
    f = ndi.gaussian_filter(mask.astype("float32"), 1.0)
    return ndi.zoom(f, scale, order=1) > 0.5


def outline(mask: np.ndarray, width: int = 2) -> np.ndarray:
    return mask & ~ndi.binary_erosion(mask, iterations=width)


def rgba(layers: list[tuple[np.ndarray, tuple[int, int, int], int]], shape: tuple[int, int]) -> Image.Image:
    arr = np.zeros((*shape, 4), dtype="uint8")
    for mask, colour, alpha in layers:
        arr[mask] = (*colour, alpha)
    return Image.fromarray(arr)


def clean(mask: np.ndarray, min_px: int) -> np.ndarray:
    lab, n = ndi.label(mask)
    if n == 0:
        return mask
    sizes = ndi.sum(mask, lab, range(1, n + 1))
    keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= min_px])
    return keep


def save(img: Image.Image, name: str, **kw) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / name, **kw)
    print("wrote", name, img.size)


def lake_pair(study: str, tag: str, earlier: str, later: list[str]) -> dict:
    a = scene(study, earlier)
    b = median_scene(study, later) if len(later) > 1 else scene(study, later[0])
    lo, hi = stretch([a, b])
    save(rgb_image(a, lo, hi), f"{tag}_2018.jpg", quality=88)
    save(rgb_image(b, lo, hi), f"{tag}_2024.jpg", quality=88)
    ea0 = np.load(FM / study / "radar_water_earlier.npy") >= 0.5
    la0 = np.load(FM / study / "radar_water_later.npy") >= 0.5
    # keep only the lake itself: components of the union that are at least 0.2 km2 (about 2,000 pixels)
    union = clean(ea0 | la0, 2000)
    union = ndi.binary_opening(union, iterations=4)      # drop thin meltwater channels attached to the lake
    lab, n = ndi.label(union)
    h, w = union.shape
    near = [i for i in range(1, n + 1) if abs(ndi.center_of_mass(lab == i)[0] - h / 2) < 0.22 * h and abs(ndi.center_of_mass(lab == i)[1] - w / 2) < 0.22 * w]
    sizes = {i: int((lab == i).sum()) for i in near}
    big = lab == max(sizes, key=sizes.get) if sizes else union
    ea = clean(ea0 & ndi.binary_dilation(big, iterations=2), 25)
    la = clean(la0 & ndi.binary_dilation(big, iterations=2), 25)
    up_e, up_l = smooth_up(ea), smooth_up(la)
    growth = clean(up_l & ~ndi.binary_dilation(up_e, iterations=3), 400)
    loss = clean(up_e & ~ndi.binary_dilation(up_l, iterations=3), 400)
    shape = up_e.shape
    save(rgba([(outline(up_e), WHITE, 235)], shape), f"{tag}_outline_2018.png")
    save(rgba([(growth, BLUE, 165), (outline(up_l), WHITE, 235)], shape), f"{tag}_outline_2024.png")
    cy, cx = ndi.center_of_mass(growth) if growth.any() else (shape[0] / 2, shape[1] / 2)
    return {"area_2018_km2": round(float(ea.sum()) * 1e-4, 2), "area_2024_km2": round(float(la.sum()) * 1e-4, 2),
            "growth_km2": round(float(growth.sum()) / 4 * 1e-4, 2), "loss_km2": round(float(loss.sum()) / 4 * 1e-4, 2),
            "growth_centre": [round(cx / shape[1], 3), round(cy / shape[0], 3)], "size": [shape[1], shape[0]]}


def forest() -> dict:
    study = "bastar_forest"
    meta = json.loads((FM / study / "study.json").read_text())
    e = median_scene(study, [s["item_id"] for s in meta["periods"]["earlier"]["scenes"]])
    l = median_scene(study, [s["item_id"] for s in meta["periods"]["later"]["scenes"]])
    loss_year = np.load(FM / study / "hansen_lossyear.npy")
    tree = np.load(FM / study / "hansen_treecover2000.npy")
    loss = (loss_year >= 22) & (loss_year <= 24) & (tree >= 30)
    density = ndi.uniform_filter(loss.astype("float32"), 260)
    cy, cx = np.unravel_index(int(np.argmax(density)), density.shape)
    half = 200
    y0 = int(np.clip(cy - half, 0, loss.shape[0] - 2 * half)); x0 = int(np.clip(cx - half, 0, loss.shape[1] - 2 * half))
    win = (slice(y0, y0 + 2 * half), slice(x0, x0 + 2 * half))
    lo, hi = stretch([e[:, win[0], win[1]], l[:, win[0], win[1]]])
    save(rgb_image(e[:, win[0], win[1]], lo, hi, 3), "forest_2021.jpg", quality=88)
    save(rgb_image(l[:, win[0], win[1]], lo, hi, 3), "forest_2025.jpg", quality=88)
    m = clean(loss[win], 6)
    up = smooth_up(m, 3)
    save(rgba([(outline(up, 2), WHITE, 240)], up.shape), "forest_loss_outline.png")
    return {"loss_share_pct": round(100 * float(m.mean()), 1), "window_km": 4.0}


def unet_panel() -> dict:
    cv = json.loads((config.DATA_DIR / "experiments" / "v3_unet" / "cv.json").read_text())
    fold = next(int(k) for k, v in cv["folds"].items() if "imja_tsho" in v["lakes"])
    pair = "S2B_45RVL_20221024_0_L2A__S1A_IW_GRDH_1SDV_20221024T121404_20221024T121429_045584_05733B_rtc"
    ckpt = torch.load(config.DATA_DIR / "models" / "lake_unet" / f"unet_fold{fold}.pt", map_location="cpu")
    net = UNet(base=ckpt["base"])
    net.load_state_dict(ckpt["state"])
    net.eval()
    static = np.load(config.DATA_DIR / "lakes" / "imja_tsho" / "static.npz")
    z = np.load(config.DATA_DIR / "lakes_train" / "imja_tsho" / "pairs" / f"{pair}.npz")
    vv, vh = z["vv_db"].astype("float32"), z["vh_db"].astype("float32")
    ok = z["valid"] & np.isfinite(vv)
    prob = predict_tile(net, D.make_input(vv, vh, static["slope"]), "cpu")
    pred = (prob > 0.5) & ok
    truth = z["water"] & ok
    r0, c0 = D.crop_window(static["seed"], 360)
    win = (slice(r0, r0 + 360), slice(c0, c0 + 360))
    g = np.clip((np.nan_to_num(vv[win], nan=-25) + 25) / 22, 0, 1)
    base = np.stack([g, g, g], axis=-1)
    base = (base * 255).astype("uint8")

    def panel(name: str, mask: np.ndarray | None, colour: tuple[int, int, int]) -> None:
        arr = base.copy()
        if mask is not None:
            m = mask[win]
            arr[m] = (0.45 * arr[m] + 0.55 * np.array(colour)).astype("uint8")
            edge = outline(m, 1)
            arr[edge] = colour
        im = Image.fromarray(arr).resize((1080, 1080), Image.NEAREST if mask is not None else Image.LANCZOS)
        save(im, name, quality=90) if name.endswith(".jpg") else save(im, name)

    panel("radar_input.jpg", None, BLUE)
    panel("radar_model.jpg", pred, BLUE)
    panel("radar_optical.jpg", truth, (240, 170, 70))
    inter = (pred & truth)[win].sum()
    union = (pred | truth)[win].sum()
    return {"pair": pair, "date": "2022-10-24", "iou": round(float(inter / union), 2),
            "model_km2": round(float(pred.sum()) * 1e-4, 2), "optical_km2": round(float(truth.sum()) * 1e-4, 2), "fold": fold}


def main() -> None:
    info = {"imja": lake_pair("lake_imja_tsho", "imja", "S2A_45RVL_20181020_1_L2A",
                              ["S2A_45RVL_20241028_0_L2A"])}
    for study, tag in (("lake_tsho_rolpa", "rolpa"), ("lake_thulagi", "thulagi")):
        meta = json.loads((FM / study / "study.json").read_text())
        early = meta["periods"]["earlier"]["scenes"][0]["item_id"]
        late = [s["item_id"] for s in meta["periods"]["later"]["scenes"]][:1]
        info[tag] = lake_pair(study, tag, early, late)
        info[tag]["earlier_date"] = meta["periods"]["earlier"]["scenes"][0]["date"]
        info[tag]["later_date"] = meta["periods"]["later"]["scenes"][0]["date"]
    info["forest"] = forest()
    info["unet"] = unet_panel()
    (OUT / "figures.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
