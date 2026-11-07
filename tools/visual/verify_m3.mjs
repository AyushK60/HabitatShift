/* M3 real-browser verification with Playwright/Chromium.
 *
 * Drives the actual M3 product served by uvicorn (frontend/dist) and covers
 * the 14 acceptance checks of the M3 brief §14: landing navigation, study
 * selection, before/after synchronisation, hover-follow swipe without
 * clicking, touch swipe, keyboard divider, reset, layer changes, validity and
 * observation-count views, pixel inspection, experiment chart visibility,
 * threshold/index switching, responsive layouts and provenance/export
 * functionality.  Screenshots are written under docs/evidence/m3/.
 *
 * Usage:
 *   HABITATSHIFT_URL=http://127.0.0.1:8098/ node tools/visual/verify_m3.mjs
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const BASE_URL = process.env.HABITATSHIFT_URL || "http://127.0.0.1:8098/";
const EVIDENCE = path.resolve("docs/evidence/m3");
const VIEWPORTS = [
  { name: "1920x1080", width: 1920, height: 1080 },
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1280x800", width: 1280, height: 800 },
  { name: "768", width: 768, height: 900 },
  { name: "390", width: 390, height: 844 },
];

const results = {
  base_url: BASE_URL,
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

async function gotoHash(page, hash) {
  await page.goto(`${BASE_URL}#${hash}`, { waitUntil: "domcontentloaded" });
  await page.evaluate(() => {
    if (!location.hash.includes(window.__m3Buster ?? "")) {
      /* cache-buster already part of base url */
    }
  });
  await page.waitForTimeout(1600);
}

function readout(text) {
  const match = text.match(/(\d+)% earlier \/ (\d+)% later/);
  return match ? { earlier: Number(match[1]), later: Number(match[2]) } : null;
}

