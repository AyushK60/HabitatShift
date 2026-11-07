import { chromium } from "playwright";
import fs from "node:fs";
const BASE_URL = "http://127.0.0.1:8099/";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const results = { base_url: BASE_URL, mode: "static-file-server-only", checks: [], console_errors: [], page_errors: [] };
const check = (name, ok, detail = "") => { results.checks.push({ name, passed: Boolean(ok), detail }); console.log((ok ? "ok    " : "FAIL  ") + name + (detail ? " — " + detail : "")); };
page.on("pageerror", (e) => results.page_errors.push(String(e).slice(0, 200)));
page.on("console", (m) => {
  if (m.type() !== "error") return;
  // The backend reachability probe (/api/studies/registry) is DESIGNED to
  // fail on a static file server — that failure is what switches the
  // workstation into showcase mode.
  if (m.location()?.url?.includes("/api/studies/registry")) return;
  results.console_errors.push(`${m.text().slice(0, 120)} @ ${m.location()?.url ?? ""}`);
});

await page.goto(BASE_URL + "#/", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
check("showcase: landing renders from bundles", await page.locator(".hero-copy h1").isVisible());
check("showcase: six gallery cards with real media", (await page.locator(".study-card").count()) === 6 && (await page.locator(".study-card-media img").count()) === 12);
for (const id of ["chilika_wetland", "western_ghats_forest", "kathmandu_urban", "himalaya_purepu_2025", "himalaya_langtang_2026"]) {
  await page.goto(BASE_URL + `#/workstation/${id}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3200);
  const state = await page.evaluate(() => ({
    h1: document.querySelector("main h1")?.textContent ?? null,
    layerSource: window.__hsMaps?.earlier?.getSource("layer-earlier")?.url ?? null,
  }));
  check(`showcase: ${id} renders map layer from bundle`, Boolean(state.h1) && state.layerSource?.includes(`/studies/${id}/previews/`), state.layerSource ?? "no source");
}
await page.goto(BASE_URL + "#/workstation/chilika_wetland", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
await page.evaluate(() => document.querySelector(".dock-toggle")?.click());
await page.waitForTimeout(900);
const plotBox = await page.locator(".dock-chart-section .ichart-plot").first().boundingBox();
await page.mouse.move(plotBox.x + plotBox.width * 0.5, plotBox.y + plotBox.height * 0.5, { steps: 3 });
await page.waitForTimeout(300);
const tip = await page.evaluate(() => document.querySelector(".ichart-tooltip")?.textContent ?? "");
check("showcase: interactive chart tooltip with recorded values", tip.includes("index units") && tip.includes("% of shared-valid AOI"), tip.slice(0, 90));
await page.screenshot({ path: "../../docs/evidence/m4/showcase_no_backend_chilika.png" });
// M4-R1 §15: the What Changed? experience works without the backend.
await page.goto(BASE_URL + "#/workstation/kathmandu_urban", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(3000);
await page.getByRole("button", { name: "What changed?", exact: true }).click();
await page.waitForTimeout(800);
await page.getByRole("tab", { name: "Findings" }).click();
await page.waitForTimeout(500);
const wcState = await page.evaluate(async () => {
  const src = window.__hsMaps?.earlier?.getSource("findings-overlay");
  const data = src ? await src.getData() : null;
  return {
    entries: document.querySelectorAll(".finding-entry").length,
    features: data?.features.length ?? 0,
    overview: document.querySelector(".findings-panel .insp-meaning")?.textContent ?? "",
  };
});
check(
  "showcase: What Changed? regions render from bundle without backend (M4-R1 §15.9)",
  wcState.entries > 0 && wcState.features === wcState.entries && wcState.overview.includes("candidate"),
  JSON.stringify({ entries: wcState.entries, features: wcState.features }),
);
await page.screenshot({ path: "../../docs/evidence/m4-r1/g9_showcase_what_changed.png" });
check("showcase: no unexpected console errors", results.console_errors.length === 0, results.console_errors.slice(0, 3).join(" | "));
check("showcase: no page errors", results.page_errors.length === 0, results.page_errors.slice(0, 3).join(" | "));
results.passed = results.checks.filter(c => c.passed).length;
results.failed = results.checks.filter(c => !c.passed).length;
fs.writeFileSync("../../docs/evidence/m4/showcase_no_backend_results.json", JSON.stringify(results, null, 2));
console.log(`\n${results.passed} passed, ${results.failed} failed`);
await browser.close();
process.exit(results.failed ? 1 : 0);
