"""Radar preprocessing and a simple water mask.

All functions are plain numpy so they can be tested without network access.
Input scenes are linear gamma-naught power (the Planetary Computer RTC unit), NaN where there is no data.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

#: Linear power below this is treated as the sensor noise floor before the dB conversion.
FLOOR = 1e-4
#: Plausible bounds for the water/land split in VV dB; outside this the Otsu value is clamped and flagged.
THRESHOLD_BOUNDS_DB = (-24.0, -10.0)


def to_db(power: np.ndarray) -> np.ndarray:
    """Linear power to decibels, keeping NaN."""
    return 10.0 * np.log10(np.maximum(power, FLOOR))


def lee_filter(power: np.ndarray, size: int = 7, looks: float = 5.0) -> np.ndarray:
    """Classic Lee speckle filter on linear power. NaN pixels are ignored and stay NaN.

    ``looks`` is the equivalent number of looks used for the noise variance; the value is a documented
    approximation for GRD-derived RTC data, not a measured one.
    """
    valid = np.isfinite(power)
    filled = np.where(valid, power, 0.0)
    weight = ndimage.uniform_filter(valid.astype("float64"), size, mode="nearest")
    safe = np.maximum(weight, 1e-6)
    mean = ndimage.uniform_filter(filled, size, mode="nearest") / safe
    mean_sq = ndimage.uniform_filter(filled**2, size, mode="nearest") / safe
    variance = np.maximum(mean_sq - mean**2, 0.0)
    noise_cv2 = 1.0 / looks
    local_cv2 = variance / np.maximum(mean**2, 1e-12)
    gain = np.clip((local_cv2 - noise_cv2) / np.maximum(local_cv2 * (1.0 + noise_cv2), 1e-12), 0.0, 1.0)
    out = mean + gain * (filled - mean)
    out[~valid] = np.nan
    return out.astype("float32")


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    """Otsu's threshold for a 1-D array of finite values (maximises between-class variance)."""
    values = values[np.isfinite(values)]
    if values.size < 50:
        raise ValueError("too few valid pixels for a threshold")
    hist, edges = np.histogram(values, bins=bins)
    centres = (edges[:-1] + edges[1:]) / 2
    weight = hist.astype("float64")
    w0 = np.cumsum(weight)
    w1 = w0[-1] - w0
    sum0 = np.cumsum(weight * centres)
    mean0 = sum0 / np.maximum(w0, 1e-12)
    mean1 = (sum0[-1] - sum0) / np.maximum(w1, 1e-12)
    between = w0 * w1 * (mean0 - mean1) ** 2
    return float(centres[int(np.argmax(between))])


def slope_degrees(dem: np.ndarray, res: float) -> np.ndarray:
    """Terrain slope in degrees from an elevation grid with ``res`` metre pixels."""
    filled = np.where(np.isfinite(dem), dem, np.nanmedian(dem))
    dy, dx = np.gradient(filled, res)
    return np.degrees(np.arctan(np.hypot(dx, dy))).astype("float32")


def water_mask(
    vv_power: np.ndarray,
    slope: np.ndarray | None = None,
    *,
    max_slope_deg: float = 8.0,
    mask_slope_deg: float = 25.0,
    lee_size: int = 7,
) -> tuple[np.ndarray, dict]:
    """Water mask from one VV scene.

    Steps: Lee filter, dB, Otsu threshold on gentle terrain (<= ``max_slope_deg``), then water = below the
    threshold on terrain up to ``mask_slope_deg``. Steep slopes are excluded because radar shadow looks like
    water there; the mask limit is looser than the threshold limit because a lake that grew since the DEM
    was made has margins the DEM records as sloping.
    Returns the boolean mask (False where unknown) and a record of what was done.
    """
    filtered_db = to_db(lee_filter(vv_power, size=lee_size))
    eligible = np.isfinite(filtered_db)
    if slope is not None:
        eligible &= slope <= max_slope_deg
    info: dict = {"eligible_pixels": int(eligible.sum()), "total_pixels": int(vv_power.size)}
    if eligible.sum() < 50:
        info["status"] = "no_valid_data"
        return np.zeros(vv_power.shape, dtype=bool), info
    raw = otsu_threshold(filtered_db[eligible])
    low, high = THRESHOLD_BOUNDS_DB
    threshold = float(np.clip(raw, low, high))
    info.update(otsu_db=round(raw, 2), threshold_db=round(threshold, 2), clamped=bool(threshold != raw), status="ok")
    allowed = np.isfinite(filtered_db)
    if slope is not None:
        allowed &= slope <= mask_slope_deg
    return (filtered_db < threshold) & allowed, info
