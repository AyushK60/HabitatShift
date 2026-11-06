/* HabitatShift proof viewer.
 *
 * Serves the M1 science-engine bundle when one exists and falls back to the
 * original M0 two-scene study otherwise. Every number is read from a pipeline
 * artefact: there is no client-side index maths and no hardcoded metric.
 *
 * M2-G0 repair: one shared image stage per comparison, an explicit raster
 * aspect ratio, overlaid swipe layers with one clip boundary, and three
 * analysis modes (historical, change, quality). Captions and toolbars live
 * outside the image geometry so metadata height cannot shift the rasters.
 */
const M0_LAYERS = {
  true_colour: {
    analysis: "historical",
    group: "Imagery",
    kind: "period",
    key: "png",
    label: "True colour",
  },
  ndvi: {
    analysis: "historical",
    group: "Spectral indices",
    kind: "period",
    key: "ndvi_png",
    label: "NDVI",
  },
  mask: {
    analysis: "historical",
    group: "Quality",
    kind: "period",
    key: "mask_png",
    label: "Valid mask",
  },
};

const M1_LAYERS = {
  true_colour: {
    analysis: "historical",
    group: "Imagery",
    kind: "period",
    key: "true_colour",
    label: "True colour",
  },
  false_colour: {
    analysis: "historical",
    group: "Imagery",
    kind: "period",
    key: "false_colour",
    label: "False colour",
  },
  ndvi: {
    analysis: "historical",
    group: "Spectral indices",
    kind: "period",
    key: "ndvi",
    label: "NDVI",
    legend: "ndvi_legend",
  },
  ndwi: {
    analysis: "historical",
    group: "Spectral indices",
    kind: "period",
    key: "ndwi",
    label: "NDWI",
    legend: "ndwi_legend",
  },
  mndwi: {
    analysis: "historical",
    group: "Spectral indices",
    kind: "period",
    key: "mndwi",
    label: "MNDWI",
    legend: "mndwi_legend",
  },
  valid_mask: {
    analysis: "historical",
    group: "Quality",
    kind: "period",
    key: "valid_mask",
    label: "Valid mask",
    neutralMask: true,
  },
  observation_count: {
    analysis: "historical",
    group: "Quality",
    kind: "period",
    key: "observation_count",
    label: "Observation count",
    legend: "observation_count_legend",
  },
  delta_ndvi: {
    analysis: "change",
    group: "Change analysis",
    kind: "change",
    index: "ndvi",
    label: "Δ NDVI",
  },
  delta_ndwi: {
    analysis: "change",
    group: "Change analysis",
    kind: "change",
    index: "ndwi",
    label: "Δ NDWI",
  },
  delta_mndwi: {
    analysis: "change",
    group: "Change analysis",
    kind: "change",
    index: "mndwi",
    label: "Δ MNDWI",
  },
  qc_count_earlier: {
    analysis: "quality",
    group: "Quality",
    kind: "quality",
    quality: "count",
    periodIndex: 0,
    label: "Obs. count · earlier",
  },
  qc_count_later: {
    analysis: "quality",
    group: "Quality",
    kind: "quality",
    quality: "count",
    periodIndex: 1,
    label: "Obs. count · later",
  },
  qc_valid_earlier: {
    analysis: "quality",
    group: "Quality",
    kind: "quality",
    quality: "valid",
    periodIndex: 0,
    label: "Earlier valid",
  },
  qc_valid_later: {
    analysis: "quality",
    group: "Quality",
    kind: "quality",
    quality: "valid",
    periodIndex: 1,
    label: "Later valid",
  },
  qc_valid_common: {
    analysis: "quality",
    group: "Quality",
    kind: "quality",
    quality: "common",
    label: "Shared valid",
  },
  qc_masked: {
    analysis: "quality",
    group: "Quality",
    kind: "quality",
    quality: "masked",
    label: "Masked / unavailable",
  },
};

const GROUP_ORDER = [
  "Imagery",
  "Spectral indices",
  "Change analysis",
  "Quality",
];

const state = {
  source: "m0",
  analysis: "historical",
  layer: "true_colour",
  mode: "side",
  split: 50,
  overlay: false,
  summary: null,
  m1: null,
  quality: null,
  studyId: null,
};

const compareEl = document.getElementById("compare");
const factsEl = document.getElementById("facts");
const metaEl = document.getElementById("meta");
const notesEl = document.getElementById("notes");
const provEl = document.getElementById("provenance");
const bannerEl = document.getElementById("banner");
const ledeEl = document.getElementById("lede");
const legendRowEl = document.getElementById("legend-row");
const legendEl = document.getElementById("legend");
const legendNoteEl = document.getElementById("legend-note");
const legendSwatchesEl = document.getElementById("legend-swatches");
const attributionEl = document.getElementById("attribution");
const layerGroupsEl = document.getElementById("layer-groups");
const analysisSwitchEl = document.getElementById("analysis-switch");
const modeSwitchEl = document.getElementById("mode-switch");
const viewGroupEl = document.getElementById("view-group");
const overlayToggleEl = document.getElementById("overlay-toggle");
const brandTagEl = document.querySelector(".brand-tag");

const fileUrl = (name) => `/files/preview/${encodeURIComponent(name)}`;
const m1File = (studyId, relPath) =>
  `/files/m1/${encodeURIComponent(studyId)}/previews/${encodeURIComponent(
    String(relPath || "").split("/").pop()
  )}`;
const g0File = (studyId, name) =>
  `/files/g0/${encodeURIComponent(studyId)}/${encodeURIComponent(name)}`;
const basename = (relPath) => String(relPath || "").split("/").pop();
const pct = (fraction) => `${(Number(fraction || 0) * 100).toFixed(1)}%`;
const num = (value, digits = 3) =>
  value === null || value === undefined ? "n/a" : Number(value).toFixed(digits);
const ha = (value) =>
  value === null || value === undefined ? "n/a" : `${num(value, 2)} ha`;
const countText = (value) =>
  value === null || value === undefined ? "n/a" : Number(value).toLocaleString("en-GB");

function fact(label, value) {
  const wrap = document.createElement("div");
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  wrap.append(dt, dd);
  return wrap;
}

