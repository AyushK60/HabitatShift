/** The Coringa research workstation — the primary M3 product experience.
 *
 * Designed for ~1440×900: study context bar on top, geographic workspace
 * (65–75%) plus research inspector (25–35%) in the middle, collapsible
 * analysis dock at the bottom. The whole composition fits one viewport on
 * desktop; the inspector scrolls internally and the dock expands as an
 * overlay.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  ExperimentSummary,
  G0Quality,
  Georef,
  M1Summary,
  PixelSample,
  RoiResult,
} from "../api/types";
import { ErrorNote } from "../components/ui";
import { MapCompare, type CompareMode, type RoiBox } from "../workstation/MapCompare";
import { Inspector, type InspectorTab } from "../workstation/Inspector";
import { Dock } from "../workstation/Dock";
import { layersFor, type Analysis, type LayerSpec } from "../workstation/layers";
import "../styles/workstation.css";

const STUDY_ID = "coringa_coastal";

type ModeState = Record<Analysis, CompareMode>;
const DEFAULT_MODES: ModeState = {
  historical: "swipe",
  change: "side",
  quality: "side",
};

export function WorkstationPage() {
  const [summary, setSummary] = useState<M1Summary | null>(null);
  const [georef, setGeoref] = useState<Georef | null>(null);
  const [quality, setQuality] = useState<G0Quality | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [analysis, setAnalysis] = useState<Analysis>("historical");
  const [layerIds, setLayerIds] = useState<Record<Analysis, string>>({
    historical: "true_colour",
    change: "delta_ndvi",
    quality: "qc_count_earlier",
  });
  const [modes, setModes] = useState<ModeState>(DEFAULT_MODES);
  const [split, setSplit] = useState(50);
  const [opacity, setOpacity] = useState(0.55);
  const [overlay, setOverlay] = useState(false);
  const [dockOpen, setDockOpen] = useState(false);

  const [pixel, setPixel] = useState<PixelSample | null>(null);
  const [pixelLoading, setPixelLoading] = useState(false);
  const [pixelError, setPixelError] = useState<string | null>(null);
  const [cursor, setCursor] = useState<[number, number] | null>(null);

  const [roiMode, setRoiMode] = useState(false);
  const [roiBox, setRoiBox] = useState<RoiBox | null>(null);
  const [roiResult, setRoiResult] = useState<RoiResult | null>(null);
  const [roiLoading, setRoiLoading] = useState(false);
  const [roiError, setRoiError] = useState<string | null>(null);

  const [experiment, setExperiment] = useState<ExperimentSummary | null>(null);
  const [experimentError, setExperimentError] = useState<string | null>(null);

  const markerSetterRef = useRef<((lonLat: [number, number] | null) => void) | null>(null);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("legend");

  /* ----------------------------------------------------------- loading --- */
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.m1Summary(STUDY_ID),
      api.georef(STUDY_ID),
      api.presentation(STUDY_ID).catch(() => null),
    ])
      .then(([m1, geo, g0]) => {
        if (!cancelled) {
          setSummary(m1);
          setGeoref(geo);
          setQuality(g0);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!dockOpen || experiment || experimentError) return;
    let cancelled = false;
    api
      .experimentLatest("coringa_m2")
      .then((payload) => {
        if (!cancelled) setExperiment(payload);
      })
      .catch((err: Error) => {
        if (!cancelled) setExperimentError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [dockOpen, experiment, experimentError]);

  /* -------------------------------------------------------- interactions --- */
  const analysisLayers = useMemo(() => (summary ? layersFor(analysis) : []), [analysis, summary]);
  const layer: LayerSpec | undefined =
    analysisLayers.find((item) => item.id === layerIds[analysis]) ?? analysisLayers[0];

  const handleMapClick = useCallback((lonLat: [number, number]) => {
    setPixelLoading(true);
    setPixelError(null);
    api
      .pixel(STUDY_ID, lonLat[0], lonLat[1])
      .then((sample) => {
        setPixel(sample);
        markerSetterRef.current?.(lonLat);
        setInspectorTab("pixel");
      })
      .catch((err: Error) => setPixelError(err.message))
      .finally(() => setPixelLoading(false));
  }, []);

  const handleRoiComplete = useCallback((box: RoiBox) => {
    setRoiBox(box);
    setRoiLoading(true);
    setRoiError(null);
    setRoiMode(false);
    api
      .roi(STUDY_ID, box)
      .then((result) => setRoiResult(result))
      .catch((err: Error) => setRoiError(err.message))
      .finally(() => setRoiLoading(false));
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setRoiMode(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const handleMarkerSetter = useCallback(
    (setter: (lonLat: [number, number] | null) => void) => {
      markerSetterRef.current = setter;
    },
    []
  );

  /* Early exit states -------------------------------------------------- */
  if (error) {
    return (
      <main id="main" className="workstation workstation-error">
        <ErrorNote
          message={`The study bundle could not be loaded (${error}). Start the backend API and reload.`}
        />
      </main>
    );
  }
  if (!summary || !georef || !layer) {
    return (
      <main id="main" className="workstation workstation-loading">
        <p className="mono-label">Loading the measured study bundle…</p>
      </main>
    );
  }

  const worstCommon = Math.min(
    ...Object.values(summary.change ?? {}).map((block) =>
      Number(block.common_valid_fraction_of_aoi ?? 0)
    )
  );
  const earlier = summary.periods?.[0];
  const later = summary.periods?.[1];

  return (
    <main id="main" className="workstation">
      {/* ------------------------------------------------ study context bar */}
      <header className="ws-context">
        <div className="ws-title">
          <p className="eyebrow">Study A · Coastal ecotone · Processed</p>
          <h1>{summary.study.title}</h1>
        </div>
        <dl className="ws-facts">
          <div>
            <dt>Acquisitions</dt>
            <dd>
              {earlier?.anchor_date} → {later?.anchor_date}
            </dd>
          </div>
          <div>
            <dt>Sensor</dt>
            <dd>Sentinel-2 MSI L2A</dd>
          </div>
          <div>
            <dt>Valid coverage</dt>
            <dd>{(worstCommon * 100).toFixed(1)}% of AOI common-valid</dd>
          </div>
          <div>
            <dt>Method</dt>
            <dd>
              {earlier?.composite_method} composite · masked Δ-index on one grid
            </dd>
          </div>
          <div>
            <dt>Provenance</dt>
            <dd>
              <a href={`/api/m1/study/${STUDY_ID}/manifest`} target="_blank" rel="noopener noreferrer">
                Run manifest
              </a>{" "}
              ·{" "}
              <Link to="/methods">Methods</Link>
            </dd>
          </div>
        </dl>
      </header>

      {/* ------------------------------------------------------- work row */}
      <div className="ws-row">
        {/* toolbar */}
        <div className="ws-toolbar" role="toolbar" aria-label="Comparison controls">
          <div className="control-group">
            <span className="control-label" id="ws-analysis-label">
              Analysis
            </span>
            <div className="segmented" role="group" aria-labelledby="ws-analysis-label">
              {(["historical", "change", "quality"] as Analysis[]).map((item) => (
                <button
                  key={item}
                  type="button"
                  className={analysis === item ? "is-active" : ""}
                  aria-pressed={analysis === item}
                  onClick={() => setAnalysis(item)}
                >
                  {item === "historical" ? "Historical" : item === "change" ? "Change" : "Quality"}
                </button>
              ))}
            </div>
          </div>

          {analysis === "historical" && (
            <>
              <div className="control-group">
                <span className="control-label" id="ws-view-label">
                  View
                </span>
                <div className="segmented" role="group" aria-labelledby="ws-view-label">
                  {(
                    [
                      ["side", "Side by side"],
                      ["swipe", "Swipe"],
                      ["opacity", "Opacity"],
                    ] as [CompareMode, string][]
                  ).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      className={modes.historical === value ? "is-active" : ""}
                      aria-pressed={modes.historical === value}
                      onClick={() => setModes((prev) => ({ ...prev, historical: value }))}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              {modes.historical === "opacity" && (
                <label className="control-group opacity-control">
                  <span className="control-label">Later opacity</span>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={Math.round(opacity * 100)}
                    onChange={(event) => setOpacity(Number(event.target.value) / 100)}
                  />
                  <span className="mono-label">{Math.round(opacity * 100)}%</span>
                </label>
              )}
              <button
                type="button"
                className={overlay ? "toggle-btn is-active" : "toggle-btn"}
                aria-pressed={overlay}
                onClick={() => setOverlay((prev) => !prev)}
              >
                Validity overlay
              </button>
            </>
          )}
          <span className="mono-label ws-split-tools">
            {analysis === "historical" && modes.historical === "swipe" && (
              <>
                <span className="swipe-readout-inline" aria-hidden="true">
                  {Math.round(split)}% earlier / {100 - Math.round(split)}% later
                </span>
                <button type="button" className="toggle-btn" onClick={() => setSplit(50)}>
                  Reset 50%
                </button>
              </>
            )}
          </span>
        </div>

        {/* layer groups */}
        <nav className="ws-layers" aria-label="Layer selection">
          {groupLayers(analysisLayers).map(([group, items]) => (
            <div key={group} className="layer-group">
              <span className="control-label">{group}</span>
              <div className="segmented" role="group" aria-label={group}>
                {items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={item.id === layer.id ? "is-active" : ""}
                    aria-pressed={item.id === layer.id}
                    onClick={() =>
                      setLayerIds((prev) => ({ ...prev, [analysis]: item.id }))
                    }
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* map + inspector */}
        <div className="ws-main">
          <MapCompare
            georef={georef}
            summary={summary}
            studyId={STUDY_ID}
            analysis={analysis}
            layer={layer}
            mode={modes[analysis]}
            opacity={opacity}
            overlay={overlay}
            split={split}
            onSplitChange={setSplit}
            onMapClick={handleMapClick}
            onCursorMove={setCursor}
            roiMode={roiMode}
            roiBox={roiBox}
            onRoiComplete={handleRoiComplete}
            onMarkerSetter={handleMarkerSetter}
          />
          <Inspector
            summary={summary}
            studyId={STUDY_ID}
            layer={layer}
            quality={quality}
            pixel={pixel}
            pixelError={pixelError}
            pixelLoading={pixelLoading}
            cursor={cursor}
            roiMode={roiMode}
            roiBox={roiBox}
            roiResult={roiResult}
            roiError={roiError}
            roiLoading={roiLoading}
            onToggleRoi={() => {
              setRoiMode((prev) => !prev);
              setInspectorTab("roi");
            }}
            tab={inspectorTab}
            onTabChange={setInspectorTab}
          />
        </div>
      </div>

      {/* ------------------------------------------------------------- dock */}
      <Dock
        summary={summary}
        experiment={experiment}
        experimentError={experimentError}
        open={dockOpen}
        onToggle={() => setDockOpen((prev) => !prev)}
      />
    </main>
  );
}

function groupLayers(layers: LayerSpec[]): [string, LayerSpec[]][] {
  const groups = new Map<string, LayerSpec[]>();
  for (const layer of layers) {
    const list = groups.get(layer.group) ?? [];
    list.push(layer);
    groups.set(layer.group, list);
  }
  return [...groups.entries()];
}
