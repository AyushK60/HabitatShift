"""Training data for the radar water model: crops around each lake, plus the lake/time splits."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

CROP = 256
MIN_CONTRAST_DB = -3.0       # pairs whose optical water is not at least this much darker in radar are dropped
MIN_WATER_PIXELS = 20
CHANNELS = ("vv", "vh", "slope", "radar_present")
FILL_DB = -25.0


def crop_window(seed: np.ndarray, size: int = CROP) -> tuple[int, int]:
    """Top-left corner of a ``size`` window centred on the lake seed, clamped inside the tile."""
    rows, cols = np.nonzero(seed)
    if rows.size == 0:
        raise ValueError("empty seed")
    r0 = int(np.clip(round(rows.mean()) - size // 2, 0, max(seed.shape[0] - size, 0)))
    c0 = int(np.clip(round(cols.mean()) - size // 2, 0, max(seed.shape[1] - size, 0)))
    return r0, c0


def make_input(vv_db: np.ndarray, vh_db: np.ndarray, slope: np.ndarray) -> np.ndarray:
    """Stack the four network channels, scaled to roughly unit range. Missing radar becomes fill + flag 0."""
    present = np.isfinite(vv_db) & np.isfinite(vh_db)
    vv = np.where(present, vv_db, FILL_DB)
    vh = np.where(present, vh_db, FILL_DB)
    return np.stack([(vv + 15.0) / 8.0, (vh + 22.0) / 8.0, np.clip(slope, 0, 60) / 30.0,
                     present.astype("float32")]).astype("float32")


def keep_pair(record: dict) -> bool:
    c = record.get("radar_contrast_db")
    return (record.get("status") == "ok" and c is not None and c <= MIN_CONTRAST_DB
            and record.get("water_pixels", 0) >= MIN_WATER_PIXELS)


def assign_split(lake_ids: list[str], n_test: int = 6, n_cal: int = 4, salt: str = "habitatshift-v3") -> dict[str, str]:
    """Whole lakes go to train / calibration / test, ordered by a hash so the choice does not depend on me."""
    ranked = sorted(lake_ids, key=lambda i: hashlib.sha256(f"{salt}:{i}".encode()).hexdigest())
    out = {}
    for k, lake in enumerate(ranked):
        out[lake] = "test" if k < n_test else "cal" if k < n_test + n_cal else "train"
    return out


def load_lake_pairs(train_dir: Path, static_dir: Path, lake: str, filtered: bool = True) -> dict | None:
    """All pairs of one lake as arrays: x (N,4,H,W), y (N,H,W) bool, ok (N,H,W) bool, plus per-pair metadata."""
    log = train_dir / lake / "pairs.jsonl"
    if not log.exists():
        return None
    seen, records = set(), []
    for line in log.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("status") == "ok" and r["pair"] not in seen:
            seen.add(r["pair"])
            if not filtered or keep_pair(r):
                records.append(r)
    if not records:
        return None
    static = np.load(static_dir / lake / "static.npz")
    r0, c0 = crop_window(static["seed"])
    window = (slice(r0, r0 + CROP), slice(c0, c0 + CROP))
    slope = static["slope"][window]
    xs, ys, oks, meta = [], [], [], []
    for r in records:
        z = np.load(train_dir / lake / "pairs" / f"{r['pair']}.npz")
        vv, vh = z["vv_db"][window].astype("float32"), z["vh_db"][window].astype("float32")
        if vv.shape != (CROP, CROP):
            continue
        xs.append(make_input(vv, vh, slope))
        ys.append(z["water"][window])
        oks.append(z["valid"][window] & np.isfinite(vv))
        meta.append({"lake": lake, "year": int(r["s2_date"][:4]), "pair": r["pair"], "contrast": r["radar_contrast_db"]})
    return {"x": np.stack(xs), "y": np.stack(ys), "ok": np.stack(oks), "meta": meta}
