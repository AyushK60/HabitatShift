/** Workstation layer registry (M4: per-study, bundle-aware).
 *
 * Layers are built from the study's recorded summary, so a layer only exists
 * when the artefact it renders actually exists.  The mapping stays explicit
 * per layer so two selections can never silently resolve to the same asset
 * (M3 brief §8 frontend audit requirement).
 *
 * All asset URLs come from an {@link AssetResolver}: live mode resolves
 * through the backend `/files` routes; showcase mode resolves bundled copies.
 */
import type { M1Summary } from "../api/types";

export type Analysis = "historical" | "change" | "quality";
export type PeriodKey = "earlier" | "later";

export interface AssetResolver {
  /** URL for a recorded preview relative path ("data/previews/..."). */
  previewUrl: (relative: string) => string;
  /** URL for a G0 presentation asset name, or null when unavailable. */
  g0Url: (name: string) => string | null;
}

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
  /** Key into the period's recorded previews map. */
  previewKey: string;
}

export interface ChangeLayer extends LayerBase {
  kind: "change";
  index: string;
}

export interface QualityLayer extends LayerBase {
  kind: "quality";
  quality: "valid" | "common" | "masked" | "count";
  period?: PeriodKey;
}

export type LayerSpec = PeriodLayer | ChangeLayer | QualityLayer;

export const NEUTRAL_VALID_SWATCHES = [
  { color: "#8fb0aa", label: "Observed valid" },
  { color: "#18272d", label: "Masked / unavailable" },
  { color: "#5f706c", label: "AOI boundary" },
];

/** Honest reading notes per index key.  The map is explicit; an index
 *  without a note fails loudly instead of borrowing another index's note. */
const INDEX_LEGEND_NOTES: Record<string, { file: string; note: string }> = {
  ndvi: {
    file: "ndvi_legend.png",
    note: "Fixed NDVI ramp for both periods, so equal values share a colour. Charcoal pixels are masked. NDVI is an observed spectral signal, not a land-cover verdict.",
  },
  ndwi: {
    file: "ndwi_legend.png",
    note: "Fixed NDWI ramp for both periods. Charcoal pixels are masked.",
  },
  mndwi: {
    file: "mndwi_legend.png",
    note: "Fixed MNDWI ramp. MNDWI uses 20 m SWIR (B11) resampled to the 10 m grid: it contains no genuine 10 m SWIR detail.",
  },
  ndsi: {
    file: "ndsi_legend.png",
    note: "Fixed NDSI ramp. NDSI (green, SWIR1) indicates snow and ice; on Sentinel-2 its formula is identical to MNDWI, so it reads snow-cover state, not liquid water. Seasonal snow evolution is a major confounder in Himalayan scenes.",
  },
  ndbi: {
    file: "ndbi_legend.png",
    note: "Fixed NDBI ramp. NDBI (SWIR1, NIR) is a candidate built-up spectral signal — NOT a building detector. Bare soil, construction sites and dry riverbeds can mimic the same signal; use the ΔNDVI and ΔNDWI layers as the counter-evidence panel.",
  },
};

const CHANGE_NOTE =
  "Diverging later − earlier map, saturated at ±0.30 index units. Ivory is no observed change, teal is lower later, copper is higher later, charcoal is outside the common-valid footprint.";

