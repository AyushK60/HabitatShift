"""Rendering of PNG previews from real reflectance and index arrays.

Colours are fixed and documented: the visible-light stretch is a per-band 2-98
percentile linear stretch (the standard "reasonable visual" mapping for
Sentinel-2 true colour), each spectral index uses its own fixed diverging ramp
declared in :mod:`backend.app.indices.spectral`, and masked pixels are drawn in
the neutral invalid colour rather than being interpolated.

Every preview in M1 is generated from the same array that is written to the
GeoTIFF, and each fixed ramp ships a matching legend so a colour can always be
mapped back to a number.  Masked pixels never take a ramp colour.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ..indices.spectral import INDEX_SPECS, Colour, IndexSpec

#: Neutral invalid-pixel colour (never green, so masks cannot be mistaken for
#: vegetation).
INVALID_RGB = (24, 39, 45)

#: Fixed NDVI ramp, sampled at -1.0 .. 1.0 in 9 stops.  Semantically ordered
#: (water/bare -> dry vegetation -> dense canopy), not brand-coloured.  Kept as
#: a module constant for backwards compatibility with the M0 API; the registry
#: copy is authoritative.
NDVI_RAMP: tuple[tuple[float, tuple[int, int, int]], ...] = INDEX_SPECS["ndvi"].ramp

NDVI_BREAKS = INDEX_SPECS["ndvi"].breaks

#: Symmetric difference-map ramp: loss of index -> teal/blue, gain -> copper.
#: Saturated at +/- this many index units, declared in the legend.
CHANGE_SCALE = 0.30
CHANGE_RAMP: tuple[tuple[float, Colour], ...] = (
    (-1.00, (25, 64, 82)),
    (-0.60, (52, 112, 126)),
    (-0.25, (127, 171, 167)),
    (0.00, (232, 229, 216)),
    (0.25, (214, 138, 93)),
    (0.60, (178, 104, 76)),
    (1.00, (120, 56, 48)),
)

#: Discrete observation-count ramp (1 -> 4 observations).
OBSERVATION_RAMP: tuple[tuple[float, Colour], ...] = (
    (0.0, (24, 39, 45)),
    (1.0, (214, 196, 168)),
    (2.0, (196, 158, 112)),
    (3.0, (176, 120, 82)),
    (4.0, (120, 72, 56)),
)


@dataclass(frozen=True)
class Stretch:
    """Percentile stretch bounds actually applied, for the legend/manifest."""

    low: tuple[float, float, float]
    high: tuple[float, float, float]
    gamma: float

    def to_dict(self) -> dict[str, object]:
        return {
            "low": list(self.low),
            "high": list(self.high),
            "gamma": self.gamma,
            "method": "per-band 2-98 percentile linear stretch on valid pixels",
        }


def stretch_bounds(
    bands: tuple[np.ndarray, ...], *, low_pct: float = 2.0, high_pct: float = 98.0
) -> Stretch:
    lows, highs = [], []
    for band in bands:
        finite = band[np.isfinite(band)]
        if finite.size == 0:
            lows.append(0.0)
            highs.append(0.15)
            continue
        lows.append(float(np.percentile(finite, low_pct)))
        highs.append(float(np.percentile(finite, high_pct)))
    return Stretch(low=tuple(lows), high=tuple(highs), gamma=1.0)


def rgb_to_png(
    red: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    valid: np.ndarray,
    stretch: Stretch,
    *,
    gamma: float = 1.0,
) -> Image.Image:
    """Compose a true-colour image with masked and stretched pixels."""
    channels = []
    for band, low, high in zip((red, green, blue), stretch.low, stretch.high):
        span = max(high - low, 1e-9)
        scaled = np.clip((band - low) / span, 0.0, 1.0)
        if gamma != 1.0:
            scaled = np.power(scaled, 1.0 / gamma)
        scaled = np.where(valid & np.isfinite(band), scaled, 0.0)
        channels.append((scaled * 255.0).astype(np.uint8))
    stack = np.dstack(channels)
    stack[~valid] = np.array(INVALID_RGB, dtype=np.uint8)
    return Image.fromarray(stack, mode="RGB")


def false_colour_png(
    nir: np.ndarray,
    red: np.ndarray,
    green: np.ndarray,
    valid: np.ndarray,
    stretch: Stretch,
    *,
    gamma: float = 1.0,
) -> Image.Image:
    """NIR/Red/Green composite; vegetation reads red, water dark."""
    return rgb_to_png(nir, red, green, valid, stretch, gamma=gamma)


def _ramp_colour(
    value: float, ramp: tuple[tuple[float, Colour], ...] = NDVI_RAMP
) -> tuple[int, int, int]:
    if value <= ramp[0][0]:
        return ramp[0][1]
    if value >= ramp[-1][0]:
        return ramp[-1][1]
    for (left_v, left_c), (right_v, right_c) in zip(ramp, ramp[1:]):
        if left_v <= value <= right_v:
            span = right_v - left_v or 1e-9
            fraction = (value - left_v) / span
            return tuple(
                int(round(left_channel + (right_channel - left_channel) * fraction))
                for left_channel, right_channel in zip(left_c, right_c)
            )  # type: ignore[return-value]
    return ramp[-1][1]


def _apply_ramp(
    values: np.ndarray,
    usable: np.ndarray,
    ramp: tuple[tuple[float, Colour], ...],
    *,
    low: float,
    high: float,
) -> np.ndarray:
    """Vectorised ramp renderer; invalid pixels take :data:`INVALID_RGB`."""
    height, width = values.shape
    rgb = np.empty((height, width, 3), dtype=np.uint8)
    rgb[:, :] = np.array(INVALID_RGB, dtype=np.uint8)
    if not usable.any():
        return rgb
    clipped = np.clip(values, low, high)
    span = high - low or 1e-9
    fraction = (clipped - low) / span
    for (left_v, left_c), (right_v, right_c) in zip(ramp, ramp[1:]):
        left_f = (left_v - low) / span
        right_f = (right_v - low) / span
        band = usable & (fraction >= left_f) & (fraction <= right_f)
        if not band.any():
            continue
        local = (fraction[band] - left_f) / max(right_f - left_f, 1e-9)
        for channel in range(3):
            rgb[..., channel][band] = np.round(
                left_c[channel] + (right_c[channel] - left_c[channel]) * local
            ).astype(np.uint8)
    return rgb


def index_to_png(
    values: np.ndarray, valid: np.ndarray, spec: IndexSpec | str = "ndvi"
) -> Image.Image:
    """Colourise one registered index with its fixed ramp."""
    if isinstance(spec, str):
        spec = INDEX_SPECS[spec]
    usable = valid & np.isfinite(values)
    rgb = _apply_ramp(
        np.nan_to_num(values, nan=spec.value_range[0]),
        usable,
        spec.ramp,
        low=spec.value_range[0],
        high=spec.value_range[1],
    )
    return Image.fromarray(rgb, mode="RGB")


def ndvi_to_png(ndvi: np.ndarray, valid: np.ndarray) -> Image.Image:
    """Colourise NDVI with the fixed ramp; masked pixels stay neutral."""
    return index_to_png(ndvi, valid, "ndvi")


def change_to_png(
    delta: np.ndarray, common: np.ndarray, *, scale: float = CHANGE_SCALE
) -> Image.Image:
    """Diverging difference map: later - earlier, saturated at +/- ``scale``."""
    usable = common & np.isfinite(delta)
    normalised = np.zeros_like(delta, dtype=np.float32)
    normalised[usable] = np.clip(delta[usable] / scale, -1.0, 1.0)
    rgb = _apply_ramp(normalised, usable, CHANGE_RAMP, low=-1.0, high=1.0)
    return Image.fromarray(rgb, mode="RGB")


def observation_count_to_png(
    counts: np.ndarray, valid: np.ndarray, *, maximum: int | None = None
) -> Image.Image:
    """Discrete map of how many observations contributed to each pixel."""
    high = float(max(1, int(maximum if maximum is not None else counts.max())))
    ramp = OBSERVATION_RAMP
    rgb = _apply_ramp(
        counts.astype(np.float32), valid, ramp, low=0.0, high=max(high, 1.0)
    )
    return Image.fromarray(rgb, mode="RGB")


def coverage_to_png(
    valid: np.ndarray, comparable: np.ndarray | None = None
) -> Image.Image:
    """Two-tone validity map: kept observations vs excluded pixels."""
    height, width = valid.shape
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[:, :] = np.array(INVALID_RGB, dtype=np.uint8)
    rgb[valid] = np.array((127, 171, 167), dtype=np.uint8)
    if comparable is not None:
        rgb[valid & comparable] = np.array((214, 138, 93), dtype=np.uint8)
    return Image.fromarray(rgb, mode="RGB")


def draw_aoi(image: Image.Image, window_mask: np.ndarray) -> Image.Image:
    """Outline the AOI boundary directly from the rasterised geometry."""
    canvas = image.convert("RGB")
    border = np.zeros(window_mask.shape, dtype=bool)
    border[:, 1:] |= window_mask[:, 1:] & ~window_mask[:, :-1]
    border[1:, :] |= window_mask[1:, :] & ~window_mask[:-1, :]
    array = np.array(canvas)
    array[border] = np.array((214, 138, 93), dtype=np.uint8)
    return Image.fromarray(array, mode="RGB")


def _legend(
    path: Path,
    *,
    ramp: tuple[tuple[float, Colour], ...],
    value_range: tuple[float, float],
    breaks: tuple[float, ...],
    payload: dict[str, object],
) -> Path:
    width, height = 320, 44
    image = Image.new("RGB", (width, height), (242, 240, 235))
    draw = ImageDraw.Draw(image)
    low, high = value_range
    for x in range(width):
        value = high - (high - low) * x / (width - 1)
        draw.line([(x, 4), (x, 24)], fill=_ramp_colour(value, ramp))
    for break_value in breaks:
        if not low <= break_value <= high:
            continue
        x = int(round((high - break_value) / (high - low) * (width - 1)))
        draw.line([(x, 24), (x, 28)], fill=(24, 39, 45))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    path.with_suffix(".json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return path


def index_legend(path: Path, spec: IndexSpec | str) -> Path:
    """Write one index's fixed colour legend as PNG plus JSON breaks."""
    if isinstance(spec, str):
        spec = INDEX_SPECS[spec]
    return _legend(
        path,
        ramp=spec.ramp,
        value_range=spec.value_range,
        breaks=spec.breaks,
        payload={
            "index": spec.key,
            "label": spec.label,
            "formula": spec.formula,
            "breaks": list(spec.breaks),
            "range": list(spec.value_range),
            "left_low": True,
        },
    )


