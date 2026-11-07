/** Portable showcase bundles (M4-G4).
 *
 * A bundle is a self-contained snapshot of one study's recorded outputs,
 * built by `scripts/build_showcase_bundles.py` from the same frozen artefacts
 * the backend serves.  Loading a bundle needs no Python process: the browser
 * fetches static files from `/studies/<study_id>/`.
 *
 * Nothing here computes scientific values.  The adapter reshapes recorded
 * data into the same shapes the backend API returns (M1Summary / Georef /
 * G0Quality) so the workstation renders identically in showcase and live
 * modes, and rewrites preview paths to their bundled copies.
 */
import type { G0Quality, Georef, M1Summary, Period } from "./types";

/* ------------------------------------------------------------ bundle types */

export interface BundleExperiment {
  experiment_id: string;
  label: string | null;
  config_path: string;
  config_sha256: string;
  summary_sha256: string;
  summary: M1Summary;
}

export interface BundleThresholdPoint {
  threshold: number;
  decrease_percent_of_common: number;
  increase_percent_of_common: number;
  decrease_area_ha?: number;
  increase_area_ha?: number;
  valid_pixels: number;
}

export interface BundleThresholdSeries {
  index: string;
  label?: string;
  estimator_id?: string;
  primary_threshold?: number | null;
  common_valid_pixels?: number;
  interpretation_guardrail?: string | null;
  points: BundleThresholdPoint[];
}

export interface BundleEstimatorPoint {
  estimator_id: string;
  family: string;
  index: string;
  label: string;
  delta_mean: number | null;
  delta_std: number | null;
  decrease_percent_of_common: number | null;
  primary_threshold: number | null;
  common_valid_pixels: number;
}

export interface BundleBootstrapCI {
  p2_5: number;
  p50: number;
  p97_5: number;
}

export interface BundleBootstrapThreshold {
  threshold: number;
  decrease_fraction: number;
  increase_fraction: number;
  decrease_fraction_ci95: BundleBootstrapCI;
  increase_fraction_ci95: BundleBootstrapCI;
}

export interface BundleBootstrap {
  method: string;
  block_size_px: number;
  iterations_used: number;
  delta_mean_ci95: BundleBootstrapCI;
  thresholds: BundleBootstrapThreshold[];
  assumptions: string[];
}

export interface BundleCharts {
  threshold_series: BundleThresholdSeries[];
  period_index_means: {
    period_id: string;
    anchor_date: string;
    index: string;
    mean: number;
    valid_fraction: number;
    valid_count: number;
  }[];
  delta_stats: {
    index: string;
    mean: number | null;
    std: number | null;
    quantiles?: { p05?: number; p50?: number; p95?: number };
    common_valid_pixels: number;
  }[];
}

export interface BundleM2Charts {
  source: { result_path: string; result_sha256: string; run_id: string; fingerprint: string };
  hypothesis_verdicts: unknown[];
  threshold_series: BundleThresholdSeries[];
  estimator_comparison: BundleEstimatorPoint[];
  bootstrap: Record<string, BundleBootstrap>;
  interpretation_guardrails: string[];
}

export interface BundleEventObservation {
  date: string;
  relative_days: number;
  experiment_id?: string;
  period_id?: string;
  item_id?: string;
  in_aoi_valid_fraction?: number;
  status?: string;
}

export interface BundleEvent {
  event_date: string;
  event_mechanism?: string;
  external_references: { title: string; role: string }[];
  observations_relative_to_event: BundleEventObservation[];
  known_unprocessed_observations: BundleEventObservation[];
  observation_gaps: { statement: string }[];
  insar_note: string;
}

export interface BundleDemContext {
  available: boolean;
  collection?: string;
  item_id?: string;
  elevation_min_m?: number;
  elevation_max_m?: number;
  elevation_mean_m?: number;
  role?: string;
  license?: string;
  reason?: string;
}

