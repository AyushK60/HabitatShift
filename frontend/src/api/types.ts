/** Shapes of the backend's stored artefacts, served verbatim.
 *
 * The backend never computes values for the viewer (see
 * docs/architecture/M3_ARCHITECTURE_DECISION.md), so these types mirror the
 * pipeline's own summaries. Fields the UI does not use are omitted.
 */

export interface Grid {
  crs: string;
  resolution_m: number;
  width: number;
  height: number;
  transform: number[];
  bounds: [number, number, number, number];
  signature: string;
  utm_epsg: number;
  pixel_area_m2: number;
}

export interface IndexStatsBlock {
  key: string;
  label: string;
  formula: string;
  bands: string[];
  native_resolution_m: number;
  analysis_resolution_m: number;
  upsampled: boolean;
  resolution_note?: string;
  value_range: [number, number];
  description: string;
  legend_breaks?: number[];
  stats: {
    min?: number;
    max?: number;
    mean: number;
    std?: number;
    valid_count?: number;
    quantiles?: { p05: number; p25: number; p50: number; p75: number; p95: number };
  };
}

export interface Period {
  period_id: "earlier" | "later";
  anchor_date: string;
  composite_method: string;
  observation_count: number;
  observation_dates: string[];
  item_ids: string[];
  valid_pixels: number;
  aoi_pixels: number;
  valid_fraction: number;
  valid_fraction_of_grid: number;
  observation_count_stats: { min: number; max: number; mean: number; median: number };
  indices: Record<string, IndexStatsBlock>;
  previews: Record<string, string>;
  stretch?: { method?: string };
}

export interface ThresholdRow {
  threshold: number;
  decrease_pixels: number;
  decrease_area_ha: number;
  stable_pixels: number;
  stable_area_ha?: number;
  increase_pixels: number;
  increase_area_ha: number;
}

export interface ChangeBlock {
  index: string;
  label: string;
  common_valid_pixels: number;
  aoi_pixels: number;
  common_valid_fraction_of_aoi: number;
  common_valid_area_ha: number;
  common_valid_area_km2: number;
  suitable_for_comparison: boolean;
  primary_threshold: number;
  primary: {
    threshold: number;
    decrease_pixels: number;
    decrease_area_ha: number;
    stable_pixels: number;
    increase_pixels: number;
    increase_area_ha: number;
    decrease_percent_of_common?: number;
    increase_percent_of_common?: number;
  };
  thresholds: ThresholdRow[];
  delta_stats: {
    mean: number;
    std?: number;
    min?: number;
    max?: number;
    valid_count: number;
    quantiles?: { p05: number; p50: number; p95: number };
  };
  pixel_area_m2: number;
  delta_preview: string;
  delta_tif?: string;
  common_valid_preview: string;
  interpretation_guardrail?: string;
  area_convention?: string;
}

export interface M1Summary {
  manifest_version: string;
  generated_utc: string;
  experiment_id: string;
  pipeline_version?: string;
  study: {
    study_id: string;
    title: string;
    study_type: string;
    question: string;
    phenomena: string[];
    limitations: string[];
    status: string;
  };
  aoi: {
    geojson: GeoJSON.FeatureCollection | GeoJSON.Feature;
    area_km2: number;
    aoi_pixels?: number;
  };
  grid: Grid;
  periods: Period[];
  indices: Record<string, IndexStatsBlock>;
  change: Record<string, ChangeBlock>;
  attribution: string | { text?: string };
  verification: { all_passed: boolean; check_count: number; failed_checks: string[] };
  limitations: string[];
}

export interface Georef {
  study_id: string;
  grid: Grid;
  bounds_utm: [number, number, number, number];
  transform: number[];
  corners_wgs84: [number, number][];
  centre_wgs84: [number, number];
}

export interface PixelPeriod {
  period_id: string;
  anchor_date: string;
  observation_count: number;
  valid_mask: number;
  valid: boolean;
  reflectance: Record<string, number> | null;
  indices: Record<string, number | null>;
}

export interface PixelSample {
  study_id: string;
  query: { lon: number; lat: number };
  utm: { x: number; y: number; epsg: number };
  pixel: { col: number; row: number };
  inside_grid: boolean;
  status: "ok" | "outside_grid";
  inside_aoi?: boolean;
  resolution_m?: number;
  periods?: PixelPeriod[];
  common_valid?: Record<string, number | boolean | null>;
  source?: string;
}

export interface RoiResult {
  study_id: string;
  query: { west: number; south: number; east: number; north: number };
  window_px: { col_off: number; row_off: number; width: number; height: number };
  source: string;
  resolution_m: number;
  pixel_area_m2: number;
  indices: Record<
    string,
    {
      common_valid_pixels: number;
      delta_stats?: {
        count: number;
        mean: number;
        p05: number;
        p50: number;
        p95: number;
      };
      primary_threshold: number;
      decrease_pixels: number;
      increase_pixels: number;
      decrease_area_ha: number;
      increase_area_ha: number;
    }
  >;
  periods: Record<string, unknown>[];
}

/* ------------------------------------------------------- presentation --- */

