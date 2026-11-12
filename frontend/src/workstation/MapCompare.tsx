/** MapLibre-based geographic comparison workspace.
 *
 * Renders the study's colourised PNG previews as *georeferenced raster image
 * sources* pinned to the real grid corners from `/api/m1/study/{id}/georef`
 * (EPSG:32644 → EPSG:4326, pyproj, server-side). The original GeoTIFFs are
 * never loaded by the browser (ADR D2/D3).
 *
 * Modes:
 * - `side`    two synchronized maps, locked shared view
 * - `swipe`   one registered viewport; the later period is a clipped second
 *             map whose divider follows the mouse with no click, keeping
 *             touch drag, keyboard slider semantics and reset
 * - `opacity` one map; the later raster's opacity is set by paint property
 *
 * Change and Quality analyses render on the primary map only: a derived
 * difference raster or a validity mask is not a second temporal observation
 * (M2-G0 lesson), so no fake temporal pairing is created.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
} from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, MapMouseEvent, ImageSource, GeoJSONSource } from "maplibre-gl";
// MapLibre v6 runs its tile/raster pipeline in a dedicated worker; Vite must
// emit that worker as an asset and hand its URL to the library.
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { Georef, M1Summary } from "../api/types";
import type { AssetResolver, LayerSpec, PeriodKey } from "./layers";
import { layerImageUrl } from "./layers";
import { smoothUpscaledUrl } from "./upscale";

export type CompareMode = "side" | "swipe" | "opacity";

export interface RoiBox {
  west: number;
  south: number;
  east: number;
  north: number;
}

interface MapCompareProps {
  georef: Georef;
  summary: M1Summary;
  /** Asset resolver: live backend routes or bundled showcase copies. */
  resolver: AssetResolver;
  analysis: "historical" | "change" | "quality" | "what_changed";
  layer: LayerSpec;
  mode: CompareMode;
  opacity: number;
  overlay: boolean;
  split: number;
  onSplitChange: (split: number) => void;
  onMapClick: (lonLat: [number, number]) => void;
  onCursorMove: (lonLat: [number, number] | null) => void;
  roiMode: boolean;
  roiBox: RoiBox | null;
  onRoiComplete: (box: RoiBox) => void;
  /** Receives a setter so the parent can place the inspected-pixel marker. */
  onMarkerSetter: (setter: (lonLat: [number, number] | null) => void) => void;
  /** Receives a setter for the "Fit Entire Study Area" action (M4-R1 §9). */
  onFitSetter?: (fit: () => void) => void;
  /** "What Changed?" findings overlay (M4-R1 §15.2): recorded regions, */
  findings?: GeoJSON.FeatureCollection | null;
  selectedEvidenceId?: string | null;
  findingsVisible?: boolean;
  onFindingSelect?: (id: string | null) => void;
  /** Receives a setter to focus (fit) a finding's geometry (§15.2.6). */
  onFocusSetter?: (focus: (geometry: GeoJSON.Geometry) => void) => void;
}

const MAP_BACKGROUND = "#dfe3de";

maplibregl.setWorkerUrl(maplibreWorkerUrl);
const EMPTY_FC: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

/** Run a style mutation once the map's style is genuinely loaded.
 *
 * The map's `load` event can fire while `isStyleLoaded()` is still false,
 * and `once("load")` registered after that event never re-fires — so a
 * naive deferral deadlocks the layer pipeline.  `idle` fires after every
 * completed render, which makes it a safe retry tick.
 */
function whenStyleReady(map: MapLibreMap, fn: () => void) {
  if (map.isStyleLoaded()) {
    fn();
    return;
  }
  const attempt = () => {
    if (map.isStyleLoaded()) {
      fn();
      return;
    }
    map.once("idle", attempt);
  };
  map.once("idle", attempt);
}

type Coord = [number, number];
type CoordQuad = [Coord, Coord, Coord, Coord];

function cornersToCoordinates(georef: Georef): CoordQuad {
  // corners are ordered [tl, tr, br, bl]; MapLibre image sources want the same.
  return georef.corners_wgs84.map(
    ([lon, lat]) => [lon, lat] as Coord
  ) as CoordQuad;
}

function boundsOf(georef: Georef): [[number, number], [number, number]] {
  const lons = georef.corners_wgs84.map((c) => c[0]);
  const lats = georef.corners_wgs84.map((c) => c[1]);
  return [
    [Math.min(...lons), Math.min(...lats)],
    [Math.max(...lons), Math.max(...lats)],
  ];
}

