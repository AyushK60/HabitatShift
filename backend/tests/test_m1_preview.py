"""M1 preview and legend rendering tests (synthetic arrays only)."""

from __future__ import annotations

import json

import numpy as np

from backend.app.preprocess import preview


def test_index_preview_colours_valid_and_marks_invalid_neutral():
    values = np.array([[-0.8, 0.0, 0.8]], dtype=np.float32)
    valid = np.array([[True, True, False]])
    image = preview.index_to_png(values, valid, "ndvi")
    assert image.mode == "RGB"
    assert image.getpixel((2, 0)) == preview.INVALID_RGB
    assert image.getpixel((0, 0)) != preview.INVALID_RGB
    assert image.getpixel((1, 0)) != preview.INVALID_RGB


def test_nan_index_pixels_are_invalid_colour():
    values = np.array([[np.nan]], dtype=np.float32)
    image = preview.index_to_png(values, np.ones((1, 1), dtype=bool), "mndwi")
    assert image.getpixel((0, 0)) == preview.INVALID_RGB


def test_change_preview_sign_colours_differ():
    delta = np.array([[-0.3, 0.0, 0.3]], dtype=np.float32)
    common = np.ones((1, 3), dtype=bool)
    image = preview.change_to_png(delta, common)
    decrease = image.getpixel((0, 0))
    stable = image.getpixel((1, 0))
    increase = image.getpixel((2, 0))
    assert decrease != stable != increase
    assert increase[0] > increase[2], "positive delta should read copper/red"
    assert decrease[2] > decrease[0], "negative delta should read teal/blue"


def test_change_preview_saturates_at_scale():
    delta = np.array([[0.3, 1.0]], dtype=np.float32)
    image = preview.change_to_png(delta, np.ones((1, 2), dtype=bool), scale=0.3)
    assert image.getpixel((0, 0)) == image.getpixel((1, 0))


def test_change_preview_masked_pixel_is_neutral():
    delta = np.array([[0.5]], dtype=np.float32)
    image = preview.change_to_png(delta, np.zeros((1, 1), dtype=bool))
    assert image.getpixel((0, 0)) == preview.INVALID_RGB


def test_observation_count_preview_is_discrete_and_ordered():
    counts = np.array([[0, 1, 2, 3]], dtype=np.int16)
    valid = np.array([[False, True, True, True]])
    image = preview.observation_count_to_png(counts, valid, maximum=3)
    zero = image.getpixel((0, 0))
    one = image.getpixel((1, 0))
    three = image.getpixel((3, 0))
    assert zero == preview.INVALID_RGB
    assert one != three


def test_false_colour_is_rgb():
    band = np.linspace(0.0, 1.0, 36, dtype=np.float32).reshape(6, 6)
    stretch = preview.stretch_bounds((band, band, band))
    image = preview.false_colour_png(band, band, band, np.ones((6, 6), bool), stretch)
    assert image.mode == "RGB"
    assert image.size == (6, 6)


def test_index_legend_writes_formula_and_breaks(tmp_path):
    path = preview.index_legend(tmp_path / "ndvi_legend.png", "ndvi")
    payload = json.loads(path.with_suffix(".json").read_text("utf-8"))
    assert payload["index"] == "ndvi"
    assert payload["formula"] == "(NIR - Red) / (NIR + Red)"
    assert payload["breaks"] == list(preview.INDEX_SPECS["ndvi"].breaks)
    assert path.exists()


def test_change_legend_states_saturation(tmp_path):
    path = preview.change_legend(tmp_path / "change_legend.png", scale=0.3)
    payload = json.loads(path.with_suffix(".json").read_text("utf-8"))
    assert payload["saturated_at"] == 0.3
    assert payload["range"] == [-0.3, 0.3]
    assert "masked" in payload["note"]


def test_observation_count_legend(tmp_path):
    path = preview.observation_count_legend(tmp_path / "count_legend.png")
    payload = json.loads(path.with_suffix(".json").read_text("utf-8"))
    assert payload["kind"] == "observation_count"
    assert payload["range"] == [0, 4]
