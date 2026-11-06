/* HabitatShift proof viewer.
 *
 * Serves the M1 science-engine bundle when one exists and falls back to the
 * original M0 two-scene study otherwise.  Every number is read from a pipeline
 * artefact: there is no client-side index maths and no hardcoded metric.
 */
const M0_LAYERS = {
  true_colour: { key: "png", label: "True colour" },
  ndvi: { key: "ndvi_png", label: "NDVI" },
  mask: { key: "mask_png", label: "Valid mask" },
};

const M1_LAYERS = {
  true_colour: { kind: "period", key: "true_colour", label: "True colour" },
  false_colour: { kind: "period", key: "false_colour", label: "False colour" },
  ndvi: { kind: "period", key: "ndvi", label: "NDVI", legend: "ndvi_legend" },
  ndwi: { kind: "period", key: "ndwi", label: "NDWI", legend: "ndwi_legend" },
  mndwi: { kind: "period", key: "mndwi", label: "MNDWI", legend: "mndwi_legend" },
  delta_ndvi: { kind: "change", index: "ndvi", label: "Δ NDVI" },
  delta_ndwi: { kind: "change", index: "ndwi", label: "Δ NDWI" },
  delta_mndwi: { kind: "change", index: "mndwi", label: "Δ MNDWI" },
  valid_mask: { kind: "period", key: "valid_mask", label: "Valid mask" },
  observation_count: {
    kind: "period",
    key: "observation_count",
    label: "Observations",
    legend: "observation_count_legend",
  },
};

const state = {
  source: "m0",
  layer: "true_colour",
  mode: "side",
  split: 50,
  summary: null,
  m1: null,
  studyId: null,
};

const compareEl = document.getElementById("compare");
const factsEl = document.getElementById("facts");
const metaEl = document.getElementById("meta");
const notesEl = document.getElementById("notes");
const provEl = document.getElementById("provenance");
const bannerEl = document.getElementById("banner");
const ledeEl = document.getElementById("lede");
const legendEl = document.getElementById("legend");
const legendNoteEl = document.getElementById("legend-note");
const attributionEl = document.getElementById("attribution");
const layerSwitchEl = document.getElementById("layer-switch");
const brandTagEl = document.querySelector(".brand-tag");

const fileUrl = (name) => `/files/preview/${encodeURIComponent(name)}`;
const m1File = (studyId, relPath) =>
  `/files/m1/${encodeURIComponent(studyId)}/previews/${encodeURIComponent(
    String(relPath || "").split("/").pop()
  )}`;
const basename = (relPath) => String(relPath || "").split("/").pop();
const pct = (fraction) => `${(Number(fraction || 0) * 100).toFixed(1)}%`;
const num = (value, digits = 3) =>
  value === null || value === undefined ? "n/a" : Number(value).toFixed(digits);
const ha = (value) => (value === null || value === undefined ? "n/a" : `${num(value, 2)} ha`);

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

