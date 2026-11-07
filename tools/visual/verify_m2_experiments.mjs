/* M2 research-workbench real-browser verification with Playwright/Chromium.
 *
 * M4-R3 NOTE: refreshed to the current product contract. The M2 experiment
 * sections originally lived on the landing page (selector `#experiments`);
 * since M4-R1 G1 they live on the dedicated `/experiments` route, rendered
 * from the portable bundles with a six-investigation study selector, an
 * honest availability panel, descriptive M1 outputs and (for Coringa, with
 * the backend reachable) the recorded M2 hypothesis-testing run.
 *
 * Drives the actual page served by uvicorn (frontend/dist) and exercises it
 * end to end: experiment loading, study switching, availability honesty,
 * chart rendering, threshold table consistency, guardrails, export links and
 * the missing-run error state. Evidence (screenshots + machine-readable
 * results) goes to docs/evidence/m2/.
 *
 * Usage:
 *   HABITATSHIFT_URL=http://127.0.0.1:8098/ node tools/visual/verify_m2_experiments.mjs
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const BASE_URL = process.env.HABITATSHIFT_URL || "http://127.0.0.1:8098/";
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

const PAGE_URL = new URL("#/experiments", BASE_URL).toString();

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

  await page.goto(PAGE_URL, { waitUntil: "networkidle" });

  // --- page presence and load ---------------------------------------------
  const main_ = page.locator("main.experiments-page");
  await main_.waitFor({ state: "visible", timeout: 20000 });
  check("experiments page renders", await main_.isVisible());
  const h1 = (await page.locator("main.experiments-page h1").textContent()) || "";
  check("page headline names per-investigation measurements", h1.includes("Recorded measurements per investigation"), h1);

  // wait until the first bundle has rendered its descriptive block
  await page.waitForFunction(
    () => Boolean(document.querySelector("dl.exp-facts")),
    undefined,
    { timeout: 20000 },
  );
  await page.locator("main.experiments-page").evaluate((el) => el.scrollIntoView());

  const selectorButtons = page.locator(".exp-study-selector .segmented button");
  const studyCount = await selectorButtons.count();
  check("six investigations in study selector", studyCount === 6, `count=${studyCount}`);
  await shotElement(main_, "m2_experiments_overview_1440.png");

  // --- availability honesty -------------------------------------------------
  const availabilityRows = await page.locator(".availability-chip").count();
  check("availability rows present", availabilityRows >= 3, `rows=${availabilityRows}`);
  const plannedCount = await page.locator(".availability-chip.availability-planned").count();
  check("planned / not-available gaps stated", plannedCount >= 1, `planned=${plannedCount}`);

  // --- descriptive facts ------------------------------------------------------
  const factsBlock = page.locator("dl.exp-facts", { hasText: "Analysis grid" }).first();
  const factsCount = await factsBlock.locator("dt").count();
  check("descriptive facts listed", factsCount >= 3, `dt=${factsCount}`);
  const factsText = (await factsBlock.innerText()).replace(/\s+/g, " ");
  check("facts name evidence status", /evidence status/i.test(factsText), factsText);
  check("facts name analysis grid", /analysis grid/i.test(factsText), factsText);

  // --- interactive charts -------------------------------------------------------
  const chartCount = await page.locator(".ichart-svg svg").count();
  check("interactive charts rendered as svg", chartCount >= 2, `charts=${chartCount}`);
  const thresholdsChart = await page.locator(".ichart-svg svg").first().isVisible();
  check("threshold chart visible", thresholdsChart);
  await shot(page, "m2_experiments_threshold_1440.png");

  // --- candidate change areas table ------------------------------------------------
  const areaRows = await page.locator('[aria-labelledby="exp-areas-title"] tbody tr').count();
  check("threshold area rows present", areaRows >= 3, `rows=${areaRows}`);
  const areasText = (await page.locator('[aria-labelledby="exp-areas-title"]').innerText()).replace(/\s+/g, " ");
  check("areas labelled candidate, not verified", /candidate spectral signals/i.test(areasText), areasText);
  // looser threshold must not yield a smaller candidate decrease area
  const decreaseAreas = await page
    .locator('[aria-labelledby="exp-areas-title"] tbody tr td:nth-child(2)')
    .evaluateAll((cells) => cells.map((cell) => Number(cell.textContent.replace(/,/g, ""))));
  check(
    "looser threshold yields larger-or-equal candidate decrease area",
    decreaseAreas.length >= 2 && decreaseAreas[0] >= decreaseAreas[decreaseAreas.length - 1],
    `areas=${decreaseAreas.join(",")}`,
  );

  // --- guardrails ---------------------------------------------------------------------
  const guardrailLists = await page.locator("ul.exp-guardrails").count();
  check("can/cannot guardrail lists present", guardrailLists === 2, `lists=${guardrailLists}`);
  const cannotText = (await page.locator("ul.exp-guardrails").nth(1).innerText()).replace(/\s+/g, " ");
  check("cannot-conclude list non-empty", cannotText.trim().length > 40, cannotText);
  await shotElement(
    page.locator('[aria-labelledby="exp-limits-title"]').locator("xpath=.."),
    "m2_experiments_uncertainty_1440.png",
  );

  // --- exports ---------------------------------------------------------------------------
  const bundleHref = await page
    .locator('ul.exp-exports a[href*="bundle.json"]')
    .first()
    .getAttribute("href");
  check("bundle export link present", Boolean(bundleHref), String(bundleHref));
  const bundleResponse = await page.request.get(new URL(String(bundleHref), BASE_URL).toString());
  check("bundle export reachable", bundleResponse.ok(), `status=${bundleResponse.status()}`);
  const bundlePayload = await bundleResponse.json();
  check(
    "bundle payload has no supervised-accuracy keys",
    !JSON.stringify(Object.keys(bundlePayload)).match(/accuracy|f1_score/i),
    "keys: " + Object.keys(bundlePayload).join(","),
  );
  const methodsHref = await page
    .locator('ul.exp-exports a[href*="/methods"]')
    .first()
    .getAttribute("href");
  check("methods link present", Boolean(methodsHref), String(methodsHref));

  // --- recorded M2 run (Coringa, backend reachable) --------------------------------------
  const runLedeLoc = page.locator("p.exp-lede", { hasText: "Recorded run" }).first();
  const hasRecordedRun = (await runLedeLoc.count()) > 0;
  const runText = hasRecordedRun ? ((await runLedeLoc.locator("code").first().textContent()) || "") : "";
  check("recorded M2 run id displayed", /\d{8}T\d{6}Z_/.test(runText || ""), runText);
  const runLede = hasRecordedRun ? ((await runLedeLoc.textContent()) || "") : "";
  check(
    "recorded run reports no supervised labels",
    runLede.includes("no supervised labels"),
    runLede,
  );
  const verdictCount = await page.locator("ul.verdict-list li").count();
  check("five hypothesis verdicts", verdictCount === 5, `count=${verdictCount}`);
  const chipCount = await page.locator(".verdict-chip").count();
  check("verdict chips rendered", chipCount === 5, `chips=${chipCount}`);
  await shot(page, "m2_experiments_section_1440.png");

  // --- study switch: an investigation without an M2 run ------------------------------------
  await selectorButtons.filter({ hasText: "Kathmandu" }).click();
  await page.waitForFunction(
    () => /no hypothesis-testing run yet/i.test(document.body.innerText),
    undefined,
    { timeout: 15000 },
  );
  const kathmanduNote = (await page.locator("p.exp-lede").filter({ hasText: /no hypothesis-testing run yet/i }).textContent()) || "";
  check("non-M2 study states the gap plainly", /descriptive measurements/i.test(kathmanduNote), kathmanduNote);
  const kathmanduCharts = await page.locator(".ichart-svg svg").count();
  check("study switch renders that study's charts", kathmanduCharts >= 2, `charts=${kathmanduCharts}`);
  await shot(page, "m2_experiments_kathmandu_1440.png");

  // switch back
  await selectorButtons.filter({ hasText: "Coringa" }).click();
  await page.waitForFunction(
    () => /recorded experiment/i.test(document.body.innerText),
    undefined,
    { timeout: 15000 },
  );
  check("switch back to Coringa restores recorded run", true);

  // --- narrow viewport ---------------------------------------------------------------------
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(400);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  check("no horizontal overflow at 390px", overflow <= 1, `overflow=${overflow}px`);
  await shot(page, "m2_experiments_390.png");

  // --- missing-run error state (fresh context, intercept API) -------------------------------
  const errorPage = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await errorPage.route("**/api/experiments/*/latest", (route) =>
    route.fulfill({ status: 404, body: '{"detail":"no recorded runs"}' }),
  );
  await errorPage.goto(PAGE_URL, { waitUntil: "networkidle" });
  await errorPage.waitForFunction(
    () => /not serving the recorded M2 run/i.test(document.body.innerText),
    undefined,
    { timeout: 15000 },
  );
  const missingNote = (await errorPage
    .locator("p.exp-note")
    .filter({ hasText: /not serving the recorded M2 run/i })
    .textContent()) || "";
  check(
    "missing-run state names the bundle fallback",
    /portable showcase bundle/i.test(missingNote),
    missingNote,
  );
  await shot(errorPage, "m2_experiments_missing_run.png");
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