async function run() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    hasTouch: true,
  });
  const page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error") results.console_errors.push(message.text());
  });
  page.on("pageerror", (error) => results.page_errors.push(String(error)));
  page.on("requestfailed", (request) =>
    results.failed_requests.push(`${request.url()} ${request.failure()?.errorText ?? ""}`)
  );

  const busted = `${BASE_URL}?v=${Date.now()}/`;
  const app = async (hash) => {
    await page.goto(`${busted}#${hash}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
  };

  /* 1 — landing navigation ------------------------------------------------ */
  await app("/");
  await page.locator(".hero-copy h1").waitFor({ state: "visible", timeout: 8000 });
  check("1. landing renders hero headline", await page.getByText("Read the landscape.").first().isVisible());
  await page.getByRole("link", { name: "Explore the Atlas" }).click();
  await page.waitForTimeout(1200);
  check("1. hero CTA navigates to workstation", page.url().includes("workstation"));
  await shot(page, "m3_workstation_1440_default");

  /* 2 — study selection via gallery --------------------------------------- */
  await app("/");
  await page.locator(".study-card--lead").waitFor({ state: "visible", timeout: 8000 });
  check(
    "2. gallery shows honest statuses",
    (await page.locator(".status-feasibility").count()) >= 1 &&
      (await page.locator(".status-provisional").count()) >= 1
  );
  await shot(page, "m3_landing_1440_gallery");
  await page.locator(".study-card--lead").getByRole("link", { name: "Open the investigation" }).click();
  await page.waitForTimeout(1200);
  check("2. study card opens the investigation", page.url().includes("workstation"));

  /* 3 — side-by-side synchronisation --------------------------------------- */
  await app("/workstation");
  await page.getByRole("button", { name: "Side by side" }).click();
  await page.waitForTimeout(800);
  const zoomIn = page.locator(".map-earlier .maplibregl-ctrl-zoom-in");
  await zoomIn.click();
  await page.waitForTimeout(300);
  await zoomIn.click();
  await page.waitForTimeout(700);
  const zooms = await page.evaluate(() => ({
    earlier: window.__hsMaps.earlier.getZoom(),
    later: window.__hsMaps.later.getZoom(),
    centerDelta: Math.abs(
      window.__hsMaps.earlier.getCenter().lng - window.__hsMaps.later.getCenter().lng
    ) + Math.abs(
      window.__hsMaps.earlier.getCenter().lat - window.__hsMaps.later.getCenter().lat
    ),
  }));
  check(
    "3. side-by-side maps stay synchronised",
    Math.abs(zooms.earlier - zooms.later) < 1e-6 && zooms.centerDelta < 1e-9,
    JSON.stringify(zooms)
  );

  /* 4 — hover-follow swipe without click ----------------------------------- */
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
  check(
    "4. divider follows mouse hover with no click",
    splitA < 30 && splitB > 65,
    `splits ${splitA.toFixed(1)} → ${splitB.toFixed(1)}`
  );
  // no reset on exit
  await page.mouse.move(stage.x + stage.width * 0.75, stage.y - 40, { steps: 2 });
  await page.waitForTimeout(300);
  const splitAfterExit = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  check(
    "4. divider position survives cursor exit",
    Math.abs(splitAfterExit - splitB) < 1.5,
    `exit split ${splitAfterExit.toFixed(1)}`
  );
  await shot(page, "m3_workstation_1440_swipe_hover");

  /* 5 — touch swipe --------------------------------------------------------- */
  await page.touchscreen.tap(stage.x + stage.width * 0.3, cy);
  await page.waitForTimeout(300);
  const touchSplit = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  check(
    "5. touch tap places the divider",
    Math.abs(touchSplit - 30) < 6,
    `split ${touchSplit.toFixed(1)}`
  );
  // Synthetic touch-pointer drag: press at 20%, move to 70%, release.
  await page.evaluate(({ sx, sy, ex, ey }) => {
    const stage = document.querySelector(".map-stage");
    const fire = (type, x, y) =>
      stage.dispatchEvent(
        new PointerEvent(type, {
          pointerType: "touch",
          pointerId: 7,
          isPrimary: true,
          clientX: x,
          clientY: y,
          buttons: type === "pointerup" ? 0 : 1,
          bubbles: true,
          cancelable: true,
        })
      );
    fire("pointerdown", sx, sy);
    fire("pointermove", sx + (ex - sx) * 0.5, sy + (ey - sy) * 0.5);
    fire("pointermove", ex, ey);
    fire("pointerup", ex, ey);
  }, {
    sx: stage.x + stage.width * 0.2, sy: cy,
    ex: stage.x + stage.width * 0.7, ey: cy,
  });
  await page.waitForTimeout(300);
  const dragSplit = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  check(
    "5. touch drag moves the divider",
    Math.abs(dragSplit - 70) < 6,
    `split ${dragSplit.toFixed(1)}`
  );
  const kbBase = dragSplit;

  /* 6 — keyboard divider ----------------------------------------------------- */
  await page.locator(".map-swipe-divider").focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(200);
  const kbSplit1 = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  await page.keyboard.press("Shift+ArrowRight");
  await page.waitForTimeout(200);
  const kbSplit2 = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  await page.keyboard.press("Home");
  await page.waitForTimeout(200);
  const kbHome = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  await page.keyboard.press("End");
  await page.waitForTimeout(200);
  const kbEnd = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  check(
    "6. keyboard arrows, Shift, Home and End control the divider",
    Math.abs(kbSplit1 - (kbBase + 2)) < 1.5 &&
      Math.abs(kbSplit2 - (kbSplit1 + 10)) < 1.5 &&
      kbHome === 0 &&
      Math.abs(kbEnd - 100) < 1.5,
    `${kbSplit1} ${kbSplit2} ${kbHome} ${kbEnd}`
  );
  const sliderAttrs = await page.locator(".map-swipe-divider").evaluate((el) => ({
    role: el.getAttribute("role"),
    min: el.getAttribute("aria-valuemin"),
    max: el.getAttribute("aria-valuemax"),
    now: el.getAttribute("aria-valuenow"),
  }));
  check(
    "6. divider exposes slider semantics",
    sliderAttrs.role === "slider" && sliderAttrs.min === "0" && sliderAttrs.max === "100" &&
      sliderAttrs.now !== null
  );

  /* 7 — reset ---------------------------------------------------------------- */
  await page.getByRole("button", { name: "Reset 50%" }).click();
  await page.waitForTimeout(300);
  const resetSplit = await page.evaluate(() =>
    parseFloat(document.querySelector(".map-stage").style.getPropertyValue("--split"))
  );
  check("7. reset returns the divider to 50%", Math.abs(resetSplit - 50) < 1.5, `${resetSplit}`);

  /* 8 — layer changes ---------------------------------------------------------- */
  for (const name of ["NDVI", "False colour", "MNDWI"]) {
    await page.getByRole("button", { name, exact: true }).first().click();
    await page.waitForTimeout(600);
  }
  const layerSources = await page.evaluate(() => ({
    earlier: window.__hsMaps.earlier.getSource("layer-earlier")?.url,
    later: window.__hsMaps.later.getSource("layer-later")?.url,
  }));
  check(
    "8. layer switch updates both map sources",
    layerSources.earlier?.includes("mndwi") && layerSources.later?.includes("mndwi"),
    JSON.stringify(layerSources)
  );
  await shot(page, "m3_workstation_1440_mndwi_swipe");

  /* 9 — validity and observation-count views ----------------------------------- */
  await page.getByRole("button", { name: "Quality", exact: true }).click();
  await page.waitForTimeout(600);
  // The earlier touch tap opened a pixel probe, which auto-switched the
  // inspector tab; return to the legend tab as a user would.
  await page.getByRole("tab", { name: "Layer & legend" }).click();
  await page.waitForTimeout(300);
  await page.getByRole("button", { name: "Shared valid", exact: true }).click();
  await page.waitForTimeout(600);
  let byteIdentical = true;
  try {
    await page.getByText("byte-identical masks", { exact: false }).first().waitFor({ timeout: 5000 });
  } catch {
    byteIdentical = false;
  }
  check("9. shared-valid explains byte-identical masks", byteIdentical);
  check(
    "9. coverage accounting shows grid vs AOI",
    (await page.getByText("165,136", { exact: false }).count()) >= 1 &&
      (await page.getByText("167,310", { exact: false }).count()) >= 1
  );
  await shot(page, "m3_workstation_1440_quality_shared_valid");
  await page.getByRole("button", { name: "Obs. count · earlier", exact: true }).click();
  await page.waitForTimeout(600);
  let obsLegend = true;
  try {
    await page.getByText("copper intensity encodes count").first().waitFor({ timeout: 5000 });
  } catch {
    obsLegend = false;
  }
  check("9. observation-count layer shows its legend note", obsLegend);
  await shot(page, "m3_workstation_1440_quality_obs_count");

  /* 10 — pixel inspection -------------------------------------------------------- */
  await page.getByRole("button", { name: "Historical", exact: true }).click();
  await page.waitForTimeout(700);
  const stage2 = await page.locator(".map-stage").boundingBox();
  await page.mouse.click(stage2.x + stage2.width * 0.45, stage2.y + stage2.height * 0.4);
  await page.waitForTimeout(1400);
  const probeText = await page.locator(".pixel-probe").textContent().catch(() => null);
  check(
    "10. pixel probe returns measured reflectance + indices",
    probeText !== null && probeText.includes("B08 NIR") && probeText.includes("NDVI"),
    probeText?.slice(0, 120)
  );
  await shot(page, "m3_workstation_1440_pixel_probe");

  /* 11 — experiment charts --------------------------------------------------------- */
  await app("/experiments");
  const chartCount = await page.locator(".exp-figure img").count();
  check("11. experiments page shows recorded charts", chartCount >= 3, `charts ${chartCount}`);
  check(
    "11. uncertainty is not described as a population CI",
    await page.getByText("not a population", { exact: false }).first().isVisible()
  );
  await shot(page, "m3_experiments_1440_top");

  /* 12 — threshold and index switching ------------------------------------------------ */
  await page.getByRole("button", { name: "NDWI", exact: true }).first().click();
  await page.waitForTimeout(400);
  await page.getByRole("button", { name: "0.25", exact: true }).click();
  await page.waitForTimeout(400);
  const thresholdRow = await page
    .locator(".exp-side", { hasText: "Measured areas" })
    .textContent();
  check(
    "12. threshold switch updates measured areas",
    thresholdRow.includes("0.25") && thresholdRow.includes("Candidate decrease"),
    thresholdRow?.slice(0, 100)
  );
  await page.locator(".exp-block", { hasText: "Method comparison" }).getByRole("button", { name: "MNDWI", exact: true }).click();
  await page.waitForTimeout(500);
  await shot(page, "m3_experiments_1440_threshold");

  /* 13 — responsive layouts ------------------------------------------------------------ */
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await app("/");
    const landingOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    await shot(page, `m3_landing_${viewport.name}`);
    await app("/workstation");
    await page.waitForTimeout(1200);
    const wsOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    const wsViewportHeightOk =
      viewport.width > 1020
        ? await page.evaluate(() => {
            const stage = document.querySelector(".map-stage");
            if (!stage) return false;
            const r = stage.getBoundingClientRect();
            return r.height > 200 && r.bottom <= window.innerHeight + 1;
          })
        : true;
    await shot(page, `m3_workstation_${viewport.name}`);
    check(
      `13. no horizontal overflow at ${viewport.name}`,
      landingOverflow <= 0 && wsOverflow <= 0,
      `landing ${landingOverflow}px, workstation ${wsOverflow}px`
    );
    if (viewport.width > 1020) {
      check(
        `13. workstation comparison fits viewport height at ${viewport.name}`,
        wsViewportHeightOk
      );
    }
  }

  /* 14 — provenance/export --------------------------------------------------------------- */
  await page.setViewportSize({ width: 1440, height: 900 });
  await app("/methods");
  check(
    "14. methods page exposes manifest export",
    await page.getByRole("link", { name: /M1 run manifest/ }).isVisible()
  );
  const manifestResponse = await page.request.get(`${BASE_URL}api/m1/study/coringa_coastal/manifest`);
  check("14. manifest endpoint serves JSON", manifestResponse.ok());
  const manifestJson = await manifestResponse.json().catch(() => null);
  check(
    "14. manifest carries scene IDs and grid",
    Boolean(manifestJson?.search?.items?.length || manifestJson?.periods?.length) &&
      Boolean(manifestJson?.grid)
  );
  const experimentsResponse = await page.request.get(`${BASE_URL}api/experiments/coringa_m2/latest`);
  check("14. experiments endpoint serves recorded run", experimentsResponse.ok());
  await shot(page, "m3_methods_1440");

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
    path.join(EVIDENCE, "m3_browser_results.json"),
    JSON.stringify(results, null, 2)
  );
  console.log(`\n${results.passed} passed, ${results.failed} failed`);
  process.exit(results.failed ? 1 : 0);
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
