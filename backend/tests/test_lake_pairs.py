"""Offline tests for pairing optical scenes with radar scenes, and for the lake registry."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import yaml

from backend.app.radar import lakes as L

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_lake_training_pairs.py"


def _module():
    spec = importlib.util.spec_from_file_location("pairs_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _s1(day, orbit="ascending", rel=85):
    return {"id": f"s1_{day}_{rel}", "properties": {"datetime": f"{day}T12:00:00Z", "sat:orbit_state": orbit,
                                                    "sat:relative_orbit": rel}}


def test_partners_within_three_days_closest_first_one_per_orbit():
    m = _module()
    candidate = SimpleNamespace(acquisition_iso="2022-10-29T05:00:00Z")
    items = [_s1("2022-10-29", rel=85), _s1("2022-10-26", rel=85),   # same orbit twice: keep the closer
             _s1("2022-11-01", "descending", 121),                   # exactly 3 days: allowed
             _s1("2022-11-02", "descending", 33)]                    # 4 days: too far
    chosen = m.partners(candidate, items)
    assert [(gap, item["id"]) for gap, item in chosen] == [(0, "s1_2022-10-29_85"), (3, "s1_2022-11-01_121")]


def test_partners_none_when_no_radar_scene_is_near():
    m = _module()
    assert m.partners(SimpleNamespace(acquisition_iso="2022-10-29T05:00:00Z"), [_s1("2022-12-01")]) == []


def test_lake_registry_is_valid_and_ids_unique():
    data = yaml.safe_load(L.LAKES_FILE.read_text(encoding="utf-8"))["lakes"]
    ids = [e["id"] for e in data]
    assert len(ids) == len(set(ids)) >= 3
    assert all(isinstance(e["note"], str) and e["half_deg"] > 0 for e in data)
    assert {"tsho_rolpa", "imja_tsho", "thulagi"} <= set(ids)


def test_lake_bbox_is_centred_on_the_lake():
    lake = L.Lake(id="x", name="x", lon=86.0, lat=28.0, half_deg=0.04)
    west, south, east, north = lake.bbox
    assert (west + east) / 2 == 86.0 and abs((south + north) / 2 - 28.0) < 1e-9
