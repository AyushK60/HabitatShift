"""Preview rendering: stretch, NDVI ramp, mask colour, AOI outline, legend."""

from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image

from backend.app.preprocess import preview


def _bands(value: float = 0.2) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    shape = (6, 6)
    return (
        np.full(shape, value, dtype=np.float32),
        np.full(shape, value, dtype=np.float32),
        np.full(shape, value, dtype=np.float32),
    )


def test_stretch_bounds_uses_percentiles():
    red, green, blue = _bands()
    red[0, 0] = 10.0
    stretch = preview.stretch_bounds((red, green, blue))
    assert stretch.high[0] >= stretch.low[0]
    assert stretch.to_dict()["method"].startswith("per-band")


def test_stretch_handles_all_nan_band():
    red, green, blue = _bands()
    red[:] = np.nan
    stretch = preview.stretch_bounds((red, green, blue))
    assert stretch.low[0] == 0.0
    assert stretch.high[0] > 0.0


def test_masked_pixels_use_invalid_colour():
    red, green, blue = _bands(0.5)
    valid = np.ones((6, 6), dtype=bool)
    valid[2, 3] = False
    image = preview.rgb_to_png(red, green, blue, valid, preview.stretch_bounds((red, green, blue)))
    assert image.getpixel((3, 2)) == preview.INVALID_RGB


def test_rgb_output_is_rgb_and_masked_elsewhere():
    red, green, blue = _bands(0.5)
    valid = np.zeros((6, 6), dtype=bool)
    image = preview.rgb_to_png(red, green, blue, valid, preview.stretch_bounds((red, green, blue)))
    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == preview.INVALID_RGB


def test_ndvi_ramp_is_monotonic_in_greenness():
    low = preview._ramp_colour(-0.9)
    mid = preview._ramp_colour(0.1)
    high = preview._ramp_colour(0.9)

    def green_fraction(rgb):
        return rgb[1] / sum(rgb)

    # Vegetation reads greener (higher share of green light) as NDVI rises,
    # even though the ramp intentionally gets darker rather than brighter.
    assert green_fraction(low) < green_fraction(mid) < green_fraction(high)
    assert high[1] > high[0] and high[1] > high[2]


def test_ndvi_png_keeps_masked_pixels_neutral():
    values = np.full((4, 4), 0.5, dtype=np.float32)
    valid = np.ones((4, 4), dtype=bool)
    valid[1, 1] = False
    image = preview.ndvi_to_png(values, valid)
    assert image.getpixel((1, 1)) == preview.INVALID_RGB
    assert image.getpixel((0, 0)) != preview.INVALID_RGB


def test_ndvi_png_distinguishes_high_and_low_values():
    values = np.array([[-0.8, 0.8]], dtype=np.float32)
    image = preview.ndvi_to_png(values, np.ones((1, 2), dtype=bool))
    assert image.getpixel((0, 0)) != image.getpixel((1, 0))


def test_coverage_png_marks_valid_and_comparable():
    valid = np.array([[True, True]], dtype=bool)
    comparable = np.array([[True, False]], dtype=bool)
    image = preview.coverage_to_png(valid, comparable)
    assert image.getpixel((0, 0)) == (214, 138, 93)
    assert image.getpixel((1, 0)) == (127, 171, 167)


def test_draw_aoi_adds_border_pixels():
    mask = np.zeros((5, 5), dtype=bool)
    mask[1:4, 1:4] = True
    image = preview.draw_aoi(Image.new("RGB", (5, 5), (0, 0, 0)), mask)
    assert image.getpixel((1, 2)) == (214, 138, 93)


def test_legend_written_with_breaks(tmp_path):
    path = preview.ndvi_legend(tmp_path / "legend.png")
    assert path.exists()
    assert Image.open(path).size[0] > 100
    payload = json.loads(path.with_suffix(".json").read_text("utf-8"))
    assert payload["range"] == [-1.0, 1.0]


def test_save_creates_parent_dirs(tmp_path):
    image = Image.new("RGB", (2, 2))
    out = preview.save(image, tmp_path / "nested" / "a.png")
    assert out.exists()