function listItems(target, items) {
  target.replaceChildren(
    ...items.map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    })
  );
}

function tableRows(target, rows) {
  target.replaceChildren();
  rows.forEach(([label, value]) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = label;
    const td = document.createElement("td");
    td.textContent = value;
    tr.append(th, td);
    target.append(tr);
  });
}

function activeLayers() {
  return state.source === "m1" ? M1_LAYERS : M0_LAYERS;
}

function activeLayer() {
  const layers = activeLayers();
  return layers[state.layer] ?? Object.values(layers)[0];
}

function layersForAnalysis(analysis) {
  return Object.entries(activeLayers()).filter(
    ([, spec]) => spec.analysis === analysis
  );
}

function setAspect(grid) {
  const width = Number(grid?.width);
  const height = Number(grid?.height);
  if (Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0) {
    compareEl.style.setProperty("--raster-aspect", `${width} / ${height}`);
  }
}

function periodImage(period, index, layer) {
  if (state.source === "m1") {
    if (layer.neutralMask) {
      const name = index === 0 ? "earlier_valid.png" : "later_valid.png";
      return g0File(state.studyId, name);
    }
    const relative = period.previews?.[layer.key];
    return relative ? m1File(state.studyId, relative) : "";
  }
  return period[layer.key] ? fileUrl(basename(period[layer.key])) : "";
}

function periodOverlay(index) {
  if (state.source !== "m1") return "";
  return g0File(
    state.studyId,
    index === 0 ? "earlier_invalid.png" : "later_invalid.png"
  );
}

function datesLabel(period) {
  const dates = (period.observation_dates || [])
    .slice()
    .sort((a, b) => String(a).localeCompare(String(b)));
  if (!dates.length) return period.date || "date unavailable";
  if (dates.length === 1) return dates[0];
  return `${dates[0]} → ${dates[dates.length - 1]} · ${dates.length} obs`;
}

function periodTitle(index) {
  return index === 0 ? "Earlier" : "Later";
}

function paneHead({ title, sub, meta, className = "" }) {
  const caption = document.createElement("figcaption");
  caption.className = `pane-head ${className}`.trim();
  const left = document.createElement("div");
  left.className = "pane-title";
  const strong = document.createElement("strong");
  strong.textContent = title;
  const span = document.createElement("span");
  span.textContent = sub || "";
  left.append(strong, span);
  const right = document.createElement("span");
  right.className = "pane-meta";
  right.textContent = meta || "";
  caption.append(left, right);
  return caption;
}

function missingNotice(stage, message = "Preview unavailable") {
  stage.classList.add("is-missing");
  stage.dataset.missing = message;
}

function rasterImage(src, alt, role = "raster", className = "") {
  const img = document.createElement("img");
  img.alt = alt;
  img.decoding = "async";
  img.loading = "eager";
  img.dataset.role = role;
  if (className) img.className = className;
  if (src) img.src = src;
  return img;
}

function overlayImage(src, alt) {
  const img = rasterImage(src, alt, "validity-overlay", "validity-overlay");
  return img;
}

function createStage({ images, overlay = "", className = "" }) {
  const stage = document.createElement("div");
  stage.className = `stage ${className}`.trim();
  images.forEach(({ src, alt, role }) => {
    const img = rasterImage(src, alt, role);
    img.addEventListener("error", () => missingNotice(stage));
    stage.append(img);
  });
  if (overlay) {
    const over = overlayImage(overlay, "Validity overlay");
    over.addEventListener("error", () => over.remove());
    stage.append(over);
  }
  return stage;
}

function emptyState(message) {
  compareEl.replaceChildren();
  const box = document.createElement("div");
  box.className = "empty-state";
  box.textContent = message;
  compareEl.append(box);
  setLegend({ note: "" });
}

function setLegend({ src = "", note = "", swatches = [] } = {}) {
  legendEl.hidden = !src;
  if (src) legendEl.src = src;
  legendEl.alt = src ? "Colour legend for the selected layer" : "";
  legendNoteEl.textContent = note;
  legendNoteEl.hidden = !note;
  legendSwatchesEl.hidden = !swatches.length;
  legendSwatchesEl.replaceChildren(
    ...swatches.map(({ color, label }) => {
      const wrap = document.createElement("span");
      wrap.className = "legend-swatch";
      const chip = document.createElement("span");
      chip.className = "swatch";
      chip.style.background = color;
      const text = document.createElement("span");
      text.textContent = label;
      wrap.append(chip, text);
      return wrap;
    })
  );
  legendRowEl.hidden = !src && !note && !swatches.length;
}

/* --------------------------------------------------------------- layers --- */
function renderLayerGroups() {
  const entries = layersForAnalysis(state.analysis);
  const groups = GROUP_ORDER.map((group) => [
    group,
    entries.filter(([, spec]) => spec.group === group),
  ]).filter(([, items]) => items.length);

  layerGroupsEl.replaceChildren(
    ...groups.map(([group, items]) => {
      const wrap = document.createElement("div");
      wrap.className = "layer-group";
      const label = document.createElement("span");
      label.className = "control-label";
      label.textContent = group;
      const segmented = document.createElement("div");
      segmented.className = "segmented";
      segmented.setAttribute("role", "group");
      segmented.setAttribute("aria-label", group);
      items.forEach(([id, spec]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.layer = id;
        button.textContent = spec.label;
        button.setAttribute("aria-pressed", String(id === state.layer));
        button.classList.toggle("is-active", id === state.layer);
        segmented.append(button);
      });
      wrap.append(label, segmented);
      return wrap;
    })
  );
}

