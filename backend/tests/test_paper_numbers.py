"""The numbers in the version 3 paper must match the recorded outputs they were taken from."""
from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "docs" / "paper" / "v3" / "paper.md"
DATA = ROOT / "frontend" / "public" / "research" / "v3.json"

pytestmark = pytest.mark.skipif(not (PAPER.exists() and DATA.exists()), reason="paper or results bundle missing")


def r2(x: float) -> str:
    """Two decimals, halves rounded up, as written in the paper (the recorded values have three decimals)."""
    return str(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _table_row(text: str, label: str) -> str:
    return next(line for line in text.splitlines() if line.startswith("| " + label))


def test_forest_table_matches_recorded_scores():
    text, data = PAPER.read_text(encoding="utf-8"), json.loads(DATA.read_text())
    names = {"ndvi_decrease": "NDVI decrease (signed)", "raw6": "Six raw bands", "prithvi": "Prithvi-EO-2.0",
             "ssl4eo_rgb": "SSL4EO ResNet-50 (RGB)", "ndvi": "NDVI (unsigned)", "ndwi": "NDWI", "indices5": "Five indices"}
    for key, label in names.items():
        row = _table_row(text, label)
        for area in ("bastar_forest", "odisha_forest"):
            r = next(x for x in data["forest"][area]["rows"] if x["id"] == key)
            assert f"{r2(r['ap'])} ({r2(r['auc'])})" in row, (label, area, row)


def test_lake_table_matches_recorded_scores():
    text, data = PAPER.read_text(encoding="utf-8"), json.loads(DATA.read_text())
    names = {"raw6": "Six raw bands", "prithvi": "Prithvi-EO-2.0", "ndvi": "NDVI", "mndwi": "MNDWI",
             "indices5": "Five indices", "ssl4eo_rgb": "SSL4EO ResNet-50 (RGB)"}
    section = text[text.index("Table: Glacial lakes"):]
    for key, label in names.items():
        row = _table_row(section, label)
        r = next(x for x in data["lakes"]["rows"] if x["id"] == key)
        assert f"{r2(r['ap'])} ({r2(r['auc'])})" in row, (label, row)


def test_unet_and_coverage_numbers_match():
    text, data = PAPER.read_text(encoding="utf-8"), json.loads(DATA.read_text())
    sets = data["unet"]["sets"]
    assert r2(sets['test_lakes']['unet_mean']) in text and r2(sets['test_lakes']['otsu']) in text
    assert r2(sets['time_holdout_2022_same_lakes']['unet_mean']) in text
    cov = data["unet"]["cv"]["coverage"]
    for alpha, c in cov.items():
        assert f"{round(c['achieved'] * 100)}%" in text, alpha
        assert f"{c['lakes_below_target']} of 30" in text, alpha
