/** Workstation layer registry.
 *
 * Maps every selectable layer to the preview artefact it actually renders.
 * The mapping is explicit per layer so two selections can never silently
 * resolve to the same asset (M3 brief §8 frontend audit requirement).
 */
import type { M1Summary } from "../api/types";
import { g0Url, m1PreviewUrl } from "../api/client";

export type Analysis = "historical" | "change" | "quality";
export type PeriodKey = "earlier" | "later";

interface LayerBase {
  id: string;
  label: string;
  group: string;
  analysis: Analysis;
  /** Legend image (relative preview name) plus an honest reading note. */
  legend?: { file: string; note: string };
  /** Swatch legend for layers without a generated ramp image. */
  swatches?: { color: string; label: string }[];
}

export interface PeriodLayer extends LayerBase {
  kind: "period";
  /** Preview file name inside period.previews, or a G0 presentation asset. */
  previewKey?: string;
  g0?: (period: PeriodKey) => string;
}

export interface ChangeLayer extends LayerBase {
  kind: "change";
  index: string;
}

export interface QualityLayer extends LayerBase {
  kind: "quality";
  quality: "valid" | "common" | "masked" | "count";
  period?: PeriodKey;
  /** Observation-count layers render the period's count preview. */
  previewKey?: string;
}

export type LayerSpec = PeriodLayer | ChangeLayer | QualityLayer;

export const NEUTRAL_VALID_SWATCHES = [
  { color: "#8fb0aa", label: "Observed valid" },
  { color: "#18272d", label: "Masked / unavailable" },
  { color: "#5f706c", label: "AOI boundary" },
];

export const LAYERS: LayerSpec[] = [
  // ------------------------------------------------------------ imagery ---
  {
    id: "true_colour",
    label: "True colour",
    group: "Imagery",
    analysis: "historical",
    kind: "period",
    previewKey: "true_colour",
  },
  {
    id: "false_colour",
    label: "False colour",
    group: "Imagery",
    analysis: "historical",
    kind: "period",
    previewKey: "false_colour",
  },
  // ------------------------------------------------------------- indices ---
  {
    id: "ndvi",
    label: "NDVI",
    group: "Spectral indices",
    analysis: "historical",
    kind: "period",
    previewKey: "ndvi",
    legend: {
      file: "ndvi_legend.png",
      note: "Fixed NDVI ramp for both periods, so equal values share a colour. Charcoal pixels are masked. NDVI is an observed spectral signal, not a land-cover verdict.",
    },
  },
  {
    id: "ndwi",
    label: "NDWI",
    group: "Spectral indices",
    analysis: "historical",
    kind: "period",
    previewKey: "ndwi",
    legend: {
      file: "ndwi_legend.png",
      note: "Fixed NDWI ramp for both periods. Charcoal pixels are masked.",
    },
  },
  {
    id: "mndwi",
    label: "MNDWI",
    group: "Spectral indices",
    analysis: "historical",
    kind: "period",
    previewKey: "mndwi",
    legend: {
      file: "mndwi_legend.png",
      note: "Fixed MNDWI ramp. MNDWI uses 20 m SWIR (B11) resampled to the 10 m grid: it contains no genuine 10 m SWIR detail.",
    },
  },
  // -------------------------------------------------------------- change ---
  {
    id: "delta_ndvi",
    label: "Δ NDVI",
    group: "Change analysis",
    analysis: "change",
    kind: "change",
    index: "ndvi",
    legend: {
      file: "change_legend.png",
      note: "Diverging later − earlier map, saturated at ±0.30 index units. Ivory is no observed change, teal is lower later, copper is higher later, charcoal is outside the common-valid footprint.",
    },
  },
  {
    id: "delta_ndwi",
    label: "Δ NDWI",
    group: "Change analysis",
    analysis: "change",
    kind: "change",
    index: "ndwi",
    legend: {
      file: "change_legend.png",
      note: "Diverging later − earlier map, saturated at ±0.30 index units. Ivory is no observed change, teal is lower later, copper is higher later.",
    },
  },
  {
    id: "delta_mndwi",
    label: "Δ MNDWI",
    group: "Change analysis",
    analysis: "change",
    kind: "change",
    index: "mndwi",
    legend: {
      file: "change_legend.png",
      note: "Diverging later − earlier map, saturated at ±0.30 index units. Ivory is no observed change, teal is lower later, copper is higher later.",
    },
  },
  // ------------------------------------------------------------- quality ---
  {
    id: "qc_valid_earlier",
    label: "Earlier valid",
    group: "Validity",
    analysis: "quality",
    kind: "quality",
    quality: "valid",
    period: "earlier",
    swatches: NEUTRAL_VALID_SWATCHES,
  },
  {
    id: "qc_valid_later",
    label: "Later valid",
    group: "Validity",
    analysis: "quality",
    kind: "quality",
    quality: "valid",
    period: "later",
    swatches: NEUTRAL_VALID_SWATCHES,
  },
  {
    id: "qc_valid_common",
    label: "Shared valid",
    group: "Validity",
    analysis: "quality",
    kind: "quality",
    quality: "common",
    swatches: NEUTRAL_VALID_SWATCHES,
  },
  {
    id: "qc_masked",
    label: "Masked / unavailable",
    group: "Validity",
    analysis: "quality",
    kind: "quality",
    quality: "masked",
    swatches: [
      { color: "#f2f0eb", label: "Inside AOI, observed" },
      { color: "#18272d", label: "Masked or outside AOI (hatched)" },
    ],
  },
  {
    id: "qc_count_earlier",
    label: "Obs. count · earlier",
    group: "Observation support",
    analysis: "quality",
    kind: "quality",
    quality: "count",
    period: "earlier",
    previewKey: "observation_count",
    legend: {
      file: "observation_count_legend.png",
      note: "Discrete count of valid observations behind each composite pixel. Charcoal = 0 valid observations; copper intensity encodes count, never index change.",
    },
  },
  {
    id: "qc_count_later",
    label: "Obs. count · later",
    group: "Observation support",
    analysis: "quality",
    kind: "quality",
    quality: "count",
    period: "later",
    previewKey: "observation_count",
    legend: {
      file: "observation_count_legend.png",
      note: "Discrete count of valid observations behind each composite pixel. Charcoal = 0 valid observations; copper intensity encodes count, never index change.",
    },
  },
];

