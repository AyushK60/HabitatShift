/** Typed fetch helpers for the HabitatShift backend.
 *
 * Every function maps to a read-only backend route over stored artefacts.
 * Nothing here recomputes scientific values; on failure the caller decides
 * what honest empty/error state to render.
 */
import { load } from "js-yaml";
import type {
  ExperimentSummary,
  G0Quality,
  Georef,
  M1Summary,
  PixelSample,
  Registry,
  RoiResult,
} from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function fetchJson<T>(url: string, notFoundMessage?: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => (body as { detail?: string }).detail)
      .catch(() => undefined);
    throw new ApiError(
      response.status,
      detail ?? notFoundMessage ?? `Request failed: HTTP ${response.status}`
    );
  }
  return (await response.json()) as T;
}

export const api = {
  m1Summary: (studyId: string) =>
    fetchJson<M1Summary>(`/api/m1/study/${encodeURIComponent(studyId)}`),

  georef: (studyId: string) =>
    fetchJson<Georef>(`/api/m1/study/${encodeURIComponent(studyId)}/georef`),

  pixel: (studyId: string, lon: number, lat: number) =>
    fetchJson<PixelSample>(
      `/api/m1/study/${encodeURIComponent(studyId)}/pixel?lon=${lon}&lat=${lat}`
    ),

  roi: (
    studyId: string,
    box: { west: number; south: number; east: number; north: number }
  ) =>
    fetchJson<RoiResult>(
      `/api/m1/study/${encodeURIComponent(studyId)}/roi` +
        `?west=${box.west}&south=${box.south}&east=${box.east}&north=${box.north}`
    ),

  presentation: (studyId: string) =>
    fetchJson<G0Quality>(`/api/m1/study/${encodeURIComponent(studyId)}/presentation`),

  experimentLatest: (experimentId: string) =>
    fetchJson<ExperimentSummary>(
      `/api/experiments/${encodeURIComponent(experimentId)}/latest`,
      "No recorded experiment run for this study."
    ),

  /** Registry YAML parsed client-side; the backend serves the file verbatim. */
  registry: async (): Promise<Registry> => {
    const response = await fetch("/api/studies/registry");
    if (!response.ok) throw new ApiError(response.status, "Study registry unavailable");
    const text = await response.text();
    return load(text) as Registry;
  },
};

/** Preview file URL for an M1 relative artefact path ("data/previews/…"). */
export function m1PreviewUrl(studyId: string, relativePath: string): string {
  const name = String(relativePath || "").split("/").pop() ?? "";
  return `/files/m1/${encodeURIComponent(studyId)}/previews/${encodeURIComponent(name)}`;
}

/** Processed (raster/summary) artefact URL for an M1 relative path. */
export function m1ProcessedUrl(studyId: string, relativePath: string): string {
  const name = String(relativePath || "").split("/").pop() ?? "";
  return `/files/m1/${encodeURIComponent(studyId)}/processed/${encodeURIComponent(name)}`;
}

/** Presentation-only G0 validity asset (neutral masks, hatched overlays). */
export function g0Url(studyId: string, name: string): string {
  return `/files/g0/${encodeURIComponent(studyId)}/${encodeURIComponent(name)}`;
}
