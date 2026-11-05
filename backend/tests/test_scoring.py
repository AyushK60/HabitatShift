"""Scoring helpers and registry sanity, using a stubbed window reader."""

from __future__ import annotations

import numpy as np
import pytest
import yaml

from backend.app import config
from backend.app.catalog.models import SceneCandidate
from backend.app.preprocess import scoring

CATALOG = "https://earth-search.aws.element84.com/v1"


@pytest.fixture
def candidate(stac_item_factory) -> SceneCandidate:
    return SceneCandidate.from_stac(stac_item_factory(), catalog_url=CATALOG)


def test_full_overlap_for_containing_footprint(candidate, small_aoi):
    assert scoring.aoi_intersection_fraction(candidate, small_aoi) == pytest.approx(1.0)


def test_no_overlap_when_aoi_elsewhere(candidate, aoi):
    from backend.app.preprocess.aoi import aoi_from_bounds

    far = aoi_from_bounds(
        study_id="far", west=90.0, south=20.0, east=90.05, north=20.05,
        description="", source="",
    )
    assert scoring.aoi_intersection_fraction(candidate, far) == pytest.approx(0.0)


def test_partial_overlap_is_between_zero_and_one(candidate, aoi):
    from backend.app.preprocess.aoi import aoi_from_bounds

    straddling = aoi_from_bounds(
        study_id="edge", west=82.30, south=16.70, east=82.45, north=16.83,
        description="", source="",
    )
    fraction = scoring.aoi_intersection_fraction(candidate, straddling)
    assert 0.0 < fraction < 1.0


def test_candidate_without_footprint_scores_zero(candidate, small_aoi):
    blank = SceneCandidate(
        item_id=candidate.item_id, collection=candidate.collection,
        acquired=candidate.acquired, platform=candidate.platform,
        constellation=candidate.constellation, instrument=candidate.instrument,
        cloud_cover=candidate.cloud_cover, footprint={}, epsg=candidate.epsg,
        catalog_url=candidate.catalog_url,
        processing_baseline=candidate.processing_baseline,
        assets=candidate.assets,
    )
    assert scoring.aoi_intersection_fraction(blank, small_aoi) == 0.0


def test_scores_are_ordered_by_valid_fraction(candidate, small_aoi, monkeypatch):
    second = SceneCandidate(
        item_id="SECOND", collection=candidate.collection,
        acquired=candidate.acquired, platform=candidate.platform,
        constellation=candidate.constellation, instrument=candidate.instrument,
        cloud_cover=0.1, footprint=candidate.footprint, epsg=candidate.epsg,
        catalog_url=candidate.catalog_url,
        processing_baseline=candidate.processing_baseline,
        assets=candidate.assets,
    )
    fractions = {candidate.item_id: 0.95, "SECOND": 0.70}
    monkeypatch.setattr(
        scoring, "measure_aoi_valid_fraction",
        lambda c, a, resolution=10.0: (fractions[c.item_id], {}),
    )
    scores = scoring.score_candidates([second, candidate], small_aoi)
    assert [s.item_id for s in scores] == [candidate.item_id, "SECOND"]
    assert all(s.usable for s in scores)


def test_low_valid_fraction_is_not_usable(candidate, small_aoi, monkeypatch):
    monkeypatch.setattr(
        scoring, "measure_aoi_valid_fraction", lambda c, a, resolution=10.0: (0.2, {})
    )
    scores = scoring.score_candidates([candidate], small_aoi)
    assert scores[0].usable is False
    assert any("below" in note for note in scores[0].notes)


def test_read_failure_is_noted_and_not_usable(candidate, small_aoi, monkeypatch):
    def boom(c, a, resolution=10.0):
        raise RuntimeError("network down")

    monkeypatch.setattr(scoring, "measure_aoi_valid_fraction", boom)
    scores = scoring.score_candidates([candidate], small_aoi)
    assert scores[0].usable is False
    assert any("read failed" in note for note in scores[0].notes)


