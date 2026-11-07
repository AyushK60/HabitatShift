/** The study research workstation — now the multi-study showcase (M4-G4).
 *
 * Every completed study renders from its portable bundle: the same recorded
 * artefacts the backend serves, loaded as static files so the maps, layers,
 * quality views and interactive charts work with no Python process running.
 *
 * Live enhancement: when the analysis backend is reachable AND the study has
 * frozen M1 outputs (today: the Coringa reference), the pixel probe, ROI
 * measurement and G0 validity overlays activate on top of the same bundle
 * numbers. Without the backend those controls degrade to honest notes — the
 * showcase itself never depends on them.
 *
 * Designed for ~1440×900: study context bar on top, geographic workspace
 * (65–75%) plus research inspector (25–35%) in the middle, collapsible
 * analysis dock at the bottom.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import {
  bundleGeoref,
  bundleResolver,
  bundleSummary,
  findingsToFeatureCollection,
  liveResolver,
  loadStudyBundle,
  qualityFromSummary,
  type BundleFindings,
  type StudyBundle,
} from "../api/bundle";
import type { Georef, M1Summary, PixelSample, RoiResult } from "../api/types";
import { ErrorNote } from "../components/ui";
import { MapCompare, type CompareMode, type RoiBox } from "../workstation/MapCompare";
import { Inspector, type InspectorTab } from "../workstation/Inspector";
import { Dock } from "../workstation/Dock";
import { StudyPicker } from "../workstation/StudyPicker";
import { buildLayers, type Analysis, type AssetResolver, type LayerSpec } from "../workstation/layers";
import { loadSelectionPolicy, type SelectionPolicy } from "../evidence/adapter";
import "../styles/workstation.css";

type ModeState = Record<Analysis, CompareMode>;
const DEFAULT_MODES: ModeState = {
  historical: "swipe",
  change: "side",
  quality: "side",
  what_changed: "side",
};

function defaultLayerId(layers: LayerSpec[], analysis: Analysis): string {
  // The "What Changed?" view composites on the Δ-index layers (the change
  // pool), so its default comes from there.
  const pool =
    analysis === "what_changed"
      ? layers.filter((layer) => layer.analysis === "change")
      : layers.filter((layer) => layer.analysis === analysis);
  if (analysis === "historical") {
    return (pool.find((l) => l.id === "true_colour") ?? pool[0])?.id ?? "";
  }
  return pool[0]?.id ?? "";
}

function useBackendReachable(): boolean {
  const [reachable, setReachable] = useState(false);
  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 2500);
    fetch("/api/studies/registry", { signal: controller.signal })
      .then((response) => {
        if (!cancelled) setReachable(response.ok);
      })
      .catch(() => {
        if (!cancelled) setReachable(false);
      })
      .finally(() => window.clearTimeout(timer));
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);
  return reachable;
}

const LIVE_STUDIES = new Set(["coringa_coastal"]);

export function WorkstationPage() {
  const params = useParams();
  const studyId = params.studyId;

  /* M4-R1 §2: /workstation without a study id presents the study-selection
   * experience instead of forcing Coringa. Direct study URLs still render
   * the workstation directly. The key forces a full remount on study
   * switches: view/analysis/selection state must never leak between
   * investigations (the suite caught cross-study asset 404s from the
   * one-frame stale render without it). */
  if (!studyId) {
    return <StudyPicker />;
  }

  return <WorkstationForStudy key={studyId} studyId={studyId} />;
}