export interface StudyBundle {
  schema: string;
  bundle_version: number;
  study_id: string;
  /** "partial" marks studies the feasibility review restricted. */
  evidence_status: "processed" | "partial";
  study: M1Summary["study"] & {
    id: string;
    slug: string;
    aoi: {
      crs: string;
      kind: string;
      boundary_source: string;
      bounds: { west: number; south: number; east: number; north: number };
      approx_km: string;
    };
    target_periods?: unknown;
  };
  interpretation: {
    can_conclude: string[];
    cannot_conclude: string[];
    note?: string;
  };
  attribution: string;
  georef: {
    native_crs: string;
    native_bounds: number[];
    native_transform: number[];
    shape: [number, number];
    resolution_m: [number, number];
    nodata: number | null;
    lonlat_bounds: [number, number, number, number];
    lonlat_corners: {
      upper_left: [number, number];
      upper_right: [number, number];
      lower_left: [number, number];
      lower_right: [number, number];
    };
  };
  experiments: BundleExperiment[];
  charts: BundleCharts;
  assets: Record<string, { path: string; sha256: string }>;
  dem_context?: BundleDemContext;
  event?: BundleEvent;
  sources?: {
    registry: { path: string; sha256: string };
    m2_experiment?: BundleM2Charts | null;
  };
  bundle_sha256_inputs?: { previews: string[] };
}

/* ---------------------------------------------------------------- loading */

export async function loadStudyBundle(studyId: string): Promise<StudyBundle> {
  const response = await fetch(`/studies/${encodeURIComponent(studyId)}/bundle.json`);
  if (!response.ok) {
    throw new Error(
      response.status === 404
        ? `No showcase bundle exists for "${studyId}".`
        : `Bundle request failed: HTTP ${response.status}`
    );
  }
  return (await response.json()) as StudyBundle;
}

export async function loadRegistryJson(): Promise<import("./types").Registry> {
  const response = await fetch("/studies/registry.json");
  if (!response.ok) throw new Error("Static study registry unavailable");
  return (await response.json()) as import("./types").Registry;
}

/* --------------------------------------------------------------- adapters */

/** Showcase asset resolver: bundled preview copies, no backend. */
export function bundleResolver(studyId: string, bundle: StudyBundle) {
  const byName = new Map<string, string>();
  for (const [key, asset] of Object.entries(bundle.assets)) {
    const name = key.split("/").pop() ?? key;
    if (!byName.has(name)) byName.set(name, asset.path);
  }
  return {
    previewUrl: (relative: string) => {
      const value = String(relative || "");
      if (value.startsWith("previews/")) return bundlePreviewUrl(studyId, value);
      const name = value.split(/[/\\]/).pop() ?? "";
      const path = byName.get(name);
      if (!path) {
        if (import.meta.env.DEV) console.warn(`bundle asset not found: ${name}`);
        return "";
      }
      return bundlePreviewUrl(studyId, path);
    },
    // G0 presentation assets exist only for the Coringa reference study;
    // studies without them simply omit the layers/overlays that need them.
    g0Url: () => null,
  };
}

/** Live asset resolver: the backend's read-only /files routes. */
export function liveResolver(studyId: string) {
  return {
    previewUrl: (relative: string) => {
      const name = String(relative || "").split(/[/\\]/).pop() ?? "";
      return `/files/m1/${encodeURIComponent(studyId)}/previews/${encodeURIComponent(name)}`;
    },
    g0Url: (name: string) =>
      `/files/g0/${encodeURIComponent(studyId)}/${encodeURIComponent(name)}`,
  };
}


/** Bundle asset URL (previews are copied flat under the bundle directory). */
export function bundlePreviewUrl(studyId: string, assetPath: string): string {
  return `/studies/${encodeURIComponent(studyId)}/${assetPath}`;
}