function updateAnalysisControls() {
  analysisSwitchEl.querySelectorAll("button[data-analysis]").forEach((button) => {
    const active = button.dataset.analysis === state.analysis;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
    const available =
      button.dataset.analysis === "historical" || state.source === "m1";
    button.disabled = !available;
    button.title = available ? "" : "Available with the M1 science-engine bundle";
  });
  modeSwitchEl.querySelectorAll("button[data-mode]").forEach((button) => {
    const active = button.dataset.mode === state.mode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  viewGroupEl.hidden = state.analysis !== "historical";
  const overlayAvailable = state.source === "m1" && state.analysis !== "quality";
  overlayToggleEl.hidden = !overlayAvailable;
  overlayToggleEl.disabled = !overlayAvailable;
  overlayToggleEl.setAttribute("aria-pressed", String(state.overlay));
  overlayToggleEl.classList.toggle("is-active", state.overlay);
}

/* --------------------------------------------------------------- history --- */
function renderHistorical() {
  const layer = activeLayer();
  const periods =
    state.source === "m1" ? state.m1?.periods : state.summary?.periods;
  if (!periods?.length) {
    emptyState("No period previews are available in this study bundle.");
    return;
  }
  if (state.mode === "swipe") {
    renderSwipe(periods, layer);
  } else {
    renderSide(periods, layer);
  }
}

function renderSide(periods, layer) {
  compareEl.replaceChildren();
  const grid = document.createElement("div");
  grid.className = "side-grid";

  periods.slice(0, 2).forEach((period, index) => {
    const figure = document.createElement("figure");
    figure.className = "pane";
    figure.append(
      paneHead({
        title: periodTitle(index),
        sub: datesLabel(period),
        meta: `valid ${pct(period.valid_fraction)}`,
      })
    );
    figure.append(
      createStage({
        images: [
          {
            src: periodImage(period, index, layer),
            alt: `${layer.label} preview for ${periodTitle(index).toLowerCase()} period`,
            role: "period",
          },
        ],
        overlay: state.overlay ? periodOverlay(index) : "",
      })
    );
    grid.append(figure);
  });

  compareEl.append(grid);
}

function renderSwipe(periods, layer) {
  compareEl.replaceChildren();
  const earlier = periods[0];
  const later = periods[1] ?? periods[0];

  const frame = document.createElement("figure");
  frame.className = "swipe-frame";

  const head = document.createElement("figcaption");
  head.className = "swipe-head";
  const left = document.createElement("div");
  left.className = "swipe-head-side";
  const leftStrong = document.createElement("strong");
  leftStrong.textContent = "Earlier";
  const leftSpan = document.createElement("span");
  leftSpan.textContent = datesLabel(earlier);
  left.append(leftStrong, leftSpan);
  const right = document.createElement("div");
  right.className = "swipe-head-side is-right";
  const rightStrong = document.createElement("strong");
  rightStrong.textContent = "Later";
  const rightSpan = document.createElement("span");
  rightSpan.textContent = datesLabel(later);
  right.append(rightStrong, rightSpan);
  head.append(left, right);

  const stage = document.createElement("div");
  stage.className = "stage swipe-stage";
  stage.tabIndex = -1;
  stage.style.setProperty("--split", `${state.split}%`);

  const earlierImg = rasterImage(
    periodImage(earlier, 0, layer),
    `${layer.label} preview for the earlier period`,
    "earlier"
  );
  earlierImg.addEventListener("error", () => missingNotice(stage));
  stage.append(earlierImg);
  if (state.overlay) {
    const over = overlayImage(periodOverlay(0), "Earlier validity overlay");
    over.addEventListener("error", () => over.remove());
    stage.append(over);
  }

  const laterLayer = document.createElement("div");
  laterLayer.className = "swipe-layer";
  const laterImg = rasterImage(
    periodImage(later, 1, layer),
    `${layer.label} preview for the later period`,
    "later"
  );
  laterImg.addEventListener("error", () => missingNotice(stage));
  laterLayer.append(laterImg);
  if (state.overlay) {
    const over = overlayImage(periodOverlay(1), "Later validity overlay");
    over.addEventListener("error", () => over.remove());
    laterLayer.append(over);
  }
  stage.append(laterLayer);

  const divider = document.createElement("div");
  divider.className = "divider";
  divider.tabIndex = 0;
  divider.setAttribute("role", "slider");
  divider.setAttribute("aria-label", "Comparison divider");
  divider.setAttribute("aria-valuemin", "0");
  divider.setAttribute("aria-valuemax", "100");
  divider.setAttribute("aria-valuenow", String(Math.round(state.split)));
  divider.innerHTML =
    '<span class="divider-line" aria-hidden="true"></span>' +
    '<span class="divider-grip" aria-hidden="true"></span>';
  stage.append(divider);

  const tools = document.createElement("div");
  tools.className = "swipe-tools";
  const hint = document.createElement("span");
  hint.textContent = "Drag, tap, or focus the divider and use ← → keys.";
  const readout = document.createElement("span");
  readout.className = "swipe-readout";
  readout.setAttribute("aria-hidden", "true");
  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "reset-split";
  reset.textContent = "Reset 50%";
  tools.append(hint, readout, reset);

  frame.append(head, stage, tools);
  compareEl.append(frame);
  attachSwipe(stage, divider, readout, reset);
}

function attachSwipe(stage, divider, readout, reset) {
  let dragging = false;

  const apply = (value) => {
    state.split = Math.min(100, Math.max(0, Number(value)));
    stage.style.setProperty("--split", `${state.split}%`);
    const rounded = Math.round(state.split);
    divider.setAttribute("aria-valuenow", String(rounded));
    divider.setAttribute(
      "aria-valuetext",
      `${rounded}% earlier, ${100 - rounded}% later`
    );
    readout.textContent = `${rounded}% earlier / ${100 - rounded}% later`;
  };

  const splitFrom = (event) => {
    const box = stage.getBoundingClientRect();
    if (!box.width) return state.split;
    return ((event.clientX - box.left) / box.width) * 100;
  };

  stage.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    event.preventDefault();
    dragging = true;
    stage.classList.add("is-dragging");
    apply(splitFrom(event));
    stage.focus({ preventScroll: true });
    if (stage.setPointerCapture) {
      try {
        stage.setPointerCapture(event.pointerId);
      } catch (error) {
        /* pointer capture is best-effort */
      }
    }
  });

  stage.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    event.preventDefault();
    apply(splitFrom(event));
  });

  const endDrag = (event) => {
    if (!dragging) return;
    dragging = false;
    stage.classList.remove("is-dragging");
    if (stage.hasPointerCapture && stage.hasPointerCapture(event.pointerId)) {
      stage.releasePointerCapture(event.pointerId);
    }
  };
  stage.addEventListener("pointerup", endDrag);
  stage.addEventListener("pointercancel", endDrag);
  stage.addEventListener("lostpointercapture", () => {
    dragging = false;
    stage.classList.remove("is-dragging");
  });
  stage.addEventListener("dblclick", (event) => {
    event.preventDefault();
    apply(50);
  });

  divider.addEventListener("keydown", (event) => {
    let next = state.split;
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
    apply(next);
  });

  reset.addEventListener("click", () => apply(50));
  apply(state.split);
}

