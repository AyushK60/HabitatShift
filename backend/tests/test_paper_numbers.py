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


FOREST_AREAS = ["bastar_forest", "odisha_forest", "kodagu_wayanad_forest", "garo_hills_forest", "uttarakhand_shivalik_forest"]


def test_forest_table_matches_recorded_scores():
    text, data = PAPER.read_text(encoding="utf-8"), json.loads(DATA.read_text())
    names = {"ndvi_decrease": "NDVI decrease (signed)", "raw6": "Six raw bands", "prithvi": "Prithvi-EO-2.0",
             "ssl4eo_rgb": "SSL4EO ResNet-50 (RGB)", "ndvi": "NDVI (unsigned)", "ndwi": "NDWI", "indices5": "Five indices"}
    for key, label in names.items():
        cells = [c.strip() for c in _table_row(text, label).strip("|").split("|")][1:]
        assert len(cells) == len(FOREST_AREAS), (label, cells)
        for area, cell in zip(FOREST_AREAS, cells):
            r = next(x for x in data["forest"][area]["rows"] if x["id"] == key)
            assert cell.startswith(f"{r2(r['ap'])} ({r2(r['auc'])})"), (label, area, cell)
            lo, hi = r["vs_reference_ci"]
            excludes_zero = key != "ndvi_decrease" and (hi < 0 or lo > 0)
            assert cell.endswith("*") == excludes_zero, (label, area, cell)


def test_forest_text_claims_match_recorded_scores():
    text, data = PAPER.read_text(encoding="utf-8"), json.loads(DATA.read_text())
    for area in FOREST_AREAS:
        rows = {x["id"]: x for x in data["forest"][area]["rows"]}
        assert rows["ndvi_decrease"]["ap"] >= max(rows[m]["ap"] for m in ("prithvi", "ssl4eo_rgb")) - 1e-9, area
    positives = [data["forest"][a]["counts"]["positives"] for a in FOREST_AREAS]
    assert "Positive patches: " + ", ".join(map(str, positives[:-1])) + " and " + str(positives[-1]) in text


def test_lake_table_matches_recorded_scores():
    text, data = PAPER.read_text(encoding="utf-8"), json.loads(DATA.read_text())
    names = {"raw6": "Six raw bands", "prithvi": "Prithvi-EO-2.0", "ndvi": "NDVI", "mndwi": "MNDWI",
             "indices5": "Five indices", "ssl4eo_rgb": "SSL4EO ResNet-50 (RGB)"}
    section = text[text.index("Table: Glacial lakes"):]
    for key, label in names.items():
        row = _table_row(section, label)
        r = next(x for x in data["lakes"]["rows"] if x["id"] == key)
        assert f"{r2(r['ap'])} ({r2(r['auc'])})" in row, (label, row)


def test_unet_is_not_in_the_workshop_paper():
    text = PAPER.read_text(encoding="utf-8")
    assert "U-Net" not in text and "Radar water model" not in text.replace("A radar water model", "")


def test_probe_table_matches_recorded_scores():
    path = ROOT / "data" / "experiments" / "v3_fm" / "probe" / "evaluation.json"
    if not path.exists():
        pytest.skip("probe results missing")
    text, probe = PAPER.read_text(encoding="utf-8"), json.loads(path.read_text())
    names = {"bastar_forest": "Bastar", "odisha_forest": "Odisha", "kodagu_wayanad_forest": "Kodagu",
             "garo_hills_forest": "Garo Hills", "uttarakhand_shivalik_forest": "Shivalik"}
    section = text[text.index("Table: Linear probe on forest loss"):]
    for key, label in names.items():
        cells = [c.strip() for c in _table_row(section, label).strip("|").split("|")]
        m = probe["forest"]["groups"][key]["metrics"]
        assert cells[1] == r2(m["reference"]["average_precision"]), label
        assert cells[2] == r2(m["prithvi:probe"]["average_precision"]), label
        assert cells[4] == r2(m["raw6:probe"]["average_precision"]), label
        lo, hi = probe["forest"]["groups"][key]["diff_vs_reference_ap_ci95"]["prithvi:probe"]
        assert cells[3].endswith("*") == (hi < 0 or lo > 0), label


def test_lake_subset_table_matches_recorded_scores():
    path = ROOT / "data" / "experiments" / "v3_fm" / "lakes" / "subsets.json"
    if not path.exists():
        pytest.skip("lake subset results missing")
    text, groups = PAPER.read_text(encoding="utf-8"), json.loads(path.read_text())["groups"]
    section = text[text.index("Table: Lakes one at a time"):]
    names = {"Imja Tsho": "imja_only", "Added lake": "added_lake_only", "Thulagi": "thulagi_only",
             "Tsho Rolpa": "tsho_rolpa_only", "All lakes except Imja Tsho": "without_imja"}
    for label, key in names.items():
        cells = [c.strip() for c in _table_row(section, label).strip("|").split("|")]
        g = groups[key]
        assert cells[1] == f"{g['positives']} ({g['blocks_with_positives']})", label
        for cell, method in zip(cells[2:], ("mndwi:z", "raw6:z", "prithvi:z", "ssl4eo_rgb:z")):
            assert cell == r2(g["metrics"][method]["average_precision"]), (label, method)