function aoiFeature(summary: M1Summary): GeoJSON.Feature | null {
  const raw = summary.aoi?.geojson as unknown;
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as { type?: string };
  if (obj.type === "Feature") return raw as GeoJSON.Feature;
  if (obj.type === "FeatureCollection") {
    return (raw as GeoJSON.FeatureCollection).features?.[0] ?? null;
  }
  return null;
}

/** Per-map memo of the last image URL applied to each image source
 *  (M4-R1 §7): content updates (`updateImage`) happen only when the URL
 *  actually changes; paint-only changes (opacity) never re-fetch or
 *  re-decode the image, which is what made the opacity slider flicker. */
type LastImageMemo = WeakMap<MapLibreMap, Record<string, string>>;
const lastImageMemo: LastImageMemo = new WeakMap();

/** Ensure an image source + raster layer exist on a map and show `url`.
 *  `coordinates` pins the raster to the real grid corners. An empty `url`
 *  hides the layer but never creates a source with an empty image (MapLibre
 *  would raise a decode error); the layer is created lazily on first real
 *  image, ordered below the AOI outline.
 *
 *  If the style has not finished loading (a fast study switch can land the
 *  paint effect before the new map's style resolves), the work is deferred
 *  to the style load instead of racing it. */
function applyImageLayer(
  map: MapLibreMap,
  id: string,
  rawUrl: string,
  coordinates: CoordQuad,
  opacity = 1,
  smooth = false
) {
  // Colour composites are enlarged with a bicubic kernel (display only);
  // data layers stay as crisp native pixels via nearest-neighbour sampling.
  const resampling = smooth ? "linear" : "nearest";
  const tokens = applyToken.get(map) ?? {};
  const token = (tokens[id] ?? 0) + 1;
  tokens[id] = token;
  applyToken.set(map, tokens);
  const run = (url: string) => {
    const source = map.getSource(id) as ImageSource | undefined;
    if (!url) {
      if (source && map.getLayer(id)) {
        map.setLayoutProperty(id, "visibility", "none");
      }
      return;
    }
    if (source && map.getLayer(id)) {
      const memo = lastImageMemo.get(map) ?? {};
      if (memo[id] !== url) {
        source.updateImage({ url, coordinates });
        memo[id] = url;
        lastImageMemo.set(map, memo);
      }
      map.setLayoutProperty(id, "visibility", "visible");
      map.setPaintProperty(id, "raster-opacity", opacity);
      map.setPaintProperty(id, "raster-resampling", resampling);
      return;
    }
    map.addSource(id, { type: "image", url, coordinates });
    map.addLayer(
      {
        id,
        type: "raster",
        source: id,
        paint: { "raster-opacity": opacity, "raster-resampling": resampling },
      },
      map.getLayer("aoi-line") ? "aoi-line" : undefined
    );
    const memo = lastImageMemo.get(map) ?? {};
    memo[id] = url;
    lastImageMemo.set(map, memo);
  };
  if (smooth && rawUrl) {
    // Show the original at once; swap in the sharpened copy when it is ready.
    whenStyleReady(map, () => {
      if (applyToken.get(map)?.[id] === token) run(rawUrl);
    });
    void smoothUpscaledUrl(rawUrl).then((url) => {
      // Only the most recent request for this map may paint (rapid layer switching).
      if (applyToken.get(map)?.[id] !== token) return;
      whenStyleReady(map, () => run(url));
    });
  } else {
    whenStyleReady(map, () => run(rawUrl));
  }
}

/** Latest-request guard per map and layer id for the async smooth path:
 *  stale smooth results from an older request are dropped. */
const applyToken: WeakMap<MapLibreMap, Record<string, number>> = new WeakMap();

/** Opacity mode (M4-R1 §7) composites on the PRIMARY map: the later raster
 *  is a second image source whose `raster-opacity` the slider drives. That
 *  keeps pan/zoom live (the later map's interaction is disabled by design),
 *  makes 50% a genuine raster-over-raster blend, and never reloads the
 *  image while dragging. */