/* ---------------------------------------------------------------- change --- */
function renderChange() {
  if (state.source !== "m1") {
    emptyState("Change analysis requires the M1 science-engine bundle.");
    return;
  }
  const layer = activeLayer();
  const block = state.m1?.change?.[layer.index];
  if (!block) {
    emptyState(`No ${layer.label} difference block is present in the M1 summary.`);
    return;
  }

  compareEl.replaceChildren();
  const layout = document.createElement("div");
  layout.className = "change-layout";

  const main = document.createElement("figure");
  main.className = "change-main";
  main.append(
    paneHead({
      title: `${layer.label} · later − earlier`,
      sub: "Observed index difference, not a land-cover verdict",
      meta: `mean ${num(block.delta_stats?.mean, 4)}`,
    })
  );
  main.append(
    createStage({
      images: [
        {
          src: m1File(state.studyId, block.delta_preview),
          alt: `Difference map for ${layer.label}`,
          role: "change",
        },
      ],
      overlay: state.overlay ? g0File(state.studyId, "common_invalid.png") : "",
      className: "change-stage",
    })
  );

  const rail = document.createElement("aside");
  rail.className = "change-rail";
  rail.append(
    coverageCard(block),
    changeStatsCard(block),
    thresholdCard(block),
    contextCard(layer.index)
  );

  layout.append(main, rail);
  compareEl.append(layout);
}

function railCard(title) {
  const card = document.createElement("section");
  card.className = "rail-card";
  const heading = document.createElement("h3");
  heading.textContent = title;
  card.append(heading);
  return card;
}

function coverageCard(block) {
  const card = railCard("Common-valid coverage");
  const fraction = Number(block.common_valid_fraction_of_aoi ?? 0);
  const uniform = fraction >= 0.999;

  const callout = document.createElement("p");
  callout.className = "coverage-callout";
  const big = document.createElement("strong");
  big.textContent = pct(fraction);
  callout.append(big, document.createTextNode(" of the AOI is common-valid."));
  card.append(callout);

  const counts = document.createElement("p");
  counts.className = "rail-counts";
  counts.textContent = `${countText(block.common_valid_pixels)} px · ${num(
    block.common_valid_area_ha,
    2
  )} ha · ${num(block.common_valid_area_km2, 3)} km²`;
  card.append(counts);

  const note = document.createElement("p");
  note.className = "rail-note";
  note.textContent = uniform
    ? "Every AOI pixel is valid in both periods, so the shared footprint is uniform by construction. This is expected scientific behaviour, not a rendering defect."
    : "Some AOI pixels are missing in at least one period. Only the intersection is used for the difference map; masked pixels are never filled.";
  card.append(note);
  return card;
}

function changeStatsCard(block) {
  const card = railCard("Difference statistics");
  const stats = block.delta_stats || {};
  const primary = block.primary || {};
  const summary = document.createElement("p");
  summary.className = "rail-note";
  summary.textContent = `At |Δ| ≥ ${num(block.primary_threshold, 2)}: ${ha(
    primary.decrease_area_ha
  )} lower · ${ha(primary.increase_area_ha)} higher · ${ha(
    (Number(primary.stable_pixels || 0) * Number(block.pixel_area_m2 || 0)) / 10000
  )} unchanged.`;
  card.append(summary);

  const rows = [
    ["Mean Δ", num(stats.mean, 4)],
    ["Median Δ", num(stats.quantiles?.p50, 4)],
    ["5th percentile", num(stats.quantiles?.p05, 4)],
    ["95th percentile", num(stats.quantiles?.p95, 4)],
    ["Valid px", countText(stats.valid_count)],
  ];
  const table = document.createElement("table");
  table.className = "rail-table";
  rows.forEach(([label, value]) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = label;
    const td = document.createElement("td");
    td.textContent = value;
    tr.append(th, td);
    table.append(tr);
  });
  card.append(table);
  return card;
}

function thresholdCard(block) {
  const card = railCard("Measured threshold response");
  const table = document.createElement("table");
  table.className = "threshold-table";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["|Δ| ≥", "lower ha", "unchanged ha", "higher ha"].forEach((text) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = text;
    headRow.append(th);
  });
  head.append(headRow);
  const body = document.createElement("tbody");
  const pixelArea = Number(block.pixel_area_m2 || 0) / 10000;
  (block.thresholds || [])
    .slice()
    .sort((a, b) => Number(a.threshold) - Number(b.threshold))
    .forEach((row) => {
      const tr = document.createElement("tr");
      const values = [
        num(row.threshold, 2),
        num(row.decrease_area_ha, 2),
        num(Number(row.stable_pixels || 0) * pixelArea, 2),
        num(row.increase_area_ha, 2),
      ];
      values.forEach((value, index) => {
        const cell = document.createElement(index === 0 ? "th" : "td");
        if (index === 0) cell.scope = "row";
        cell.textContent = value;
        tr.append(cell);
      });
      body.append(tr);
    });
  table.append(head, body);
  card.append(table);

  const note = document.createElement("p");
  note.className = "rail-note";
  note.textContent = `These are the M1 measured thresholds (${(block.thresholds || [])
    .map((row) => num(row.threshold, 2))
    .join(", ")}). The wider M2 sensitivity sweep is a separate experiment.`;
  card.append(note);
  return card;
}

