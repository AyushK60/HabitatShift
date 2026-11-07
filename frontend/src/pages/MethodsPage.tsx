/** Methods & exports (M3-G4).
 *
 * Documents what the pipeline actually does — the same statements as
 * docs/SCIENCE_PROTOCOL.md and the M1/M2 manifests — with provenance
 * exports resolved from the live backend, and a strict separation between
 * project-generated measurements, external references, interpretations and
 * limitations.
 */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { M1Summary, Registry } from "../api/types";
import { ErrorNote } from "../components/ui";
import "../styles/methods.css";

const METHODS = [
  {
    title: "Sentinel-2 L2A source data",
    body: [
      "All observations are Copernicus Sentinel-2 MSI Level-2A products: top-of-atmosphere reflectance corrected to surface reflectance by ESA's Sen2Cor, distributed as Cloud-Optimised GeoTIFFs. The catalogue is the Element 84 Earth Search STAC API (sentinel-2-l2a collection) on AWS Open Data; scenes are read as windowed COG byte ranges, never whole-scene downloads.",
      "The analysis grid is a single co-registered window (one grid signature per study) so every layer, mask and difference map refers to exactly the same pixel centres. For the Coringa study the grid is EPSG:32644 at 10 m.",
    ],
  },
  {
    title: "STAC-based scene discovery",
    body: [
      "Candidate scenes are queried per period from the STAC catalogue with the AOI as the intersection geometry and the target date windows as the temporal filter. Every accepted scene ID is written to the run manifest, together with its acquisition datetime and cloud metadata, so any image in the product can be traced back to an exact catalogue item.",
    ],
  },
  {
    title: "Surface reflectance processing",
    body: [
      "Bands B02 (blue), B03 (green), B04 (red) and B08 (NIR) are read at their native 10 m; B11 (SWIR1) and the SCL classification layer are native 20 m and resampled on read — bilinear for reflectance, nearest-neighbour for SCL. The 20 m origin of SWIR is documented wherever MNDWI appears: MNDWI contains no genuine 10 m SWIR detail.",
      "Reflectance values are stored as float32 surface reflectance (0–1 scale). No atmospheric correction is applied beyond the L2A baseline; no per-scene histogram matching is performed between dates.",
    ],
  },
  {
    title: "Cloud and quality masking",
    body: [
      "The SCL layer classifies each pixel; cloud, cloud shadow, cirrus, saturated and nodata classes are excluded before any composite or index is computed. The per-pixel valid mask is carried through every product, and masked pixels are never interpolated, filled or averaged over. Validity is computed per period and intersected (shared valid) before any two dates are compared.",
      "The SCL flags do not record a per-pixel masking cause beyond the class itself, so the product never claims a specific cause (e.g. 'cloud on 2025-03-25 at this pixel') that the data does not state.",
    ],
  },
  {
    title: "Composite generation",
    body: [
      "Each period's valid observations are combined into a median composite (the M1 configuration for Coringa uses the median of up to three acquisitions). The observation count per pixel is exported alongside the composite, because a median of one observation is not the same evidence as a median of three — the quality layers expose this honestly.",
    ],
  },
  {
    title: "Spectral indices: NDVI, NDWI, MNDWI",
    body: [
      "Index formulas on surface reflectance: NDVI = (B08 − B04) / (B08 + B04); NDWI = (B03 − B08) / (B03 + B08); MNDWI = (B03 − B11) / (B03 + B11). Each index uses one fixed colour ramp for both periods so equal values share a colour; legends are generated from the same ramp that renders the pixels.",
      "NDVI is an observed vegetation-signal proxy, not proof of ecological health; NDWI/MNDWI are observed water-signal proxies, not hydrological measurements.",
    ],
  },
  {
    title: "Change estimation",
    body: [
      "The change map is the per-pixel difference (later − earlier) of an index, restricted to the shared-valid footprint and presented with a diverging legend saturated at ±0.30 index units. Candidate decrease/increase areas are reported at stated absolute thresholds; the primary threshold for Coringa is ±0.15, and the measured threshold sweep covers 0.05–0.25.",
      "Thresholded areas are 'candidate spectral change', never verified land-cover change: no independent reference labels exist for this study.",
    ],
  },
  {
    title: "Threshold sensitivity",
    body: [
      "The M2 experiment re-measures candidate change areas across the recorded threshold sweep with an area-conservation check (decrease + stable + increase must equal the footprint exactly). The sweep is monotone by construction; the recorded response is published as a chart and CSV.",
    ],
  },
  {
    title: "Observation-selection robustness",
    body: [
      "Three estimator families quantify how the answer depends on which observations are used: composite (median/mean of all valid scenes), single scene pairs, and leave-one-out variants. The spread of measured change areas across estimators is reported as an observation-selection effect, not as an error bar.",
    ],
  },
  {
    title: "Uncertainty analysis",
    body: [
      "A spatial block bootstrap (15 px blocks, 200 resamples, fixed seed) resamples the AOI's blocks and recomputes change-area fractions. The reported 95% ranges describe resampling variability for this AOI and grid; they are not population confidence intervals and do not transfer to other areas or dates.",
    ],
  },
  {
    title: "Verification & audit",
    body: [
      "The engine verifies itself after every run (26 checks for the Coringa M1 study: grid geometry, NDVI re-computation within tolerance, mask agreement, area cross-checks). An independent audit script re-derives key statistics directly from the rasters. The M2 run records its own verification plus a cross-pipeline anchor against the M0 implementation.",
    ],
  },
];