/** Presentation-only G0 quality payload (data/previews/g0/<study>/quality.json). */
export interface G0Quality {
  presentation_version: string;
  study_id: string;
  coverage: {
    aoi_pixels: number;
    grid_pixels: number;
    earlier_valid_pixels: number;
    later_valid_pixels: number;
    common_valid_pixels: number;
    masked_pixels: number;
    /** M4-R1 §4: pixels of the rectangular grid that lie outside the AOI.
     *  These are NOT masked-inside-AOI observations. */
    outside_aoi_pixels?: number;
    /** M4-R1 §4: AOI pixels unusable in at least one period
     *  (aoi − shared valid). Never mixed with outside-AOI pixels. */
    masked_inside_aoi_pixels?: number;
    earlier_valid_fraction_of_aoi: number;
    later_valid_fraction_of_aoi: number;
    common_valid_fraction_of_aoi: number;
    uniform_common: boolean;
    uniform_note?: string;
  };
  observation_counts?: Record<string, Record<string, number>>;
  artifact_sha256?: Record<string, string>;
}

/* ------------------------------------------------------------- registry --- */

export interface RegistryPeriod {
  label?: string;
  start: string;
  end: string;
}

export interface RegistryStudy {
  id: string;
  study_id: string;
  slug: string;
  title: string;
  study_type: string;
  status: "processed" | "feasibility" | "provisional";
  question: string;
  phenomena: string[];
  event_date?: string;
  event_mechanism?: string;
  target_periods?: Record<string, RegistryPeriod>;
  aoi: {
    crs: string;
    kind: string;
    boundary_source: string;
    bounds: { west: number; south: number; east: number; north: number };
    approx_km: string;
  };
  limitations: string[];
}

export interface Registry {
  registry_version: number;
  generated_for: string;
  common: {
    target_sensor: string;
    stac_collection: string;
    catalog: string;
    license: string;
    analysis_crs_rule: string;
  };
  studies: RegistryStudy[];
}

/* ----------------------------------------------------------- experiments --- */

export interface ExperimentSummary {
  schema: string;
  experiment_id: string;
  study_id: string;
  run_id: string;
  generated_utc: string;
  fingerprint: string;
  hypotheses: { id: string; statement: string }[];
  hypothesis_verdicts: {
    id: string;
    statement: string;
    verdict: "supported" | "not_supported" | "inconclusive";
    evidence?: Record<string, unknown>;
  }[];
  config: {
    indices: string[];
    thresholds: number[];
    primary_threshold: number;
    estimator_families: string[];
    block_size_px: number;
    bootstrap_iterations: number;
    bootstrap_seed: number;
    m1_composite_method: string;
  };
  coverage: {
    aoi_pixels: number;
    grid_pixels: number;
    aoi_area_km2: number;
    pixel_area_m2: number;
    minimum_common_valid_fraction_of_aoi: number;
    periods: {
      period_id: string;
      anchor_date: string;
      observation_count: number;
      item_ids: string[];
      dates: string[];
    }[];
  };
  verification: Record<string, unknown>;
  primary_threshold_rows: Record<
    string,
    {
      threshold: number;
      decrease_area_ha: number;
      decrease_percent_of_common: number;
      stable_area_ha: number;
      stable_percent_of_common: number;
      increase_area_ha: number;
      increase_percent_of_common: number;
      valid_area_ha: number;
      area_conservation: { ok: boolean };
    }[]
  >;
  estimators_at_primary: {
    estimator_id: string;
    family: string;
    label: string;
    index: string;
    common_valid_pixels: number;
    common_valid_fraction_of_aoi: number;
    delta_mean: number;
    delta_std: number;
    decrease_area_ha: number;
    increase_area_ha: number;
    decrease_percent_of_common: number;
    increase_percent_of_common: number;
    earlier: string[];
    later: string[];
  }[];
  temporal_robustness: Record<
    string,
    {
      available: boolean;
      rows: {
        threshold: number;
        decrease_percent_of_common: { count: number; min: number; max: number };
        increase_percent_of_common?: { count: number; min: number; max: number };
      }[];
    }
  >;
  bootstrap: Record<
    string,
    {
      enabled: boolean;
      method: string;
      block_size_px: number;
      block_size_m: number;
      blocks_total: number;
      blocks_with_valid_data: number;
      iterations_requested: number;
      iterations_used: number;
      seed: number;
      thresholds: {
        threshold: number;
        decrease_fraction: number;
        increase_fraction: number;
        decrease_area_ha: number;
        increase_area_ha: number;
        decrease_fraction_ci95: { p2_5: number; p50: number; p97_5: number };
        increase_fraction_ci95: { p2_5: number; p50: number; p97_5: number };
      }[];
      assumptions: string[];
    }
  >;
  cross_pipeline: {
    available: boolean;
    shared_pixels: number;
    pixels_identical_within_1e_9: number;
  } | null;
  guardrails: string[];
  artifacts: {
    result: string;
    manifest: string;
    estimator_thresholds_csv: string;
    threshold_sensitivity_csv: string;
    charts: Record<string, string>;
  };
}