function contextCard(index) {
  const card = railCard("Context previews");
  const grid = document.createElement("div");
  grid.className = "context-grid";
  (state.m1?.periods || []).slice(0, 2).forEach((period, periodIndex) => {
    const figure = document.createElement("figure");
    figure.className = "context-figure";
    const caption = document.createElement("figcaption");
    caption.textContent = `${periodTitle(periodIndex)} · ${datesLabel(period)}`;
    const mean = period.indices?.[index]?.stats?.mean;
    const meta = document.createElement("span");
    meta.textContent = `${index.toUpperCase()} mean ${num(mean, 4)}`;
    caption.append(meta);
    const stage = createStage({
      images: [
        {
          src: m1File(state.studyId, period.previews?.[index] || ""),
          alt: `${index.toUpperCase()} context preview for ${periodTitle(
            periodIndex
          ).toLowerCase()} period`,
          role: "context",
        },
      ],
      className: "context-stage",
    });
    figure.append(caption, stage);
    grid.append(figure);
  });
  card.append(grid);
  return card;
}

/* --------------------------------------------------------------- quality --- */
function qualityCommonBlock() {
  if (state.source === "m1") {
    return Object.values(state.m1?.change || {})[0] || null;
  }
  return state.summary?.delta || null;
}

function qualityPeriod(index) {
  if (state.source === "m1") return state.m1?.periods?.[index] || null;
  return state.summary?.periods?.[index] || null;
}

function qualityImage(layer) {
  if (state.source !== "m1") {
    const period = qualityPeriod(layer.periodIndex ?? 0);
    return period?.mask_png ? fileUrl(basename(period.mask_png)) : "";
  }
  const period = qualityPeriod(layer.periodIndex ?? 0);
  if (layer.quality === "count") {
    const relative = period?.previews?.observation_count;
    return relative ? m1File(state.studyId, relative) : "";
  }
  if (layer.quality === "valid") {
    const name = (layer.periodIndex ?? 0) === 0 ? "earlier_valid.png" : "later_valid.png";
    return g0File(state.studyId, name);
  }
  if (layer.quality === "common") return g0File(state.studyId, "common_valid.png");
  if (layer.quality === "masked") return g0File(state.studyId, "masked_common.png");
  return "";
}

function renderQuality() {
  const layer = activeLayer();
  const period = qualityPeriod(layer.periodIndex ?? 0);
  const common = qualityCommonBlock();
  if (!period && !common) {
    emptyState("No quality artefacts are available in this study bundle.");
    return;
  }

  compareEl.replaceChildren();
  const layout = document.createElement("div");
  layout.className = "quality-layout";

  const main = document.createElement("figure");
  main.className = "quality-main";
  const meta =
    layer.quality === "count"
      ? `observations ${period?.observation_count ?? "n/a"}`
      : layer.quality === "common"
        ? `common-valid ${pct(common?.common_valid_fraction_of_aoi ?? common?.comparable_valid_fraction)}`
        : layer.quality === "masked"
          ? "invalid or unavailable pixels"
          : `valid ${pct(period?.valid_fraction)}`;
  main.append(
    paneHead({
      title: layer.label,
      sub:
        layer.quality === "count"
          ? `${periodTitle(layer.periodIndex ?? 0)} period`
          : "Validity and observation support",
      meta,
    })
  );
  main.append(
    createStage({
      images: [
        {
          src: qualityImage(layer),
          alt: `${layer.label} quality layer`,
          role: "quality",
        },
      ],
      className: "quality-stage",
    })
  );

  const rail = document.createElement("aside");
  rail.className = "quality-rail";
  rail.append(coverageSummaryCard(), qualityExplanationCard(), observationCountsCard());
  const dates = sourceDatesCard();
  if (dates) rail.append(dates);

  layout.append(main, rail);
  compareEl.append(layout);
}

function coverageSummaryCard() {
  const card = railCard("Valid coverage");
  const earlier = qualityPeriod(0);
  const later = qualityPeriod(1);
  const common = qualityCommonBlock();
  const grid = document.createElement("div");
  grid.className = "coverage-grid";

  const entries = [
    ["Earlier", earlier?.valid_fraction, earlier?.valid_pixels],
    ["Later", later?.valid_fraction, later?.valid_pixels],
    [
      "Shared",
      common?.common_valid_fraction_of_aoi ?? common?.comparable_valid_fraction,
      common?.common_valid_pixels ?? common?.valid_common_pixels,
    ],
  ];
  entries.forEach(([label, fraction, pixels]) => {
    const item = document.createElement("div");
    item.className = "coverage-card";
    if (Number(fraction) >= 0.999) item.classList.add("is-uniform");
    const heading = document.createElement("span");
    heading.className = "coverage-label";
    heading.textContent = label;
    const value = document.createElement("strong");
    value.className = "coverage-value";
    value.textContent = fraction === undefined ? "n/a" : pct(fraction);
    const count = document.createElement("span");
    count.className = "coverage-count";
    count.textContent = `${countText(pixels)} px`;
    item.append(heading, value, count);
    grid.append(item);
  });
  card.append(grid);
  return card;
}

function qualityExplanationCard() {
  const card = railCard("How to read this");
  const common = qualityCommonBlock();
  const fraction = Number(
    common?.common_valid_fraction_of_aoi ?? common?.comparable_valid_fraction ?? 0
  );
  const note = document.createElement("p");
  note.className = "rail-note";
  if (fraction >= 0.999) {
    note.textContent =
      "All AOI pixels are valid in both periods. A uniform shared footprint is mathematically expected here; it is not an all-clear map and it is not a mask defect. Use the observation-count layers to inspect genuine per-pixel variation.";
  } else {
    note.textContent = `Coverage is partial: ${pct(
      1 - fraction
    )} of the AOI is missing in at least one period. Masked pixels are shown in neutral charcoal and are never interpolated as observations.`;
  }
  card.append(note);
  return card;
}

