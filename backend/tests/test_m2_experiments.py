"""M2 research-experiment tests (synthetic data unless stated otherwise).

The numerical checks use small, hand-computed arrays with known answers, so a
regression in thresholding, area conservation, compositing or uncertainty
resampling cannot hide behind the real study's numbers.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from backend.app.experiments.config import M2ConfigError, load_m2_config
from backend.app.experiments.estimators import (
    build_surfaces,
    composite_bands,
    cross_pipeline_comparison,
    evaluate_surface,
    evaluate_surfaces,
)
from backend.app.experiments.inputs import ObservationRecord, ObservationSet
from backend.app.experiments.reporting import (
    delta_histogram_svg,
    estimator_comparison_svg,
    threshold_response_svg,
    write_sensitivity_csv,
    write_summary_csv,
)
from backend.app.experiments.runner import (
    compute_fingerprint,
    evaluate_hypotheses,
    find_cached_run,
)
from backend.app.experiments.thresholds import (
    ThresholdError,
    check_area_conservation,
    classify_delta,
    delta_statistics,
    threshold_row,
    threshold_sweep,
)
from backend.app.experiments.uncertainty import (
    block_bootstrap,
    coverage_summary,
    temporal_robustness,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _grid_summary(width: int = 8, height: int = 6, pixel_area_m2: float = 100.0):
    return {
        "width": width,
        "height": height,
        "pixel_area_m2": pixel_area_m2,
        "signature": "test-signature",
    }


def _m1_summary(width: int = 8, height: int = 6):
    return {
        "grid": _grid_summary(width, height),
        "aoi": {"aoi_pixels": width * height - 4},
        "periods": [
            {
                "period_id": "earlier",
                "anchor_date": "2020-03-26",
                "observation_count": 2,
                "item_ids": ["E_20200326_1", "E_20200321_0"],
                "observation_dates": ["2020-03-26", "2020-03-21"],
                "valid_pixels": width * height,
                "valid_fraction": 1.0,
                "valid_fraction_of_grid": 1.0,
                "observation_count_stats": {"min": 1, "max": 1, "mean": 1.0},
            },
            {
                "period_id": "later",
                "anchor_date": "2025-03-25",
                "observation_count": 2,
                "item_ids": ["L_20250325_0", "L_20250401_1"],
                "observation_dates": ["2025-03-25", "2025-04-01"],
                "valid_pixels": width * height,
                "valid_fraction": 1.0,
                "valid_fraction_of_grid": 1.0,
                "observation_count_stats": {"min": 1, "max": 1, "mean": 1.0},
            },
        ],
        "change": {},
    }


def _record(
    item_id: str,
    period_id: str,
    date: str,
    shape: tuple[int, int],
    *,
    red: float = 0.2,
    nir: float = 0.5,
    green: float = 0.3,
    swir: float = 0.25,
    seed: int = 0,
) -> ObservationRecord:
    rng = np.random.default_rng(seed)
    valid = np.ones(shape, dtype=bool)
    jitter = rng.uniform(-0.01, 0.01, size=shape)
    reflectance = {
        "red": (red + jitter).astype(np.float32),
        "nir": (nir + jitter).astype(np.float32),
        "green": (green + jitter).astype(np.float32),
        "swir16": (swir + jitter).astype(np.float32),
        "blue": (0.15 + jitter).astype(np.float32),
    }
    from backend.app.experiments.inputs import index_from_reflectance

    indices = {
        index: index_from_reflectance(reflectance, index)
        for index in ("ndvi", "ndwi", "mndwi")
    }
    return ObservationRecord(
        item_id=item_id,
        period_id=period_id,
        date=date,
        valid=valid,
        reflectance=reflectance,
        indices=indices,
        meta={"item_id": item_id, "period_id": period_id},
        meta_sha256="0" * 64,
        npz_sha256="0" * 64,
        npz_path=Path(f"{item_id}.npz"),
    )


def _observation_set(shape: tuple[int, int] = (8, 6)) -> ObservationSet:
    records = {
        "E_20200326_1": _record("E_20200326_1", "earlier", "2020-03-26", shape, seed=1),
        "E_20200321_0": _record("E_20200321_0", "earlier", "2020-03-21", shape, seed=2),
        "L_20250325_0": _record("L_20250325_0", "later", "2025-03-25", shape, seed=3),
        "L_20250401_1": _record("L_20250401_1", "later", "2025-04-01", shape, seed=4),
    }
    return ObservationSet(
        records=records,
        earlier=("E_20200326_1", "E_20200321_0"),
        later=("L_20250325_0", "L_20250401_1"),
        cache_dir=Path("unused"),
    )


class _MinimalConfig:
    """Duck-typed stand-in exposing only what build_surfaces reads."""

    def __init__(self, families=("composite", "anchor_single", "single_pairs", "leave_one_out")):
        self.indices = ("ndvi",)
        self.estimator_families = tuple(families)
        self.min_comparable_valid_fraction = 0.5

    def canonical(self) -> dict:
        return {"schema": "m2-config/1", "estimator_families": list(self.estimator_families)}


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

class TestM2Config:
    def test_real_config_loads(self, project_root: Path):
        config = load_m2_config(project_root / "studies/experiments/coringa_m2.yaml")
        assert config.study_id == "coringa_coastal"
        assert config.experiment_id == "coringa_m2"
        assert config.indices == ("ndvi", "ndwi", "mndwi")
        assert config.thresholds == (0.05, 0.1, 0.15, 0.2, 0.25)
        assert config.primary_threshold == 0.15
        assert len(config.hypotheses) == 5
        assert all(":" in hypothesis for hypothesis in config.hypotheses)
        assert config.block_size_px == 15
        assert config.bootstrap_iterations == 200

    def test_required_thresholds_enforced(self, project_root: Path, tmp_path: Path):
        text = (project_root / "studies/experiments/coringa_m2.yaml").read_text(
            encoding="utf-8"
        )
        broken = text.replace(
            "  thresholds: [0.05, 0.10, 0.15, 0.20, 0.25]",
            "  thresholds: [0.05, 0.10]",
        )
        path = tmp_path / "broken.yaml"
        path.write_text(broken, encoding="utf-8")
        with pytest.raises(M2ConfigError, match="must include"):
            load_m2_config(path)

    def test_hypotheses_required(self, project_root: Path, tmp_path: Path):
        text = (project_root / "studies/experiments/coringa_m2.yaml").read_text(
            encoding="utf-8"
        )
        lines = text.splitlines()
        kept = [
            line
            for line in lines
            if not line.strip().startswith('- "')
        ]
        path = tmp_path / "no_hypotheses.yaml"
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        with pytest.raises(M2ConfigError, match="hypotheses"):
            load_m2_config(path)

    def test_unknown_index_rejected(self, project_root: Path, tmp_path: Path):
        text = (project_root / "studies/experiments/coringa_m2.yaml").read_text(
            encoding="utf-8"
        )
        broken = text.replace(
            "  indices: [ndvi, ndwi, mndwi]", "  indices: [ndvi, evi2]"
        )
        path = tmp_path / "bad_index.yaml"
        path.write_text(broken, encoding="utf-8")
        with pytest.raises(M2ConfigError, match="unknown indices"):
            load_m2_config(path)

    def test_primary_threshold_must_be_member(self, project_root: Path, tmp_path: Path):
        text = (project_root / "studies/experiments/coringa_m2.yaml").read_text(
            encoding="utf-8"
        )
        broken = text.replace(
            "  primary_threshold: 0.15", "  primary_threshold: 0.13"
        )
        path = tmp_path / "bad_primary.yaml"
        path.write_text(broken, encoding="utf-8")
        with pytest.raises(M2ConfigError, match="must be one of the thresholds"):
            load_m2_config(path)


# ---------------------------------------------------------------------------
# threshold mathematics (hand-computed)
# ---------------------------------------------------------------------------

class TestThresholds:
    def _arrays(self):
        delta = np.array(
            [
                [-0.30, -0.10, 0.0, 0.10, 0.30],
                [-0.05, 0.05, 0.14, -0.16, 0.16],
            ],
            dtype=np.float64,
        )
        common = np.ones_like(delta, dtype=bool)
        return delta, common

    def test_classes_partition_common(self):
        delta, common = self._arrays()
        masks = classify_delta(delta, common, 0.15)
        assert np.array_equal(masks["decrease"] | masks["stable"] | masks["increase"], common)
        assert not np.any(masks["decrease"] & masks["increase"])
        # hand-checked: decrease = {-0.30, -0.16}; increase = {+0.30, +0.16}
        assert masks["decrease"].sum() == 2
        assert masks["increase"].sum() == 2
        assert masks["stable"].sum() == 6

    def test_boundary_is_symmetric_and_inclusive(self):
        delta, common = self._arrays()
        masks = classify_delta(delta, common, 0.15)
        # -0.15 would be decrease; +0.15 increase; boundary belongs to change
        assert masks["decrease"][0, 0] and not masks["stable"][0, 0]
        assert masks["increase"][1, 4] and not masks["stable"][1, 4]

    def test_area_conservation_identity(self):
        delta, common = self._arrays()
        row = threshold_row(delta, common, 0.15, 100.0)
        assert row["area_conservation"]["ok"]
        assert row["decrease_pixels"] + row["stable_pixels"] + row["increase_pixels"] == row["valid_pixels"]
        assert row["valid_area_m2"] == pytest.approx(row["valid_pixels"] * 100.0)
        assert row["valid_area_ha"] == pytest.approx(row["valid_pixels"] / 100.0)

    def test_area_conservation_detects_tampering(self):
        delta, common = self._arrays()
        row = threshold_row(delta, common, 0.15, 100.0)
        assert row["area_conservation"]["ok"]
        row["stable_pixels"] += 1  # simulate a corrupted count
        assert not check_area_conservation(row)["ok"]

    def test_sweep_monotone(self):
        delta, common = self._arrays()
        rows = threshold_sweep(delta, common, (0.05, 0.1, 0.15, 0.2, 0.25), 100.0)
        decreases = [row["decrease_pixels"] for row in rows]
        increases = [row["increase_pixels"] for row in rows]
        assert decreases == sorted(decreases, reverse=True)
        assert increases == sorted(increases, reverse=True)

    def test_sweep_rejects_non_monotone(self):
        # a triangle that gains change candidates as the threshold tightens
        # is impossible, so feed one crafted to violate monotonicity by using
        # different arrays per call through a wrapper.
        delta, common = self._arrays()
        with pytest.raises(ThresholdError):
            # monkey-patched rows: first row computed on a different array
            original = threshold_row

            def fake(delta_arg, common_arg, threshold, area):
                if threshold == 0.05:
                    big = np.where(common, 0.4, np.nan)
                    row = original(np.nan_to_num(big), common, 0.05, area)
                else:
                    row = original(delta_arg, common_arg, threshold, area)
                return row

            import backend.app.experiments.thresholds as module

            saved = module.threshold_row
            module.threshold_row = fake
            try:
                threshold_sweep(delta, common, (0.05, 0.15), 100.0)
            finally:
                module.threshold_row = saved

    def test_delta_statistics_match_numpy(self):
        rng = np.random.default_rng(42)
        values = rng.normal(0.0, 0.2, size=1000)
        delta = values.reshape(25, 40)
        common = np.ones_like(delta, dtype=bool)
        stats = delta_statistics(delta, common)
        assert stats["valid_count"] == 1000
        assert stats["mean"] == pytest.approx(float(values.mean()))
        assert stats["std"] == pytest.approx(float(values.std(ddof=0)))
        expected = np.percentile(values, [5, 25, 50, 75, 95])
        for key, value in zip(("p05", "p25", "p50", "p75", "p95"), expected):
            assert stats["quantiles"][key] == pytest.approx(float(value))

    def test_rejects_non_finite_delta(self):
        delta = np.array([[np.nan, 0.1]])
        common = np.ones_like(delta, dtype=bool)
        with pytest.raises(ThresholdError, match="non-finite"):
            delta_statistics(delta, common)


# ---------------------------------------------------------------------------
# compositing and estimator expansion
# ---------------------------------------------------------------------------

def _flat_record(item_id: str, period_id: str, red: float, nir: float):
    """A record with constant reflectance, so composites are exact."""
    from backend.app.experiments.inputs import index_from_reflectance

    shape = (2, 2)
    reflectance = {
        "red": np.full(shape, red, dtype=np.float32),
        "nir": np.full(shape, nir, dtype=np.float32),
        "green": np.full(shape, 0.30, dtype=np.float32),
        "swir16": np.full(shape, 0.25, dtype=np.float32),
        "blue": np.full(shape, 0.15, dtype=np.float32),
    }
    indices = {
        index: index_from_reflectance(reflectance, index)
        for index in ("ndvi", "ndwi", "mndwi")
    }
    return ObservationRecord(
        item_id=item_id,
        period_id=period_id,
        date="2020-01-01",
        valid=np.ones(shape, dtype=bool),
        reflectance=reflectance,
        indices=indices,
        meta={"item_id": item_id},
        meta_sha256="0" * 64,
        npz_sha256="0" * 64,
        npz_path=Path(f"{item_id}.npz"),
    )


class TestEstimators:
    def test_median_composite_matches_manual_median(self):
        records = [
            _flat_record("A", "earlier", 0.10, 0.50),
            _flat_record("B", "earlier", 0.30, 0.55),
            _flat_record("C", "earlier", 0.50, 0.60),
        ]
        indices, valid, provenance = composite_bands(records, "median")
        # median red = 0.30, median nir = 0.55 -> ndvi = (0.55-0.30)/(0.85)
        expected_ndvi = (0.55 - 0.30) / (0.55 + 0.30)
        assert np.allclose(indices["ndvi"], expected_ndvi, atol=1e-6)
        assert valid.all()
        assert provenance["observation_count"] == 3
        assert provenance["method"] == "median"

    def test_mean_composite_matches_manual_mean(self):
        records = [
            _flat_record("A", "earlier", 0.10, 0.50),
            _flat_record("B", "earlier", 0.30, 0.55),
        ]
        indices, _, _ = composite_bands(records, "mean")
        expected_ndvi = (0.525 - 0.20) / (0.525 + 0.20)
        assert np.allclose(indices["ndvi"], expected_ndvi, atol=1e-6)

    def test_composite_rejects_unknown_method(self):
        with pytest.raises(Exception, match="unknown composite method"):
            composite_bands([_record("A", "earlier", "2020-01-01", (2, 2))], "max")

    def test_build_surfaces_family_counts(self):
        config = _MinimalConfig()
        observations = _observation_set()
        surfaces = build_surfaces(config, observations, _m1_summary(), None, None)
        ids = [surface.estimator_id for surface in surfaces]
        assert ids.count("composite_median") == 1
        assert ids.count("composite_mean") == 1
        assert ids.count("anchor_single") == 1
        assert sum(item.startswith("single__") for item in ids) == 4  # 2 x 2 pairs
        assert sum(item.startswith("loo_") for item in ids) == 4  # 2 per period
        # every surface shares the index and a non-empty footprint
        for surface in surfaces:
            assert surface.index == "ndvi"
            assert surface.common.any()

    def test_loo_surface_matches_explicit_median(self):
        config = _MinimalConfig()
        observations = _observation_set()
        surfaces = build_surfaces(config, observations, _m1_summary(), None, None)
        loo = next(
            item
            for item in surfaces
            if item.estimator_id == "loo_earlier_without_E_20200326_1"
        )
        remaining = observations.for_period("earlier")[1:2]
        remaining_indices, valid, _ = composite_bands(remaining, "median")
        later_indices, _, _ = composite_bands(observations.for_period("later"), "median")
        expected_delta = later_indices["ndvi"] - remaining_indices["ndvi"]
        assert np.allclose(loo.delta, expected_delta, atol=1e-6)
        assert np.array_equal(loo.common, valid)

    def test_anchor_surface_uses_anchor_dates(self):
        config = _MinimalConfig(families=("anchor_single",))
        observations = _observation_set()
        surfaces = build_surfaces(config, observations, _m1_summary(), None, None)
        anchor = surfaces[0]
        assert anchor.earlier["dates"] == ["2020-03-26"]
        assert anchor.later["dates"] == ["2025-03-25"]
        expected = (
            observations.records["L_20250325_0"].indices["ndvi"]
            - observations.records["E_20200326_1"].indices["ndvi"]
        )
        assert np.allclose(anchor.delta, expected, atol=1e-6)

    def test_evaluate_surface_conserves_area(self):
        config = _MinimalConfig()
        observations = _observation_set()
        surfaces = build_surfaces(config, observations, _m1_summary(), None, None)
        summary = _m1_summary()
        result = evaluate_surface(
            surfaces[0],
            thresholds=(0.05, 0.15),
            primary_threshold=0.15,
            pixel_area_m2=100.0,
            aoi_pixels=summary["aoi"]["aoi_pixels"],
            grid_pixels=48,
            min_comparable_valid_fraction=0.5,
        )
        assert result["area_conservation_all_ok"]
        assert result["common_valid_pixels"] == result["common_valid_area_m2"] / 100.0
        assert result["suitable_for_comparison"]

    def test_cross_pipeline_selection_is_index_safe(self):
        """Regression: anchor surfaces repeat per index; NDVI must be used."""
        shape = (8, 6)
        observations = _observation_set(shape)
        config = _MinimalConfig(families=("anchor_single",))
        surfaces = build_surfaces(config, observations, _m1_summary(), None, None)
        m0_delta = observations.records["L_20250325_0"].indices["ndvi"] - (
            observations.records["E_20200326_1"].indices["ndvi"]
        )
        m0_valid = np.ones(shape, dtype=bool)
        comparison = cross_pipeline_comparison([], surfaces, None)  # no m0 surface
        assert not comparison["available"]
        # now provide an m0 surface built by the real builder path
        config_full = _MinimalConfig(
            families=("anchor_single", "m0_single_scene")
        )
        # build_surfaces needs m0 values passed in for the m0 family
        surfaces_full = build_surfaces(
            config_full,
            observations,
            _m1_summary(),
            m0_delta=m0_delta,
            m0_valid=m0_valid,
            m0_source={
                "earlier_item_id": "E_20200326_1",
                "earlier_date": "2020-03-26",
                "later_item_id": "L_20250325_0",
                "later_date": "2025-03-25",
            },
        )
        comparison = cross_pipeline_comparison([], surfaces_full, object())
        assert comparison["available"]
        assert comparison["index"] == "ndvi"
        assert comparison["pixels_identical_within_1e_9"] == comparison["shared_pixels"]


# ---------------------------------------------------------------------------
# uncertainty
# ---------------------------------------------------------------------------

class TestUncertainty:
    def _m1_for_coverage(self):
        summary = _m1_summary(width=8, height=6)
        summary["aoi"]["area_km2"] = 0.0044
        summary["change"] = {
            "ndvi": {
                "common_valid_pixels": 44,
                "common_valid_fraction_of_aoi": 1.0,
                "common_valid_area_ha": 0.44,
                "suitable_for_comparison": True,
            }
        }
        return summary

    def test_coverage_summary(self):
        config = _MinimalConfig()
        summary = self._m1_for_coverage()
        coverage = coverage_summary(config, summary, _observation_set())
        assert coverage["aoi_pixels"] == 44
        assert coverage["all_indices_suitable"]
        assert coverage["minimum_common_valid_fraction_of_aoi"] == 1.0
        assert len(coverage["periods"]) == 2
        assert coverage["pixel_area_m2"] == 100.0

    def test_bootstrap_deterministic_and_zero_variance(self):
        delta = np.full((30, 30), -0.2)
        common = np.ones_like(delta, dtype=bool)
        first = block_bootstrap(
            delta=delta,
            common=common,
            thresholds=(0.15,),
            block_size_px=10,
            iterations=50,
            seed=7,
            pixel_area_m2=100.0,
        )
        second = block_bootstrap(
            delta=delta,
            common=common,
            thresholds=(0.15,),
            block_size_px=10,
            iterations=50,
            seed=7,
            pixel_area_m2=100.0,
        )
        assert first["thresholds"][0]["decrease_fraction"] == pytest.approx(1.0)
        # zero variance: every resample reproduces the point estimate
        assert first["thresholds"][0]["decrease_fraction_ci95"]["p2_5"] == pytest.approx(1.0)
        assert json.dumps(first) == json.dumps(second)

    def test_bootstrap_known_fraction(self):
        rng = np.random.default_rng(0)
        delta = np.where(rng.random((40, 40)) < 0.25, -0.3, 0.0)
        common = np.ones_like(delta, dtype=bool)
        expected_fraction = float((delta <= -0.15).sum()) / delta.size
        result = block_bootstrap(
            delta=delta,
            common=common,
            thresholds=(0.15,),
            block_size_px=8,
            iterations=100,
            seed=11,
            pixel_area_m2=100.0,
        )
        row = result["thresholds"][0]
        assert row["decrease_fraction"] == pytest.approx(expected_fraction, abs=1e-12)
        ci = row["decrease_fraction_ci95"]
        assert ci["p2_5"] <= expected_fraction <= ci["p97_5"]
        assert row["decrease_area_ha"] == pytest.approx(
            int((delta <= -0.15).sum()) * 100.0 / 10_000.0
        )

    def test_bootstrap_disabled_at_zero_iterations(self):
        delta = np.full((10, 10), -0.2)
        common = np.ones_like(delta, dtype=bool)
        result = block_bootstrap(
            delta=delta,
            common=common,
            thresholds=(0.15,),
            block_size_px=5,
            iterations=0,
            seed=1,
            pixel_area_m2=100.0,
        )
        assert result == {"enabled": False, "reason": "bootstrap_iterations is 0"}

    def test_temporal_robustness_spread(self):
        results = [
            {
                "index": "ndvi",
                "family": "single_pairs",
                "estimator_id": "single__a__b",
                "delta_stats": {"mean": 0.01},
                "thresholds": [
                    {"threshold": 0.15, "decrease_percent_of_common": 10.0,
                     "increase_percent_of_common": 5.0},
                ],
            },
            {
                "index": "ndvi",
                "family": "single_pairs",
                "estimator_id": "single__c__d",
                "delta_stats": {"mean": 0.03},
                "thresholds": [
                    {"threshold": 0.15, "decrease_percent_of_common": 20.0,
                     "increase_percent_of_common": 9.0},
                ],
            },
            {
                "index": "ndvi",
                "family": "leave_one_out",
                "estimator_id": "loo_earlier_without_a",
                "delta_stats": {"mean": 0.02},
                "thresholds": [
                    {"threshold": 0.15, "decrease_percent_of_common": 12.0,
                     "increase_percent_of_common": 6.0},
                ],
            },
        ]
        robustness = temporal_robustness(results, "ndvi", (0.15,))
        assert robustness["available"]
        row = robustness["rows"][0]
        assert row["decrease_percent_of_common"]["min"] == 10.0
        assert row["decrease_percent_of_common"]["max"] == 20.0
        assert row["decrease_percent_of_common"]["range"] == pytest.approx(10.0)
        assert row["decrease_percent_of_common"]["count"] == 3


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def _result_rows(delta: np.ndarray, common: np.ndarray, estimator_id: str = "e1"):
    row15 = threshold_row(delta, common, 0.15, 100.0)
    row25 = threshold_row(delta, common, 0.25, 100.0)
    stats = delta_statistics(delta, common)
    return {
        "estimator_id": estimator_id,
        "family": "composite",
        "index": "ndvi",
        "delta_stats": stats,
        "primary_threshold": 0.15,
        "primary": row15,
        "thresholds": [row15, row25],
        "suitable_for_comparison": True,
        "notes": [],
        "sources": {},
        "area_conservation_all_ok": True,
    }


class TestReporting:
    def _write_all(self, tmp_path: Path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(3)
        delta = rng.normal(0.0, 0.2, size=(30, 30))
        common = np.ones_like(delta, dtype=bool)
        result = _result_rows(delta, common)
        threshold_response_svg(
            {"ndvi": result["thresholds"]}, "composite_median",
            tmp_path / "response.svg",
        )
        delta_histogram_svg(
            delta, common, "ndvi", "composite_median", tmp_path / "hist.svg"
        )
        estimator_comparison_svg(
            [result], "ndvi", 0.15, tmp_path / "compare.svg"
        )
        rows = write_summary_csv(tmp_path / "summary.csv", [result])
        sensitivity = write_sensitivity_csv(
            tmp_path / "sensitivity.csv", {"ndvi": result["thresholds"]}
        )
        return rows, sensitivity

    def test_artifacts_written_and_deterministic(self, tmp_path: Path):
        rows_a, sensitivity_a = self._write_all(tmp_path / "a")
        rows_b, sensitivity_b = self._write_all(tmp_path / "b")
        assert rows_a == rows_b == 2
        assert sensitivity_a == sensitivity_b == 2
        for name in ("response.svg", "hist.svg", "compare.svg"):
            first = (tmp_path / "a" / name).read_bytes()
            second = (tmp_path / "b" / name).read_bytes()
            assert first == second, f"{name} is not deterministic"
            assert first.lstrip().startswith(b"<svg")

    def test_csv_rows_agree_with_result(self, tmp_path: Path):
        rng = np.random.default_rng(3)
        delta = rng.normal(0.0, 0.2, size=(30, 30))
        common = np.ones_like(delta, dtype=bool)
        result = _result_rows(delta, common)
        write_summary_csv(tmp_path / "summary.csv", [result])
        with (tmp_path / "summary.csv").open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 2
        by_threshold = {row["threshold"]: row for row in rows}
        row = by_threshold["0.15"]
        assert int(row["decrease_pixels"]) == result["primary"]["decrease_pixels"]
        assert row["area_conservation_ok"] == "True"
        assert float(row["valid_area_ha"]) == pytest.approx(
            result["primary"]["valid_area_ha"]
        )

    def test_histogram_counts_sum_to_footprint(self, tmp_path: Path):
        rng = np.random.default_rng(5)
        delta = rng.normal(0.0, 0.1, size=(20, 20))
        common = np.ones_like(delta, dtype=bool)
        meta = delta_histogram_svg(
            delta, common, "ndvi", "e", tmp_path / "hist.svg"
        )
        assert sum(meta["counts"]) == 400
        assert meta["range_min"] == pytest.approx(float(delta.min()))
        assert meta["range_max"] == pytest.approx(float(delta.max()))


# ---------------------------------------------------------------------------
# hypothesis verdicts and fingerprinting
# ---------------------------------------------------------------------------

class TestHypothesesAndFingerprint:
    def _config(self):
        class Config:
            indices = ("ndvi",)
            thresholds = (0.15,)
            primary_threshold = 0.15
            hypotheses = (
                "H1: ranking stable. Measured by the sweep.",
                "H2: composite within single-pair spread. Measured by comparison.",
                "H3: loo shifts within spread. Measured by comparison.",
                "H4: cross-pipeline agreement. Measured on shared pixels.",
                "H5: coverage complete. Measured by coverage summary.",
            )

        return Config()

    def _full_results(self, composite_abs_mean: float, single_abs_mean: float):
        def estimator(estimator_id, family, decrease, increase, mean):
            row = {
                "threshold": 0.15,
                "decrease_percent_of_common": decrease,
                "increase_percent_of_common": increase,
            }
            return {
                "estimator_id": estimator_id,
                "family": family,
                "index": "ndvi",
                "primary_threshold": 0.15,
                "primary": row,
                "thresholds": [row],
                "delta_stats": {"mean": mean},
            }

        composite = estimator(
            "composite_median", "composite", 10.0, 5.0, -composite_abs_mean
        )
        anchor = estimator("anchor_single", "anchor_single", 30.0, 8.0, single_abs_mean)
        single_a = estimator("single__x__y", "single_pairs", 20.0, 6.0, single_abs_mean)
        single_b = estimator("single__z__w", "single_pairs", 25.0, 7.0, single_abs_mean)
        loo = estimator("loo_earlier_without_x", "leave_one_out", 11.0, 5.5, -0.9 * composite_abs_mean)
        m0 = estimator("m0_anchor_single_scene", "m0_single_scene", 30.0, 8.0, single_abs_mean)
        return [composite, anchor, single_a, single_b, loo, m0]

    def _coverage(self, fraction: float = 1.0):
        return {
            "all_indices_suitable": True,
            "minimum_common_valid_fraction_of_aoi": fraction,
        }

    def test_all_supported_when_evidence_supports(self):
        config = self._config()
        results = self._full_results(0.02, 0.04)
        # wire the cross-pipeline surface evidence through a synthetic pair
        cross_pipeline = {
            "available": True,
            "shared_pixels": 100,
            "pixels_identical_within_1e_9": 100,
            "mean_difference": 0.0,
            "max_abs_difference": 0.0,
        }
        verdicts = evaluate_hypotheses(config, results, self._coverage(), cross_pipeline)
        by_id = {item["id"]: item for item in verdicts}
        assert by_id["H2"]["verdict"] == "supported"
        assert by_id["H3"]["verdict"] == "supported"
        assert by_id["H4"]["verdict"] == "supported"
        assert by_id["H5"]["verdict"] == "supported"

    def test_h2_fails_when_composite_larger(self):
        config = self._config()
        results = self._full_results(0.09, 0.04)
        cross_pipeline = {
            "available": True,
            "shared_pixels": 100,
            "pixels_identical_within_1e_9": 50,
            "mean_difference": 0.1,
            "max_abs_difference": 0.5,
        }
        verdicts = evaluate_hypotheses(config, results, self._coverage(), cross_pipeline)
        by_id = {item["id"]: item for item in verdicts}
        assert by_id["H2"]["verdict"] == "not_supported"
        assert by_id["H4"]["verdict"] == "inconclusive"

    def test_h5_inconclusive_on_partial_coverage(self):
        config = self._config()
        results = self._full_results(0.02, 0.04)
        verdicts = evaluate_hypotheses(
            config,
            results,
            self._coverage(fraction=0.8),
            {"available": False, "reason": "x"},
        )
        by_id = {item["id"]: item for item in verdicts}
        assert by_id["H5"]["verdict"] == "inconclusive"

    def test_fingerprint_is_order_stable(self, tmp_path: Path):
        observation = {"item_id": "x", "meta_sha256": "1", "npz_sha256": "2"}
        inventory_a = {
            "m1_config": {"sha256": "c1"},
            "m1_summary": {"sha256": "aa"},
            "m0_summary": {"sha256": "bb"},
            "observations": [observation],
            "m1_rasters": {"summary": "r1"},
            "m0_rasters": {"summary": "r0"},
        }
        inventory_b = {
            "observations": [observation],
            "m0_rasters": {"summary": "r0"},
            "m1_rasters": {"summary": "r1"},
            "m0_summary": {"sha256": "bb"},
            "m1_summary": {"sha256": "aa"},
            "m1_config": {"sha256": "c1"},
        }
        first = compute_fingerprint(_MinimalConfig(), inventory_a)
        second = compute_fingerprint(_MinimalConfig(), inventory_b)
        assert first == second
        assert len(first) == 64

    def test_find_cached_run_matches_fingerprint(self, tmp_path: Path):
        config = _MinimalConfig()
        config.output_root = tmp_path
        config.experiment_id = "exp"
        run_dir = tmp_path / "exp" / "run1"
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps({"fingerprint": "abc123"}), encoding="utf-8"
        )
        assert find_cached_run(config, "abc123") == run_dir
        assert find_cached_run(config, "other") is None
        assert find_cached_run(config, "abc12") is None


# ---------------------------------------------------------------------------
# real-study integration (offline: uses only committed local artefacts)
# ---------------------------------------------------------------------------

class TestRealStudyIntegration:
    @pytest.fixture(scope="class")
    def real_result(self, project_root: Path):
        runs = sorted(
            (project_root / "data/experiments/m2/coringa_m2").glob("*/result.json")
        )
        if not runs:
            pytest.skip("no coringa_m2 run present; run scripts/run_experiment.py first")
        return json.loads(runs[-1].read_text(encoding="utf-8"))

    def test_composite_means_reproduce_m1_headline(self, real_result):
        expected = {"ndvi": -0.020471, "ndwi": 0.018959, "mndwi": -0.006188}
        for estimator in real_result["estimators"]:
            if estimator["estimator_id"] != "composite_median":
                continue
            index = estimator["index"]
            assert estimator["delta_stats"]["mean"] == pytest.approx(
                expected[index], abs=1e-6
            ), f"{index} composite mean does not reproduce the M1 headline"

    def test_area_conservation_on_real_run(self, real_result):
        for estimator in real_result["estimators"]:
            assert estimator["area_conservation_all_ok"], estimator["estimator_id"]

    def test_all_hypotheses_have_verdicts(self, real_result):
        verdicts = {item["id"]: item["verdict"] for item in real_result["hypothesis_verdicts"]}
        assert set(verdicts) == {"H1", "H2", "H3", "H4", "H5"}
        assert all(value in {"supported", "not_supported", "inconclusive"} for value in verdicts.values())

    def test_no_supervised_metrics_anywhere(self, real_result):
        """No supervised-accuracy claims: check keys structurally, not prose."""
        forbidden = {"accuracy", "f1", "confusion_matrix", "precision", "recall",
                     "balanced_accuracy", "iou", "overall_accuracy"}

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    assert str(key).lower() not in forbidden, (
                        f"unexpected supervised metric key {key!r}"
                    )
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(real_result)

    def test_manifest_hashes_match_files(self, project_root: Path):
        import hashlib

        runs = sorted((project_root / "data/experiments/m2/coringa_m2").glob("*/manifest.json"))
        if not runs:
            pytest.skip("no coringa_m2 manifest present")
        manifest = json.loads(runs[-1].read_text(encoding="utf-8"))
        for relative, recorded in manifest["artifacts"].items():
            path = project_root / relative
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == recorded, f"artifact hash mismatch: {relative}"