def test_registry_is_valid_yaml_with_required_studies(registry_yaml):
    studies = registry_yaml["studies"]
    ids = {s["study_id"] for s in studies}
    assert {
        "coringa_coastal",
        "chilika_wetland",
        "western_ghats_forest",
        "himalaya_purepu_2025",
        "himalaya_langtang_2026",
        "kathmandu_urban",
    } <= ids


def test_registry_aois_are_inside_valid_ranges(registry_yaml):
    for study in registry_yaml["studies"]:
        b = study["aoi"]["bounds"]
        assert -180 <= b["west"] < b["east"] <= 180
        assert -90 <= b["south"] < b["north"] <= 90
        assert study["status"] in {"processed", "feasibility", "provisional"}


def test_registry_periods_are_ordered(registry_yaml):
    for study in registry_yaml["studies"]:
        for window in study["target_periods"].values():
            assert window["start"] < window["end"]


def test_himalayan_events_stay_distinct(registry_yaml):
    by_id = {s["id"]: s for s in registry_yaml["studies"]}
    assert by_id["D1"]["event_date"] != by_id["D2"]["event_date"]
    assert "outburst" in by_id["D2"]["event_mechanism"]
    assert "supraglacial" in by_id["D1"]["event_mechanism"]


def test_threshold_constants_are_sane():
    assert 0 < config.MIN_COMPARABLE_VALID_FRACTION <= 1
    assert config.MIN_SCENE_VALID_FRACTION >= config.MIN_COMPARABLE_VALID_FRACTION
    assert config.SCL_VALID_CLASSES


def _candidate(candidate, item_id: str, cloud: float) -> SceneCandidate:
    return SceneCandidate(
        item_id=item_id,
        collection=candidate.collection,
        acquired=candidate.acquired,
        platform=candidate.platform,
        constellation=candidate.constellation,
        instrument=candidate.instrument,
        cloud_cover=cloud,
        footprint=candidate.footprint,
        epsg=candidate.epsg,
        catalog_url=candidate.catalog_url,
        processing_baseline=candidate.processing_baseline,
        assets=candidate.assets,
    )


def test_measurement_budget_leaves_extra_candidates_unmeasured(
    candidate, small_aoi, monkeypatch
):
    measured: list[str] = []

    def fake_measure(c, a, resolution=10.0, cache_dir=None):
        measured.append(c.item_id)
        return 0.9, {"valid_fraction": 0.9}

    monkeypatch.setattr(scoring, "measure_aoi_valid_fraction", fake_measure)
    candidates = [
        _candidate(candidate, "THIRD", 3.0),
        _candidate(candidate, "FIRST", 1.0),
        _candidate(candidate, "SECOND", 2.0),
    ]
    scores = scoring.score_candidates(candidates, small_aoi, max_measured=1)

    by_id = {s.item_id: s for s in scores}
    assert measured == ["FIRST"]                       # metadata pre-rank wins
    assert by_id["FIRST"].usable is True
    for item_id in ("SECOND", "THIRD"):
        assert by_id[item_id].aoi_valid_fraction is None
        assert by_id[item_id].usable is False
        assert any("budget" in note for note in by_id[item_id].notes)


def test_measurement_cache_reuses_memoised_fraction(
    candidate, small_aoi, monkeypatch, tmp_path
):
    reads: list[str] = []

    def fake_read(href, request):
        reads.append(href)
        array = np.full((request.height, request.width), 4, dtype=np.int32)
        array[0, 0] = 9                                # one high-cloud pixel
        return array

    monkeypatch.setattr(scoring, "read_window", fake_read)

    first, report = scoring.measure_aoi_valid_fraction(
        candidate, small_aoi, cache_dir=tmp_path
    )
    second, _ = scoring.measure_aoi_valid_fraction(
        candidate, small_aoi, cache_dir=tmp_path
    )

    assert reads == [candidate.asset(config.ASSET_SCL).href]   # one remote read
    assert first == second
    total = report["total_pixels"]
    assert first == pytest.approx((total - 1) / total)
    assert len(list(tmp_path.glob("*.json"))) == 1