function WorkstationForStudy({ studyId }: { studyId: string }) {
  const backendReachable = useBackendReachable();
  const live = backendReachable && LIVE_STUDIES.has(studyId);

  const [bundle, setBundle] = useState<StudyBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [experimentIndex, setExperimentIndex] = useState(0);

  const [analysis, setAnalysis] = useState<Analysis>("historical");
  const [layerIds, setLayerIds] = useState<Record<Analysis, string>>({
    historical: "true_colour",
    change: "",
    quality: "",
    what_changed: "",
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

  const markerSetterRef = useRef<((lonLat: [number, number] | null) => void) | null>(null);
  const fitRef = useRef<(() => void) | null>(null);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("legend");

  /* ----------------------------------------------------------- loading --- */
  useEffect(() => {
    let cancelled = false;
    setBundle(null);
    setError(null);
    setExperimentIndex(0);
    setDockOpen(false);
    setPixel(null);
    setPixelError(null);
    setRoiResult(null);
    setRoiError(null);
    setRoiMode(false);
    setRoiBox(null);
    setSelectedEvidenceId(null);
    setFindingsOverlay(true);
    loadStudyBundle(studyId)
      .then((payload) => {
        if (!cancelled) setBundle(payload);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [studyId]);

  const summary: M1Summary | null = useMemo(
    () => (bundle ? bundleSummary(studyId, bundle, experimentIndex, !live) : null),
    [bundle, studyId, experimentIndex, live]
  );
  const georef: Georef | null = useMemo(
    () => (bundle ? bundleGeoref(studyId, bundle) : null),
    [bundle, studyId]
  );
  const resolver: AssetResolver = useMemo(
    () => (bundle ? (live ? liveResolver(studyId) : bundleResolver(studyId, bundle)) : null)!,
    [bundle, live, studyId]
  );

  const layers = useMemo(
    () => (summary && resolver ? buildLayers(summary, resolver) : []),
    [summary, resolver]
  );

  useEffect(() => {
    if (!layers.length) return;
    setLayerIds((prev) => {
      const next = { ...prev };
      for (const key of ["historical", "change", "quality", "what_changed"] as Analysis[]) {
        const poolAnalysis = key === "what_changed" ? "change" : key;
        if (
          !next[key] ||
          !layers.some((l) => l.id === next[key] && l.analysis === poolAnalysis)
        ) {
          next[key] = defaultLayerId(layers, key);
        }
      }
      return next;
    });
  }, [layers]);

  const quality = useMemo(() => (summary ? qualityFromSummary(summary) : null), [summary]);

  /* -------------------------------------------------------- interactions --- */
  // The "What Changed?" view composites on the Δ-index (change) layers.
  const layerPoolAnalysis: Analysis | "change" =
    analysis === "what_changed" ? "change" : analysis;
  const analysisLayers = useMemo(
    () => layers.filter((layer) => layer.analysis === layerPoolAnalysis),
    [layers, layerPoolAnalysis]
  );
  const layer: LayerSpec | undefined =
    analysisLayers.find((item) => item.id === layerIds[analysis]) ?? analysisLayers[0];

  /* ------------------------------------- What Changed? state (M4-R1 §15) --- */
  const [selectionPolicy, setSelectionPolicy] = useState<SelectionPolicy | null>(null);
  useEffect(() => {
    let cancelled = false;
    loadSelectionPolicy().then((policy) => {
      if (!cancelled) setSelectionPolicy(policy);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  const [findingsOverlay, setFindingsOverlay] = useState(true);
  // Selection carries the stable content-derived evidence_id (M4-R3 §2),
  // shared verbatim by the Explore card, Research Mode record and map overlay.
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const findings: BundleFindings | null =
    bundle?.experiments[experimentIndex]?.findings ?? null;
  const findingsFC = useMemo(
    () => (findings ? findingsToFeatureCollection(findings) : null),
    [findings]
  );
  const focusRef = useRef<((geometry: GeoJSON.Geometry) => void) | null>(null);
  const handleFocusSetter = useCallback((focus: (geometry: GeoJSON.Geometry) => void) => {
    focusRef.current = focus;
  }, []);
  const handleFindingSelect = useCallback(
    (evidenceId: string | null) => {
      setSelectedEvidenceId(evidenceId);
      if (evidenceId && findings) {
        const finding = findings.findings.find((item) => item.evidence_id === evidenceId);
        if (finding) focusRef.current?.(finding.geometry_wgs84);
      }
      setInspectorTab("findings");
    },
    [findings]
  );
  const handleOpenResearch = useCallback(() => setInspectorTab("evidence"), []);

  const handleMapClick = useCallback(
    (lonLat: [number, number]) => {
      if (!live) {
        setPixelError(
          "Live pixel sampling needs the analysis backend (run `python -m uvicorn backend.app.api.app:app --port 8098`). The showcase bundle itself does not include per-pixel sampling."
        );
        setInspectorTab("pixel");
        return;
      }
      setPixelLoading(true);
      setPixelError(null);
      api
        .pixel(studyId, lonLat[0], lonLat[1])
        .then((sample) => {
          setPixel(sample);
          markerSetterRef.current?.(lonLat);
          setInspectorTab("pixel");
        })
        .catch((err: Error) => setPixelError(err.message))
        .finally(() => setPixelLoading(false));
    },
    [live, studyId]
  );

  const handleRoiComplete = useCallback(
    (box: RoiBox) => {
      if (!live) {
        setRoiError(
          "Live ROI measurement needs the analysis backend. The showcase bundle includes the full recorded change statistics in the analysis dock instead."
        );
        setInspectorTab("roi");
        return;
      }
      setRoiBox(box);
      setRoiLoading(true);
      setRoiError(null);
      setRoiMode(false);
      api
        .roi(studyId, box)
        .then((result) => setRoiResult(result))
        .catch((err: Error) => setRoiError(err.message))
        .finally(() => setRoiLoading(false));
    },
    [live, studyId]
  );

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

  /** M4-R1 §9: restore the complete study extent from any view. */
  const handleFitSetter = useCallback((fit: () => void) => {
    fitRef.current = fit;
  }, []);
  const fitStudy = useCallback(() => fitRef.current?.(), []);

  /* Early exit states -------------------------------------------------- */
  if (error) {
    return (
      <main id="main" className="workstation workstation-error">
        <ErrorNote
          message={`The study bundle could not be loaded (${error}). Build the bundles with \`python scripts/build_showcase_bundles.py\` and reload.`}
        />
      </main>
    );
  }
  if (!bundle || !summary || !georef || !resolver || !layer) {
    return (
      <main id="main" className="workstation workstation-loading">
        <p className="mono-label">Loading the measured study bundle…</p>
      </main>
    );
  }

  const worstCommon = Math.min(
    ...Object.values(summary.change ?? {}).map((block) =>
      Number(block.common_valid_fraction_of_aoi ?? 1)
    )
  );
  const earlier = summary.periods?.[0];
  const later = summary.periods?.[1];
  const isHimalaya = Boolean(bundle.event);

  return (
    <main id="main" className="workstation">
      {/* ------------------------------------------------ study context bar */}
      <header className="ws-context">
        <div className="ws-title">
          <p className="eyebrow">
            {bundle.study.id ? `Study ${bundle.study.id} · ` : ""}
            {String(bundle.study.study_type ?? "").replace(/_/g, " ")}
            {bundle.evidence_status === "partial" ? " · PARTIAL evidence" : " · Processed"}
            {isHimalaya ? ` · event ${bundle.event?.event_date}` : ""}
          </p>
          <h1>{bundle.study.title}</h1>
          {bundle.experiments.length > 1 && (
            <div className="ws-experiment-switch" role="group" aria-label="Experiment">
              {bundle.experiments.map((item, index) => (
                <button
                  key={item.experiment_id}
                  type="button"
                  className={index === experimentIndex ? "chip is-active" : "chip"}
                  aria-pressed={index === experimentIndex}
                  onClick={() => setExperimentIndex(index)}
                >
                  {item.label ?? item.experiment_id}
                </button>
              ))}
            </div>
          )}
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
            <dd>
              {(worstCommon * 100).toFixed(1)}%
              {worstCommon < 0.999 ? " of AOI shared-valid" : " of AOI common-valid"}
            </dd>
          </div>
          <div>
            <dt>Method</dt>
            <dd>
              {earlier?.composite_method} composite · masked Δ-index on one grid
            </dd>
          </div>
          <div>
            <dt>Evidence mode</dt>
            <dd>
              {live ? "Showcase + live probe" : "Portable showcase (bundled)"}
              {" · "}
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
              {(["historical", "change", "quality", "what_changed"] as Analysis[]).map(
                (item) => (
                  <button
                    key={item}
                    type="button"
                    className={analysis === item ? "is-active" : ""}
                    aria-pressed={analysis === item}
                    onClick={() => setAnalysis(item)}
                  >
                    {item === "historical"
                      ? "Historical"
                      : item === "change"
                        ? "Change"
                        : item === "quality"
                          ? "Quality"
                          : "What changed?"}
                  </button>
                )
              )}
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
              {live && (
                <button
                  type="button"
                  className={overlay ? "toggle-btn is-active" : "toggle-btn"}
                  aria-pressed={overlay}
                  onClick={() => setOverlay((prev) => !prev)}
                >
                  Validity overlay
                </button>
              )}
            </>
          )}
          {analysis === "what_changed" && (
            <>
              <button
                type="button"
                className={findingsOverlay ? "toggle-btn is-active" : "toggle-btn"}
                aria-pressed={findingsOverlay}
                onClick={() => setFindingsOverlay((prev) => !prev)}
              >
                Finding regions
              </button>
              <button
                type="button"
                className="toggle-btn"
                onClick={() => {
                  setSelectedEvidenceId(null);
                  fitStudy();
                }}
                title="Clear the selection and restore the complete study extent"
              >
                Reset View
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
            <button
              type="button"
              className="toggle-btn"
              onClick={() => setInspectorTab("guide")}
              title="Plain-language explanation of the selected layer"
            >
              What am I looking at?
            </button>
            <button
              type="button"
              className="toggle-btn"
              onClick={fitStudy}
              title="Fit the complete study AOI into the map viewport"
            >
              Fit Entire Study Area
            </button>
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
            resolver={resolver}
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
            onFitSetter={handleFitSetter}
            findings={findingsFC}
            selectedEvidenceId={selectedEvidenceId}
            findingsVisible={analysis === "what_changed" && findingsOverlay}
            onFindingSelect={handleFindingSelect}
            onFocusSetter={handleFocusSetter}
          />
          <Inspector
            summary={summary}
            studyId={studyId}
            resolver={resolver}
            layer={layer}
            quality={quality}
            bundle={bundle}
            live={live}
            analysis={analysis}
            findings={findings}
            selectedEvidenceId={selectedEvidenceId}
            onSelectFinding={handleFindingSelect}
            onOpenResearch={handleOpenResearch}
            selectionPolicy={selectionPolicy}
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
        bundle={bundle}
        experimentIndex={experimentIndex}
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