function observationCountsCard() {
  const card = railCard("Observations per pixel");
  const counts = state.quality?.observation_counts;
  const periods = [
    ["Earlier", counts?.earlier, qualityPeriod(0)],
    ["Later", counts?.later, qualityPeriod(1)],
  ];
  if (!counts && !periods.some(([, , period]) => period?.observation_count_stats)) {
    const note = document.createElement("p");
    note.className = "rail-note";
    note.textContent = "Observation-count statistics are not present in this bundle.";
    card.append(note);
    return card;
  }

  periods.forEach(([label, histogram, period]) => {
    const block = document.createElement("div");
    block.className = "count-block";
    const heading = document.createElement("h4");
    heading.textContent = label;
    block.append(heading);
    if (histogram) {
      const max = Math.max(1, ...Object.values(histogram).map(Number));
      Object.entries(histogram)
        .sort(([a], [b]) => Number(a) - Number(b))
        .forEach(([key, value]) => {
          const row = document.createElement("div");
          row.className = "count-row";
          const name = document.createElement("span");
          name.textContent = Number(key) === 0 ? "0 (masked)" : `${key} obs`;
          const track = document.createElement("span");
          track.className = "count-track";
          const bar = document.createElement("span");
          bar.className = "count-bar";
          bar.style.width = `${(Number(value) / max) * 100}%`;
          track.append(bar);
          const total = document.createElement("span");
          total.className = "count-value";
          total.textContent = countText(value);
          row.append(name, track, total);
          block.append(row);
        });
    } else {
      const stats = period.observation_count_stats || {};
      const note = document.createElement("p");
      note.className = "rail-note";
      note.textContent = `range ${stats.min ?? "?"}–${stats.max ?? "?"}, mean ${num(
        stats.mean,
        2
      )}, median ${num(stats.median, 1)}`;
      block.append(note);
    }
    card.append(block);
  });
  return card;
}

function sourceDatesCard() {
  if (state.source !== "m1") return null;
  const card = railCard("Source observations");
  const list = document.createElement("ul");
  list.className = "source-list";
  (state.m1?.periods || []).forEach((period, index) => {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = `${periodTitle(index)} · ${period.observation_count} obs`;
    const detail = document.createElement("span");
    detail.textContent = (period.item_ids || []).join(", ") || "scene IDs unavailable";
    item.append(title, detail);
    list.append(item);
  });
  card.append(list);
  return card;
}

/* ------------------------------------------------------------------ M0 --- */
function renderFacts(summary) {
  factsEl.replaceChildren(
    fact("Analysis CRS", summary.grid?.crs ?? "n/a"),
    fact("Resolution", `${summary.grid?.resolution_m ?? "?"} m`),
    fact("Raster size", `${summary.grid?.width ?? "?"} × ${summary.grid?.height ?? "?"} px`),
    fact("Comparable valid pixels", String(summary.delta?.valid_common_pixels ?? "n/a")),
    fact("Comparable valid", pct(summary.delta?.comparable_valid_fraction)),
    fact("Generated (UTC)", summary.generated_utc ?? "n/a")
  );
}

function renderMeta(summary) {
  const rows = [];
  summary.periods.forEach((period, index) => {
    const tag = index === 0 ? "Earlier" : "Later";
    rows.push(
      [`${tag} scene`, period.item_id],
      [`${tag} date`, period.date],
      [
        `${tag} scene cloud`,
        period.cloud_cover_percent === null
          ? "n/a"
          : `${Number(period.cloud_cover_percent).toFixed(2)} % (whole scene)`,
      ],
      [`${tag} AOI valid`, pct(period.valid_fraction)],
      [`${tag} NDVI mean`, num(period.ndvi_stats?.mean, 4)]
    );
  });
  tableRows(metaEl, rows);
}

function renderNotes(summary) {
  const delta = summary.delta ?? {};
  const items = [];
  if (!delta.suitable_for_comparison) {
    items.push(
      "Comparable valid coverage is below the 50 % usability threshold; treat the difference as indicative only."
    );
  }
  items.push(
    `Common mask covers ${pct(delta.comparable_valid_fraction)} of the AOI (${delta.valid_common_pixels ?? 0} px).`
  );
  items.push(
    "Cloud, cloud shadow, cirrus, saturated and nodata pixels are excluded via the SCL layer; nothing is interpolated."
  );
  items.push(
    `Thresholded change at |ΔNDVI| ≥ ${delta.threshold}: ${delta.thresholded_areas?.decrease_pixels ?? 0} px decrease, ${delta.thresholded_areas?.increase_pixels ?? 0} px increase.`
  );
  items.push(
    "Tidal stage and turbidity differ between the two dates and are not controlled here."
  );
  items.push(
    "NDVI difference is an observed spectral signal, not a land-cover classification."
  );
  listItems(notesEl, items);
}

function renderProvenance(summary) {
  const items = [
    "Catalog collection: sentinel-2-l2a via Element 84 Earth Search (AWS Open Data)",
    "Bands: B02, B03, B04, B08 and SCL read as windowed COG byte ranges",
    "Manifest: data/manifests/m0_primary_study.json",
  ];
  (summary.verification ?? []).forEach((check) => {
    items.push(
      `NDVI re-check ${check.period_id}: max |Δ| ${Number(check.max_abs_difference).toExponential(2)} over ${check.sample_size} px — ${check.within_tolerance ? "within tolerance" : "OUT OF TOLERANCE"}`
    );
  });
  listItems(provEl, items);
}

function applyM0Legend() {
  const layer = activeLayer();
  if (layer.key === "ndvi_png") {
    setLegend({
      src: "/files/preview/ndvi_legend.png",
      note: "NDVI colour ramp is fixed for both dates, so equal values share a colour. Charcoal pixels are masked (cloud, shadow, nodata or outside the AOI).",
    });
  } else if (layer.key === "mask_png") {
    setLegend({
      note: "This is the M0 valid-mask preview. It is shown for continuity with the M1 quality mode; the M1 bundle provides neutral validity and observation-count layers.",
    });
  } else {
    setLegend({
      note: "Per-band 2–98 percentile linear stretch on valid pixels. Charcoal pixels are masked or outside the AOI.",
    });
  }
}

