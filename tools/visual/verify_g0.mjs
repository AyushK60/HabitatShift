/* M2-G0 real-browser verification with Playwright/Chromium.
 *
 * The script drives the actual proof viewer served by uvicorn, checks that the
 * side-by-side and swipe layers share one geographic stage, exercises mouse,
 * touch-like pointer, click and keyboard divider control, and compares
 * screenshots pixel-for-pixel after substituting an identical raster on both
 * sides.  Evidence is written under docs/evidence/m2/.
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";
import { PNG } from "pngjs";

const BASE_URL = process.env.HABITATSHIFT_URL || "http://127.0.0.1:8095/";
const EVIDENCE = path.resolve("docs/evidence/m2");
const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 768, height: 900 },
  { width: 390, height: 844 },
];
const SPLITS = [0, 10, 25, 50, 75, 90, 100];
const results = {
  base_url: BASE_URL,
  started_utc: new Date().toISOString(),
  viewports: {},
  console_errors: [],
  page_errors: [],
  failed_requests: [],
  screenshots: [],
  checks: [],
};

fs.mkdirSync(EVIDENCE, { recursive: true });

function check(name, condition, detail = "") {
  results.checks.push({ name, passed: Boolean(condition), detail });
  if (!condition) {
    throw new Error(`${name}${detail ? `: ${detail}` : ""}`);
  }
}

function close(a, b, tolerance = 1.0) {
  return Math.abs(a - b) <= tolerance;
}

function comparePngs(bufferA, bufferB) {
  const a = PNG.sync.read(bufferA);
  const b = PNG.sync.read(bufferB);
  if (a.width !== b.width || a.height !== b.height) {
    return { same_size: false, max: 255, mean: 255, width: a.width, height: a.height };
  }
  let max = 0;
  let sum = 0;
  let count = 0;
  let over4 = 0;
  for (let index = 0; index < a.data.length; index += 4) {
    const diff = Math.max(
      Math.abs(a.data[index] - b.data[index]),
      Math.abs(a.data[index + 1] - b.data[index + 1]),
      Math.abs(a.data[index + 2] - b.data[index + 2])
    );
    max = Math.max(max, diff);
    sum += diff;
    count += 1;
    if (diff > 4) over4 += 1;
  }
  return {
    same_size: true,
    width: a.width,
    height: a.height,
    max,
    mean: count ? sum / count : 255,
    over4,
    fraction_over4: count ? over4 / count : 1,
  };
}

function aligned(diff) {
  // A handful of antialiased edge samples can differ when two panes have
  // fractional CSS widths; the test requires negligible spatial disagreement.
  if (!diff.same_size) return false;
  if (diff.max <= 4) return true;
  return diff.fraction_over4 <= 0.002 && diff.mean <= 0.5;
}

async function stageMetrics(page, selector) {
  return page.evaluate((sel) => {
    const stages = [...document.querySelectorAll(sel)];
    return stages.map((stage) => {
      const stageBox = stage.getBoundingClientRect();
      const images = [...stage.querySelectorAll("img")].map((img) => {
        const box = img.getBoundingClientRect();
        return {
          role: img.dataset.role || "",
          src: img.getAttribute("src") || "",
          width: box.width,
          height: box.height,
          left: box.left,
          top: box.top,
          naturalWidth: img.naturalWidth,
          naturalHeight: img.naturalHeight,
          complete: img.complete,
        };
      });
      return {
        width: stageBox.width,
        height: stageBox.height,
        left: stageBox.left,
        top: stageBox.top,
        aspect: stageBox.width / stageBox.height,
        images,
      };
    });
  }, selector);
}

async function waitForStage(page, selector) {
  await page.waitForSelector(selector, { state: "visible" });
  await page
    .waitForFunction(
      (sel) =>
        [...document.querySelectorAll(`${sel} img`)].every(
          (img) => img.complete && img.naturalWidth > 0
        ),
      selector,
      { timeout: 15000 }
    )
    .catch(() => {});
}

async function selectAnalysis(page, name) {
  await page.click(`#analysis-switch button[data-analysis="${name}"]`);
  await page.waitForTimeout(120);
}

async function selectMode(page, name) {
  await page.click(`#mode-switch button[data-mode="${name}"]`);
  await page.waitForTimeout(120);
}

async function selectLayer(page, id) {
  await page.click(`#layer-groups button[data-layer="${id}"]`);
  await page.waitForTimeout(100);
}

async function setSplit(page, value) {
  const stage = page.locator(".swipe-stage");
  await stage.scrollIntoViewIfNeeded();
  const box = await stage.boundingBox();
  const x = box.x + Math.min(box.width - 1, Math.max(1, (value / 100) * box.width));
  await page.mouse.click(x, box.y + box.height / 2);
  await page.waitForTimeout(60);
  return Number(await page.locator(".divider").getAttribute("aria-valuenow"));
}

async function hideDivider(page) {
  await page.evaluate(() => {
    const divider = document.querySelector(".divider");
    if (divider) divider.style.visibility = "hidden";
    document.querySelectorAll(".validity-overlay").forEach((overlay) => {
      overlay.style.visibility = "hidden";
    });
  });
}

async function showDivider(page) {
  await page.evaluate(() => {
    const divider = document.querySelector(".divider");
    if (divider) divider.style.visibility = "visible";
    document.querySelectorAll(".validity-overlay").forEach((overlay) => {
      overlay.style.visibility = "";
    });
  });
}

async function screenshot(page, name, options = {}) {
  const target = path.join(EVIDENCE, name);
  await page.screenshot({ path: target, ...options });
  results.screenshots.push(name);
  return target;
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  reducedMotion: "no-preference",
});
const page = await context.newPage();

page.on("console", (message) => {
  if (message.type() === "error") results.console_errors.push(message.text());
});
page.on("pageerror", (error) => results.page_errors.push(String(error)));
page.on("requestfailed", (request) => {
  if (!request.url().includes("/favicon.ico")) {
    results.failed_requests.push({
      url: request.url(),
      failure: request.failure()?.errorText || "unknown",
    });
  }
});

try {
  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  await page.waitForFunction(
    () =>
      document.querySelector(".brand-tag")?.textContent?.includes("M2") &&
      document.querySelectorAll("#layer-groups button").length > 0,
    null,
    { timeout: 20000 }
  );
  await waitForStage(page, ".side-grid .stage");
  check("M1 bundle loaded", true);

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport);
    await page.waitForTimeout(150);
    const label = `${viewport.width}x${viewport.height}`;
    const entry = {
      side: {},
      swipe: {},
      change: {},
      quality: {},
    };
    results.viewports[label] = entry;

    /* ---------------------------------------------------------- side --- */
    await selectAnalysis(page, "historical");
    await selectMode(page, "side");
    await waitForStage(page, ".side-grid .stage");
    let stages = await stageMetrics(page, ".side-grid .stage");
    check(`${label} side has two stages`, stages.length === 2, String(stages.length));
    check(
      `${label} side stages share width`,
      close(stages[0].width, stages[1].width, 0.75),
      `${stages[0].width} vs ${stages[1].width}`
    );
    check(
      `${label} side stages share height`,
      close(stages[0].height, stages[1].height, 0.75),
      `${stages[0].height} vs ${stages[1].height}`
    );
    entry.side.stage = {
      width: stages[0].width,
      height: stages[0].height,
      aspect: stages[0].aspect,
    };
    for (const stage of stages) {
      check(
        `${label} side image fills stage`,
        stage.images.length === 1 &&
          close(stage.images[0].width, stage.width, 0.75) &&
          close(stage.images[0].height, stage.height, 0.75),
        JSON.stringify(stage.images[0])
      );
      check(
        `${label} side raster aspect preserved`,
        close(stage.aspect, 429 / 390, 0.01),
        String(stage.aspect)
      );
      check(
        `${label} side natural raster is 429x390`,
        stage.images[0].naturalWidth === 429 && stage.images[0].naturalHeight === 390,
        `${stage.images[0].naturalWidth}x${stage.images[0].naturalHeight}`
      );
    }

    // Controlled alignment: replace the later preview with the earlier one.
    await page.evaluate(() => {
      const imgs = [...document.querySelectorAll(".side-grid .stage img[data-role='period']")];
      if (imgs.length >= 2) imgs[1].src = imgs[0].src;
    });
    await page.waitForTimeout(250);
    const stageLocators = page.locator(".side-grid .stage");
    const paneA = await stageLocators.nth(0).screenshot();
    const paneB = await stageLocators.nth(1).screenshot();
    const sideDiff = comparePngs(paneA, paneB);
    entry.side.identical_pattern_diff = sideDiff;
    check(
      `${label} side identical pattern is pixel-aligned`,
      aligned(sideDiff),
      JSON.stringify(sideDiff)
    );

    const baselineBoxes = stages.map((stage) => ({
      width: stage.width,
      height: stage.height,
    }));
    for (const layer of [
      "ndvi",
      "ndwi",
      "mndwi",
      "valid_mask",
      "observation_count",
      "true_colour",
    ]) {
      await selectLayer(page, layer);
      await waitForStage(page, ".side-grid .stage");
      const switched = await stageMetrics(page, ".side-grid .stage");
      check(
        `${label} layer ${layer} keeps stage bounds`,
        switched.length === 2 &&
          switched.every(
            (stage, index) =>
              close(stage.width, baselineBoxes[index].width, 0.75) &&
              close(stage.height, baselineBoxes[index].height, 0.75)
          ),
        JSON.stringify(switched.map((stage) => [stage.width, stage.height]))
      );
    }

    /* --------------------------------------------------------- swipe --- */
    await selectMode(page, "swipe");
    await waitForStage(page, ".swipe-stage");
    let swipeStages = await stageMetrics(page, ".swipe-stage");
    check(`${label} swipe has one stage`, swipeStages.length === 1);
    const swipeStage = swipeStages[0];
    check(
      `${label} swipe raster aspect preserved`,
      close(swipeStage.aspect, 429 / 390, 0.01),
      String(swipeStage.aspect)
    );
    const rasterRoles = swipeStage.images.map((image) => image.role);
    check(
      `${label} swipe has earlier and later layers`,
      rasterRoles.includes("earlier") && rasterRoles.includes("later"),
      JSON.stringify(rasterRoles)
    );
    for (const image of swipeStage.images.filter((item) => item.role !== "validity-overlay")) {
      check(
        `${label} swipe ${image.role} fills shared stage`,
        close(image.width, swipeStage.width, 0.75) &&
          close(image.height, swipeStage.height, 0.75),
        JSON.stringify(image)
      );
    }

    // Controlled alignment: both layers use one identical georeferenced pattern.
    await page.evaluate(() => {
      const earlier = document.querySelector(".swipe-stage img[data-role='earlier']");
      const later = document.querySelector(".swipe-stage img[data-role='later']");
      if (earlier && later) later.src = earlier.src;
    });
    await page.waitForTimeout(250);
    await hideDivider(page);
    const reference = await page.locator(".swipe-stage").screenshot();
    const splitResults = {};
    for (const split of SPLITS) {
      const actual = await setSplit(page, split);
      check(
        `${label} swipe click reaches ${split}%`,
        Math.abs(actual - split) <= 1,
        `aria-valuenow=${actual}`
      );
      const shot = await page.locator(".swipe-stage").screenshot();
      const diff = comparePngs(reference, shot);
      splitResults[split] = { aria: actual, diff };
      check(
        `${label} swipe ${split}% remains pixel-aligned`,
        aligned(diff),
        JSON.stringify(diff)
      );
      if (viewport.width === 1440) {
        await showDivider(page);
        await page.locator(".swipe-frame").screenshot({
          path: path.join(EVIDENCE, `g0_swipe_split_${String(split).padStart(3, "0")}.png`),
        });
        results.screenshots.push(`g0_swipe_split_${String(split).padStart(3, "0")}.png`);
        await hideDivider(page);
      }
    }
    entry.swipe.splits = splitResults;

    await showDivider(page);
    const divider = page.locator(".divider");
    const stageBox = await page.locator(".swipe-stage").boundingBox();
    const dividerBox = await divider.boundingBox();
    check(
      `${label} divider sits on the clip boundary at 100%`,
      close(dividerBox.x, stageBox.x + stageBox.width, 2.0),
      `${dividerBox.x} vs ${stageBox.x + stageBox.width}`
    );

    await divider.focus();
    await page.keyboard.press("Home");
    check(
      `${label} keyboard Home sets 0%`,
      Number(await divider.getAttribute("aria-valuenow")) === 0
    );
    await page.keyboard.press("End");
    check(
      `${label} keyboard End sets 100%`,
      Number(await divider.getAttribute("aria-valuenow")) === 100
    );
    await page.keyboard.press("ArrowLeft");
    check(
      `${label} keyboard ArrowLeft steps 1%`,
      Number(await divider.getAttribute("aria-valuenow")) === 99
    );
    await page.keyboard.press("Shift+ArrowLeft");
    check(
      `${label} keyboard Shift+ArrowLeft steps 10%`,
      Number(await divider.getAttribute("aria-valuenow")) === 89
    );

    await page.mouse.click(
      stageBox.x + stageBox.width * 0.25,
      stageBox.y + stageBox.height / 2
    );
    check(
      `${label} click positions divider near 25%`,
      Math.abs(Number(await divider.getAttribute("aria-valuenow")) - 25) <= 1
    );

    await page.mouse.move(
      stageBox.x + stageBox.width * 0.5,
      stageBox.y + stageBox.height / 2
    );
    await page.mouse.down();
    await page.mouse.move(
      stageBox.x + stageBox.width * 0.75,
      stageBox.y + stageBox.height / 2,
      { steps: 5 }
    );
    await page.mouse.up();
    check(
      `${label} pointer drag releases at 75%`,
      Math.abs(Number(await divider.getAttribute("aria-valuenow")) - 75) <= 1
    );

    await page.click(".reset-split");
    check(
      `${label} reset restores 50%`,
      Number(await divider.getAttribute("aria-valuenow")) === 50
    );

    await page.click("#overlay-toggle");
    const overlayVisible = await page.evaluate(() => {
      const overlays = [...document.querySelectorAll(".swipe-stage .validity-overlay")];
      return overlays.length === 2 &&
        overlays.every((overlay) => getComputedStyle(overlay).opacity === "1");
    });
    check(`${label} validity overlay toggles on`, overlayVisible);
    await page.click("#overlay-toggle");

    entry.swipe.stage = {
      width: swipeStage.width,
      height: swipeStage.height,
      aspect: swipeStage.aspect,
    };

    /* -------------------------------------------------------- change --- */
    await selectAnalysis(page, "change");
    await page.waitForSelector(".change-layout");
    await waitForStage(page, ".change-stage");
    const changeStages = await stageMetrics(page, ".change-stage");
    check(`${label} change mode shows one derived map`, changeStages.length === 1);
    check(
      `${label} change stage preserves raster aspect`,
      close(changeStages[0].aspect, 429 / 390, 0.01),
      String(changeStages[0].aspect)
    );
    const callout = await page.locator(".coverage-callout").first().innerText();
    check(`${label} change coverage reports 100%`, callout.includes("100.0%"), callout);
    const thresholdRows = await page.locator(".threshold-table tbody tr").count();
    check(`${label} threshold table has measured rows`, thresholdRows >= 3, String(thresholdRows));
    check(
      `${label} change legend visible`,
      await page.locator("#legend-row").isVisible()
    );
    check(
      `${label} change hides the temporal view switch`,
      !(await page.locator("#view-group").isVisible())
    );
    check(
      `${label} change keeps the validity-overlay control`,
      await page.locator("#overlay-toggle").isVisible()
    );
    entry.change.stage = {
      width: changeStages[0].width,
      height: changeStages[0].height,
      aspect: changeStages[0].aspect,
    };

    for (const layer of ["delta_ndwi", "delta_mndwi", "delta_ndvi"]) {
      await selectLayer(page, layer);
      await waitForStage(page, ".change-stage");
      const switched = await stageMetrics(page, ".change-stage");
      check(
        `${label} change layer ${layer} keeps stage bounds`,
        switched.length === 1 &&
          close(switched[0].width, changeStages[0].width, 0.75) &&
          close(switched[0].height, changeStages[0].height, 0.75)
      );
    }

    /* ------------------------------------------------------- quality --- */
    await selectAnalysis(page, "quality");
    await page.waitForSelector(".quality-layout");
    await waitForStage(page, ".quality-stage");
    const qualityStages = await stageMetrics(page, ".quality-stage");
    check(`${label} quality mode shows one inspection stage`, qualityStages.length === 1);
    const coverageValues = await page
      .locator(".coverage-value")
      .allInnerTexts();
    check(
      `${label} quality coverage cards report 100%`,
      coverageValues.length === 3 && coverageValues.every((value) => value === "100.0%"),
      JSON.stringify(coverageValues)
    );
    const explanation = await page.locator(".quality-rail").innerText();
    check(
      `${label} quality explanation states uniform coverage is expected`,
      /uniform|expected/i.test(explanation),
      explanation.slice(0, 200)
    );
    check(
      `${label} quality hides the temporal view switch`,
      !(await page.locator("#view-group").isVisible())
    );
    check(
      `${label} quality hides the overlay toggle`,
      !(await page.locator("#overlay-toggle").isVisible())
    );
    entry.quality.stage = {
      width: qualityStages[0].width,
      height: qualityStages[0].height,
      aspect: qualityStages[0].aspect,
    };

    for (const layer of ["qc_valid_earlier", "qc_valid_common", "qc_masked", "qc_count_later"]) {
      await selectLayer(page, layer);
      await waitForStage(page, ".quality-stage");
      const switched = await stageMetrics(page, ".quality-stage");
      check(
        `${label} quality layer ${layer} keeps stage bounds`,
        switched.length === 1 &&
          close(switched[0].width, qualityStages[0].width, 0.75) &&
          close(switched[0].height, qualityStages[0].height, 0.75)
      );
    }

    if (viewport.width === 1440 || viewport.width === 390) {
      await selectAnalysis(page, "historical");
      await selectMode(page, "side");
      await screenshot(page, `g0_side_${viewport.width}.png`, { fullPage: true });
      await selectLayer(page, "valid_mask");
      await screenshot(page, `g0_valid_mask_side_${viewport.width}.png`, {
        fullPage: true,
      });
      await selectMode(page, "swipe");
      await page.click(".reset-split");
      await screenshot(page, `g0_swipe_${viewport.width}_50.png`, { fullPage: true });
      await selectAnalysis(page, "change");
      await screenshot(page, `g0_change_${viewport.width}.png`, { fullPage: true });
      await page.click("#overlay-toggle");
      await screenshot(page, `g0_change_overlay_${viewport.width}.png`, {
        fullPage: true,
      });
      await page.click("#overlay-toggle");
      await selectAnalysis(page, "quality");
      await screenshot(page, `g0_quality_${viewport.width}.png`, { fullPage: true });
      await selectLayer(page, "qc_valid_common");
      await screenshot(page, `g0_quality_common_${viewport.width}.png`, {
        fullPage: true,
      });
      await selectLayer(page, "qc_masked");
      await screenshot(page, `g0_quality_masked_${viewport.width}.png`, {
        fullPage: true,
      });
    }
  }

  /* -------------------------------------------- resize stability --- */
  await page.setViewportSize({ width: 1440, height: 900 });
  await selectAnalysis(page, "historical");
  await selectMode(page, "swipe");
  const before = await setSplit(page, 37);
  await page.setViewportSize({ width: 768, height: 900 });
  await page.waitForTimeout(180);
  const afterResize = Number(
    await page.locator(".divider").getAttribute("aria-valuenow")
  );
  const resizedStages = await stageMetrics(page, ".swipe-stage");
  check(
    "resize preserves divider percentage",
    Math.abs(before - afterResize) <= 1,
    `${before} -> ${afterResize}`
  );
  check(
    "resize preserves raster aspect",
    close(resizedStages[0].aspect, 429 / 390, 0.01),
    String(resizedStages[0].aspect)
  );
  const resizedImages = resizedStages[0].images.filter(
    (image) => image.role !== "validity-overlay"
  );
  check(
    "resize keeps both swipe layers on identical bounds",
    resizedImages.length === 2 &&
      close(resizedImages[0].width, resizedImages[1].width, 0.75) &&
      close(resizedImages[0].height, resizedImages[1].height, 0.75)
  );

  /* ------------------------------------------- reduced motion support --- */
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.click("#overlay-toggle");
  const transition = await page.evaluate(() => {
    const overlay = document.querySelector(".validity-overlay");
    return overlay ? getComputedStyle(overlay).transitionDuration : "missing";
  });
  check(
    "reduced motion disables overlay transition",
    transition === "0s" || transition === "missing",
    transition
  );

  check("no browser console errors", results.console_errors.length === 0, JSON.stringify(results.console_errors));
  check("no uncaught page errors", results.page_errors.length === 0, JSON.stringify(results.page_errors));
  check(
    "no failed network requests",
    results.failed_requests.length === 0,
    JSON.stringify(results.failed_requests)
  );
} catch (error) {
  results.failure = String(error);
  console.error("BROWSER VERIFICATION FAILED:", error);
  process.exitCode = 1;
} finally {
  results.finished_utc = new Date().toISOString();
  results.checks_total = results.checks.length;
  results.checks_passed = results.checks.filter((item) => item.passed).length;
  fs.writeFileSync(
    path.join(EVIDENCE, "g0_browser_results.json"),
    JSON.stringify(results, null, 2)
  );
  await browser.close();
  console.log(
    `G0 browser checks: ${results.checks_passed}/${results.checks_total} passed, ${results.screenshots.length} screenshots`
  );
  if (results.failure) console.log(`Failure: ${results.failure}`);
}
