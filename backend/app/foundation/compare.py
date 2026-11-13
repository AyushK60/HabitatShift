"""Judge change scores from different feature sets by the same scene-to-scene noise.

Every method turns each scene into a feature vector per 16 x 16 pixel patch (160 m):
  * ``raw6``      the six reflectance bands (standardised)
  * ``indices5``  NDVI, NDWI, MNDWI, NDBI, NDSI (standardised)
  * ``ndvi`` ... single indices, the version 2 baseline
  * ``prithvi``   Prithvi-EO-2.0 patch embedding (L2-normalised)

For one patch with n_A scenes in the earlier period and n_B in the later period:
  D^2    = |mean_B - mean_A|^2                       (raw change)
  sigma2 = mean over same-period scene pairs of |f_i - f_j|^2 / 2   (per-scene noise variance)
  z^2    = D^2 / ( sigma2 * (1/n_A + 1/n_B) )        (change in units of its own noise; about 1 if nothing changed)
sigma2 is pooled over a 3 x 3 neighbourhood of patches because 3 scenes give only 3 pairs per period.
This is the version 2 "change vs scene-to-scene noise" idea written for vectors of any length.
"""
from __future__ import annotations

import itertools

import numpy as np
from scipy import ndimage

PATCH = 16
INDEX_FORMULAS = {
    "ndvi": ("nir08", "red"),
    "ndwi": ("green", "nir08"),
    "mndwi": ("green", "swir16"),
    "ndbi": ("swir16", "nir08"),
    "ndsi": ("green", "swir16"),
}
BAND_ORDER = ("blue", "green", "red", "nir08", "swir16", "swir22")
MIN_VALID_FRACTION = 0.8


def _nd(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return (a - b) / (a + b)


def band_index(refl: np.ndarray, name: str) -> np.ndarray:
    return refl[BAND_ORDER.index(name)]


def patch_mean(stack: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mean of (C, H, W) over valid pixels per 16 x 16 patch -> (h, w, C) and valid fraction (h, w)."""
    c, height, width = stack.shape
    ph, pw = (-height) % PATCH, (-width) % PATCH
    padded = np.pad(np.where(valid, stack, np.nan), ((0, 0), (0, ph), (0, pw)), constant_values=np.nan)
    mask = np.pad(valid, ((0, ph), (0, pw)), constant_values=False)
    h, w = padded.shape[1] // PATCH, padded.shape[2] // PATCH
    blocks = padded.reshape(c, h, PATCH, w, PATCH)
    count = np.isfinite(blocks).sum(axis=(2, 4))
    total = blocks.copy()
    total[~np.isfinite(total)] = 0.0
    mean = total.sum(axis=(2, 4)) / np.maximum(count, 1)
    mean[count == 0] = np.nan
    fraction = mask.reshape(h, PATCH, w, PATCH).mean(axis=(1, 3))
    return np.moveaxis(mean, 0, -1), fraction


def scene_features(refl: np.ndarray, valid: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Patch features per method for one scene: {method: (features (h, w, d), valid fraction (h, w))}."""
    out = {}
    out["raw6"] = patch_mean(refl, valid)
    idx = {name: _nd(band_index(refl, a), band_index(refl, b)) for name, (a, b) in INDEX_FORMULAS.items()}
    out["indices5"] = patch_mean(np.stack([idx[k] for k in INDEX_FORMULAS]), valid)
    for name in ("ndvi", "ndwi", "mndwi", "ndbi"):
        out[name] = patch_mean(idx[name][None], valid)
    return out


def standardise(per_scene: list[np.ndarray]) -> list[np.ndarray]:
    """Divide each feature by its standard deviation over all scenes and patches (one fixed scale per study)."""
    stacked = np.concatenate([f.reshape(-1, f.shape[-1]) for f in per_scene])
    scale = np.nanstd(stacked, axis=0)
    scale[~np.isfinite(scale) | (scale == 0)] = 1.0
    return [f / scale for f in per_scene]


def l2_normalise(features: np.ndarray) -> np.ndarray:
    return features / np.maximum(np.linalg.norm(features, axis=-1, keepdims=True), 1e-9)


def _nan_uniform(values: np.ndarray, size: int = 3) -> np.ndarray:
    ok = np.isfinite(values)
    num = ndimage.uniform_filter(np.where(ok, values, 0.0), size, mode="nearest")
    den = ndimage.uniform_filter(ok.astype(float), size, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[den == 0] = np.nan
    return out


def noise_variance(features: list[np.ndarray], ok: list[np.ndarray], groups: list[list[int]]) -> np.ndarray:
    """Per-scene noise variance per patch from same-group scene pairs, pooled over 3 x 3 patches."""
    total = np.zeros(features[0].shape[:2])
    count = np.zeros(features[0].shape[:2])
    for group in groups:
        for i, j in itertools.combinations(group, 2):
            both = ok[i] & ok[j]
            d2 = np.where(both, ((features[i] - features[j]) ** 2).sum(-1), 0.0)
            total += d2 / 2.0
            count += both
    with np.errstate(invalid="ignore", divide="ignore"):
        pair_mean = np.where(count > 0, total / count, np.nan)
    return _nan_uniform(pair_mean)


def change_scores(features: list[np.ndarray], ok: list[np.ndarray], earlier: list[int], later: list[int],
                  sigma2: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """Raw change D and noise-calibrated change z for each patch (NaN where it cannot be computed)."""
    def mean_of(idx: list[int]):
        stack = np.stack([np.where(ok[i][..., None], features[i], np.nan) for i in idx])
        n = np.stack([ok[i] for i in idx]).sum(0)
        with np.errstate(invalid="ignore"):
            return np.nanmean(stack, axis=0), n

    mean_a, n_a = mean_of(earlier)
    mean_b, n_b = mean_of(later)
    d2 = ((mean_b - mean_a) ** 2).sum(-1)
    if sigma2 is None:
        sigma2 = noise_variance(features, ok, [earlier, later])
    with np.errstate(invalid="ignore", divide="ignore"):
        z2 = d2 / (sigma2 * (1.0 / n_a + 1.0 / n_b))
    good = (n_a >= 1) & (n_b >= 1) & np.isfinite(sigma2) & (sigma2 > 0)
    out = {"D": np.where(good, np.sqrt(d2), np.nan), "z": np.where(good, np.sqrt(z2), np.nan)}
    if mean_a.shape[-1] == 1:   # single index: keep the sign (later minus earlier) for directional baselines
        with np.errstate(invalid="ignore", divide="ignore"):
            signed = (mean_b - mean_a)[..., 0] / np.sqrt(sigma2 * (1.0 / n_a + 1.0 / n_b))
        out["z_signed"] = np.where(good, signed, np.nan)
        out["D_signed"] = np.where(good, (mean_b - mean_a)[..., 0], np.nan)
    return out


def placebo_scores(features: list[np.ndarray], ok: list[np.ndarray], earlier: list[int], later: list[int]
                   ) -> list[dict[str, np.ndarray]]:
    """Comparisons where nothing changed: one scene of a period against the rest of the same period.

    The noise variance never includes the held-out scene: it comes from the other period's scene pairs
    when that period has at least 2 scenes, otherwise from the remaining scenes of the same period.
    A period needs at least 3 scenes to be used (one held out, a pair left over).
    """
    out = []
    for held, other in ((earlier, later), (later, earlier)):
        if len(held) < 3:
            continue
        for i in held:
            rest = [j for j in held if j != i]
            sigma2 = noise_variance(features, ok, [other] if len(other) >= 2 else [rest])
            out.append(change_scores(features, ok, [i], rest, sigma2=sigma2))
    return out
