"""Rendering of PNG previews from real reflectance and index arrays.

Colours are fixed and documented: the visible-light stretch is a per-band 2-98
percentile linear stretch (the standard "reasonable visual" mapping for
Sentinel-2 true colour), NDVI uses a fixed diverging ramp so values are
comparable between both dates, and masked pixels are drawn in the neutral
invalid colour rather than being interpolated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

#: Neutral invalid-pixel colour (never green, so masks cannot be mistaken for
#: vegetation).
INVALID_RGB = (24, 39, 45)

#: Fixed NDVI ramp, sampled at -1.0 .. 1.0 in 9 stops.  Semantically ordered
#: (water/bare -> dry vegetation -> dense canopy), not brand-coloured.
NDVI_RAMP: tuple[tuple[float, tuple[int, int, int]], ...] = (
    (-1.00, (36, 66, 82)),
    (-0.40, (86, 112, 106)),
    (-0.15, (168, 158, 124)),
    (-0.02, (196, 178, 132)),
    (0.10, (176, 186, 138)),
    (0.25, (140, 168, 122)),
    (0.45, (86, 138, 96)),
    (0.65, (44, 108, 78)),
    (1.00, (18, 74, 56)),
)

NDVI_BREAKS = (-0.6, -0.35, -0.12, 0.02, 0.16, 0.30, 0.50)


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


def _ramp_colour(value: float) -> tuple[int, int, int]:
    if value <= NDVI_RAMP[0][0]:
        return NDVI_RAMP[0][1]
    if value >= NDVI_RAMP[-1][0]:
        return NDVI_RAMP[-1][1]
    for (left_v, left_c), (right_v, right_c) in zip(NDVI_RAMP, NDVI_RAMP[1:]):
        if left_v <= value <= right_v:
            span = right_v - left_v or 1e-9
            fraction = (value - left_v) / span
            return tuple(
                int(round(l + (r - l) * fraction)) for l, r in zip(left_c, right_c)
            )  # type: ignore[return-value]
    return NDVI_RAMP[-1][1]


def ndvi_to_png(ndvi: np.ndarray, valid: np.ndarray) -> Image.Image:
    """Colourise NDVI with the fixed ramp; masked pixels stay neutral."""
    height, width = ndvi.shape
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[:, :] = np.array(INVALID_RGB, dtype=np.uint8)
    usable = valid & np.isfinite(ndvi)
    clipped = np.clip(ndvi, -1.0, 1.0)
    for stop, colour in NDVI_RAMP:
        touches = usable & (np.abs(clipped - stop) < 0.005)
        rgb[touches] = np.array(colour, dtype=np.uint8)
    # Fill the gradient between ramp stops in one vectorised pass.
    ordered = np.sort(np.clip(clipped, -1.0, 1.0))
    del ordered
    for (left_v, left_c), (right_v, right_c) in zip(NDVI_RAMP, NDVI_RAMP[1:]):
        band = usable & (clipped > left_v) & (clipped < right_v)
        if not band.any():
            continue
        fraction = (clipped[band] - left_v) / (right_v - left_v)
        for channel in range(3):
            rgb[..., channel][band] = np.round(
                left_c[channel] + (right_c[channel] - left_c[channel]) * fraction
            ).astype(np.uint8)
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


def ndvi_legend(path: Path) -> Path:
    """Write the NDVI colour legend as its own PNG plus JSON breaks."""
    width, height = 320, 44
    image = Image.new("RGB", (width, height), (242, 240, 235))
    draw = ImageDraw.Draw(image)
    for x in range(width):
        value = 1.0 - 2.0 * x / (width - 1)
        draw.line([(x, 4), (x, 24)], fill=_ramp_colour(value))
    for break_value in NDVI_BREAKS:
        x = int(round((1.0 - break_value) / 2.0 * (width - 1)))
        draw.line([(x, 24), (x, 28)], fill=(24, 39, 45))
    image.save(path)
    path.with_suffix(".json").write_text(
        json.dumps(
            {"breaks": list(NDVI_BREAKS), "range": [-1.0, 1.0], "left_low": True},
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def save(image: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    return path