/** Rewrite recorded `data/previews/...` paths to their bundled copies. */
function rebasedPreview(studyId: string, bundle: StudyBundle, relative: string): string {
  const name = String(relative || "").split(/[/\\]/).pop() ?? "";
  // Preview file names are unique within an experiment; find the asset that
  // carries the file name (the bundle may hold several experiments).
  for (const experiment of bundle.experiments) {
    const direct = bundle.assets[`${experiment.experiment_id}/${name}`];
    if (direct) return bundlePreviewUrl(studyId, direct.path);
  }
  if (import.meta.env.DEV) {
    console.warn(`bundle asset not found: ${name}`);
  }
  return "";
}

/** The bundle's M1 summary, with preview paths pointed at the bundled files. */
export function bundleSummary(studyId: string, bundle: StudyBundle, experimentIndex = 0): M1Summary {
  const experiment = bundle.experiments[experimentIndex] ?? bundle.experiments[0];
  const summary = experiment.summary;
  const periods = summary.periods.map((period) => ({
    ...period,
    previews: Object.fromEntries(
      Object.entries(period.previews ?? {}).map(([key, relative]) => [
        key,
        rebasedPreview(studyId, bundle, relative),
      ])
    ),
  })) as Period[];
  const change = Object.fromEntries(
    Object.entries(summary.change ?? {}).map(([key, block]) => [
      key,
      {
        ...block,
        delta_preview: rebasedPreview(studyId, bundle, block.delta_preview),
        common_valid_preview: rebasedPreview(studyId, bundle, block.common_valid_preview),
      },
    ])
  );
  return {
    ...summary,
    study: {
      ...bundle.study,
    },
    periods,
    change,
  };
}

/** Georef in the exact shape the backend `/georef` route returns. */
export function bundleGeoref(studyId: string, bundle: StudyBundle): Georef {
  const corners = bundle.georef.lonlat_corners;
  const { lonlat_bounds } = bundle.georef;
  return {
    study_id: studyId,
    grid: bundle.experiments[0].summary.grid,
    bounds_utm: bundle.georef.native_bounds as Georef["bounds_utm"],
    transform: bundle.georef.native_transform,
    corners_wgs84: [
      corners.upper_left,
      corners.upper_right,
      corners.lower_right,
      corners.lower_left,
    ],
    centre_wgs84: [
      (lonlat_bounds[0] + lonlat_bounds[2]) / 2,
      (lonlat_bounds[1] + lonlat_bounds[3]) / 2,
    ],
  };
}

/** Quality coverage derived from the recorded summary (same denominators the
 *  G0 presentation uses).  Shared-valid is taken from the change blocks, so
 *  it is the footprint the difference maps actually use. */
export function qualityFromSummary(summary: M1Summary): G0Quality {
  const periods = summary.periods ?? [];
  const earlier = periods[0];
  const later = periods[1];
  const changeBlocks = Object.values(summary.change ?? {});
  const common = changeBlocks[0]?.common_valid_pixels ?? 0;
  const aoi = Number(summary.aoi?.aoi_pixels ?? earlier?.aoi_pixels ?? 0);
  const gridPixels = (summary.grid?.width ?? 0) * (summary.grid?.height ?? 0);
  const uniform =
    earlier?.valid_pixels === common && later?.valid_pixels === common;
  return {
    presentation_version: "bundle-derived/1",
    study_id: summary.study.study_id,
    coverage: {
      aoi_pixels: aoi,
      grid_pixels: gridPixels || aoi,
      earlier_valid_pixels: earlier?.valid_pixels ?? 0,
      later_valid_pixels: later?.valid_pixels ?? 0,
      common_valid_pixels: common,
      masked_pixels: Math.max(0, aoi - common),
      earlier_valid_fraction_of_aoi: earlier?.valid_fraction ?? 0,
      later_valid_fraction_of_aoi: later?.valid_fraction ?? 0,
      common_valid_fraction_of_aoi: changeBlocks[0]?.common_valid_fraction_of_aoi ?? 0,
      uniform_common: uniform,
      uniform_note: uniform
        ? "Derived from the recorded rasters: every AOI pixel is a usable observation in both periods, so the shared-valid footprint equals each period's valid footprint."
        : undefined,
    },
  };
}
