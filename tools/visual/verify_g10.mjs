/* M4-R1-G10 dedicated probe: chart layout, tooltip clipping and hover
 * simplification.
 *
 * Drives the interactive charts at every screen edge, expands the details
 * section, exercises narrow/mobile layouts and captures the evidence
 * screenshots listed in the G10 brief.  Run against the backend server
 * (port 8098, which serves frontend/dist):
 *
 *   node tools/visual/verify_g10.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const BASE_URL = process.env.HABITATSHIFT_URL || "http://127.0.0.1:8098/";
const EVIDENCE = path.resolve(import.meta.dirname, "../../docs/evidence/m4-r1-g10");
const results = {
  base_url: BASE_URL,
  suite: "habitatshift-m4-r1-g10-chart-qa/1",
  started_utc: new Date().toISOString(),
  checks: [],
  screenshots: [],
  console_errors: [],
  page_errors: [],
};

fs.mkdirSync(EVIDENCE, { recursive: true });

function check(name, condition, detail = "") {
  results.checks.push({ name, passed: Boolean(condition), detail });
  console.log(`${condition ? "ok   " : "FAIL "} ${name}${detail ? ` — ${detail}` : ""}`);
}

async function shot(page, name) {
  const file = path.join(EVIDENCE, `${name}.png`);
  await page.screenshot({ path: file });
  results.screenshots.push(path.basename(file));
}

const app = async (page, hash, wait = 2200) => {
  await page.goto(`${BASE_URL}#${hash}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(wait);
};

/** Tooltip containment within the plot AND the viewport, at its rendered
 *  position (the overlay is absolutely positioned, so this is geometry only
 *  — it cannot shift layout). */
async function tooltipGeometry(page) {
  return page.evaluate(() => {
    const tip = document.querySelector(".ichart-tooltip");
    const plot = tip?.closest(".ichart-plot");
    if (!tip || !plot) return null;
    const t = tip.getBoundingClientRect();
    const p = plot.getBoundingClientRect();
    return {
      withinPlot:
        t.left >= p.left - 1 &&
        t.right <= p.right + 1 &&
        t.top >= p.top - 1 &&
        t.bottom <= p.bottom + 1,
      withinPlotHorizontal: t.left >= p.left - 1 && t.right <= p.right + 1,
      withinViewport: t.top >= 0 && t.left >= 0 && t.right <= innerWidth && t.bottom <= innerHeight,
      height: Math.round(t.height),
      plotHeight: Math.round(p.height),
      rows: tip.querySelectorAll(".ichart-tooltip-row").length,
      expanded: tip.classList.contains("is-expanded"),
      text: tip.textContent?.slice(0, 140) ?? "",
    };
  });
}

/** Hover the recorded point whose x is closest to a fraction of the plot.
 *  Scrolls the chart into the viewport first — Playwright mouse events only
 *  land inside the visible viewport. */
async function hoverAtFraction(page, fraction, selector = ".ichart-plot") {
  const handle = await page.locator(selector).first().elementHandle();
  await handle.scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  const box = await handle.boundingBox();
  await page.mouse.move(box.x + box.width * fraction, box.y + box.height * 0.5, { steps: 4 });
  await page.waitForTimeout(350);
  return box;
}

/** Viewport-relative box of the Nth chart plot, scrolled into view. */
async function plotBox(page, index) {
  const handle = await page.locator(".ichart-plot").nth(index).elementHandle();
  await handle.scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  return handle.boundingBox();
}