function ensureLineRect(map: MapLibreMap, box: RoiBox | null) {
  const run = () => {
    if (!map.getSource("roi-rect")) {
      map.addSource("roi-rect", { type: "geojson", data: EMPTY_FC });
      map.addLayer({
        id: "roi-rect-fill",
        type: "fill",
        source: "roi-rect",
        paint: { "fill-color": "#7faba7", "fill-opacity": 0.12 },
      });
      map.addLayer({
        id: "roi-rect-line",
        type: "line",
        source: "roi-rect",
        paint: { "line-color": "#193c43", "line-width": 2 },
      });
    }
    const source = map.getSource("roi-rect") as GeoJSONSource;
    source.setData(box ? roiFeature(box) : EMPTY_FC);
  };
  whenStyleReady(map, run);
}

function roiFeature(box: RoiBox): GeoJSON.Feature {
  const { west, south, east, north } = box;
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [west, south],
          [east, south],
          [east, north],
          [west, north],
          [west, south],
        ],
      ],
    },
  };
}

export function MapCompare({
  georef,
  summary,
  resolver,
  analysis,
  layer,
  mode,
  opacity,
  overlay,
  split,
  onSplitChange,
  onMapClick,
  onCursorMove,
  roiMode,
  roiBox,
  onRoiComplete,
  onMarkerSetter,
  onFitSetter,
  findings,
  selectedEvidenceId,
  findingsVisible,
  onFindingSelect,
  onFocusSetter,
}: MapCompareProps) {
  const earlierMapDiv = useRef<HTMLDivElement>(null);
  const laterMapDiv = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const mapsRef = useRef<{ earlier?: MapLibreMap; later?: MapLibreMap }>({});
  const [ready, setReady] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const [liveRoi, setLiveRoi] = useState<RoiBox | null>(null);

  const coordinates = useMemo(() => cornersToCoordinates(georef), [georef]);
  const bounds = useMemo(() => boundsOf(georef), [georef]);
  const layerUrlEarlier = layerImageUrl(layer, summary, resolver, "earlier");
  const layerUrlLater = layerImageUrl(layer, summary, resolver, "later");
  const singleMap = analysis !== "historical";
  const smoothLayer =
    layer.kind === "period" &&
    (layer.previewKey === "true_colour" || layer.previewKey === "false_colour");

  const overlayUrl = useCallback(
    (period: PeriodKey) => {
      if (!overlay || analysis === "quality") return "";
      if (analysis === "change") {
        return resolver.g0Url("common_invalid.png") ?? "";
      }
      return (
        resolver.g0Url(period === "later" ? "later_invalid.png" : "earlier_invalid.png") ?? ""
      );
    },
    [overlay, analysis, resolver]
  );

  /* --------------------------------------------------------- map init --- */
  useEffect(() => {
    if (!earlierMapDiv.current || mapsRef.current.earlier) return;
    const attribution =
      "Contains modified Copernicus Sentinel data (ESA) · HabitatShift previews from processed L2A scenes";
    // Each map needs its own style object; sharing one instance across two
    // MapLibre maps lets the first map's normalization corrupt the second.
    const makeStyle = () =>
      ({
        version: 8,
        sources: {},
        layers: [
          { id: "bg", type: "background", paint: { "background-color": MAP_BACKGROUND } },
        ],
      }) as never;
    const earlier = new maplibregl.Map({
      container: earlierMapDiv.current,
      style: makeStyle(),
      center: georef.centre_wgs84 as [number, number],
      zoom: 14,
      attributionControl: false,
      maxBounds: bounds,
    });
    const later = laterMapDiv.current
      ? new maplibregl.Map({
          container: laterMapDiv.current,
          style: makeStyle(),
          center: georef.centre_wgs84 as [number, number],
          zoom: 14,
          attributionControl: false,
          maxBounds: bounds,
        })
      : undefined;

    mapsRef.current = { earlier, later };
    (window as unknown as { __hsMaps?: typeof mapsRef.current }).__hsMaps = mapsRef.current;

    // Benign MapLibre lifecycle errors (e.g. a style still loading while a
    // study switch tears the map down) must not escape as page errors —
    // React 19 unmounts the whole tree on an uncaught one.  Anything else
    // is logged for the console-error hygiene check.
    const swallow = (map: MapLibreMap) => {
      map.on("error", (event) => {
        const message = String(
          (event as unknown as { error?: { message?: string } }).error?.message ?? ""
        );
        if (message.includes("Style is not done loading")) return;
        console.debug("maplibre:", message);
      });
    };
    swallow(earlier);
    if (later) swallow(later);

    // The later map must never lead the shared view, but must still emit
    // click events for the pixel probe.
    if (later) {
      later.dragPan.disable();
      later.dragRotate.disable();
      later.scrollZoom.disable();
      later.boxZoom.disable();
      later.keyboard.disable();
      later.doubleClickZoom.disable();
      later.touchZoomRotate.disable();
      later.touchPitch.disable();
    }

    earlier.fitBounds(bounds, { padding: 6, duration: 0, animate: false });

    const addControls = (map: MapLibreMap) => {
      map.addControl(
        new maplibregl.ScaleControl({ maxWidth: 96, unit: "metric" }),
        "bottom-left"
      );
      map.addControl(
        new maplibregl.AttributionControl({
          compact: true,
          customAttribution: attribution,
        }),
        "bottom-right"
      );
      map.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        "top-right"
      );
    };
    addControls(earlier);
    if (later) addControls(later);

    let readyCount = later ? 0 : 1;
    const onReady = () => {
      readyCount += 1;
      if (readyCount >= (later ? 2 : 1)) setReady(true);
    };
    earlier.on("load", onReady);
    later?.on("load", onReady);

    /* Locked shared view: jump the later map only on real drift. */
    const sync = () => {
      const laterMap = mapsRef.current.later;
      if (!laterMap) return;
      const c = earlier.getCenter();
      const z = earlier.getZoom();
      const b = earlier.getBearing();
      const p = earlier.getPitch();
      const tc = laterMap.getCenter();
      if (
        tc.lng !== c.lng ||
        tc.lat !== c.lat ||
        laterMap.getZoom() !== z ||
        laterMap.getBearing() !== b ||
        laterMap.getPitch() !== p
      ) {
        laterMap.jumpTo({ center: c, zoom: z, bearing: b, pitch: p });
      }
    };
    earlier.on("move", sync);
    earlier.on("resize", sync);

    earlier.on("mousemove", (event: MapMouseEvent) => {
      onCursorMove([event.lngLat.lng, event.lngLat.lat]);
    });
    earlier.on("mouseout", () => onCursorMove(null));

    const clickHandler = (event: MapMouseEvent) => {
      if (roiModeRef.current) return;
      // A click on a findings polygon selected that finding (M4-R3 §3.6);
      // it must never also fire the pixel probe / ROI click path.
      if (findingClickRef.current) {
        findingClickRef.current = false;
        return;
      }
      onMapClick([event.lngLat.lng, event.lngLat.lat]);
    };
    earlier.on("click", clickHandler);
    later?.on("click", clickHandler);

    const resizeObserver = new ResizeObserver(() => {
      earlier.resize();
      later?.resize();
    });
    resizeObserver.observe(earlierMapDiv.current);
    if (laterMapDiv.current) resizeObserver.observe(laterMapDiv.current);

    return () => {
      resizeObserver.disconnect();
      // A teardown racing a pending style load can throw inside MapLibre;
      // the maps are being discarded either way, so a clean stop is enough.
      try {
        earlier.remove();
      } catch {
        /* discarding anyway */
      }
      try {
        later?.remove();
      } catch {
        /* discarding anyway */
      }
      mapsRef.current = {};
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [georef]);

  const roiModeRef = useRef(roiMode);
  // Set briefly when a findings polygon click selects a finding, so the
  // generic map click handler can skip the pixel probe for that same click.
  const findingClickRef = useRef(false);
  roiModeRef.current = roiMode;

  /* -------------------------------------------------- shared overlays --- */
  useEffect(() => {
    if (!ready) return;
    const { earlier, later } = mapsRef.current;
    if (!earlier) return;
    const aoi = aoiFeature(summary);
    const setup = (map: MapLibreMap) => {
      const run = () => {
        if (aoi && !map.getSource("aoi")) {
          map.addSource("aoi", { type: "geojson", data: aoi });
          map.addLayer({
            id: "aoi-line",
            type: "line",
            source: "aoi",
            paint: { "line-color": "#d68a5d", "line-width": 1.6, "line-dasharray": [3, 2] },
          });
        }
        if (!map.getSource("pixel-marker")) {
          map.addSource("pixel-marker", { type: "geojson", data: EMPTY_FC });
          map.addLayer({
            id: "pixel-marker-circle",
            type: "circle",
            source: "pixel-marker",
            paint: {
              "circle-radius": 5,
              "circle-color": "#d68a5d",
              "circle-stroke-color": "#18272d",
              "circle-stroke-width": 1.5,
            },
          });
        }
        ensureLineRect(map, null);
      };
      whenStyleReady(map, run);
    };
    setup(earlier);
    if (later) setup(later);
  }, [ready, summary]);

  const setPixelMarker = useCallback((lonLat: [number, number] | null) => {
    const data: GeoJSON.FeatureCollection = lonLat
      ? {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: {},
              geometry: { type: "Point", coordinates: lonLat },
            },
          ],
        }
      : EMPTY_FC;
    const { earlier, later } = mapsRef.current;
    for (const map of [earlier, later].filter(Boolean) as MapLibreMap[]) {
      const source = map.getSource("pixel-marker") as GeoJSONSource | undefined;
      if (source) source.setData(data);
    }
  }, []);

  useEffect(() => {
    onMarkerSetter(setPixelMarker);
  }, [setPixelMarker, onMarkerSetter]);

  /* ------------------------------------------- fit-to-extent (M4-R1 §9) --- */
  const fitToStudy = useCallback(() => {
    const { earlier } = mapsRef.current;
    // The earlier map leads the shared view; the later map follows on move.
    earlier?.fitBounds(bounds, { padding: 8, duration: 350 });
  }, [bounds]);

  useEffect(() => {
    onFitSetter?.(fitToStudy);
  }, [fitToStudy, onFitSetter]);

  /** Focus a finding's geometry: fit the map to the region's true bbox. */
  const focusGeometry = useCallback((geometry: GeoJSON.Geometry) => {
    const { earlier } = mapsRef.current;
    if (!earlier) return;
    const lons: number[] = [];
    const lats: number[] = [];
    const collect = (position: GeoJSON.Position | GeoJSON.Position[]) => {
      if (typeof position[0] === "number") {
        lons.push(position[0] as number);
        lats.push(position[1] as number);
      } else {
        (position as GeoJSON.Position[]).forEach(collect);
      }
    };
    const rings =
      geometry.type === "Polygon"
        ? geometry.coordinates
        : geometry.type === "MultiPolygon"
          ? geometry.coordinates.flat()
          : [];
    rings.forEach((ring) => ring.forEach(collect));
    if (!lons.length) return;
    earlier.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: 60, duration: 500, maxZoom: 15 }
    );
  }, []);

  useEffect(() => {
    onFocusSetter?.(focusGeometry);
  }, [focusGeometry, onFocusSetter]);

  /* ------------------------------ findings overlay (M4-R1 §15.2) --- */
  const onFindingSelectRef = useRef(onFindingSelect);
  onFindingSelectRef.current = onFindingSelect;

  useEffect(() => {
    if (!ready) return;
    const { earlier } = mapsRef.current;
    if (!earlier) return;
    const run = () => {
      if (!earlier.getSource("findings-overlay")) {
        earlier.addSource("findings-overlay", { type: "geojson", data: EMPTY_FC });
        // Subdued, scientifically meaningful colours, distinct from the
        // brand's active-state teal/copper: muted versions with low fill
        // opacity so the underlying imagery stays readable (§15.7).
        earlier.addLayer(
          {
            id: "findings-fill",
            type: "fill",
            source: "findings-overlay",
            paint: {
              "fill-color": [
                "match",
                ["get", "direction"],
                "decrease", "#4e7d74",
                "#b3744e",
              ],
              "fill-opacity": 0.22,
            },
          },
          earlier.getLayer("aoi-line") ? "aoi-line" : undefined
        );
        earlier.addLayer({
          id: "findings-line",
          type: "line",
          source: "findings-overlay",
          paint: {
            "line-color": [
              "case",
              ["==", ["get", "evidence_id"], ["literal", selectedEvidenceId ?? "__none__"]],
              "#193c43",
              ["match", ["get", "direction"], "decrease", "#3c655d", "#8a5a3a"],
            ],
            "line-width": ["case",
              ["==", ["get", "evidence_id"], ["literal", selectedEvidenceId ?? "__none__"]], 3, 1.6],
          },
        });
        earlier.on("click", "findings-fill", (event) => {
          findingClickRef.current = true;
          const evidenceId = event.features?.[0]?.properties?.evidence_id;
          if (typeof evidenceId === "string") onFindingSelectRef.current?.(evidenceId);
        });
        // Pointer affordance + stable region identifier tooltip (M4-R3 §3.3).
        const hoverPopup = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          className: "findings-hover",
        });
        earlier.on("mousemove", "findings-fill", (event) => {
          earlier.getCanvas().style.cursor = "pointer";
          const props = event.features?.[0]?.properties;
          if (!props) return;
          const direction = String(props.direction ?? "");
          hoverPopup
            .setLngLat(event.lngLat)
            .setHTML(
              `<strong>${String(props.display_id ?? "")}</strong> · Δ${String(
                props.index ?? ""
              ).toUpperCase()} ${direction}<br>${Number(props.area_ha ?? 0).toFixed(
                2
              )} ha · ${direction === "decrease" ? "candidate decrease" : "candidate increase"}<br><span class="mono-label">${String(
                props.evidence_id ?? ""
              )}</span>`
            )
            .addTo(earlier);
        });
        earlier.on("mouseleave", "findings-fill", () => {
          earlier.getCanvas().style.cursor = "";
          hoverPopup.remove();
        });
      }
      const source = earlier.getSource("findings-overlay") as GeoJSONSource;
      const data =
        findingsVisible && findings && findings.features.length ? findings : EMPTY_FC;
      source.setData(data);
      if (earlier.getLayer("findings-line")) {
        earlier.setPaintProperty("findings-line", "line-color", [
          "case",
          ["==", ["get", "evidence_id"], ["literal", selectedEvidenceId ?? "__none__"]],
          "#193c43",
          ["match", ["get", "direction"], "decrease", "#3c655d", "#8a5a3a"],
        ]);
        earlier.setPaintProperty("findings-line", "line-width", [
          "case",
          ["==", ["get", "evidence_id"], ["literal", selectedEvidenceId ?? "__none__"]], 3, 1.6,
        ]);
      }
    };
    whenStyleReady(earlier, run);
  }, [ready, findings, findingsVisible, selectedEvidenceId]);

  /* --------------------------------------------------- layer painting --- */
  useEffect(() => {
    if (!ready) return;
    const { earlier, later } = mapsRef.current;
    if (!earlier) return;
    const earlierOverlay = overlayUrl("earlier");
    const laterOverlay = overlayUrl("later");

    if (analysis === "historical") {
      applyImageLayer(earlier, "layer-earlier", layerUrlEarlier, coordinates, 1, smoothLayer);
      applyImageLayer(earlier, "validity-overlay", earlierOverlay, coordinates);
      if (later) {
        if (mode === "opacity") {
          // Single-map blend: the later raster lives on the primary map and
          // only its paint opacity changes with the slider (M4-R1 §7).
          applyImageLayer(earlier, "layer-later", layerUrlLater, coordinates, opacity, smoothLayer);
          applyImageLayer(later, "layer-later", "", coordinates);
        } else {
          applyImageLayer(earlier, "layer-later", "", coordinates);
          applyImageLayer(later, "layer-later", layerUrlLater, coordinates, 1, smoothLayer);
          applyImageLayer(later, "validity-overlay", laterOverlay, coordinates);
        }
      }
    } else {
      const url =
        analysis === "change" || analysis === "what_changed"
          ? layerUrlEarlier
          : layerImageUrl(layer, summary, resolver, "later");
      applyImageLayer(earlier, "layer-earlier", url, coordinates, 1);
      applyImageLayer(earlier, "validity-overlay", overlayUrl("earlier"), coordinates);
      if (later) {
        applyImageLayer(later, "layer-later", "", coordinates);
        applyImageLayer(later, "validity-overlay", "", coordinates);
        applyImageLayer(earlier, "layer-later", "", coordinates);
      }
    }
  }, [
    ready,
    layer,
    layerUrlEarlier,
    layerUrlLater,
    analysis,
    mode,
    opacity,
    overlayUrl,
    coordinates,
    summary,
    resolver,
    smoothLayer,
  ]);

  /* -------------------------------------------------------- ROI draw --- */
  useEffect(() => {
    const { earlier } = mapsRef.current;
    if (!earlier) return;
    if (roiMode) {
      earlier.dragPan.disable();
      earlier.getCanvas().style.cursor = "crosshair";
    } else {
      earlier.dragPan.enable();
      earlier.getCanvas().style.cursor = "";
      setLiveRoi(null);
    }
  }, [roiMode, ready]);

  useEffect(() => {
    const { earlier } = mapsRef.current;
    if (!earlier || !ready) return;
    let start: { lng: number; lat: number } | null = null;
    const onDown = (event: MapMouseEvent) => {
      if (!roiModeRef.current) return;
      event.preventDefault();
      start = { lng: event.lngLat.lng, lat: event.lngLat.lat };
      setDrawing(true);
    };
    const onMoveRoi = (event: MapMouseEvent) => {
      if (!start) return;
      setLiveRoi({
        west: Math.min(start.lng, event.lngLat.lng),
        east: Math.max(start.lng, event.lngLat.lng),
        south: Math.min(start.lat, event.lngLat.lat),
        north: Math.max(start.lat, event.lngLat.lat),
      });
    };
    const onUp = (event: MapMouseEvent) => {
      if (!start) return;
      const from = start;
      start = null;
      setDrawing(false);
      setLiveRoi(null);
      const box: RoiBox = {
        west: Math.min(from.lng, event.lngLat.lng),
        east: Math.max(from.lng, event.lngLat.lng),
        south: Math.min(from.lat, event.lngLat.lat),
        north: Math.max(from.lat, event.lngLat.lat),
      };
      if ((box.east - box.west) * (box.north - box.south) > 1e-10) {
        onRoiComplete(box);
      }
    };
    earlier.on("mousedown", onDown);
    earlier.on("mousemove", onMoveRoi);
    earlier.on("mouseup", onUp);
    return () => {
      earlier.off("mousedown", onDown);
      earlier.off("mousemove", onMoveRoi);
      earlier.off("mouseup", onUp);
    };
  }, [ready, onRoiComplete]);

  useEffect(() => {
    if (!ready) return;
    const { earlier, later } = mapsRef.current;
    const box = liveRoi ?? roiBox;
    for (const map of [earlier, later].filter(Boolean) as MapLibreMap[]) {
      ensureLineRect(map, box);
    }
  }, [liveRoi, roiBox, ready]);

  /* -------------------------------------------------- swipe handling --- */
  // splitRef is the interaction source of truth. It must NOT be re-assigned
  // in the render body: a render triggered between applySplit() and its rAF
  // (e.g. the pixel-probe state update from the same tap) would clobber the
  // pending value with the stale prop. External prop changes (reset button)
  // sync it after commit.
  const splitRef = useRef(split);
  const rafRef = useRef<number | null>(null);
  const draggingRef = useRef(false);

  useEffect(() => {
    splitRef.current = split;
  }, [split]);

  const applySplit = useCallback(
    (value: number) => {
      const next = Math.min(100, Math.max(0, value));
      splitRef.current = next;
      if (rafRef.current !== null) return;
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        const stage = stageRef.current;
        if (stage) {
          stage.style.setProperty("--split", `${splitRef.current}%`);
          const divider = stage.querySelector<HTMLDivElement>(".map-swipe-divider");
          if (divider) {
            const rounded = Math.round(splitRef.current);
            divider.setAttribute("aria-valuenow", String(rounded));
            divider.setAttribute(
              "aria-valuetext",
              `${rounded}% earlier, ${100 - rounded}% later`
            );
          }
        }
        onSplitChange(splitRef.current);
      });
    },
    [onSplitChange]
  );

  useEffect(() => {
    const stage = stageRef.current;
    if (stage) stage.style.setProperty("--split", `${split}%`);
  }, [split, mode]);

  const splitFromEvent = (clientX: number): number | null => {
    const stage = stageRef.current;
    if (!stage) return null;
    const box = stage.getBoundingClientRect();
    if (!box.width) return null;
    return ((clientX - box.left) / box.width) * 100;
  };

  const onStagePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (mode !== "swipe" || singleMap) return;
    if (event.pointerType !== "mouse" && !(draggingRef.current && event.buttons !== 0)) return;
    const value = splitFromEvent(event.clientX);
    if (value !== null) applySplit(value);
  };

  const onStagePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (mode !== "swipe" || singleMap) return;
    // Mouse users already have hover-follow: a mouse *click* on the map must
    // stay free for the pixel probe, so only touch/pen start a drag here.
    if (event.pointerType === "mouse") return;
    event.preventDefault();
    draggingRef.current = true;
    stageRef.current?.classList.add("is-dragging");
    const stage = stageRef.current;
    try {
      stage?.setPointerCapture(event.pointerId);
    } catch {
      /* best-effort */
    }
    const value = splitFromEvent(event.clientX);
    if (value !== null) applySplit(value);
  };

  const onStagePointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    stageRef.current?.classList.remove("is-dragging");
    if (event.pointerType !== "mouse") {
      const stage = stageRef.current;
      if (stage?.hasPointerCapture?.(event.pointerId)) {
        stage.releasePointerCapture(event.pointerId);
      }
    }
  };

  /* Touch/pen drag in capture phase: the map canvas would otherwise win the
   * pointer, so in swipe mode the stage claims touch pointers first and the
   * divider follows the finger. Mouse hover-follow stays in React handlers. */
  useEffect(() => {
    if (mode !== "swipe" || singleMap) return;
    const stage = stageRef.current;
    if (!stage) return;
    let active = false;
    const down = (event: PointerEvent) => {
      if (event.pointerType === "mouse") return;
      active = true;
      event.preventDefault();
      event.stopPropagation();
      try {
        stage.setPointerCapture(event.pointerId);
      } catch {
        /* best-effort */
      }
      const box = stage.getBoundingClientRect();
      if (box.width) {
        applySplit(((event.clientX - box.left) / box.width) * 100);
      }
    };
    const move = (event: PointerEvent) => {
      if (!active || event.pointerType === "mouse") return;
      event.preventDefault();
      event.stopPropagation();
      const box = stage.getBoundingClientRect();
      if (box.width) {
        applySplit(((event.clientX - box.left) / box.width) * 100);
      }
    };
    const up = (event: PointerEvent) => {
      if (!active || event.pointerType === "mouse") return;
      active = false;
      event.stopPropagation();
      if (stage.hasPointerCapture?.(event.pointerId)) {
        stage.releasePointerCapture(event.pointerId);
      }
    };
    stage.addEventListener("pointerdown", down, true);
    stage.addEventListener("pointermove", move, true);
    stage.addEventListener("pointerup", up, true);
    stage.addEventListener("pointercancel", up, true);
    return () => {
      stage.removeEventListener("pointerdown", down, true);
      stage.removeEventListener("pointermove", move, true);
      stage.removeEventListener("pointerup", up, true);
      stage.removeEventListener("pointercancel", up, true);
    };
  }, [mode, singleMap, applySplit]);

  const onDividerKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    let next = splitRef.current;
    const step = event.shiftKey ? 10 : 1;
    switch (event.key) {
      case "ArrowLeft":
      case "ArrowDown":
        next -= step;
        break;
      case "ArrowRight":
      case "ArrowUp":
        next += step;
        break;
      case "PageDown":
        next -= 10;
        break;
      case "PageUp":
        next += 10;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = 100;
        break;
      default:
        return;
    }
    event.preventDefault();
    applySplit(next);
  };

  return (
    <div
      ref={stageRef}
      className={`map-stage mode-${mode} ${singleMap ? "single-map" : ""} ${
        roiMode ? "roi-mode" : ""
      } ${drawing ? "is-drawing" : ""}`}
      data-analysis={analysis}
      onPointerMove={onStagePointerMove}
      onPointerDown={onStagePointerDown}
      onPointerUp={onStagePointerUp}
      onPointerCancel={onStagePointerUp}
      style={{ ["--split" as string]: `${split}%` }}
    >
      <div className="map-cell map-earlier" data-period="earlier">
        <div className="map-host" ref={earlierMapDiv} />
        <span className="map-cell-tag">
          {analysis === "historical"
            ? "Earlier"
            : analysis === "change"
              ? "Difference map"
              : analysis === "what_changed"
                ? "What changed"
                : "Quality layer"}
        </span>
        {/* M4-R1 §8: the native analysis resolution travels with the imagery. */}
        <span className="map-resolution-tag" title="Native analysis grid resolution">
          {summary.grid.resolution_m} m/px native
        </span>
      </div>
      {/* M4-R1 §5/§6: the later cell stays mounted for the map's lifetime.
          Unmounting it orphaned the MapLibre instance (the visible div became
          an empty host after Historical → Change → Quality → Historical),
          which blanked the later image and broke swipe. Change/Quality hide
          the cell with the `.single-map` CSS rule instead of removing it. */}
      <div className="map-cell map-later" data-period="later">
        <div className="map-host" ref={laterMapDiv} />
        <span className="map-cell-tag">Later</span>
      </div>
      {mode === "swipe" && !singleMap && (
        <div
          className="map-swipe-divider"
          role="slider"
          tabIndex={0}
          aria-label="Map comparison divider"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(split)}
          onKeyDown={onDividerKeyDown}
        >
          <span className="map-swipe-line" aria-hidden="true" />
          <span className="map-swipe-grip" aria-hidden="true" />
        </div>
      )}
      {roiMode && (
        <span className="map-roi-banner" role="status">
          Draw a rectangle on the map to measure a region of interest · Esc cancels
        </span>
      )}
    </div>
  );
}

/** Ref handle type used by the parent to store the marker setter. */
export type MarkerSetterRef = MutableRefObject<((lonLat: [number, number] | null) => void) | null>;