export function MethodsPage() {
  const [summary, setSummary] = useState<M1Summary | null>(null);
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.m1Summary("coringa_coastal"), api.registry()])
      .then(([m1, reg]) => {
        if (!cancelled) {
          setSummary(m1);
          setRegistry(reg);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const attribution =
    typeof summary?.attribution === "string" ? summary.attribution : summary?.attribution?.text;

  return (
    <main id="main" className="methods-page">
      <header className="methods-head">
        <p className="eyebrow">Methods &amp; exports</p>
        <h1>How HabitatShift turns open satellite scenes into checkable evidence</h1>
        <p className="methods-lede">
          This page documents the pipeline as it is actually implemented — the
          same statements recorded in the run manifests — and separates
          project-generated measurements from external references,
          interpretations and limitations.
        </p>
      </header>

      {error && (
        <ErrorNote message={`Live provenance values could not be loaded (${error}); the methods text below is static documentation.`} />
      )}

      <section className="methods-grid" aria-label="Method steps">
        {METHODS.map((method, index) => (
          <article key={method.title} className="method-entry">
            <h2>
              <span className="method-number">{String(index + 1).padStart(2, "0")}</span>
              {method.title}
            </h2>
            {method.body.map((paragraph) => (
              <p key={paragraph.slice(0, 32)}>{paragraph}</p>
            ))}
          </article>
        ))}
      </section>

      <section className="methods-sep" aria-labelledby="limits-title">
        <h2 id="limits-title">Limitations stated by the study itself</h2>
        {summary && (
          <>
            <ul className="methods-list">
              {(summary.study.limitations ?? []).map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
              {(summary.limitations ?? []).map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
            <p className="methods-note">
              Recorded interpretation guardrails travel with every change layer
              in the workstation: {Object.values(summary.change ?? {})[0]?.interpretation_guardrail ??
                "see the study summary for the recorded guardrail text."}
            </p>
          </>
        )}
      </section>

      <section className="methods-sep" aria-labelledby="vocab-title">
        <h2 id="vocab-title">Status vocabulary used across the product</h2>
        <p className="methods-note">
          A study is called <strong>Processed</strong> only when a verified
          bundle of real processed artefacts exists in the repository.{" "}
          <strong>Feasibility</strong> means an M0 data-availability
          investigation was recorded and no processing has happened.{" "}
          <strong>Planned</strong> means the study is registered with an AOI and
          question but processing belongs to a later milestone. The gallery
          statuses come from <code>studies/registry.yaml</code> served verbatim
          by the API
          {registry ? ` (version ${registry.registry_version}, ${registry.common.target_sensor}).` : "."}
        </p>
      </section>

      <section className="methods-sep" aria-labelledby="m4-title">
        <h2 id="m4-title">M4 — five studies, radiometry honesty and the portable showcase</h2>
        <p className="methods-note">
          M4 extends the pipeline from the Coringa reference to six
          investigations: Chilika Lake (matched dry-season and matched
          post-monsoon experiments, read together as the documented
          seasonal-sensitivity investigation), a Western Ghats forest block
          (Supa taluk, Uttara Kannada, with Copernicus GLO-30 DEM terrain
          context), two separate Himalayan event investigations (the 8 July
          2025 Purepu lake drainage — PARTIAL, seasonal pair only — and the
          26 August 2026 Langtang Lirung rock–ice collapse), and the Kathmandu
          Valley built-up pilot (NDBI as a candidate signal with an explicit
          no-labels guardrail). Scene selections and per-window validity
          measurements are recorded in <code>docs/M4_FEASIBILITY.md</code>.
        </p>
        <p className="methods-note">
          <strong>Radiometry.</strong> During M4 processing it was found that
          the 2025 Earth Search reprocessing stores baseline-05.11 DNs
          <em> without</em> the baked +1000 BOA offset while item metadata still
          declares −0.1 (<code>earthsearch:boa_offset_applied: false</code>).
          Applying the declared offset produced physically impossible negative
          reflectance. The engine now validates every observation's applied
          transform empirically: any window whose mean reflectance falls below
          the physical floor retries the scale-only convention and records the
          full evidence in the manifest; if neither convention is plausible the
          observation is refused. All M4 results use the corrected convention;
          the frozen Coringa M0–M2 artefacts were checked and were never
          affected (their 2025 scenes carry the offset-applied flag and were
          processed scale-only throughout).
        </p>
        <p className="methods-note">
          <strong>Portable showcase.</strong> Each completed study has a
          checksummed bundle (<code>frontend/public/studies/&lt;study_id&gt;/</code>)
          containing its recorded summaries, georeferenced grid placement,
          preview rasters, distilled chart series, quality information,
          limitations and provenance. The workstation renders bundles as
          static files, so maps, layers and the interactive charts work with
          no backend. Live-only features (pixel probe, ROI measurement,
          validity overlays) are labelled as such and activate only when the
          backend is serving the study's frozen outputs.
        </p>
        <p className="methods-note">
          <strong>Interactive charts.</strong> Charts snap to the nearest
          recorded data point on hover — interpolated values are never shown —
          with exact values, units, valid-pixel denominators, a plain-language
          interpretation and an explicit can/cannot-conclude note. Point
          pinning, touch tapping and full keyboard navigation (arrow keys,
          Enter to pin, Escape to dismiss) are supported, and a visually hidden
          table mirrors every recorded value for screen readers.
        </p>
      </section>

      <section className="methods-sep" aria-labelledby="exports-title">
        <h2 id="exports-title">Methodology &amp; provenance exports</h2>
        <ul className="methods-exports">
          <li>
            <a href="/api/m1/study/coringa_coastal/manifest" target="_blank" rel="noopener noreferrer">
              M1 run manifest — scenes, dates, grid, formulas, hashes
            </a>
          </li>
          <li>
            <a href="/api/m1/study/coringa_coastal" target="_blank" rel="noopener noreferrer">
              M1 study summary — statistics as the engine wrote them
            </a>
          </li>
          <li>
            <a href="/api/experiments/coringa_m2/latest" target="_blank" rel="noopener noreferrer">
              M2 experiment summary — thresholds, estimators, bootstrap
            </a>
          </li>
          <li>
            <a href="/studies/registry.json" target="_blank" rel="noopener noreferrer">
              Static study registry (bundle copy, verbatim from YAML)
            </a>
          </li>
          <li>
            <a href="/studies/chilika_wetland/bundle.json" target="_blank" rel="noopener noreferrer">
              Example M4 showcase bundle — Chilika (both experiments, checksums)
            </a>
          </li>
          <li>
            <a href="/api/studies/registry" target="_blank" rel="noopener noreferrer">
              Study registry (YAML, verbatim)
            </a>
          </li>
          <li>
            <a href="/api/m1/study/coringa_coastal/presentation" target="_blank" rel="noopener noreferrer">
              G0 presentation assets record (validity previews + SHA-256)
            </a>
          </li>
        </ul>
        <p className="methods-note">
          Every exported value is a stored artefact. Nothing on this site
          computes a new scientific number except the explicitly labelled
          full-resolution pixel and ROI lookups, which read the same frozen
          rasters.
        </p>
      </section>

      <section className="methods-sep" aria-labelledby="attribution-title">
        <h2 id="attribution-title">Attribution &amp; licensing</h2>
        <p className="methods-note">
          {attribution ??
            "Contains modified Copernicus Sentinel data, processed by ESA."}{" "}
          Sentinel-2 data is free and open with attribution (ESA Copernicus).
          Catalogue services by Element 84 Earth Search (AWS Open Data). The
          product's own code, pipeline and documentation are part of the
          HabitatShift research repository.
        </p>
        <p className="methods-note">
          External scientific references (e.g. the NDVI formula, Rouse et al.
          1974) are cited where used; any interpretation offered in the product
          is labelled as interpretation, and the limitations above are part of
          the record, not a disclaimer appended after the fact.
        </p>
      </section>
    </main>
  );
}
