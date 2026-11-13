"""Offline tests for the radar helpers and the lake time-series aggregation."""
from __future__ import annotations

import numpy as np
import pytest

from backend.app.radar import lakes as L
from backend.app.radar import sar
from backend.app.radar.planetary import make_grid, utm_epsg


def test_utm_epsg_north_and_south():
    assert utm_epsg(86.5, 27.9) == 32645
    assert utm_epsg(-57.0, -10.0) == 32721


def test_make_grid_snaps_to_resolution():
    grid = make_grid((86.4, 27.8, 86.5, 27.9), res=10.0)
    assert grid.crs == "EPSG:32645"
    assert grid.transform.c % 10 == 0 and grid.transform.f % 10 == 0
    assert grid.width > 800 and grid.height > 1000


def test_to_db_known_values_and_nan():
    out = sar.to_db(np.array([1.0, 0.1, np.nan]))
    assert out[0] == pytest.approx(0.0) and out[1] == pytest.approx(-10.0)
    assert np.isnan(out[2])


def test_lee_filter_reduces_speckle_keeps_nan_and_edges():
    rng = np.random.default_rng(0)
    image = np.full((80, 80), 0.1)
    image[:, 40:] = 0.4
    noisy = (image * rng.gamma(5.0, 1 / 5.0, image.shape)).astype("float32")
    noisy[0, 0] = np.nan
    out = sar.lee_filter(noisy)
    assert np.isnan(out[0, 0])
    flat = (slice(10, 70), slice(5, 30))
    assert np.nanstd(out[flat]) < 0.6 * np.nanstd(noisy[flat])
    assert out[40, 20] < 0.2 < 0.3 < out[40, 60]  # edge survives


def test_otsu_splits_two_modes():
    rng = np.random.default_rng(1)
    values = np.concatenate([rng.normal(-18, 1.5, 3000), rng.normal(-7, 2.0, 7000)])
    assert -16 < sar.otsu_threshold(values) < -9


def test_otsu_needs_enough_pixels():
    with pytest.raises(ValueError):
        sar.otsu_threshold(np.array([1.0, 2.0]))


def test_slope_of_tilted_plane():
    cols = np.arange(50) * 10.0
    dem = np.tile(cols * np.tan(np.radians(12.0)), (50, 1))
    assert np.nanmedian(sar.slope_degrees(dem, 10.0)) == pytest.approx(12.0, abs=0.2)


def _scene_with_lake():
    rng = np.random.default_rng(2)
    power = 0.2 * rng.gamma(5.0, 1 / 5.0, (120, 120))
    lake = np.zeros((120, 120), bool)
    lake[40:80, 30:70] = True
    power[lake] = 0.02 * rng.gamma(5.0, 1 / 5.0, lake.sum())
    return power.astype("float32"), lake


def test_water_mask_finds_the_lake():
    power, lake = _scene_with_lake()
    mask, info = sar.water_mask(power, np.zeros_like(power))
    assert info["status"] == "ok"
    assert (mask & lake).sum() / lake.sum() > 0.9
    assert (mask & ~lake).sum() / (~lake).sum() < 0.02


def test_water_mask_excludes_steep_terrain():
    power, lake = _scene_with_lake()
    slope = np.zeros_like(power)
    slope[lake] = 40.0
    mask, _ = sar.water_mask(power, slope)
    assert (mask & lake).sum() == 0  # steep pixels are never called water


def test_water_mask_no_data():
    mask, info = sar.water_mask(np.full((20, 20), np.nan, dtype="float32"))
    assert info["status"] == "no_valid_data" and not mask.any()


def test_lake_patch_area_counts_only_patches_touching_seed():
    seed = np.zeros((60, 60), bool)
    seed[20:30, 20:30] = True
    water = np.zeros_like(seed)
    water[18:32, 18:32] = True   # the lake, a bit larger than the seed
    water[50:58, 50:58] = True   # unrelated pond
    area, patches = L.lake_patch_area(water, seed, 10.0)
    assert patches == 1
    assert area == pytest.approx(14 * 14 * 100 / 1e6)


def test_find_seed_picks_nearest_flat_area():
    grid = make_grid((86.0, 27.0, 86.02, 27.02))
    slope = np.full(grid.shape, 30.0, dtype="float32")
    slope[100:140, 100:140] = 0.0   # flat lake, 1600 px
    slope[10:40, 10:40] = 0.0       # distant flat field
    from pyproj import Transformer
    x, y = grid.transform * (120, 120)
    lon, lat = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True).transform(x, y)
    seed, info = L.find_seed(slope, grid, lon, lat)
    assert seed[120, 120] and not seed[20, 20]
    assert info["seed_pixels"] == pytest.approx(1600, rel=0.05)


def test_find_seed_refuses_when_no_flat_area_nearby():
    grid = make_grid((86.0, 27.0, 86.02, 27.02))
    with pytest.raises(ValueError):
        L.find_seed(np.full(grid.shape, 30.0, dtype="float32"), grid, 86.01, 27.01)


