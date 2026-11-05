/* HabitatShift M0 proof viewer.
 * Renders only what /api/study returns: no client-side index maths, no
 * hardcoded metrics.
 */
const LAYERS = {
  true_colour: { key: "png", label: "True colour" },
  ndvi: { key: "ndvi_png", label: "NDVI" },
  mask: { key: "mask_png", label: "Valid mask" },
};

const state = { layer: "true_colour", mode: "side", split: 50, summary: null };

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

const fileUrl = (name) => `/files/preview/${encodeURIComponent(name)}`;
const basename = (relPath) => String(relPath || "").split("/").pop();
const pct = (fraction) => `${(Number(fraction || 0) * 100).toFixed(1)}%`;
const num = (value, digits = 3) =>
  value === null || value === undefined ? "n/a" : Number(value).toFixed(digits);

function fact(label, value) {
  const wrap = document.createElement("div");
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  wrap.append(dt, dd);
  return wrap;
}

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
    img.alt = `${LAYERS[state.layer].label} preview, ${period.date}, scene ${period.item_id}`;
    img.src = fileUrl(basename(period[LAYERS[state.layer].key]));
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
  metaEl.replaceChildren();
  summary.periods.forEach((period, index) => {
    const tag = index === 0 ? "Earlier" : "Later";
    const rows = [
      [`${tag} scene`, period.item_id],
      [`${tag} date`, period.date],
      [
        `${tag} scene cloud`,
        period.cloud_cover_percent === null
          ? "n/a"
          : `${Number(period.cloud_cover_percent).toFixed(2)} % (whole scene)`,
      ],
      [`${tag} AOI valid`, pct(period.valid_fraction)],
      [`${tag} NDVI mean`, num(period.ndvi_stats?.mean, 4)],
    ];
    rows.forEach(([label, value]) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.scope = "row";
      th.textContent = label;
      const td = document.createElement("td");
      td.textContent = value;
      tr.append(th, td);
      metaEl.append(tr);
    });
  });
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
  notesEl.replaceChildren(
    ...items.map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    })
  );
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
  provEl.replaceChildren(
    ...items.map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    })
  );
}

function applyLayer() {
  if (!state.summary) return;
  renderPanes(state.summary);
  const isNdvi = state.layer === "ndvi";
  legendEl.hidden = !isNdvi;
  legendNoteEl.hidden = !isNdvi;
  if (isNdvi) legendEl.src = "/files/preview/ndvi_legend.png";
}

async function load() {
  try {
    const response = await fetch("/api/study");
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `HTTP ${response.status}`);
    }
    const summary = await response.json();
    state.summary = summary;
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
  applyLayer();
});

document.getElementById("mode-switch").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-mode]");
  if (!button) return;
  state.mode = button.dataset.mode;
  compareEl.dataset.mode = state.mode;
  document
    .querySelectorAll("#mode-switch button")
    .forEach((b) => b.classList.toggle("is-active", b === button));
  applyLayer();
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
