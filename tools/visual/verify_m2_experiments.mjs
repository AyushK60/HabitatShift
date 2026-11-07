/* M2 research-workbench real-browser verification with Playwright/Chromium.
 *
 * Drives the actual proof viewer served by uvicorn and exercises the
 * Experiments section end to end: experiment loading, index switching,
 * threshold switching, statistic synchronisation, chart rendering, method
 * comparison, uncertainty display, export links and error/missing states.
 * Evidence (screenshots + machine-readable results) goes to docs/evidence/m2/.
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const BASE_URL = process.env.HABITATSHIFT_URL || "http://127.0.0.1:8097/";
// The project root is two levels above tools/visual, regardless of cwd.
const EVIDENCE = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "docs",
  "evidence",
  "m2",
);
const results = {
  base_url: BASE_URL,
  started_utc: new Date().toISOString(),
  console_errors: [],
  page_errors: [],
  failed_requests: [],
  screenshots: [],
  checks: [],
};

fs.mkdirSync(EVIDENCE, { recursive: true });

function check(name, condition, detail = "") {
  results.checks.push({ name, passed: Boolean(condition), detail: String(detail) });
  if (!condition) throw new Error(`${name}${detail ? `: ${detail}` : ""}`);
}

async function shot(page, name) {
  const file = path.join(EVIDENCE, name);
  await page.screenshot({ path: file, fullPage: false });
  results.screenshots.push(name);
  return file;
}

async function shotElement(locator, name) {
  const file = path.join(EVIDENCE, name);
  await locator.screenshot({ path: file });
  results.screenshots.push(name);
  return file;
}

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on("console", (message) => {
    if (message.type() === "error") results.console_errors.push(message.text());
  });
  page.on("pageerror", (error) => results.page_errors.push(String(error)));
  page.on("requestfailed", (request) =>
    results.failed_requests.push(`${request.url()} :: ${request.failure()?.errorText}`),
  );

  await page.goto(BASE_URL, { waitUntil: "networkidle" });

  // --- section presence and load -----------------------------------------
  const section = page.locator("#experiments");
  // The page enables CSS smooth scrolling; use an instant jump so the
  // viewport is already at the section when the screenshot fires.
  await section.evaluate((el) =>
    window.scrollTo({ top: el.offsetTop, behavior: "instant" }),
  );
  await page.waitForTimeout(300);
  await page.waitForFunction(
    () => {
      const el = document.getElementById("experiments");
      return el && !el.hidden && document.getElementById("exp-facts").rows.length > 0;
    },
    undefined,
    { timeout: 15000 },
  );
  check("experiments section visible", !(await section.isHidden()));
  const lede = (await page.locator("#exp-lede").textContent()) || "";
  check("lede names recorded run", /Recorded run \d{8}T\d{6}Z_/.test(lede), lede);
  check(
    "lede reports no supervised labels",
    lede.includes("no supervised labels"),
    lede,
  );

  const factCount = await page.locator("#exp-facts tr").count();
  check("overview rows present", factCount >= 7, `rows=${factCount}`);
  const factsText = await page.locator("#exp-facts").innerText();
  check("overview shows fingerprint", factsText.includes("Fingerprint"), "");
  check(
    "overview shows common-valid coverage",
    /Common-valid coverage\s+100\.00%/.test(factsText.replace(/\n/g, " ")),
    factsText,
  );

  const verdictCount = await page.locator("#exp-verdicts .verdict-line").count();
  check("five hypothesis verdicts", verdictCount === 5, `count=${verdictCount}`);
  const supportedCount = await page.locator(".verdict-supported").count();
  check("verdict chips rendered", supportedCount >= 4, `supported=${supportedCount}`);

  await shotElement(
    page.locator("#exp-overview"),
    "m2_experiments_overview_1440.png",
  );
  await shotElement(
    page.locator(".exp-card:has(#exp-threshold-table)").first(),
    "m2_experiments_threshold_1440.png",
  );

  // --- threshold explorer --------------------------------------------------
  const thresholds = await page.locator("#exp-threshold-switch button").count();
  check("five threshold buttons", thresholds === 5, `count=${thresholds}`);

  const tableText = await page.locator("#exp-threshold-table").innerText();
  check("threshold table shows area conservation", tableText.includes("holds"), tableText);
  const ndviText = await page.locator("#exp-threshold-table").innerText();
  const ndviDecrease = ndviText.match(/Candidate decrease\s+([\d,.]+) ha/);
  check("decrease area displayed", Boolean(ndviDecrease), ndviText);

  // switch index to mndwi and confirm values change (synchronised statistics)
  await page.locator('#exp-index-switch button[data-value="mndwi"]').click();
  const mndwiText = (await page.locator("#exp-threshold-table").innerText()).replace(/\s+/g, " ");
  check("index switch updates threshold label", mndwiText.includes("ΔMNDWI"), mndwiText);
  check(
    "index switch changes areas",
    !mndwiText.includes(ndviDecrease?.[1] || "__nomatch__"),
    mndwiText,
  );

  // switch threshold and confirm the row updates from recorded values
  await page.locator('#exp-threshold-switch button[data-value="0.05"]').click();
  const looseText = (await page.locator("#exp-threshold-table").innerText()).replace(/\s+/g, " ");
  check("threshold switch updates label", looseText.includes("±0.05"), looseText);
  const looseDecrease = looseText.match(/Candidate decrease\s+([\d,.]+) ha/);
  check(
    "looser threshold yields larger candidate area",
    Number(looseDecrease?.[1]?.replace(/,/g, "")) >
      Number(mndwiText.match(/Candidate decrease\s+([\d,.]+) ha/)?.[1]?.replace(/,/g, "")),
    `${looseDecrease?.[1]} vs ${mndwiText.match(/Candidate decrease\s+([\d,.]+) ha/)?.[1]}`,
  );

  const responseChartVisible = await page
    .locator("#exp-response-chart img")
    .isVisible();
  check("threshold response chart embedded", responseChartVisible);


  // --- method comparison ----------------------------------------------------
  const methodRows = await page.locator("#exp-method-table tr").count();
  check("method comparison rows for mndwi", methodRows >= 17, `rows=${methodRows}`);
  const methodNote = (await page.locator("#exp-method-note").textContent()) || "";
  check("method note names index", methodNote.includes("MNDWI"), methodNote);
  const compareChartVisible = await page
    .locator("#exp-compare-chart img")
    .isVisible();
  check("estimator comparison chart embedded", compareChartVisible);
  await shotElement(
    page.locator(".exp-card:has(#exp-method-table)").first(),
    "m2_experiments_methods_1440.png",
  );

  // --- uncertainty ------------------------------------------------------------
  const uncertaintyText = (await page.locator("#exp-uncertainty").innerText()).replace(/\s+/g, " ");
  check("bootstrap method named", uncertaintyText.includes("spatial block bootstrap"), uncertaintyText);
  check("resample count shown", /\d+ of 200 requested/.test(uncertaintyText), uncertaintyText);
  check("seed shown", uncertaintyText.includes("seed 20260326"), uncertaintyText);
  check(
    "95% range shown",
    uncertaintyText.includes("95% range"),
    uncertaintyText,
  );
  const bootstrapChartVisible = await page
    .locator("#exp-bootstrap-chart img")
    .isVisible();
  check("bootstrap chart embedded", bootstrapChartVisible);
  await shotElement(
    page.locator(".exp-card:has(#exp-uncertainty)").first(),
    "m2_experiments_uncertainty_1440.png",
  );
  await shot(page, "m2_experiments_section_1440.png");

  // --- guardrails and exports -------------------------------------------------
  const guardrailCount = await page.locator("#exp-guardrails li").count();
  check("guardrails listed", guardrailCount >= 4, `count=${guardrailCount}`);
  const guardrailText = (await page.locator("#exp-guardrails").innerText()).replace(/\s+/g, " ");
  check(
    "no-verification guardrail stated",
    guardrailText.includes("not verified environmental change"),
    guardrailText,
  );
  check("observation counts stated", guardrailText.includes("Observation counts"), guardrailText);

  const exportLinks = await page.locator("#exp-exports a").count();
  check("four export links", exportLinks === 4, `count=${exportLinks}`);
  const manifestNote = (await page.locator("#exp-manifest-note").textContent()) || "";
  check("manifest note names run", manifestNote.includes("run "), manifestNote);

  // --- export responses actually exist ----------------------------------------
  const hrefs = await page.locator("#exp-exports a").evaluateAll((links) =>
    links.map((link) => link.getAttribute("href")),
  );
  for (const href of hrefs) {
    const response = await page.request.get(new URL(href, BASE_URL).toString());
    check(`export reachable: ${href}`, response.ok(), `status=${response.status()}`);
  }
  const resultResponse = await page.request.get(
    new URL(hrefs.find((h) => h.includes("result.json")), BASE_URL).toString(),
  );
  const resultPayload = await resultResponse.json();
  check(
    "exported result has no accuracy keys",
    !JSON.stringify(Object.keys(resultPayload)).match(/accuracy|f1/i),
    "keys: " + Object.keys(resultPayload).join(","),
  );

  // --- chart sources reachable and served as SVG -------------------------------
  const chartSrc = await page
    .locator("#exp-response-chart img")
    .getAttribute("src");
  const chartResponse = await page.request.get(new URL(chartSrc, BASE_URL).toString());
  check("chart served as svg", chartResponse.ok() && (chartResponse.headers()["content-type"] || "").includes("svg"), chartSrc);

  // --- narrow viewport ----------------------------------------------------------
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(400);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  check("no horizontal overflow at 390px", overflow <= 1, `overflow=${overflow}px`);
  await shot(page, "m2_experiments_390.png");

  // --- missing-run error state (fresh context, intercept API) --------------------
  const errorPage = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await errorPage.route("**/api/experiments/*/latest", (route) =>
    route.fulfill({ status: 404, body: '{"detail":"no recorded runs"}' }),
  );
  await errorPage.goto(BASE_URL, { waitUntil: "networkidle" });
  await errorPage.waitForFunction(
    () => {
      const el = document.getElementById("experiments");
      return el && !el.hidden;
    },
    undefined,
    { timeout: 10000 },
  );
  const errorLede = (await errorPage.locator("#exp-lede").textContent()) || "";
  check(
    "missing-run state names the runner command",
    errorLede.includes("run_experiment.py"),
    errorLede,
  );
  await shot.call(null, errorPage, "m2_experiments_missing_run.png").then(() => {});
  await errorPage.close();

  check("no console errors", results.console_errors.length === 0, results.console_errors.join(" | "));
  check("no page errors", results.page_errors.length === 0, results.page_errors.join(" | "));
  check(
    "no failed requests",
    results.failed_requests.length === 0,
    results.failed_requests.join(" | "),
  );

  await browser.close();
  results.completed_utc = new Date().toISOString();
  results.passed = results.checks.filter((item) => item.passed).length;
  results.failed = results.checks.filter((item) => !item.passed).length;
  fs.writeFileSync(
    path.join(EVIDENCE, "m2_browser_results.json"),
    JSON.stringify(results, null, 2),
  );
  console.log(`checks passed: ${results.passed}, failed: ${results.failed}`);
  console.log(`screenshots: ${results.screenshots.join(", ")}`);
}

main().catch((error) => {
  console.error("VERIFY_FAILED:", error.message);
  results.completed_utc = new Date().toISOString();
  results.passed = results.checks.filter((item) => item.passed).length;
  results.failed = results.checks.filter((item) => !item.passed).length;
  fs.writeFileSync(
    path.join(EVIDENCE, "m2_browser_results.json"),
    JSON.stringify(results, null, 2),
  );
  process.exit(1);
});
