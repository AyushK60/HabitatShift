"""Limits and safety of the bounded custom-area analysis (offline: no engine run, no network)."""
from __future__ import annotations

import datetime as dt

import pytest

from backend.app.pipeline import custom_run as cr

TODAY = dt.date(2026, 11, 12)
BOX = dict(west=85.30, south=27.69, east=85.32, north=27.71)  # ~4 km2


def test_valid_box_passes_validation():
    aoi = cr._validate(**BOX, earlier=dt.date(2020, 3, 31), later=dt.date(2025, 3, 29), today=TODAY)
    assert cr.MIN_AREA_KM2 <= aoi.area_km2() <= cr.MAX_AREA_KM2


@pytest.mark.parametrize(
    "box,message",
    [
        (dict(west=85.0, south=27.0, east=85.5, north=27.5), "above"),       # ~2800 km2
        (dict(west=85.30, south=27.69, east=85.3005, north=27.6905), "below"),  # tiny
        (dict(west=85.32, south=27.69, east=85.30, north=27.71), "west<east"),  # inverted
    ],
)
def test_area_and_geometry_limits(box, message):
    with pytest.raises(cr.CustomRunError, match=message):
        cr._validate(**box, earlier=dt.date(2020, 3, 31), later=dt.date(2025, 3, 29), today=TODAY)


@pytest.mark.parametrize(
    "earlier,later",
    [
        (dt.date(2014, 1, 1), dt.date(2020, 1, 1)),    # before Sentinel-2
        (dt.date(2020, 1, 1), dt.date(2020, 2, 1)),    # too close together
        (dt.date(2020, 1, 1), dt.date(2026, 11, 10)),  # too recent
    ],
)
def test_date_limits(earlier, later):
    with pytest.raises(cr.CustomRunError):
        cr._validate(**BOX, earlier=earlier, later=later, today=TODAY)


def test_second_request_is_refused_while_a_run_is_active():
    assert cr._LOCK.acquire(blocking=False)
    try:
        with pytest.raises(cr.CustomRunBusy):
            cr.start_run(**BOX, earlier=dt.date(2020, 3, 31), later=dt.date(2025, 3, 29), today=TODAY)
    finally:
        cr._LOCK.release()


@pytest.mark.parametrize("name", ["../secret.png", "a/b.png", "x.tif", "..\\x.png", ""])
def test_preview_path_rejects_unsafe_names(name):
    cr._JOBS["testjob"] = {}
    try:
        with pytest.raises(KeyError):
            cr.preview_path("testjob", name)
    finally:
        cr._JOBS.pop("testjob", None)


def test_config_is_sandboxed_and_limited():
    cfg = cr._build_config("abc123", (85.30, 27.69, 85.32, 27.71), dt.date(2020, 3, 31), dt.date(2025, 3, 29), TODAY)
    assert "custom_runs" in str(cfg.processed_dir) and "abc123" in str(cfg.processed_dir)
    assert "data/processed" not in str(cfg.processed_dir).replace("\\", "/")
    assert cfg.indices == cr.INDICES
    assert cfg.periods["later"].search_end <= TODAY
    assert cfg.aoi().bounds_4326 == (85.30, 27.69, 85.32, 27.71)
