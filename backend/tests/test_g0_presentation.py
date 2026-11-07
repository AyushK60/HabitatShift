"""M2-G0 presentation repair tests.

These tests exercise the presentation derivatives independently of the browser:
the neutral previews must be generated from the exported M1 masks, must agree
with the frozen summary counts, must not use copper, and must refuse to
overwrite existing assets silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from scripts.build_g0_presentation import (
    BOUNDARY_RGB,
    INVALID_RGB,
    VALID_RGB,
    build_presentation,
)

STUDY = "coringa_coastal"


def test_g0_presentation_matches_frozen_counts(tmp_path):
    result = build_presentation(STUDY, out_dir=tmp_path / "g0", force=True)
    coverage = result["coverage"]

    assert coverage["aoi_pixels"] == 165136
    assert coverage["earlier_valid_pixels"] == 165136
    assert coverage["later_valid_pixels"] == 165136
    assert coverage["common_valid_pixels"] == 165136
    assert coverage["masked_pixels"] == 2174
    assert coverage["common_valid_fraction_of_aoi"] == 1.0
    assert coverage["uniform_common"] is True

    assert result["observation_counts"]["earlier"] == {
        "0": 2174,
        "1": 44,
        "2": 33723,
        "3": 131369,
    }
    assert result["observation_counts"]["later"] == {
        "0": 2174,
        "1": 166,
        "2": 19754,
        "3": 145216,
    }


def test_g0_neutral_previews_have_expected_geometry_and_colours(tmp_path):
    out = tmp_path / "g0"
    build_presentation(STUDY, out_dir=out, force=True)

    for name in ("earlier_valid.png", "later_valid.png", "common_valid.png"):
        image = Image.open(out / name).convert("RGB")
        assert image.size == (429, 390)
        colours = {colour for _, colour in image.getcolors(maxcolors=1_000_000)}
        assert VALID_RGB in colours
        assert INVALID_RGB in colours
        assert BOUNDARY_RGB in colours
        # Copper belongs to positive index change, never to validity.
        assert (214, 138, 93) not in colours

    masked = Image.open(out / "masked_common.png").convert("RGB")
    assert masked.size == (429, 390)
    masked_colours = {colour for _, colour in masked.getcolors(maxcolors=1_000_000)}
    assert INVALID_RGB in masked_colours


def test_g0_invalid_overlay_is_transparent_inside_valid_area(tmp_path):
    out = tmp_path / "g0"
    build_presentation(STUDY, out_dir=out, force=True)
    overlay = np.asarray(Image.open(out / "common_invalid.png").convert("RGBA"))
    assert overlay.shape == (390, 429, 4)
    # 165,136 valid pixels must be fully transparent.
    assert int(np.count_nonzero(overlay[:, :, 3] == 0)) >= 165136
    # Masked pixels must carry a visible neutral hatch.
    assert int(np.count_nonzero(overlay[:, :, 3] > 0)) == 2174


def test_g0_builder_refuses_silent_overwrite(tmp_path):
    out = tmp_path / "g0"
    build_presentation(STUDY, out_dir=out, force=True)
    with pytest.raises(FileExistsError):
        build_presentation(STUDY, out_dir=out, force=False)


def test_g0_quality_json_documents_sources_and_hashes(tmp_path):
    out = tmp_path / "g0"
    build_presentation(STUDY, out_dir=out, force=True)
    payload = json.loads((out / "quality.json").read_text("utf-8"))

    assert payload["presentation_version"] == "g0-1.0"
    assert payload["study_id"] == STUDY
    assert payload["grid"]["signature"] == "ad1601d5620e5f23"
    assert payload["coverage"]["uniform_common"] is True
    assert "sources" in payload and "source_sha256" in payload
    assert "artifact_sha256" in payload
    for name, digest in payload["artifact_sha256"].items():
        assert (out / name).exists()
        assert len(digest) == 64


def test_frontend_uses_shared_raster_aspect_and_overlay_stage():
    root = Path(__file__).resolve().parents[2]
    # M3 moved the legacy M0–M2 proof viewer to frontend/legacy; the
    # shared-stage swipe contract still applies to those verified files.
    css = (root / "frontend" / "legacy" / "styles.css").read_text("utf-8")
    js = (root / "frontend" / "legacy" / "app.js").read_text("utf-8")

    assert "aspect-ratio: 1 / 1" not in css
    assert "aspect-ratio: var(--raster-aspect" in css
    assert ".swipe-layer" in css
    assert "clip-path: inset(0 0 0 var(--split" in css
    assert "touch-action: none" in css
    assert "setPointerCapture" in js
    assert 'role", "slider"' in js
    assert "aria-valuenow" in js
    assert "periodOverlay" in js
    assert "common_valid.png" in js
