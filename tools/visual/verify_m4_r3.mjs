/* M4-R3 real-browser verification with Playwright/Chromium.
 *
 * Covers the M4-R3 brief §11 items not already carried by verify_m4 /
 * verify_m4_showcase / verify_m2_experiments, with emphasis on the core
 * architectural rule: both experiences display values that are byte-equal
 * (modulo recorded display precision) to the underlying evidence records —
 * the browser never recomputes.
 *
 * Checks: Explore/Research open, study preservation, finding selection,
 * map highlighting matches the selected evidence_id, map click selects,
 * Explore→Research keeps evidence_id, UI numbers equal the record numbers
 * (measurements + sensitivity), related findings open, top-five disclosure
 * visible, PARTIAL study note, study-switch state isolation, responsive
 * layouts without horizontal overflow, and no console/page/network errors.
 *
 * Usage:
 *   HABITATSHIFT_URL=http://127.0.0.1:8098/ node tools/visual/verify_m4_r3.mjs
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const BASE_URL = process.env.HABITATSHIFT_URL || "http://127.0.0.1:8098/";
const EVIDENCE = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "docs",
  "evidence",
  "m4-r3",
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
  console.log(`${condition ? "ok    " : "FAIL  "}${name}${detail ? ` — ${detail}` : ""}`);
  if (!condition) throw new Error(`${name}${detail ? `: ${detail}` : ""}`);
}

async function shot(page, name) {
  const file = path.join(EVIDENCE, name);
  await page.screenshot({ path: file, fullPage: false });
  results.screenshots.push(name);
  return file;
}

const app = async (page, hash) => {
  await page.goto(`${BASE_URL}#${hash}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
};

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on("console", (m) => {
    if (m.type() === "error") results.console_errors.push(m.text());
  });
  page.on("pageerror", (e) => results.page_errors.push(String(e)));
  page.on("requestfailed", (r) =>
    results.failed_requests.push(`${r.url()} :: ${r.failure()?.errorText}`)
  );

  const bundleFor = (studyId) =>
    page.evaluate(async (id) => {
      const bundle = await (await fetch(`/studies/${id}/bundle.json`)).json();
      return bundle;
    }, studyId);

  /* --- 1–4: Explore opens, finding selection, study preservation (§11.1–4) --- */
  await app(page, "/workstation/kathmandu_urban");
  await page.getByRole("button", { name: "What changed?", exact: true }).click();
  await page.waitForTimeout(900);
  await page.getByRole("tab", { name: "Explore the Evidence" }).click();
  await page.waitForTimeout(500);
  check("1. Explore the Evidence opens with overview", (await page.locator(".findings-panel .insp-meaning").count()) === 1);

  const bundle = await bundleFor("kathmandu_urban");
  const recordList = bundle.experiments[0].findings.findings;
  const target = recordList.slice().sort((a, b) => b.area_ha - a.area_ha)[0];
  check("4. finding list renders the recorded count", (await page.locator(".finding-entry").count()) === recordList.length);

  await page.locator(".finding-entry", { hasText: target.display_id }).first().click();
  await page.waitForTimeout(900);
  const selectedText = await page.evaluate(() => ({
    entry: document.querySelector(".finding-entry.is-selected")?.textContent ?? "",
    detail: document.querySelector(".finding-detail")?.textContent ?? "",
  }));
  check(
    "4. selecting a finding shows its card with the evidence_id",
    selectedText.detail.includes(target.evidence_id),
    target.evidence_id,
  );

  /* --- 5: map highlighting matches the selected evidence (§11.5) --- */
  const mapState = await page.evaluate(async (evidenceId) => {
    const map = window.__hsMaps.earlier;
    const src = map.getSource("findings-overlay");
    const data = await src.getData();
    const feature = data.features.find((f) => f.properties.evidence_id === evidenceId);
    if (!feature) return { found: false };
    // point-in-polygon on the recorded exterior ring: take the recorded
    // centroid and confirm the rendered feature under it is the selection
    const rings = feature.geometry.coordinates;
    const ring = rings[0];
    const lon = ring.reduce((s, p) => s + p[0], 0) / ring.length;
    const lat = ring.reduce((s, p) => s + p[1], 0) / ring.length;
    const px = map.project([lon, lat]);
    const hits = map.queryRenderedFeatures([px.x, px.y], { layers: ["findings-fill"] });
    return {
      found: true,
      zoom: map.getZoom(),
      hitId: hits[0]?.properties?.evidence_id ?? null,
    };
  }, target.evidence_id);
  check(
    "5. map highlight matches the selected evidence geometry",
    mapState.found && mapState.hitId === target.evidence_id && mapState.zoom > 3,
    JSON.stringify({ found: mapState.found, hitId: mapState.hitId, zoom: mapState.zoom }),
  );
  await shot(page, "m4_r3_explore_selected_1440.png");

  /* --- 6: map click selects a finding (§11.6) --- */
  // From the default study view, click a recorded region whose top rendered
  // feature is that finding (regions can overlap; queryRenderedFeatures
  // decides, exactly as the map's own click handler does).
  const clickTarget = await page.evaluate((recordList) => {
    const map = window.__hsMaps.earlier;
    const rect = map.getContainer().getBoundingClientRect();
    for (const f of recordList.slice().sort((a, b) => b.area_ha - a.area_ha)) {
      // the recorded centroid is an interior point of the component — fill
      // queries at a boundary vertex can miss the polygon
      const px = map.project(f.centroid_lonlat);
      if (px.x < 5 || px.y < 5 || px.x > rect.width - 5 || px.y > rect.height - 5) continue;
      const hits = map.queryRenderedFeatures([px.x, px.y], { layers: ["findings-fill"] });
      if (hits.length && hits[0].properties.evidence_id === f.evidence_id) {
        return { evidence_id: f.evidence_id, x: rect.left + px.x, y: rect.top + px.y };
      }
    }
    return null;
  }, recordList);
  check("6. a clickable recorded region is visible in the study view", Boolean(clickTarget), JSON.stringify(clickTarget));
  await page.mouse.click(clickTarget.x, clickTarget.y);
  await page.waitForTimeout(1000);
  const afterClick = await page.evaluate((expected) => ({
    detail: document.querySelector(".finding-detail")?.textContent ?? "",
    tab: document.querySelector(".insp-tab.is-active")?.textContent ?? "",
    matches: (document.querySelector(".finding-detail")?.textContent ?? "").includes(expected),
  }), clickTarget.evidence_id);
  check(
    "6. clicking a region on the map selects that finding",
    afterClick.matches && afterClick.tab === "Explore the Evidence",
    JSON.stringify({ expected: clickTarget.evidence_id, tab: afterClick.tab }),
  );

  /* --- 8: mathematical values equal the evidence record (§11.8) --- */
  const uiCard = await page.evaluate(() => {
    const detail = document.querySelector(".finding-detail");
    const facts = [...detail.querySelectorAll(".insp-facts > div")].map((row) =>
      row.textContent.replace(/\s+/g, " ").trim()
    );
    return facts;
  });
  const rec = recordList.find((f) => f.evidence_id === clickTarget.evidence_id);
  const areaRow = uiCard.find((row) => row.includes("Candidate area"));
  const meanRow = uiCard.find((row) => row.includes("Measured signal"));
  const denomRow = uiCard.find((row) => row.includes("Denominator"));
  const expArea = Number(rec.area_ha.toFixed(2));
  const uiArea = Number((areaRow.match(/([\d,]+\.\d{2}) ha/) ?? [])[1]?.replace(/,/g, ""));
  check(
    "8. card area equals recorded area_ha",
    uiArea === expArea,
    `ui ${uiArea} vs record ${expArea}`,
  );
  const uiMean = Number((meanRow.match(/mean (-?[\d.]+)/) ?? [])[1]);
  check(
    "8. card mean Δ equals recorded mean_delta (3 dp)",
    uiMean === Number(Number(rec.mean_delta).toFixed(3)),
    `ui ${uiMean} vs record ${Number(rec.mean_delta).toFixed(3)}`,
  );
  const uiPx = Number((denomRow.match(/([\d,]+) shared-valid/) ?? [])[1]?.replace(/,/g, ""));
  check(
    "8. card denominator equals recorded valid_pixel_denominator",
    uiPx === rec.evidence.spatial_measurements.valid_pixel_denominator,
    `ui ${uiPx} vs record ${rec.evidence.spatial_measurements.valid_pixel_denominator}`,
  );

  /* --- 7: Explore→Research preserves evidence_id (§11.7) --- */
  await page.getByRole("tab", { name: "Research Mode" }).click();
  await page.waitForTimeout(500);
  const researchState = await page.evaluate((evidenceId) => {
    const text = document.querySelector(".evidence-record")?.textContent ?? "";
    return {
      sameRecord: text.includes(evidenceId),
      schema: text.includes("habitatshift-evidence-record/1"),
      urlCarries: location.href.includes(`finding=${evidenceId}`),
    };
  }, clickTarget.evidence_id);
  check(
    "7. Research Mode shows the same evidence_id as the Explore card",
    researchState.sameRecord && researchState.schema && researchState.urlCarries,
    JSON.stringify(researchState),
  );

  /* --- 10: sensitivity table shows actual recorded values (§11.10) --- */
  const sens = await page.evaluate(() =>
    [...document.querySelectorAll(".sensitivity-table tbody tr")].map((row) =>
      [...row.querySelectorAll("th,td")].map((cell) => cell.textContent.trim())
    )
  );
  const sensRecord = rec.evidence.evidence_quality.threshold_sensitivity;
  for (const row of sens) {
    const key = row[0].includes("−") ? "t_minus_0.05" : "t_plus_0.05";
    const neighbour = sensRecord.neighbours[key];
    check(
      `10. sensitivity ${key} pixels equal record`,
      Number(row[1].replace(/,/g, "")) === neighbour.component_pixels,
      `ui ${row[1]} vs record ${neighbour.component_pixels}`,
    );
    check(
      `10. sensitivity ${key} retained % equals record`,
      Number(row[2].replace(/[ %]/g, "")) === Number((neighbour.retained_fraction_of_region * 100).toFixed(1)),
      `ui ${row[2]} vs record ${(neighbour.retained_fraction_of_region * 100).toFixed(1)}`,
    );
  }
  const sensLabel = await page.evaluate(
    (label) =>
      (document.querySelector(".evidence-record")?.textContent ?? "").includes(label),
    sensRecord.label
  );
  check("10. recorded sensitivity label shown verbatim", sensLabel);

  /* --- 9: related findings open correctly (§11.9) --- */
  const withLinks = recordList.find((f) => (f.evidence?.relationships?.links ?? []).length > 0);
  check("9. a related-finding test case exists", Boolean(withLinks), withLinks?.evidence_id ?? "none");
  if (withLinks) {
    const firstLink = withLinks.evidence.relationships.links[0];
    // hash-only navigation does not remount the workstation; a real reload
    // exercises the deep link as a fresh visit would
    await page.goto(`${BASE_URL}#/workstation/kathmandu_urban?finding=${encodeURIComponent(withLinks.evidence_id)}&view=research`, { waitUntil: "networkidle" });
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(2200);
    await page.locator(".evidence-record .insp-note button.insp-link").first().click();
    await page.waitForTimeout(1500);
    const relatedState = await page.evaluate((expected) => ({
      record: (document.querySelector(".evidence-record")?.textContent ?? "").includes(expected),
      url: location.href.includes(encodeURIComponent(expected)),
    }), firstLink.with_evidence_id);
    check(
      "9. related record opens in place with the linked evidence_id",
      relatedState.record && relatedState.url,
      JSON.stringify(relatedState),
    );
  }

  /* --- 11: top-five disclosure visible (§11.5/§5) --- */
  await app(page, "/workstation/kathmandu_urban");
  await page.getByRole("button", { name: "What changed?", exact: true }).click();
  await page.waitForTimeout(800);
  await page.getByRole("tab", { name: "Explore the Evidence" }).click();
  await page.waitForTimeout(500);
  const disclosure = await page.evaluate(
    () => (document.querySelector(".selection-disclosure")?.textContent ?? "").replace(/\s+/g, " ")
  );
  const policyRow = await page.evaluate(async () => {
    const policy = await (await fetch("studies/selection_policy.json")).json();
    return policy.experiments.find((e) => e.experiment_id === "kathmandu_m4");
  });
  check(
    "11. top-five selection disclosure visible with audited counts",
    disclosure.includes("Curated selection") &&
      disclosure.includes(`${policyRow.findings_recorded} findings`) &&
      disclosure.includes(`${policyRow.components_at_or_above_mmu_unrecorded_top5_cap} additional qualifying components`),
    disclosure.slice(0, 200),
  );

  /* --- 14: PARTIAL study limitations visible (§11.14) --- */
  await app(page, "/workstation/himalaya_purepu_2025");
  await page.getByRole("button", { name: "What changed?", exact: true }).click();
  await page.waitForTimeout(1000);
  await page.getByRole("tab", { name: "Explore the Evidence" }).click();
  await page.waitForTimeout(500);
  const partialNote = await page.evaluate(() =>
    (document.querySelector(".partial-note")?.textContent ?? "")
  );
  check(
    "14. PARTIAL evidence note visible for the restricted study",
    partialNote.includes("PARTIAL evidence"),
    partialNote.slice(0, 60),
  );
  await shot(page, "m4_r3_partial_study_1440.png");

  /* --- 3/15: study selection preserved + no state leak (§11.3/15) --- */
  const purepuUrl = page.url();
  check("3. study id preserved in the URL", purepuUrl.includes("himalaya_purepu_2025"), purepuUrl);
  await app(page, "/workstation/chilika_wetland");
  await page.waitForTimeout(1500);
  const leak = await page.evaluate(() => ({
    kathmandu: document.body.textContent.includes("ev-kathmandu"),
    purepu: document.body.textContent.includes("ev-himalaya_purepu"),
    detail: Boolean(document.querySelector(".finding-detail")),
  }));
  check(
    "15. switching studies leaks no stale findings or selection",
    !leak.kathmandu && !leak.purepu && !leak.detail,
    JSON.stringify(leak),
  );

  /* --- 12: What am I looking at? guide still works (§11.12) --- */
  await page.getByRole("tab", { name: "What am I looking at?" }).click();
  await page.waitForTimeout(500);
  const guide = await page.evaluate(() => {
    const panel = document.querySelector(".layer-guide");
    return (
      Boolean(panel) &&
      panel.textContent.includes("cannot establish") &&
      panel.textContent.includes("m per pixel")
    );
  });
  check("12. What am I looking at? layer guide works", guide);

  /* --- 13: every study's interpretation is appropriate (§11.13) --- */
  // Per-study themes verified programmatically by
  // verification/audit_m4r3_disclosure.py (106/106, committed evidence); here we
  // verify each study's Explore overview renders its own recorded
  // limitations list in the UI.
  for (const studyId of ["coringa_coastal", "chilika_wetland", "western_ghats_forest", "himalaya_purepu_2025", "himalaya_langtang_2026", "kathmandu_urban"]) {
    await app(page, `/workstation/${studyId}`);
    await page.getByRole("button", { name: "What changed?", exact: true }).click();
    await page.waitForTimeout(900);
    await page.getByRole("tab", { name: "Explore the Evidence" }).click();
    await page.waitForTimeout(400);
    const studyState = await page.evaluate(() => ({
      limitations: document.querySelectorAll(".findings-panel .insp-guardrail li").length,
      overview: (document.querySelector(".findings-panel .insp-meaning")?.textContent ?? "").includes("candidate"),
    }));
    check(
      `13. ${studyId}: Explore renders candidate framing + recorded limitations`,
      studyState.overview && studyState.limitations > 0,
      JSON.stringify(studyState),
    );
  }

  /* --- 17/18: responsive layouts, no horizontal overflow (§11.17/18) --- */
  await app(page, "/workstation/kathmandu_urban");
  await page.getByRole("button", { name: "What changed?", exact: true }).click();
  await page.waitForTimeout(800);
  await page.getByRole("tab", { name: "Explore the Evidence" }).click();
  await page.waitForTimeout(400);
  await page.locator(".finding-entry").first().click();
  await page.waitForTimeout(700);
  for (const viewport of [
    { name: "1920x1080", width: 1920, height: 1080 },
    { name: "1280x800", width: 1280, height: 800 },
    { name: "768x900", width: 768, height: 900 },
    { name: "390x844", width: 390, height: 844 },
  ]) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.waitForTimeout(500);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    check(
      `18. no horizontal overflow at ${viewport.name} (Explore + selected card)`,
      overflow <= 1,
      `overflow=${overflow}px`,
    );
    await shot(page, `m4_r3_responsive_${viewport.name}.png`);
  }

  /* --- 19: no console/page/network errors (§11.19) --- */
  check("19. no console errors", results.console_errors.length === 0, results.console_errors.slice(0, 3).join(" | "));
  check("19. no page errors", results.page_errors.length === 0, results.page_errors.slice(0, 3).join(" | "));
  check("19. no failed requests", results.failed_requests.length === 0, results.failed_requests.slice(0, 3).join(" | "));

  await browser.close();
  results.completed_utc = new Date().toISOString();
  results.passed = results.checks.filter((c) => c.passed).length;
  results.failed = results.checks.filter((c) => !c.passed).length;
  fs.writeFileSync(
    path.join(EVIDENCE, "m4_r3_browser_results.json"),
    JSON.stringify(results, null, 2)
  );
  console.log(`checks passed: ${results.passed}, failed: ${results.failed}`);
  console.log(`screenshots: ${results.screenshots.join(", ")}`);
}

main().catch((error) => {
  console.error("VERIFY_FAILED:", error.message);
  results.completed_utc = new Date().toISOString();
  results.passed = results.checks.filter((c) => c.passed).length;
  results.failed = results.checks.filter((c) => !c.passed).length;
  fs.writeFileSync(
    path.join(EVIDENCE, "m4_r3_browser_results.json"),
    JSON.stringify(results, null, 2)
  );
  process.exit(1);
});