export function buildLayers(summary: M1Summary, resolver: AssetResolver): LayerSpec[] {
  const layers: LayerSpec[] = [];
  const periods = summary.periods ?? [];
  const earlier = periods[0];
  if (!earlier) return layers;

  const hasPreview = (key: string) => Boolean(earlier.previews?.[key]);

  // ------------------------------------------------------------ imagery ---
  if (hasPreview("true_colour")) {
    layers.push({
      id: "true_colour",
      label: "True colour",
      group: "Imagery",
      analysis: "historical",
      kind: "period",
      previewKey: "true_colour",
    });
  }
  if (hasPreview("false_colour")) {
    layers.push({
      id: "false_colour",
      label: "False colour",
      group: "Imagery",
      analysis: "historical",
      kind: "period",
      previewKey: "false_colour",
    });
  }

  // --------------------------------------------------------- spectral ---
  for (const key of Object.keys(earlier.indices ?? {})) {
    if (!hasPreview(key)) continue;
    const legend = INDEX_LEGEND_NOTES[key];
    layers.push({
      id: key,
      label: key.toUpperCase(),
      group: "Spectral indices",
      analysis: "historical",
      kind: "period",
      previewKey: key,
      ...(legend ? { legend } : {}),
    });
  }

  // ------------------------------------------------------------ change ---
  for (const key of Object.keys(summary.change ?? {})) {
    if (!summary.change[key]?.delta_preview) continue;
    layers.push({
      id: `delta_${key}`,
      label: `Δ ${key.toUpperCase()}`,
      group: "Change analysis",
      analysis: "change",
      kind: "change",
      index: key,
      legend: { file: "change_legend.png", note: CHANGE_NOTE },
    });
  }

  // ----------------------------------------------------------- quality ---
  if (hasPreview("valid_mask")) {
    for (const period of ["earlier", "later"] as PeriodKey[]) {
      layers.push({
        id: `qc_valid_${period}`,
        label: period === "earlier" ? "Earlier valid" : "Later valid",
        group: "Validity",
        analysis: "quality",
        kind: "quality",
        quality: "valid",
        period,
        swatches: NEUTRAL_VALID_SWATCHES,
      });
    }
  }
  const commonPreview = Object.values(summary.change ?? {})[0]?.common_valid_preview;
  if (commonPreview) {
    layers.push({
      id: "qc_valid_common",
      label: "Shared valid",
      group: "Validity",
      analysis: "quality",
      kind: "quality",
      quality: "common",
      swatches: NEUTRAL_VALID_SWATCHES,
    });
  }
  if (resolver.g0Url("masked_common.png")) {
    layers.push({
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
    });
  }
  if (hasPreview("observation_count")) {
    for (const period of ["earlier", "later"] as PeriodKey[]) {
      layers.push({
        id: `qc_count_${period}`,
        label: `Obs. count · ${period}`,
        group: "Observation support",
        analysis: "quality",
        kind: "quality",
        quality: "count",
        period,
        legend: {
          file: "observation_count_legend.png",
          note: "Discrete count of valid observations behind each composite pixel. Charcoal = 0 valid observations; copper intensity encodes count, never index change.",
        },
      });
    }
  }
  return layers;
}

export const GROUP_ORDER = [
  "Imagery",
  "Spectral indices",
  "Change analysis",
  "Validity",
  "Observation support",
];

export function groupLayers(layers: LayerSpec[]): [string, LayerSpec[]][] {
  const groups = new Map<string, LayerSpec[]>();
  for (const layer of layers) {
    const list = groups.get(layer.group) ?? [];
    list.push(layer);
    groups.set(layer.group, list);
  }
  return [...groups.entries()].sort(
    (a, b) => GROUP_ORDER.indexOf(a[0]) - GROUP_ORDER.indexOf(b[0])
  );
}

/** Resolve the image URL a layer renders. Every branch is explicit. */
export function layerImageUrl(
  layer: LayerSpec,
  summary: M1Summary,
  resolver: AssetResolver,
  period: PeriodKey
): string {
  const periods = summary.periods ?? [];
  const periodIndex = period === "earlier" ? 0 : 1;
  const periodData = periods[periodIndex];
  if (layer.kind === "period") {
    const relative = periodData?.previews?.[layer.previewKey];
    return relative ? resolver.previewUrl(relative) : "";
  }
  if (layer.kind === "change") {
    const block = summary.change?.[layer.index];
    return block?.delta_preview ? resolver.previewUrl(block.delta_preview) : "";
  }
  // Quality layers — each maps to its own recorded asset.
  switch (layer.quality) {
    case "count": {
      const relative = periodData?.previews?.observation_count;
      return relative ? resolver.previewUrl(relative) : "";
    }
    case "valid": {
      const relative = periodData?.previews?.valid_mask;
      return relative ? resolver.previewUrl(relative) : "";
    }
    case "common": {
      const relative = Object.values(summary.change ?? {})[0]?.common_valid_preview;
      return relative ? resolver.previewUrl(relative) : "";
    }
    case "masked": {
      const url = resolver.g0Url("masked_common.png");
      return url ?? "";
    }
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
    return "Neutral validity colours generated from the same valid-mask rasters the engine exported. This layer records observation validity (was there a usable, unmasked observation?), not visual image sharpness and not a general quality score. Masked pixels are never interpolated or filled.";
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