function addPane(label, meta, src, alt) {
  const figure = document.createElement("figure");
  figure.className = "pane";
  const caption = document.createElement("figcaption");
  const left = document.createElement("span");
  left.textContent = label;
  const right = document.createElement("span");
  right.textContent = meta;
  caption.append(left, right);

  const img = document.createElement("img");
  img.className = "slot";
  img.alt = alt;
  img.src = src;
  figure.append(caption, img);
  compareEl.append(figure);
  return figure;
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

function renderPanes(summary) {
  compareEl.replaceChildren();
  summary.periods.forEach((period, index) => {
    const figure = document.createElement("figure");
    figure.className = "pane";
    const caption = document.createElement("figcaption");
    const left = document.createElement("span");
    left.textContent = `${index === 0 ? "Earlier" : "Later"} · ${period.date}`;
    const right = document.createElement("span");
    right.textContent = `valid ${pct(period.valid_fraction)}`;
    caption.append(left, right);

    const img = document.createElement("img");
    img.className = "slot";
    img.alt = `${M0_LAYERS[state.layer].label} preview, ${period.date}, scene ${period.item_id}`;
    img.src = fileUrl(basename(period[M0_LAYERS[state.layer].key]));
    figure.append(caption, img);
    compareEl.append(figure);
  });
  if (state.mode === "swipe") {
    const handle = document.createElement("div");
    handle.className = "swipe-handle";
    compareEl.append(handle);
  }
  compareEl.style.setProperty("--split", `${state.split}%`);
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

function applyM0Layer() {
  renderPanes(state.summary);
  const isNdvi = state.layer === "ndvi";
  legendEl.hidden = !isNdvi;
  legendNoteEl.hidden = !isNdvi;
  if (isNdvi) legendEl.src = "/files/preview/ndvi_legend.png";
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
  brandTagEl.textContent = "M0 · data proof";
  document.title = "HabitatShift · M0 proof viewer";
  document.querySelector("h1").textContent = summary.title;
  ledeEl.textContent =
    "Same bounded window, two acquisition dates: true colour, NDVI and validity masks from real Sentinel-2 L2A scenes. Toggle layers to see what the mask removes before trusting any difference.";
  renderFacts(summary);
  renderPanes(summary);
  renderMeta(summary);
  renderNotes(summary);
  renderProvenance(summary);
  attributionEl.textContent = summary.attribution;
  if (!summary.delta?.suitable_for_comparison) {
    bannerEl.hidden = false;
    bannerEl.textContent =
      "Limited comparison quality: valid coverage in both dates is below the usability threshold.";
  }
}

/* ------------------------------------------------------------------ M1 --- */
function renderM1LayerSwitch() {
  layerSwitchEl.replaceChildren(
    ...Object.entries(M1_LAYERS).map(([id, spec]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.layer = id;
      button.textContent = spec.label;
      button.classList.toggle("is-active", id === state.layer);
      return button;
    })
  );
}

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

function renderM1Panes() {
  const m1 = state.m1;
  const studyId = state.studyId;
  const layer = M1_LAYERS[state.layer];
  compareEl.replaceChildren();

  if (layer.kind === "change") {
    const block = (m1.change || {})[layer.index];
    if (!block) {
      addPane("Difference unavailable", "no change block", "", "No difference map");
    } else {
      addPane(
        `Δ ${layer.index.toUpperCase()} · later − earlier`,
        `common-valid ${pct(block.common_valid_fraction_of_aoi)}`,
        m1File(studyId, block.delta_preview),
        `Difference map for ${layer.index.toUpperCase()}`
      );
      addPane(
        `Common-valid footprint · ${layer.index.toUpperCase()}`,
        `${block.common_valid_pixels ?? 0} px`,
        m1File(studyId, block.common_valid_preview),
        `Common-valid mask for ${layer.index.toUpperCase()}`
      );
    }
  } else {
    m1.periods.forEach((period, index) => {
      const dates = (period.observation_dates || []).join(", ");
      addPane(
        `${index === 0 ? "Earlier" : "Later"} · ${dates}`,
        `valid ${pct(period.valid_fraction)}`,
        m1File(studyId, period.previews?.[layer.key]),
        `${layer.label} preview, ${dates}`
      );
    });
  }

  if (state.mode === "swipe") {
    const handle = document.createElement("div");
    handle.className = "swipe-handle";
    compareEl.append(handle);
  }
  compareEl.style.setProperty("--split", `${state.split}%`);
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
  m1.periods.forEach((period) => {
    items.push(
      `${period.period_id === "earlier" ? "Earlier" : "Later"} scenes: ${(period.item_ids || []).join(", ")}`
    );
  });
  listItems(provEl, items);
}

function applyM1Layer() {
  renderM1Panes();
  const layer = M1_LAYERS[state.layer];
  let legend = null;
  let note = "";
  if (layer.legend) {
    legend = `${layer.legend}.png`;
    note =
      layer.legend === "observation_count_legend"
        ? "Discrete count of valid observations contributing to each composite pixel; charcoal = 0."
        : `${layer.label} ramp is fixed for both periods, so equal values share a colour. Charcoal pixels are masked.`;
    if (layer.key === "mndwi") {
      note += " MNDWI uses 20 m SWIR resampled to 10 m: no genuine 10 m SWIR detail.";
    }
  } else if (layer.kind === "change") {
    legend = "change_legend.png";
    note =
      "Diverging map of later minus earlier, saturated at ±0.30 index units. Teal = lower later value, copper = higher; charcoal = outside the common-valid footprint.";
  }
  legendEl.hidden = !legend;
  legendNoteEl.hidden = !legend;
  if (legend) legendEl.src = m1File(state.studyId, legend);
  if (legend) legendNoteEl.textContent = note;
}

async function loadM1(studyId) {
  const response = await fetch(`/api/m1/study/${encodeURIComponent(studyId)}`);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${response.status}`);
  }
  const m1 = await response.json();
  state.source = "m1";
  state.studyId = studyId;
  state.m1 = m1;
  state.summary = null;
  state.layer = "true_colour";

  brandTagEl.textContent = "M1 · temporal change";
  document.title = "HabitatShift · M1 science engine";
  document.querySelector("h1").textContent = m1.study?.title ?? studyId;
  ledeEl.textContent = `${m1.study?.question ?? ""} Median composites of up to ${
    m1.periods?.[0]?.observation_count ?? 3
  } observations per period, NDVI/NDWI/MNDWI on surface reflectance, and matched-valid difference maps. Every value below is read from the M1 summary.`;

  renderM1LayerSwitch();
  renderM1Facts(m1);
  renderM1Panes();
  renderM1Meta(m1);
  renderM1Notes(m1);
  renderM1Provenance(m1);
  attributionEl.textContent =
    typeof m1.attribution === "string"
      ? m1.attribution
      : "Copernicus Sentinel data — free and open with attribution (ESA)";
  applyM1Layer();

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
  }
}

document.getElementById("layer-switch").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-layer]");
  if (!button) return;
  state.layer = button.dataset.layer;
  document
    .querySelectorAll("#layer-switch button")
    .forEach((b) => b.classList.toggle("is-active", b === button));
  if (state.source === "m1") applyM1Layer();
  else applyM0Layer();
});

document.getElementById("mode-switch").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-mode]");
  if (!button) return;
  state.mode = button.dataset.mode;
  compareEl.dataset.mode = state.mode;
  document
    .querySelectorAll("#mode-switch button")
    .forEach((b) => b.classList.toggle("is-active", b === button));
  if (state.source === "m1") applyM1Layer();
  else applyM0Layer();
});

compareEl.addEventListener("pointermove", (event) => {
  if (state.mode !== "swipe") return;
  const box = compareEl.getBoundingClientRect();
  state.split = Math.min(
    100,
    Math.max(0, ((event.clientX - box.left) / box.width) * 100)
  );
  compareEl.style.setProperty("--split", `${state.split}%`);
});

load();
