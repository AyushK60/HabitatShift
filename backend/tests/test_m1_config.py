"""M1 experiment-configuration validation tests (synthetic YAML)."""

from __future__ import annotations

import textwrap

import pytest
import yaml

from backend.app.pipeline.config import ConfigError, load_study_config

BASE = {
    "experiment_id": "test_m1",
    "study_id": "coringa_coastal",
    "registry": "studies/registry.yaml",
    "analysis": {
        "resolution_m": 10.0,
        "indices": ["ndvi", "ndwi", "mndwi"],
        "composite": {
            "method": "median",
            "max_observations": 3,
            "min_observations": 1,
            "anchor_max_offset_days": 30,
        },
        "selection": {"max_cloud_cover": 60.0},
    },
    "periods": {
        "earlier": {
            "anchor": "2020-03-26",
            "search_start": "2020-02-25",
            "search_end": "2020-04-25",
            "max_offset_days": 30,
        },
        "later": {
            "anchor": "2025-03-25",
            "search_start": "2025-02-23",
            "search_end": "2025-04-24",
            "max_offset_days": 30,
        },
    },
    "change": {"thresholds": [0.1, 0.15, 0.2], "primary_threshold": 0.15},
    "outputs": {
        "processed_dir": "data/processed/m1/test_m1",
        "preview_dir": "data/previews/m1/test_m1",
        "manifest": "data/manifests/m1_test_m1.json",
    },
}


def _write(tmp_path, payload):
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_valid_config_loads_and_validates(tmp_path, project_root):
    cfg = load_study_config(_write(tmp_path, BASE))
    assert cfg.experiment_id == "test_m1"
    assert cfg.study_id == "coringa_coastal"
    assert cfg.indices == ("ndvi", "ndwi", "mndwi")
    assert cfg.composite_method == "median"
    assert cfg.thresholds == (0.1, 0.15, 0.2)
    assert cfg.primary_threshold == pytest.approx(0.15)
    assert cfg.periods["earlier"].anchor.isoformat() == "2020-03-26"
    assert cfg.processed_dir == project_root / "data/processed/m1/test_m1"
    # The registry study is actually resolvable, including its AOI.
    assert cfg.aoi().study_id == "coringa_coastal"
    assert cfg.study_meta()["title"]


def test_experiment_id_required(tmp_path):
    payload = yaml.safe_load(yaml.safe_dump(BASE))
    payload["experiment_id"] = ""
    with pytest.raises(ConfigError, match="experiment_id"):
        load_study_config(_write(tmp_path, payload))


def test_unknown_index_rejected(tmp_path):
    payload = yaml.safe_load(yaml.safe_dump(BASE))
    payload["analysis"]["indices"] = ["ndvi", "evi"]
    with pytest.raises(ConfigError, match="unknown indices"):
        load_study_config(_write(tmp_path, payload))


def test_invalid_observation_bounds_rejected(tmp_path):
    payload = yaml.safe_load(yaml.safe_dump(BASE))
    payload["analysis"]["composite"]["min_observations"] = 4
    payload["analysis"]["composite"]["max_observations"] = 3
    with pytest.raises(ConfigError, match="observation bounds"):
        load_study_config(_write(tmp_path, payload))


def test_invalid_composite_method_rejected(tmp_path):
    payload = yaml.safe_load(yaml.safe_dump(BASE))
    payload["analysis"]["composite"]["method"] = "mode"
    with pytest.raises(ConfigError, match="composite method"):
        load_study_config(_write(tmp_path, payload))


def test_missing_period_rejected(tmp_path):
    payload = yaml.safe_load(yaml.safe_dump(BASE))
    del payload["periods"]["later"]
    with pytest.raises(ConfigError, match="period 'later'"):
        load_study_config(_write(tmp_path, payload))


def test_anchor_outside_window_rejected(tmp_path):
    payload = yaml.safe_load(yaml.safe_dump(BASE))
    payload["periods"]["earlier"]["anchor"] = "2020-05-26"
    with pytest.raises(ConfigError, match="outside search window"):
        load_study_config(_write(tmp_path, payload))


def test_inverted_search_window_rejected(tmp_path):
    payload = yaml.safe_load(yaml.safe_dump(BASE))
    payload["periods"]["earlier"]["search_start"] = "2020-04-30"
    with pytest.raises(ConfigError, match="precede"):
        load_study_config(_write(tmp_path, payload))


def test_non_positive_threshold_rejected(tmp_path):
    payload = yaml.safe_load(yaml.safe_dump(BASE))
    payload["change"]["thresholds"] = [0.1, -0.2]
    with pytest.raises(ConfigError, match="thresholds must be positive"):
        load_study_config(_write(tmp_path, payload))


def test_unknown_study_id_rejected(tmp_path):
    payload = yaml.safe_load(yaml.safe_dump(BASE))
    payload["study_id"] = "not_in_registry"
    cfg = load_study_config(_write(tmp_path, payload))
    with pytest.raises(ConfigError, match="not found"):
        cfg.aoi()


def test_missing_config_file_rejected(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_study_config(tmp_path / "absent.yaml")