function applyM1Legend() {
  if (state.analysis === "change") {
    const layer = activeLayer();
    setLegend({
      src: m1File(state.studyId, "change_legend.png"),
      note: `Diverging map of later minus earlier ${layer.index.toUpperCase()}, saturated at ±0.30 index units. Ivory is zero (no observed change), teal is lower later, copper is higher later, charcoal is outside the common-valid footprint.`,
    });
    return;
  }
  if (state.analysis === "quality") {
    const layer = activeLayer();
    if (layer.quality === "count") {
      setLegend({
        src: m1File(state.studyId, "observation_count_legend.png"),
        note: "Discrete count of valid observations contributing to each composite pixel; charcoal = 0 valid observations. Copper intensity encodes count, not positive index change.",
      });
    } else {
      setLegend({
        swatches: [
          { color: "#8fb0aa", label: "Observed valid" },
          { color: "#18272d", label: "Masked / unavailable" },
          { color: "#5f706c", label: "AOI boundary" },
        ],
        note: "Neutral validity colours. Masked pixels are never interpolated or filled as observations.",
      });
    }
    return;
  }

  const layer = activeLayer();
  if (layer.legend) {
    let note =
      layer.legend === "observation_count_legend"
        ? "Discrete count of valid observations contributing to each composite pixel; charcoal = 0 valid observations."
        : `${layer.label} ramp is fixed for both periods, so equal values share a colour. Charcoal pixels are masked.`;
    if (layer.key === "mndwi") {
      note += " MNDWI uses 20 m SWIR resampled to 10 m: no genuine 10 m SWIR detail.";
    }
    setLegend({ src: m1File(state.studyId, `${layer.legend}.png`), note });
  } else if (layer.neutralMask) {
    setLegend({
      swatches: [
        { color: "#8fb0aa", label: "Observed valid" },
        { color: "#18272d", label: "Masked / unavailable" },
        { color: "#5f706c", label: "AOI boundary" },
      ],
      note: "Neutral validity colours, generated from the same valid-mask rasters used by the M1 engine. A uniform footprint is expected when both dates are fully valid inside the AOI.",
    });
  } else {
    setLegend({
      note: "Per-band 2–98 percentile linear stretch on valid pixels. Charcoal pixels are masked or outside the AOI.",
    });
  }
}

async function loadM0() {
  const response = await fetch("/api/study");
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${response.status}`);
  }
  const summary = await response.json();
  state.source = "m0";
  state.summary = summary;
  state.m1 = null;
  state.quality = null;
  state.studyId = null;
  state.analysis = "historical";
  state.layer = "true_colour";
  state.mode = "side";
  state.split = 50;
  state.overlay = false;

  brandTagEl.textContent = "M0 · data proof";
  document.title = "HabitatShift · M0 proof viewer";
  document.querySelector("h1").textContent = summary.title;
  ledeEl.textContent =
    "Same bounded window, two acquisition dates: true colour, NDVI and validity masks from real Sentinel-2 L2A scenes. The M0 bundle has no derived difference maps; the M1 bundle adds change and quality analysis.";
  setAspect(summary.grid);
  renderFacts(summary);
  renderMeta(summary);
  renderNotes(summary);
  renderProvenance(summary);
  attributionEl.textContent = summary.attribution;
  updateAnalysisControls();
  renderLayerGroups();
  render();
  applyM0Legend();

  if (!summary.delta?.suitable_for_comparison) {
    bannerEl.hidden = false;
    bannerEl.textContent =
      "Limited comparison quality: valid coverage in both dates is below the usability threshold.";
  } else {
    bannerEl.hidden = true;
  }
}

/* ---------------------------------------------------------------- M1 ----- */
function renderM1Facts(m1) {
  const changes = Object.values(m1.change || {});
  const common = changes.length
    ? Math.min(...changes.map((block) => Number(block.common_valid_fraction_of_aoi || 0)))
    : null;
  const observations = m1.periods
    .map((period) => period.observation_count)
    .join(" / ");
  factsEl.replaceChildren(
    fact("Analysis CRS", m1.grid?.crs ?? "n/a"),
    fact("Resolution", `${m1.grid?.resolution_m ?? "?"} m`),
    fact("Raster size", `${m1.grid?.width ?? "?"} × ${m1.grid?.height ?? "?"} px`),
    fact("AOI area", `${num(m1.aoi?.area_km2, 3)} km²`),
    fact("Observations earlier / later", observations),
    fact("Common-valid (worst index)", common === null ? "n/a" : pct(common))
  );
}

function renderM1Meta(m1) {
  const rows = [
    ["Experiment", m1.experiment_id ?? "n/a"],
    ["Grid signature", m1.grid?.signature ?? "n/a"],
    ["Composite method", `${m1.periods?.[0]?.composite_method ?? "n/a"} of valid observations`],
    ["Generated (UTC)", m1.generated_utc ?? "n/a"],
  ];
  m1.periods.forEach((period, index) => {
    const tag = index === 0 ? "Earlier" : "Later";
    const means = Object.entries(period.indices || {})
      .map(([key, block]) => `${key.toUpperCase()} ${num(block.stats?.mean, 4)}`)
      .join(" · ");
    rows.push(
      [`${tag} dates`, (period.observation_dates || []).join(", ")],
      [`${tag} observations`, String(period.observation_count ?? "n/a")],
      [
        `${tag} count range`,
        `${period.observation_count_stats?.min ?? "?"}–${period.observation_count_stats?.max ?? "?"} per pixel`,
      ],
      [`${tag} scenes`, (period.item_ids || []).join(", ")],
      [`${tag} index means`, means || "n/a"]
    );
  });
  tableRows(metaEl, rows);
}

function renderM1Notes(m1) {
  const items = [];
  Object.entries(m1.change || {}).forEach(([key, block]) => {
    const threshold = Number(block.primary_threshold);
    items.push(
      `${key.toUpperCase()} at |Δ| ≥ ${threshold}: ${ha(
        block.primary?.decrease_area_ha
      )} lower / ${ha(block.primary?.increase_area_ha)} higher on the ${num(
        block.common_valid_area_ha,
        1
      )} ha common-valid footprint.`
    );
  });
  const common = Object.values(m1.change || {})[0];
  if (common && Number(common.common_valid_fraction_of_aoi) >= 0.999) {
    items.push(
      "Every AOI pixel is common-valid in both periods. The shared footprint is uniform by construction; its 100% coverage indicator is not a thematic all-clear map."
    );
  }
  items.push(
    "Differences are candidate spectral signals at a stated threshold; they are not verified deforestation, wetland loss, construction or glacier damage."
  );
  if (m1.indices?.mndwi?.upsampled || m1.indices?.ndsi?.upsampled) {
    items.push(
      "MNDWI uses 20 m SWIR (B11) resampled to the 10 m grid; it contains no genuine 10 m SWIR detail."
    );
  }
  items.push(...(m1.limitations || []));
  listItems(notesEl, items);
}

function renderM1Provenance(m1) {
  const verification = m1.verification || {};
  const items = [
    `Pipeline ${m1.pipeline_version ?? "?"}, experiment ${m1.experiment_id ?? "?"}`,
    `Grid ${m1.grid?.crs ?? "?"} at ${m1.grid?.resolution_m ?? "?"} m, ${m1.grid?.width ?? "?"} × ${m1.grid?.height ?? "?"} px, signature ${m1.grid?.signature ?? "?"}`,
    "Bands read: B02/B03/B04/B08 at 10 m and B11/SCL at 20 m, resampled on read (bilinear reflectance, nearest SCL)",
    `Independent verification: ${verification.check_count ?? 0} checks — ${verification.all_passed ? "all passed" : "FAILED: " + (verification.failed_checks || []).join(", ")}`,
    `Manifest: data/manifests/m1_${state.studyId}.json`,
  ];
  if (state.quality) {
    items.push(
      "Neutral validity previews and overlays are presentation-only derivatives of the exported valid-mask rasters; they do not alter the M1 summary, statistics or manifest."
    );
  }
  m1.periods.forEach((period) => {
    items.push(
      `${period.period_id === "earlier" ? "Earlier" : "Later"} scenes: ${(period.item_ids || []).join(", ")}`
    );
  });
  listItems(provEl, items);
}

async function loadM1(studyId) {
  const [response, presentation] = await Promise.all([
    fetch(`/api/m1/study/${encodeURIComponent(studyId)}`),
    fetch(`/api/m1/study/${encodeURIComponent(studyId)}/presentation`).catch(
      () => null
    ),
  ]);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${response.status}`);
  }
  const m1 = await response.json();
  state.source = "m1";
  state.studyId = studyId;
  state.m1 = m1;
  state.summary = null;
  state.quality =
    presentation && presentation.ok ? await presentation.json().catch(() => null) : null;
  state.analysis = "historical";
  state.layer = "true_colour";
  state.mode = "side";
  state.split = 50;
  state.overlay = false;

  brandTagEl.textContent = "M2 · comparison repair";
  document.title = "HabitatShift · M1 science engine";
  document.querySelector("h1").textContent = m1.study?.title ?? studyId;
  ledeEl.textContent = `${m1.study?.question ?? ""} Median composites of up to ${
    m1.periods?.[0]?.observation_count ?? 3
  } observations per period, NDVI/NDWI/MNDWI on surface reflectance, and matched-valid difference maps. Use Historical for shared-viewport comparison, Change for the derived difference map, and Quality for validity and observation support. Every value is read from the M1 summary.`;

  setAspect(m1.grid);
  renderM1Facts(m1);
  renderM1Meta(m1);
  renderM1Notes(m1);
  renderM1Provenance(m1);
  attributionEl.textContent =
    typeof m1.attribution === "string"
      ? m1.attribution
      : "Copernicus Sentinel data — free and open with attribution (ESA)";

  updateAnalysisControls();
  renderLayerGroups();
  render();
  applyM1Legend();

  const unsuitable = Object.values(m1.change || {}).filter(
    (block) => block.suitable_for_comparison === false
  );
  if (unsuitable.length) {
    bannerEl.hidden = false;
    bannerEl.textContent =
      "Limited comparison quality: at least one index falls below the common-valid coverage threshold.";
  } else {
    bannerEl.hidden = true;
  }
}

