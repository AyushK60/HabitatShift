/* M4 real-browser verification with Playwright/Chromium.
 *
 * Evolves the M3 suite (verify_m3.mjs) to the M4 product: the gallery now
 * links six processed investigations, the workstation renders portable
 * bundles for every study (showcase mode) with live enhancement for Coringa,
 * and every analytical chart is interactive and explanatory.
 *
 * Coverage: all M3 interaction contracts (synchronised maps, hover/touch/
 * keyboard swipe, reset, layers, quality views, pixel probe, experiments
 * workspace, responsive layouts, provenance) PLUS the M4 additions: gallery
 * statuses incl. the recorded PARTIAL verdict, Chilika's experiment
 * switcher, interactive chart hover/keyboard/pin behaviour with recorded
 * values, both Himalayan event views as separate investigations, the
 * Kathmandu NDBI guardrail, and showcase independence from the backend.
 * Screenshots are written under docs/evidence/m4/.
 *
 * Usage:
 *   HABITATSHIFT_URL=http://127.0.0.1:8098/ node tools/visual/verify_m4.mjs
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const BASE_URL = process.env.HABITATSHIFT_URL || "http://127.0.0.1:8098/";
const EVIDENCE = path.resolve(import.meta.dirname, "../../docs/evidence/m4");
const VIEWPORTS = [
  { name: "1920x1080", width: 1920, height: 1080 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1280x800", width: 1280, height: 800 },
  { name: "768", width: 768, height: 900 },
  { name: "390", width: 390, height: 844 },
];

const results = {
  base_url: BASE_URL,
  suite: "habitatshift-m4-browser/1",
  started_utc: new Date().toISOString(),
  checks: [],
  screenshots: [],
  console_errors: [],
  page_errors: [],
  failed_requests: [],
};

fs.mkdirSync(EVIDENCE, { recursive: true });

function check(name, condition, detail = "") {
  results.checks.push({ name, passed: Boolean(condition), detail });
  if (!condition) {
    console.error(`FAIL  ${name}${detail ? ` — ${detail}` : ""}`);
  } else {
    console.log(`ok    ${name}`);
  }
}

async function shot(page, name) {
  const file = path.join(EVIDENCE, `${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  results.screenshots.push(path.relative(process.cwd(), file));
}

async function app(page, hash) {
  await page.goto(`${BASE_URL}#${hash}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
}

async function run() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    hasTouch: true,
  });
  const page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error") {
      const location = message.location()?.url ?? "";
      results.console_errors.push(
        location && !location.startsWith("http")
          ? message.text()
          : `${message.text()} @ ${location}`
      );
    }
  });
  page.on("pageerror", (error) => results.page_errors.push(String(error)));
  page.on("requestfailed", (request) =>
    results.failed_requests.push(`${request.url()} ${request.failure()?.errorText ?? ""}`)
  );

  /* 1 — landing navigation (M4-R1 §2: Atlas CTA presents the gallery) ------ */
  await app(page, "/");
  await page.locator(".hero-copy h1").waitFor({ state: "visible", timeout: 8000 });
  check("1. landing renders hero headline", await page.getByText("Read the landscape.").first().isVisible());
  await page.getByRole("link", { name: "Explore the Atlas" }).click();
  await page.waitForTimeout(1200);
  check(
    "1. hero CTA stays on the atlas and reveals the study gallery",
    !page.url().includes("/workstation") &&
      (await page.evaluate(() => {
        const grid = document.querySelector(".study-grid");
        const box = grid?.getBoundingClientRect();
        return Boolean(box && box.top < window.innerHeight);
      })),
  );
  check(
    "1. workstation nav opens the study selector, not a forced study",
    await (async () => {
      await app(page, "/workstation");
      return (
        (await page.locator(".picker-card").count()) === 6 &&
        !page.url().includes("/workstation/")
      );
    })(),
  );
  await shot(page, "m4_r1_workstation_study_selector_1440");

  /* 2 — gallery: six processed investigations, honest PARTIAL --------------- */
  await app(page, "/");
  await page.locator(".study-card--lead").waitFor({ state: "visible", timeout: 8000 });
  const cardStates = await page.evaluate(() =>
    [...document.querySelectorAll(".study-card")].map((card) => ({
      id: card.getAttribute("data-study-id"),
      status: card.querySelector(".status-chip")?.getAttribute("data-status"),
      hasMedia: Boolean(card.querySelector(".study-card-media img")),
      link: card.querySelector("a.button")?.getAttribute("href") ?? null,
    }))
  );
  check(
    "2. gallery shows six processed investigations with real media and routes",
    cardStates.length === 6 &&
      cardStates.every((card) => card.status === "processed" || card.status === "partial") &&
      cardStates.every((card) => card.hasMedia && card.link?.includes("/workstation/")),
    JSON.stringify(cardStates.map((c) => [c.id, c.status]))
  );
  check(
    "2. gallery carries the recorded PARTIAL verdict for the 2025 event only",
    cardStates.filter((card) => card.status === "partial").map((card) => card.id).join(",") ===
      "himalaya_purepu_2025"
  );
  await shot(page, "m4_landing_1440_gallery");
  await page.locator('.study-card[data-study-id="chilika_wetland"]').getByRole("link").click();
  await page.waitForTimeout(1500);
  check("2. study card opens its own investigation", page.url().includes("workstation/chilika_wetland"));

  /* 3 — Chilika showcase: experiment switcher ------------------------------- */
  await app(page, "/workstation/chilika_wetland");
  const switcher = await page.evaluate(() =>
    [...document.querySelectorAll(".ws-experiment-switch .chip")].map((chip) => chip.textContent)
  );
  check(
    "3. Chilika offers both matched experiments",
    switcher.length === 2 && switcher[0].includes("dry season") && switcher[1].includes("post-monsoon"),
    JSON.stringify(switcher)
  );
  const acquisitionsBefore = await page.evaluate(() =>
    [...document.querySelectorAll(".ws-facts dd")][0]?.textContent
  );
  await page.locator(".ws-experiment-switch .chip").nth(1).click();
  await page.waitForTimeout(1200);
  const acquisitionsAfter = await page.evaluate(() =>
    [...document.querySelectorAll(".ws-facts dd")][0]?.textContent
  );
  check(
    "3. switching experiments changes the recorded acquisitions",
    acquisitionsBefore?.includes("2020-02-17") &&
      acquisitionsAfter?.includes("2020-11-08"),
    `${acquisitionsBefore} → ${acquisitionsAfter}`
  );
  await shot(page, "m4_chilika_workstation_1440");

  /* 4 — interactive chart hover --------------------------------------------- */
  await page.getByRole("button", { name: /Analysis dock/ }).click();
  await page.waitForTimeout(900);
  const chartSections = await page.evaluate(() =>
    [...document.querySelectorAll(".dock-section h3")].map((h) => h.textContent)
  );
  check(
    "4. dock exposes interactive chart sections",
    chartSections.includes("Threshold sensitivity") && chartSections.includes("Period index means"),
    JSON.stringify(chartSections)
  );
  const plotBox = await page.locator(".dock-chart-section .ichart-plot").first().boundingBox();
  await page.mouse.move(plotBox.x + plotBox.width * 0.7, plotBox.y + plotBox.height * 0.5, { steps: 4 });
  await page.waitForTimeout(400);
  const hoverState = await page.evaluate(() => {
    const tooltip = document.querySelector(".ichart-tooltip");
    return {
      shown: Boolean(tooltip),
      guide: Boolean(document.querySelector(".ichart-guide")),
      activeDots: document.querySelectorAll(".ichart-dot.is-active").length,
      text: tooltip?.textContent?.replace(/\s+/g, " ").slice(0, 260) ?? null,
    };
  });
  check(
    "4. hover snaps to the nearest recorded point with an explanatory tooltip",
    hoverState.shown && hoverState.guide && hoverState.activeDots > 0 &&
      hoverState.text?.includes("% of shared-valid AOI"),
    hoverState.text ?? "no tooltip"
  );
  const hoverValue = hoverState.text?.match(/([\d.]+) index units/)?.[1];
  check(
    "4. tooltip values come from the recorded threshold sweep",
    hoverValue !== null && ["0.05", "0.10", "0.15", "0.20"].includes(hoverValue),
    `threshold ${hoverValue}`
  );
  await shot(page, "m4_interactive_chart_hover");

  /* 5 — keyboard navigation and pinning -------------------------------------- */
  await page.mouse.move(60, 300);
  await page.waitForTimeout(300);
  const keyboardState = await page.evaluate(async () => {
    const plot = document.querySelector(".dock-chart-section .ichart-plot");
    plot.focus();
    const fire = (key) =>
      plot.dispatchEvent(
        new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true })
      );
    fire("ArrowRight");
    fire("ArrowRight");
    await new Promise((resolve) => setTimeout(resolve, 150));
    const movedText = document.querySelector(".ichart-tooltip")?.textContent ?? "";
    fire("Enter");
    await new Promise((resolve) => setTimeout(resolve, 150));
    const pinned = document
      .querySelector(".ichart-tooltip")
      ?.textContent?.includes("Pinned");
    return { movedThreshold: movedText.match(/([\d.]+) index units/)?.[1] ?? null, pinned };
  });
  check(
    "5. arrow keys walk the recorded points; Enter pins the tooltip",
    keyboardState.movedThreshold !== null && keyboardState.pinned,
    JSON.stringify(keyboardState)
  );
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const dismissed = await page.evaluate(() => !document.querySelector(".ichart-tooltip"));
  check("5. Escape dismisses the pinned tooltip", dismissed);
  await shot(page, "m4_interactive_chart_keyboard");

  /* 6 — can/cannot-conclude guardrails ---------------------------------------- */
  const guardrail = await page.evaluate(() =>
    document.querySelector(".dock-chart-section .ichart-caption")?.textContent ?? ""
  );
  check(
    "6. charts state what can and cannot be concluded",
    guardrail.includes("Can be read") && guardrail.includes("Cannot be read"),
    guardrail.slice(0, 120)
  );

  /* 7 — Himalayan event views are separate investigations ---------------------- */
  await app(page, "/workstation/himalaya_purepu_2025");
  const d1 = await page.evaluate(() => ({
    eyebrow: document.querySelector(".ws-title .eyebrow")?.textContent ?? "",
    h1: document.querySelector("main h1")?.textContent ?? "",
  }));
  check(
    "7. D1 renders as a PARTIAL event investigation",
    d1.eyebrow.includes("PARTIAL") && d1.eyebrow.includes("event 2025-07-08"),
    d1.eyebrow
  );
  await page.getByRole("tab", { name: "Acquisition" }).click();
  await page.waitForTimeout(500);
  const d1Context = await page.evaluate(() => document.querySelector(".insp-body")?.textContent ?? "");
  check(
    "7. D1 records the same-day observation and why it is not a difference baseline",
    d1Context.includes("S2C_45RUM_20250708_0_L2A") &&
      d1Context.includes("not used as a difference baseline"),
    ""
  );
  check(
    "7. D1 states lake area is not discharged volume and InSAR stays external",
    d1Context.includes("not discharged-water volume") &&
      d1Context.includes("InSAR"),
    ""
  );
  await shot(page, "m4_d1_event_view");
  await app(page, "/workstation/himalaya_langtang_2026");
  const d2 = await page.evaluate(() => ({
    eyebrow: document.querySelector(".ws-title .eyebrow")?.textContent ?? "",
    context: document.querySelector("main")?.textContent ?? "",
  }));
  check(
    "7. D2 is a distinct rock-ice collapse investigation, not a GLOF page",
    d2.eyebrow.includes("event 2026-08-26") &&
      !d2.eyebrow.includes("PARTIAL") &&
      d2.context.includes("rock-ice collapse"),
    d2.eyebrow
  );
  await shot(page, "m4_d2_event_view");

  /* 8 — Kathmandu NDBI guardrail ------------------------------------------------ */
  await app(page, "/workstation/kathmandu_urban");
  const kathmanduLayers = await page.evaluate(() =>
    [...document.querySelectorAll(".ws-layers button")].map((b) => b.textContent)
  );
  // The guardrail lives on the NDBI layer legend — select it as a user would.
  await page.getByRole("button", { name: "NDBI", exact: true }).click();
  await page.waitForTimeout(500);
  const kathmanduBody = await page.evaluate(() => document.querySelector("main")?.textContent ?? "");
  check(
    "8. Kathmandu exposes NDBI with the not-a-building-detector guardrail",
    kathmanduLayers.includes("NDBI") &&
      kathmanduBody.includes("NOT a building detector"),
    ""
  );
  await shot(page, "m4_kathmandu_workstation");

  /* 9 — showcase independence from the backend ---------------------------------- */
  const bundleResponse = await page.request.get(`${BASE_URL}studies/chilika_wetland/bundle.json`);
  check("9. bundle is served as a static artefact", bundleResponse.ok());
  const bundleJson = await bundleResponse.json().catch(() => null);
  check(
    "9. bundle carries summaries, charts, checksums and provenance",
    bundleJson?.experiments?.length === 2 &&
      bundleJson?.charts?.threshold_series?.length > 0 &&
      Object.keys(bundleJson?.assets ?? {}).length > 10 &&
      Boolean(bundleJson?.attribution),
    ""
  );
  const chilikaMode = await page.evaluate(() => document.body.textContent.includes("Portable showcase"));
  check(
    "9. workstation labels the evidence mode honestly",
    chilikaMode,
    ""
  );

  /* 10 — coringa live enhancement + M3 interaction contracts --------------------- */
  await app(page, "/workstation/coringa_coastal");
  const mode = await page.evaluate(() => document.body.textContent.includes("Showcase + live probe"));
  check("10. coringa activates the live probe when the backend is present", mode);
  await page.getByRole("button", { name: "Side by side" }).click();
  await page.waitForTimeout(800);
  const zoomIn = page.locator(".map-earlier .maplibregl-ctrl-zoom-in");
  await zoomIn.click();
  await zoomIn.click();
  await page.waitForTimeout(700);
  const zooms = await page.evaluate(() => ({
    earlier: window.__hsMaps.earlier.getZoom(),
    later: window.__hsMaps.later.getZoom(),
  }));
  check("10. side-by-side maps stay synchronised", Math.abs(zooms.earlier - zooms.later) < 1e-6, JSON.stringify(zooms));

  await page.getByRole("button", { name: "Swipe" }).click();
  await page.waitForTimeout(600);
  const stage = await page.locator(".map-stage").boundingBox();
  const cy = stage.y + stage.height / 2;
  await page.mouse.move(stage.x + stage.width * 0.2, cy, { steps: 4 });
  await page.waitForTimeout(300);
  const splitA = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  await page.mouse.move(stage.x + stage.width * 0.75, cy, { steps: 4 });
  await page.waitForTimeout(300);
  const splitB = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  check("10. divider follows mouse hover with no click", splitA < 30 && splitB > 65, `${splitA.toFixed(1)} → ${splitB.toFixed(1)}`);

  await page.touchscreen.tap(stage.x + stage.width * 0.3, cy);
  await page.waitForTimeout(300);
  const touchSplit = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  check("10. touch tap places the divider", Math.abs(touchSplit - 30) < 6, `${touchSplit.toFixed(1)}`);

  await page.locator(".map-swipe-divider").focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Home");
  await page.keyboard.press("End");
  await page.waitForTimeout(200);
  const kbEnd = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  check("10. keyboard divider controls work", Math.abs(kbEnd - 100) < 1.5, `${kbEnd}`);
  await page.getByRole("button", { name: "Reset 50%" }).click();
  await page.waitForTimeout(300);

  /* 11 — pixel probe (live) ------------------------------------------------------ */
  await page.waitForTimeout(600);
  const stage2 = await page.locator(".map-stage").boundingBox();
  await page.mouse.click(stage2.x + stage2.width * 0.45, stage2.y + stage2.height * 0.4);
  await page.waitForTimeout(1400);
  const probeText = await page.locator(".pixel-probe").textContent().catch(() => null);
  check(
    "11. pixel probe returns measured reflectance + indices",
    probeText !== null && probeText.includes("B08 NIR") && probeText.includes("NDVI"),
    probeText?.slice(0, 120)
  );
  await shot(page, "m4_pixel_probe_live");

  /* 12 — experiments workspace ----------------------------------------------------- */
  await app(page, "/experiments");
  const chartCount = await page.locator(".ichart").count();
  check("12. experiments page shows recorded charts", chartCount >= 3, `interactive charts ${chartCount}`);
  check(
    "12. uncertainty is not described as a population CI",
    await page.getByText("not a population", { exact: false }).first().isVisible()
  );

  /* 12b — M4-R1 corrections + What Changed? (§15) ------------------------------------ */
  // Quality accounting: outside-AOI vs masked-inside-AOI stay distinct (§4).
  await app(page, "/workstation/western_ghats_forest");
  await page.getByRole("button", { name: "Quality", exact: true }).click();
  await page.waitForTimeout(600);
  const coverage = await page.evaluate(() =>
    [...document.querySelectorAll(".quality-coverage .insp-facts div")].map((d) => [
      d.querySelector("dt")?.textContent,
      d.querySelector("dd")?.textContent,
    ])
  );
  const findRow = (label) => coverage.find(([dt]) => dt?.startsWith(label))?.[1] ?? null;
  check(
    "12b. quality accounting separates outside-AOI from masked-inside-AOI (§4)",
    findRow("Outside AOI") === "2,081 (not observations)" &&
      findRow("Masked inside AOI")?.startsWith("0"),
    JSON.stringify(coverage),
  );
  await shot(page, "m4_r1_quality_accounting_1440");

  // Later-map lifecycle: Historical → Change → Quality → Historical keeps the
  // later map attached and painted (§5/§6).
  await page.getByRole("button", { name: "Change", exact: true }).click();
  await page.getByRole("button", { name: "Quality", exact: true }).click();
  await page.getByRole("button", { name: "Historical", exact: true }).click();
  await page.waitForTimeout(1200);
  const lifecycle = await page.evaluate(() => {
    const maps = window.__hsMaps ?? {};
    const laterHost = document.querySelector(".map-later .map-host");
    return {
      canvas: Boolean(laterHost?.querySelector("canvas")),
      detached: maps.later ? !maps.later.getContainer().isConnected : null,
    };
  });
  check(
    "12b. later map survives the analysis-tab sequence attached (§5/§6)",
    lifecycle.canvas && lifecycle.detached === false,
    JSON.stringify(lifecycle),
  );

  // Opacity endpoints drive the raster blend on the primary map (§7).
  await page.getByRole("button", { name: "Opacity" }).click();
  await page.waitForTimeout(600);
  await page.locator('.opacity-control input[type="range"]').fill("100");
  await page.waitForTimeout(500);
  const opacityHigh = await page.evaluate(() =>
    window.__hsMaps.earlier.getPaintProperty("layer-later", "raster-opacity")
  );
  await page.locator('.opacity-control input[type="range"]').fill("0");
  await page.waitForTimeout(500);
  const opacityLow = await page.evaluate(() =>
    window.__hsMaps.earlier.getPaintProperty("layer-later", "raster-opacity")
  );
  check(
    "12b. opacity endpoints reach the raster paint property (§7)",
    opacityHigh === 1 && opacityLow === 0,
    `at 100%: ${opacityHigh}, at 0%: ${opacityLow}`,
  );
  await shot(page, "m4_r1_opacity_mode_1440");

  // What Changed? view: recorded regions + guided panel + layer guide (§15).
  await app(page, "/workstation/kathmandu_urban");
  await page.getByRole("button", { name: "What changed?", exact: true }).click();
  await page.waitForTimeout(1000);
  await page.getByRole("tab", { name: "Explore the Evidence" }).click();
  await page.waitForTimeout(500);
  const whatChanged = await page.evaluate(async () => {
    const maps = window.__hsMaps ?? {};
    const src = maps.earlier?.getSource("findings-overlay");
    const data = src ? await src.getData() : null;
    return {
      entries: document.querySelectorAll(".finding-entry").length,
      overlayFeatures: data?.features.length ?? 0,
      overview: document.querySelector(".findings-panel .insp-meaning")?.textContent ?? "",
      guardrail: document.querySelector(".finding-detail")?.textContent ?? "",
    };
  });
  check(
    "12b. What Changed? shows recorded regions on map and panel (§15.2/§15.3)",
    whatChanged.entries > 0 && whatChanged.overlayFeatures === whatChanged.entries,
    JSON.stringify({ entries: whatChanged.entries, features: whatChanged.overlayFeatures }),
  );
  check(
    "12b. What Changed? overview frames regions as candidates (§15.6)",
    whatChanged.overview.includes("candidate") &&
      whatChanged.overview.includes("not confirmed environmental events"),
  );
  // Selecting a finding zooms the map and reveals the measurement + limits.
  const zoomBeforeSelect = await page.evaluate(() => window.__hsMaps.earlier.getZoom());
  await page.locator(".finding-entry").first().click();
  await page.waitForTimeout(900);
  const findingSelection = await page.evaluate(() => ({
    zoom: window.__hsMaps.earlier.getZoom(),
    detail: document.querySelector(".finding-detail")?.textContent ?? "",
  }));
  check(
    "12b. selecting a finding zooms and shows measurement + limitations (§15.3)",
    findingSelection.zoom > zoomBeforeSelect &&
      findingSelection.detail.includes("What was measured?") &&
      findingSelection.detail.includes("What should we not conclude?"),
  );
  await shot(page, "m4_r1_what_changed_1440");

  // "What am I looking at?" explains the current layer (§15.5).
  await page.getByRole("button", { name: "What am I looking at?" }).click();
  await page.waitForTimeout(500);
  const guide = await page.evaluate(() => {
    const panel = document.querySelector(".layer-guide");
    return panel
      ? {
          resolution: panel.textContent.includes("m per pixel"),
          bands: panel.textContent.includes("ΔNDBI"),
          cannot: panel.textContent.includes("cannot establish"),
        }
      : null;
  });
  check(
    "12b. layer guide explains type, values and limits (§15.5)",
    guide && guide.resolution && guide.bands && guide.cannot,
    JSON.stringify(guide),
  );

  // M4-R2 G7: Research-mode evidence record shares the Explore selection and
  // shows the same sealed record (same evidence_id, no separate computation).
  await page.getByRole("tab", { name: "Explore the Evidence" }).click();
  await page.waitForTimeout(400);
  // The first entry is still selected from the earlier check — select the
  // second one (the click toggles selection).
  await page.locator(".finding-entry").nth(1).click();
  await page.waitForTimeout(600);
  const exploreCard = await page.evaluate(() => ({
    evidenceId: document.querySelector(".finding-detail .mono-label")?.textContent ?? "",
    hasSensitivity: (document.querySelector(".finding-detail")?.textContent ?? "").includes("Threshold behaviour"),
  }));
  await page.getByRole("tab", { name: "Research Mode" }).click();
  await page.waitForTimeout(400);
  const evidenceRecord = await page.evaluate(() => {
    const panel = document.querySelector(".evidence-record");
    const text = panel?.textContent ?? "";
    return {
      present: !!panel,
      heading: text.includes("Research Mode"),
      identification: text.includes("Identification") && text.includes("threshold-connected-region"),
      provenance: text.includes("Method provenance") && text.includes("Git commit"),
      measurements: text.includes("Spatial measurements") && text.includes("Valid denominator"),
      checksum: text.includes("checksum"),
      relationships: text.includes("Relationships"),
      schema: text.includes("habitatshift-evidence-record/1"),
    };
  });
  check(
    "12b. M4-R2 Research Mode tab renders the full research record",
    evidenceRecord.present &&
      evidenceRecord.heading &&
      evidenceRecord.identification &&
      evidenceRecord.provenance &&
      evidenceRecord.measurements &&
      evidenceRecord.checksum &&
      evidenceRecord.relationships &&
      evidenceRecord.schema,
    JSON.stringify(evidenceRecord),
  );
  check(
    "12b. M4-R2 Explore card shows sensitivity + record id (same record)",
    exploreCard.hasSensitivity && exploreCard.evidenceId.includes("ev-kathmandu_m4-"),
    JSON.stringify({ hasSensitivity: exploreCard.hasSensitivity, id: exploreCard.evidenceId.slice(0, 80) }),
  );
  await shot(page, "m4_r2_evidence_record_1440");

  // Fit Entire Study Area restores the full extent (§9). Checked on a large
  // study: Kathmandu's AOI is so small that its overview zoom is already ~15.
  await app(page, "/workstation/western_ghats_forest");
  const zoomInBtn = page.locator(".map-earlier .maplibregl-ctrl-zoom-in");
  await zoomInBtn.click();
  await zoomInBtn.click();
  await page.waitForTimeout(600);
  const zoomBeforeFit = await page.evaluate(() => window.__hsMaps.earlier.getZoom());
  await page.getByRole("button", { name: "Fit Entire Study Area" }).click();
  await page.waitForTimeout(1200);
  const fitZoom = await page.evaluate(() => window.__hsMaps.earlier.getZoom());
  check(
    "12b. Fit Entire Study Area restores the overview zoom (§9)",
    fitZoom < zoomBeforeFit - 1,
    `zoom ${zoomBeforeFit} → ${fitZoom}`,
  );

  // Kathmandu carries the native-resolution tag beside the imagery (§8).
  await app(page, "/workstation/kathmandu_urban");
  const resolutionTag = await page.evaluate(() =>
    document.querySelector(".map-resolution-tag")?.textContent ?? null
  );
  check(
    "12b. native-resolution tag renders beside the imagery (§8)",
    resolutionTag === "10 m/px native",
    String(resolutionTag),
  );

  /* 13 — responsive layouts ---------------------------------------------------------- */
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await app(page, "/");
    const landingOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    await shot(page, `m4_landing_${viewport.name}`);
    await app(page, "/workstation/chilika_wetland");
    await page.waitForTimeout(1200);
    const wsOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    await shot(page, `m4_workstation_${viewport.name}`);
    check(
      `13. no horizontal overflow at ${viewport.name}`,
      landingOverflow <= 0 && wsOverflow <= 0,
      `landing ${landingOverflow}px, workstation ${wsOverflow}px`
    );
  }

  /* 14 — provenance / methods ---------------------------------------------------------- */
  await page.setViewportSize({ width: 1440, height: 900 });
  await app(page, "/methods");
  check(
    "14. methods page documents the radiometry correction",
    await page.getByText("Radiometry", { exact: false }).first().isVisible()
  );
  check(
    "14. methods page documents the portable showcase",
    await page.getByText("Portable showcase", { exact: false }).first().isVisible()
  );
  const registryResponse = await page.request.get(`${BASE_URL}studies/registry.json`);
  check("14. static registry serves JSON", registryResponse.ok());
  const manifestResponse = await page.request.get(`${BASE_URL}api/m1/study/coringa_coastal/manifest`);
  check("14. manifest endpoint serves JSON", manifestResponse.ok());
  await shot(page, "m4_methods_1440");

  /* console / error hygiene ---------------------------------------------------------------- */
  check(
    "15. no P0/P1 browser errors",
    results.console_errors.length === 0 &&
      results.page_errors.length === 0 &&
      results.failed_requests.length === 0,
    `console ${results.console_errors.length}, page ${results.page_errors.length}, failed ${results.failed_requests.length}: ` +
      [...results.console_errors, ...results.page_errors, ...results.failed_requests].slice(0, 6).join(" | ")
  );

  await browser.close();

  results.finished_utc = new Date().toISOString();
  results.passed = results.checks.filter((c) => c.passed).length;
  results.failed = results.checks.filter((c) => !c.passed).length;
  fs.writeFileSync(
    path.join(EVIDENCE, "m4_browser_results.json"),
    JSON.stringify(results, null, 2)
  );
  console.log(`\n${results.passed} passed, ${results.failed} failed`);
  process.exit(results.failed ? 1 : 0);
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