export const GROUP_ORDER = ["Imagery", "Spectral indices", "Change analysis", "Validity", "Observation support"];

export function layersFor(analysis: Analysis): LayerSpec[] {
  return LAYERS.filter((layer) => layer.analysis === analysis);
}

/** Resolve the image URL a layer renders. Every branch is explicit. */
export function layerImageUrl(
  layer: LayerSpec,
  summary: M1Summary,
  studyId: string,
  period: PeriodKey
): string {
  const periods = summary.periods ?? [];
  const periodIndex = period === "earlier" ? 0 : 1;
  const periodData = periods[periodIndex];
  if (layer.kind === "period") {
    if (layer.g0) return layer.g0(period);
    const relative = periodData?.previews?.[layer.previewKey ?? ""];
    return relative ? m1PreviewUrl(studyId, relative) : "";
  }
  if (layer.kind === "change") {
    const block = summary.change?.[layer.index];
    return block?.delta_preview ? m1PreviewUrl(studyId, block.delta_preview) : "";
  }
  // Quality layers — each maps to its own verified asset.
  switch (layer.quality) {
    case "count": {
      const relative = periodData?.previews?.observation_count;
      return relative ? m1PreviewUrl(studyId, relative) : "";
    }
    case "valid":
      return g0Url(studyId, layer.period === "later" ? "later_valid.png" : "earlier_valid.png");
    case "common":
      return g0Url(studyId, "common_valid.png");
    case "masked":
      return g0Url(studyId, "masked_common.png");
  }
}

export function layerLegend(layer: LayerSpec): { file?: string; note: string; swatches?: { color: string; label: string }[] } {
  if (layer.legend) return { file: layer.legend.file, note: layer.legend.note };
  if (layer.swatches) return { note: defaultQualityNote(layer), swatches: layer.swatches };
  return { note: defaultQualityNote(layer) };
}

function defaultQualityNote(layer: LayerSpec): string {
  if (layer.kind === "quality") {
    if (layer.quality === "masked") {
      return "Light canvas: inside the AOI with valid observations. Hatched: masked (cloud, shadow, cirrus, saturation or nodata via the SCL layer) or outside the rectangular grid footprint. No specific cause is assigned per pixel — the SCL mask does not record one.";
    }
    return "Neutral validity colours generated from the same valid-mask rasters the engine exported. Masked pixels are never interpolated or filled.";
  }
  if (layer.kind === "period" && layer.previewKey === "false_colour") {
    return "False colour (NIR, red, green) composite; vegetation appears in red tones. Per-band 2–98 percentile stretch on valid pixels.";
  }
  if (layer.kind === "period" && layer.previewKey === "true_colour") {
    return "True-colour median composite of the period's valid observations. Per-band 2–98 percentile stretch on valid pixels.";
  }
  return "Per-band 2–98 percentile linear stretch on valid pixels.";
}

/** Short description of what a quality layer *means*, shown in the inspector. */
export function qualityExplanation(layer: LayerSpec): string {
  if (layer.kind !== "quality") return "";
  switch (layer.quality) {
    case "valid":
      return `Valid pixels for the ${layer.period} period only: pixels inside the AOI where the SCL mask found a usable observation after excluding cloud, cloud shadow, cirrus, saturation and nodata.`;
    case "common":
      return "Shared valid = pixels valid in BOTH periods. Only these pixels enter the difference maps, so the two dates are compared on identical support.";
    case "masked":
      return "Everything the analysis does NOT use: pixels masked by the SCL quality flags or lying outside the rectangular raster-grid footprint but inside the map frame.";
    case "count":
      return `Observation count for the ${layer.period} composite: how many valid acquisitions contribute at this pixel. Unlike the validity maps, this layer has genuine per-pixel variation (histogram in the analysis dock).`;
  }
}

export function periodLabel(period: PeriodKey): string {
  return period === "earlier" ? "Earlier" : "Later";
}