async function run() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, hasTouch: true });
  const page = await context.newPage();
  page.on("pageerror", (e) => results.page_errors.push(String(e).slice(0, 200)));
  page.on("console", (m) => {
    if (m.type() === "error") results.console_errors.push(m.text().slice(0, 120));
  });

  /* ---------------- Coringa experiments page: all four chart types ------ */
  await app(page, "/experiments");
  await page.evaluate(() => document.querySelector(".exp-block")?.scrollIntoView());
  await page.waitForTimeout(400);

  // 1 — threshold legend labels are all distinct (M2 estimators disambiguated)
  const legendLabels = await page.evaluate(() =>
    [...document.querySelectorAll(".ichart-legend-item")].map((el) => el.textContent?.trim())
  );
  const thresholdLegends = legendLabels.slice(0, 6);
  check(
    "1. threshold legend labels are distinct per estimator configuration",
    new Set(thresholdLegends).size === thresholdLegends.length &&
      thresholdLegends.some((l) => l?.includes("mean composite")) &&
      thresholdLegends.some((l) => l?.includes("median composite")),
    thresholdLegends.join(" | ")
  );
  await shot(page, "g10_threshold_chart_coringa");

  // 2 — hover simplification: only ONE series row in the tooltip
  const tb = await plotBox(page, 0);
  await page.mouse.move(tb.x + tb.width * 0.5, tb.y + tb.height * 0.45, { steps: 4 });
  await page.waitForTimeout(350);
  const normal = await tooltipGeometry(page);
  check("2. tooltip shows a single series by default", normal?.rows === 1, `rows=${normal?.rows}`);
  check("3. tooltip carries exact value + units + denominator", /% of shared-valid AOI/.test(normal?.text ?? ""), normal?.text.slice(0, 80));
  check("4. tooltip inside plot and viewport (centre hover)", normal?.withinPlot && normal?.withinViewport);
  await shot(page, "g10_tooltip_normal");

  // 3 — left edge
  await hoverAtFraction(page, 0.02);
  const atLeft = await tooltipGeometry(page);
  check("5. tooltip near LEFT edge stays inside plot+viewport", atLeft?.withinPlot && atLeft?.withinViewport);
  await shot(page, "g10_tooltip_left_edge");

  // 4 — right edge (must flip to the left of the guide)
  await hoverAtFraction(page, 0.985);
  const atRight = await tooltipGeometry(page);
  check("6. tooltip near RIGHT edge stays inside plot+viewport", atRight?.withinPlot && atRight?.withinViewport);
  await shot(page, "g10_tooltip_right_edge");

  // 5 — top edge / bottom edge on the bootstrap (uncertainty) chart
  const charts = await page.locator(".ichart-plot").count();
  check("7. all four chart types render", charts >= 4, `count=${charts}`);
  const uncertainty = await plotBox(page, 3);
  await page.mouse.move(uncertainty.x + uncertainty.width * 0.5, uncertainty.y + 8, { steps: 4 });
  await page.waitForTimeout(350);
  const atTop = await tooltipGeometry(page);
  check("8. tooltip near TOP edge stays inside plot+viewport", atTop?.withinPlot && atTop?.withinViewport);
  await shot(page, "g10_tooltip_top_edge");
  await page.mouse.move(uncertainty.x + uncertainty.width * 0.5, uncertainty.y + uncertainty.height - 6, { steps: 4 });
  await page.waitForTimeout(350);
  const atBottom = await tooltipGeometry(page);
  check("9. tooltip near BOTTOM edge stays inside plot+viewport", atBottom?.withinPlot && atBottom?.withinViewport);
  await shot(page, "g10_tooltip_bottom_edge");

  // 6 — expandable details
  await page.mouse.move(uncertainty.x + uncertainty.width * 0.5, uncertainty.y + uncertainty.height * 0.4, { steps: 3 });
  await page.waitForTimeout(300);
  await page.click(".ichart-details-toggle");
  await page.waitForTimeout(250);
  const expandedState = await page.evaluate(() => {
    const tip = document.querySelector(".ichart-tooltip");
    return {
      expanded: tip?.classList.contains("is-expanded") ?? false,
      hasDetails: Boolean(document.querySelector(".ichart-details")),
      text: tip?.textContent ?? "",
    };
  });
  check(
    "10. expanded details show related series, context and limitations",
    expandedState.expanded &&
      expandedState.hasDetails &&
      /Other series at this x value/.test(expandedState.text) &&
      /Measurement context/.test(expandedState.text) &&
      /Limitations/.test(expandedState.text),
    `expanded=${expandedState.expanded} hasDetails=${expandedState.hasDetails} text=${expandedState.text.slice(0, 110)}`
  );
  const expanded = await tooltipGeometry(page);
  check(
    "11. expanded tooltip stays visible (viewport-clamped; vertically it may exceed a plot shorter than itself)",
    expanded?.withinViewport &&
      expanded?.withinPlotHorizontal !== false,
    JSON.stringify(expanded)
  );
  await shot(page, "g10_tooltip_expanded");
  await page.keyboard.press("Escape");

  // 7 — estimator chart: abbreviated, unique tick labels
  const tickTexts = await page.evaluate(() => {
    const plots = [...document.querySelectorAll(".ichart-plot")];
    const svg = plots[2]?.querySelector("svg");
    if (!svg) return [];
    // x-axis ticks carry their own class; y ticks share plain ichart-tick.
    return [...svg.querySelectorAll("text.ichart-tick-x")].map((t) => t.textContent);
  });
  check(
    "12. estimator ticks are short, unique and family-free",
    tickTexts.length > 5 &&
      tickTexts.every((t) => (t ?? "").length <= 12) &&
      !tickTexts.includes("leave_one_out") &&
      new Set(tickTexts).size === tickTexts.length,
    tickTexts.join(" | ")
  );

  // 8 — period-means chart: no repeated date on the x axis
  const meansTicks = await page.evaluate(() => {
    const plots = [...document.querySelectorAll(".ichart-plot")];
    const svg = plots[1]?.querySelector("svg");
    if (!svg) return [];
    return [...svg.querySelectorAll("text.ichart-tick-x")].map((t) => t.textContent);
  });
  check(
    "13. period-means axis shows each anchor date exactly once",
    meansTicks.length >= 2 && new Set(meansTicks).size === meansTicks.length,
    meansTicks.join(" | ")
  );
  const meansPlot = await plotBox(page, 1);
  await page.mouse.move(meansPlot.x + meansPlot.width * 0.5, meansPlot.y + meansPlot.height * 0.5, { steps: 3 });
  await page.waitForTimeout(300);
  await shot(page, "g10_period_means_chart");

  // 9 — estimator chart screenshot (short labels + full names in tooltip)
  const estPlot = await plotBox(page, 2);
  await page.mouse.move(estPlot.x + estPlot.width * 0.55, estPlot.y + estPlot.height * 0.5, { steps: 3 });
  await page.waitForTimeout(300);
  const estTip = await tooltipGeometry(page);
  check(
    "14. estimator tooltip carries the full technical identifier",
    /Estimator: /.test(estTip?.text ?? ""),
    estTip?.text.slice(0, 90)
  );
  await shot(page, "g10_estimator_chart");

  // 10 — aspect ratio sanity: plots are no longer excessively wide
  const geom = await page.evaluate(() => {
    const el = document.querySelector(".ichart-plot svg");
    const r = el?.getBoundingClientRect();
    return r ? { w: Math.round(r.width), h: Math.round(r.height), ratio: +(r.width / r.height).toFixed(2) } : null;
  });
  check(
    "15. chart proportions balanced (height 320, width capped ≤ 860)",
    geom?.h === 320 && geom?.w <= 861 && geom?.ratio <= 2.7,
    JSON.stringify(geom)
  );

  // 11 — pin + dismiss still work
  await hoverAtFraction(page, 0.5);
  await page.locator(".ichart-plot").first().click();
  await page.waitForTimeout(250);
  const pinned = await page.evaluate(() => document.querySelector(".ichart-pin-hint")?.textContent ?? "");
  check("16. click-to-pin works", /Pinned/.test(pinned));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(250);
  check("17. Escape dismisses the pinned tooltip", !(await page.locator(".ichart-tooltip").count()));

  /* ---------------- narrow desktop + mobile ------------------------------ */
  const narrow = await browser.newContext({ viewport: { width: 1024, height: 800 } });
  const np = await narrow.newPage();
  await np.goto(`${BASE_URL}#/experiments`, { waitUntil: "domcontentloaded" });
  await np.waitForTimeout(2200);
  await shot(np, "g10_narrow_1024");
  await hoverAtFraction(np, 0.97, ".ichart-plot");
  const narrowGeom = await tooltipGeometry(np);
  check("18. narrow desktop: tooltip stays inside plot+viewport", narrowGeom?.withinPlot && narrowGeom?.withinViewport);
  await narrow.close();

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true });
  const mp = await mobile.newPage();
  await mp.goto(`${BASE_URL}#/experiments`, { waitUntil: "domcontentloaded" });
  await mp.waitForTimeout(2200);
  const mobileOverflow = await mp.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth
  );
  check("19. mobile 390: no horizontal overflow", !mobileOverflow);
  await shot(mp, "g10_mobile_390");
  await hoverAtFraction(mp, 0.97, ".ichart-plot");
  const mobileGeom = await tooltipGeometry(mp);
  check("20. mobile: tooltip stays inside plot+viewport", mobileGeom?.withinPlot && mobileGeom?.withinViewport);
  await shot(mp, "g10_mobile_tooltip_right_edge");
  await mobile.close();

  check("21. no page errors during probe", results.page_errors.length === 0, results.page_errors.join("; "));
  check("22. no console errors during probe", results.console_errors.length === 0, results.console_errors.join("; "));

  await browser.close();
  fs.writeFileSync(path.join(EVIDENCE, "g10_probe_results.json"), JSON.stringify(results, null, 2));
  const failed = results.checks.filter((c) => !c.passed).length;
  console.log(`\n${results.checks.length - failed} passed, ${failed} failed`);
  if (failed) process.exit(1);
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
