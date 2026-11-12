// Browser checks for the Tier 2/3 additions: report export, guided tour, accessibility (axe-core).
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const axeSource = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.HS_URL ?? "http://127.0.0.1:8098/";
const results = [];
const check = (name, ok, detail = "") => { results.push({ name, passed: !!ok, detail }); console.log((ok ? "ok    " : "FAIL  ") + name + (detail ? " — " + detail : "")); };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 160)));

// ---- export
await page.goto(BASE + "#/workstation/kathmandu_urban", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(4000);
const downloads = [];
page.on("download", (d) => downloads.push(d));
await page.getByTestId("export-report").click();
await page.waitForTimeout(1500);
check("export: two files downloaded", downloads.length === 2, downloads.map((d) => d.suggestedFilename()).join(", "));
const names = downloads.map((d) => d.suggestedFilename());
const md = downloads.find((d) => d.suggestedFilename().endsWith("_report.md"));
const js = downloads.find((d) => d.suggestedFilename().endsWith("_provenance.json"));
if (md && js) {
  const mdText = fs.readFileSync(await md.path(), "utf8");
  const prov = JSON.parse(fs.readFileSync(await js.path(), "utf8"));
  check("export: report states candidate-signal framing", /candidate spectral signals/.test(mdText));
  check("export: report lists scene ids from the bundle", /S2[ABC]_/.test(mdText));
  check("export: report has ML agreement framing, no accuracy claim", /agreement/i.test(mdText) && /not accuracy against ground truth/.test(mdText));
  check("export: provenance has scene ids + sha256 + ML reference", prov.periods?.[0]?.scene_ids?.length > 0 && !!prov.experiment?.summary_sha256 && prov.ml_reference?.reference_dataset?.includes("WorldCover"));
}

// ---- guided tour
await page.getByTestId("start-tour").click();
await page.waitForTimeout(600);
check("tour: opens at step 1", (await page.getByTestId("guided-tour").innerText()).includes("step 1 of 6"));
const analysisActive = async () => page.evaluate(() => [...document.querySelectorAll(".segmented button.is-active")].map((b) => b.textContent).join("|"));
await page.getByRole("button", { name: "Next" }).click(); await page.waitForTimeout(500);
check("tour: step 2 switches to Change", (await analysisActive()).includes("Change"));
await page.getByRole("button", { name: "Next" }).click(); await page.waitForTimeout(500);
check("tour: step 3 switches to Quality", (await analysisActive()).includes("Quality"));
await page.getByRole("button", { name: "Back" }).click(); await page.waitForTimeout(400);
check("tour: Back returns to Change", (await analysisActive()).includes("Change"));
await page.keyboard.press("Escape"); await page.waitForTimeout(300);
check("tour: Escape closes", (await page.getByTestId("guided-tour").count()) === 0);

// ---- accessibility (axe, WCAG A/AA tags)
// ---- custom-area scene availability (needs the live backend)
if (!process.env.HS_STATIC) {
  await page.goto(BASE + "#/availability", { waitUntil: "domcontentloaded" }); await page.waitForTimeout(1500);
  await page.getByTestId("avail-run").click();
  await page.waitForSelector('[data-testid="avail-result"]', { timeout: 60000 });
  const rows = await page.locator('[data-testid="avail-result"] tbody tr').count();
  check("availability: live catalogue returns scenes for the preset box", rows > 0, `${rows} scenes`);
  check("availability: honest notes shown", (await page.locator(".availability-notes li").count()) >= 3);
  await page.getByLabel("East").fill("86.5"); await page.getByLabel("North").fill("20.5"); await page.getByLabel("West").fill("85"); await page.getByLabel("South").fill("19");
  await page.getByTestId("avail-run").click();
  await page.waitForSelector('[data-testid="avail-error"]', { timeout: 20000 });
  check("availability: oversized box rejected with the limit message", /limit/.test(await page.getByTestId("avail-error").innerText()));
}

const pages = [["landing", "#/"], ["availability", "#/availability"], ["workstation", "#/workstation/chilika_wetland"], ["experiments", "#/experiments"], ["methods", "#/methods"]];
for (const [name, hash] of pages) {
  await page.goto(BASE + hash, { waitUntil: "domcontentloaded" }); await page.waitForTimeout(3500);
  await page.evaluate(axeSource);
  const r = await page.evaluate(async () => await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] } }));
  const serious = r.violations.filter((v) => ["serious", "critical"].includes(v.impact));
  fs.writeFileSync(`../../docs/evidence/portfolio_axe_${name}.json`, JSON.stringify(r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help, targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")) })), null, 2));
  check(`a11y ${name}: no serious/critical WCAG A/AA violations`, serious.length === 0, serious.map((v) => `${v.id}×${v.nodes.length}`).join(", ") || `${r.violations.length} minor`);
}
check("no uncaught page errors", errors.length === 0, errors.join(" | "));
fs.writeFileSync("../../docs/evidence/verify_tier23.json", JSON.stringify({ base: BASE, checks: results }, null, 2));
await browser.close();
process.exit(results.every((r) => r.passed) ? 0 : 1);