def _rec(date, area, orbit=85, contrast=-9.0, sensor="s1", status="ok", state="ascending"):
    return {"sensor": sensor, "datetime": f"{date}T12:00:00Z", "orbit_state": state, "relative_orbit": orbit,
            "contrast_db": contrast, "area_km2": area, "status": status}


def test_usable_orbits_uses_reference_years_then_falls_back():
    records = [_rec(f"2019-0{m}-10", 1.0, orbit=85, contrast=-9) for m in range(1, 6)]
    records += [_rec(f"2023-0{m}-10", 1.0, orbit=12, contrast=-0.5) for m in range(1, 6)]
    orbits = L.usable_orbits(records, (2019, 2020))
    assert orbits["asc85"] == {"scenes": 5, "basis": "reference_years", "q25_contrast_db": -9.0, "usable": True}
    assert orbits["asc12"]["basis"] == "all_years" and orbits["asc12"]["usable"] is False


def test_monthly_series_excludes_and_explains():
    records = [_rec("2023-07-01", 1.0), _rec("2023-07-13", 1.2), _rec("2023-07-25", 1.1),
               _rec("2023-07-05", 5.0, orbit=12, contrast=-0.5),        # orbit cannot see lake
               _rec("2023-07-06", 0.1, contrast=-1.0),                  # lake not dark in a good orbit
               _rec("2023-07-07", 0.0, status="lake_not_covered")]
    orbits = {"asc85": {"usable": True}, "asc12": {"usable": False}}
    (row,) = L.monthly_series(records, orbits)
    assert row["n"] == 3 and row["area_km2"] == pytest.approx(1.1)  # median
    assert row["excluded"] == {"orbit_cannot_see_lake": 1, "lake_not_dark": 1, "lake_not_covered": 1}
    assert row["se_km2"] == pytest.approx(0.1 / np.sqrt(3), abs=1e-3)


def test_monthly_series_marks_frozen_optical_scenes():
    records = [{"sensor": "s2", "datetime": "2023-01-05T05:00:00Z", "area_km2": 0.0, "status": "ok",
                "seed_ice_fraction": 0.9}]
    (row,) = L.monthly_series(records, None)
    assert row["n"] == 0 and row["excluded"] == {"frozen": 1} and "area_km2" not in row


def test_flag_changes_uses_three_standard_errors():
    series = [
        {"month": "2023-01", "area_km2": 1.00, "se_km2": 0.01},
        {"month": "2023-02", "area_km2": 1.02, "se_km2": 0.01},   # within noise
        {"month": "2023-03", "area_km2": 1.30, "se_km2": 0.01},   # real jump
        {"month": "2023-04", "n": 0},                              # gap, skipped
        {"month": "2023-05", "area_km2": 1.31, "se_km2": 0.01},
    ]
    out = L.flag_changes(series)
    assert out[0]["change_vs_previous"] is None
    assert out[1]["change_vs_previous"]["exceeds_noise"] is False
    assert out[2]["change_vs_previous"]["exceeds_noise"] is True
    assert out[4]["change_vs_previous"]["exceeds_noise"] is False


def test_partly_frozen_optical_scene_is_excluded():
    records = [{"sensor": "s2", "datetime": "2023-04-05T05:00:00Z", "area_km2": 0.7, "status": "ok",
                "seed_ice_fraction": 0.3},
               {"sensor": "s2", "datetime": "2023-04-10T05:00:00Z", "area_km2": 1.5, "status": "ok",
                "seed_ice_fraction": 0.0}]
    (row,) = L.monthly_series(records, None)
    assert row["n"] == 1 and row["area_km2"] == 1.5 and row["excluded"] == {"frozen": 1}


def test_frozen_season_and_cloud_screens_for_optical():
    scenes = [{"sensor": "s2", "datetime": "2023-01-05T05:00:00Z", "area_km2": 0.1, "status": "ok", "seed_ice_fraction": 0.0, "cloud_cover": 0.1},
              {"sensor": "s2", "datetime": "2023-07-05T05:00:00Z", "area_km2": 0.1, "status": "ok", "seed_ice_fraction": 0.0, "cloud_cover": 0.7},
              {"sensor": "s2", "datetime": "2023-07-10T05:00:00Z", "area_km2": 1.5, "status": "ok", "seed_ice_fraction": 0.0, "cloud_cover": 0.1}]
    jan, jul = L.monthly_series(scenes, None, {"2023-01"})
    assert jan["n"] == 0 and jan["excluded"] == {"frozen_season": 1}
    assert jul["n"] == 1 and jul["excluded"] == {"cloudy_scene": 1}


def test_not_dark_months_uses_only_usable_orbits():
    orbits = {"asc85": {"usable": True}, "asc12": {"usable": False}}
    records = [_rec("2023-01-03", 0.0, contrast=-0.5), _rec("2023-01-15", 0.0, contrast=-1.0),
               _rec("2023-07-03", 1.4, contrast=-10.0), _rec("2023-07-15", 5.0, orbit=12, contrast=-0.2)]
    assert L.not_dark_months(records, orbits) == {"2023-01"}
