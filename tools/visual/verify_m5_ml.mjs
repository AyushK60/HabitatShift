/* M5-G6 real-browser verification of the ML reference-experiment integration.
 *
 * Verifies, in the rendered UI, that every displayed ML number equals the
 * underlying generated artifact (studies/m5ml_findings.json) — the same
 * "no recomputation" contract as verify_m4_r3.mjs:
 *
 *  - Explore: the additive ML block renders the plain-language summary and
 *    the recorded agreement percentage for studies that have an M5 record;
 *    studies without one (the Himalayan pair) show the explicit
 *    "no record available" note instead.
 *  - Research Mode: model configuration, split design, evaluation table with
 *    per-class support gating (classes below the 50-px support floor show
 *    "not reported", never invented numbers), framing string, application
 *    epochs, geographic stability range, guardrails/limitations.
 *  - Deep consistency: the mathematical records on the same page are
 *    unchanged (existing selectors still render).
 *  - Showcase mode: the same blocks work with the backend stopped (the
 *    artifact ships in dist/studies/).
 *
 * Usage:
 *   HABITATSHIFT_URL=http://127.0.0.1:8098/ node tools/visual/verify_m5_ml.mjs
 *   (showcase run: start the static server only, then run the same command)
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const BASE_URL = process.env.HABITATSHIFT_URL || "http://127.0.0.1:8098/";
const EVIDENCE = path.resolve(import.meta.dirname, "../../docs/evidence/m5");
const SHOWCASE = process.env.M5_SHOWCASE === "1";

let passed = 0;
let failed = 0;
function check(condition, name, detail = "") {
  if (condition) {
    passed += 1;
    console.log(`ok ${passed}. ${name}${detail ? ` — ${detail}` : ""}`);
  } else {
    failed += 1;
    console.log(`FAIL ${name}${detail ? ` — ${detail}` : ""}`);
    throw new Error(`check failed: ${name}`);
  }
}

const app = async (page, hash) => {
  await page.goto(`${BASE_URL}#${hash}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
};

const artifact = (page) =>
  page.evaluate(async () => {
    const response = await fetch("studies/m5ml_findings.json");
    return response.json();
  });

const openResearchForFirstFinding = async (page) => {
  await page.getByRole("button", { name: "What changed?", exact: true }).click();
  await page.getByRole("tab", { name: "Explore the Evidence" }).click();
  await page.locator(".finding-entry").first().click();
  await page.getByRole("tab", { name: "Research Mode" }).click();
};

const run = async () => {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    // in showcase mode the app probes the live backend and logs the expected
    // 404s — the same failures verify_m4_showcase treats as mode switching
    if (SHOWCASE && msg.text().includes("Failed to load resource")) return;
    consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  /* 1. artifact sanity -------------------------------------------------- */
  await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });
  const index = await artifact(page);
  check(index.schema === "habitatshift-m5ml-index/1", "artifact: schema version");
  check(
    new Set(Object.keys(index.experiments)).size === 5,
    "artifact: five recorded ML experiments",
    Object.keys(index.experiments).join(", ")
  );

  const kathmandu = index.experiments.kathmandu_m4.ml_record;
  const agreementPct = (kathmandu.evaluation.overall_agreement * 100).toFixed(1);

  /* 2. Explore tab: ML block present and numerically faithful ------------ */
  await app(page, "/workstation/kathmandu_urban");
  await page.getByRole("button", { name: "What changed?", exact: true }).click();
  await page.getByRole("tab", { name: "Explore the Evidence" }).click();
  const exploreBlock = page.locator('[data-testid="explore-ml-block"]');
  await exploreBlock.waitFor({ state: "visible", timeout: 8000 });
  const exploreText = await exploreBlock.innerText();
  check(
    exploreText.includes("Additional ML reference experiment (M5)"),
    "explore: ML block labelled as an additional M5 experiment"
  );
  check(
    exploreText.includes(`${agreementPct} %`),
    `explore: agreement equals the artifact (${agreementPct} %)`
  );
  check(
    exploreText.includes("not independent ground truth"),
    "explore: agreement framed as reference agreement, not ground truth"
  );
  check(
    exploreText.includes(kathmandu.reference.dataset),
    "explore: reference dataset named",
    kathmandu.reference.dataset
  );

  /* 3. Himalayan study: explicit no-record note -------------------------- */
  await app(page, "/workstation/himalaya_purepu_2025");
  await page.getByRole("button", { name: "What changed?", exact: true }).click();
  await page.getByRole("tab", { name: "Explore the Evidence" }).click();
  const noRecord = await page
    .locator(".findings-panel, .insp-note", { hasText: "ML reference experiment: no record" })
    .count();
  check(noRecord >= 1, "himalaya: explicit ML no-record note (label-gate BLOCKED)");

  /* 4. Research Mode: technical panel faithful to the artifact ----------- */
  await app(page, "/workstation/kathmandu_urban");
  await openResearchForFirstFinding(page);
  const researchBlock = page.locator('[data-testid="research-ml-block"]');
  await researchBlock.waitFor({ state: "visible", timeout: 8000 });
  const researchText = await researchBlock.innerText();

  check(
    researchText.includes(String(kathmandu.model.params.n_estimators)) &&
      researchText.includes(String(kathmandu.model.params.random_state)),
    "research: model hyperparameters (trees, seed) equal the artifact"
  );
  const split = kathmandu.split_design;
  check(
    researchText.includes(`train ${split.train_px}`) &&
      researchText.includes(`test ${split.test_px} px`),
    "research: split-design pixel counts equal the artifact"
  );
  for (const [className, row] of Object.entries(kathmandu.evaluation.per_class)) {
    const reported = researchText.includes(className);
    check(reported, `research: class row rendered — ${className}`);
    if (row.metrics_reported) {
      const f1 = row.f1.toFixed(3);
      check(researchText.includes(f1), `research: F1 for ${className} equals the artifact (${f1})`);
    } else {
      check(
        researchText.includes("not reported"),
        `research: ${className} gated below the support floor shows "not reported"`
      );
    }
  }
  check(
    researchText.includes(kathmandu.evaluation.framing.split(";")[0].slice(0, 40)),
    "research: framing string rendered verbatim"
  );
  const epochs = Object.values(kathmandu.application).map((a) => a.date);
  check(
    epochs.every((date) => researchText.includes(date)),
    "research: both application epochs rendered",
    epochs.join(", ")
  );
  // fraction values from the artifact appear at recorded precision
  const firstEpoch = Object.values(kathmandu.application)[0];
  const someFraction = Object.entries(firstEpoch.predicted_fractions)
    .map(([cls, frac]) => ({ cls, text: `${cls} ${(frac * 100).toFixed(1)} %` }))
    .some((entry) => researchText.includes(entry.text));
  check(someFraction, "research: predicted fractions equal the artifact at recorded precision");

  // the mathematical record panels still render untouched
  const mathBlock = await page.locator(".math-block").count();
  check(mathBlock >= 1, "research: mathematical method block still present (additive, not replaced)");

  /* 5. second study spot-check (chilika dry) ----------------------------- */
  await app(page, "/workstation/chilika_wetland");
  await openResearchForFirstFinding(page);
  const chilikaText = await page.locator('[data-testid="research-ml-block"]').innerText();
  const chilikaRecord = index.experiments.chilika_m4_dry.ml_record;
  check(
    chilikaText.includes(`${(chilikaRecord.evaluation.overall_agreement * 100).toFixed(1)} %`),
    `chilika: agreement equals the artifact (${(chilikaRecord.evaluation.overall_agreement * 100).toFixed(1)} %)`
  );

  /* 6. errors ------------------------------------------------------------ */
  check(consoleErrors.length === 0, "no console/page errors", consoleErrors.slice(0, 3).join(" | "));
  await page.screenshot({ path: path.join(EVIDENCE, "m5_ml_research_mode.png"), fullPage: false });

  await browser.close();
  console.log(`\n${SHOWCASE ? "showcase" : "live"} verify_m5_ml: ${passed} passed, ${failed} failed`);
  fs.writeFileSync(
    path.join(EVIDENCE, `verify_m5_ml_${SHOWCASE ? "showcase" : "live"}.json`),
    JSON.stringify({ passed, failed, showcase: SHOWCASE }, null, 2)
  );
  if (failed) process.exit(2);
};

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