/* --------------------------------------------------------------- routing --- */
function render() {
  compareEl.dataset.mode = state.mode;
  compareEl.dataset.analysis = state.analysis;
  compareEl.dataset.overlay = state.overlay ? "on" : "off";
  if (state.analysis === "historical") {
    renderHistorical();
  } else if (state.analysis === "change") {
    renderChange();
  } else {
    renderQuality();
  }
}

async function load() {
  try {
    const response = await fetch("/api/m1/studies");
    if (response.ok) {
      const payload = await response.json();
      const study = (payload.studies || [])[0];
      if (study) {
        try {
          await loadM1(study.study_id);
          return;
        } catch (m1Error) {
          console.warn("M1 bundle unavailable, falling back to M0:", m1Error);
        }
      }
    }
  } catch (error) {
    console.warn("M1 discovery failed, falling back to M0:", error);
  }
  try {
    await loadM0();
  } catch (error) {
    ledeEl.textContent = `Could not load measured data: ${error.message}. Start the API with scripts/serve_viewer.ps1.`;
    emptyState("The study bundle could not be loaded.");
  }
}

function selectAnalysis(analysis) {
  state.analysis = analysis;
  const entries = layersForAnalysis(analysis);
  if (!entries.some(([id]) => id === state.layer)) {
    state.layer = entries[0]?.[0] ?? state.layer;
  }
  updateAnalysisControls();
  renderLayerGroups();
  render();
  if (state.source === "m1") applyM1Legend();
  else applyM0Legend();
}

analysisSwitchEl.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-analysis]");
  if (!button || button.disabled) return;
  selectAnalysis(button.dataset.analysis);
});

modeSwitchEl.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-mode]");
  if (!button) return;
  state.mode = button.dataset.mode;
  updateAnalysisControls();
  render();
  if (state.source === "m1") applyM1Legend();
  else applyM0Legend();
});

layerGroupsEl.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-layer]");
  if (!button) return;
  state.layer = button.dataset.layer;
  renderLayerGroups();
  render();
  if (state.source === "m1") applyM1Legend();
  else applyM0Legend();
});

overlayToggleEl.addEventListener("click", () => {
  state.overlay = !state.overlay;
  updateAnalysisControls();
  render();
});

load();