def ndvi_legend(path: Path) -> Path:
    """Write the NDVI colour legend as its own PNG plus JSON breaks."""
    return index_legend(path, "ndvi")


def change_legend(path: Path, *, scale: float = CHANGE_SCALE) -> Path:
    """Write the symmetric difference-map legend, stating its saturation."""
    breaks = (-0.5 * scale, 0.0, 0.5 * scale)
    return _legend(
        path,
        ramp=CHANGE_RAMP,
        value_range=(-scale, scale),
        breaks=breaks,
        payload={
            "kind": "difference_map",
            "label": "later period minus earlier period (index units)",
            "breaks": list(breaks),
            "range": [-scale, scale],
            "saturated_at": scale,
            "left_low": True,
            "note": (
                "blue/teal = lower later index; ivory = unchanged; "
                "copper = higher later index; charcoal = masked or not common-valid"
            ),
        },
    )


def observation_count_legend(path: Path) -> Path:
    """Write a legend for the observation-count mask."""
    return _legend(
        path,
        ramp=OBSERVATION_RAMP,
        value_range=(0.0, 4.0),
        breaks=(1.0, 2.0, 3.0),
        payload={
            "kind": "observation_count",
            "label": "valid observations contributing per pixel",
            "range": [0, 4],
            "breaks": [1, 2, 3],
            "note": "charcoal = 0 valid observations",
        },
    )


def save(image: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    return path
