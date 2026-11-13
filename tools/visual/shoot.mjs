/* Capture full-page screenshots of the running dev server for design review.
 *   node tools/visual/shoot.mjs <outDir> [width] [height] route1 route2 ...
 */
import { chromium } from "playwright";
import fs from "node:fs";

const [outDir, w = "1440", h = "900", ...routes] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
for (const route of routes.length ? routes : ["/"]) {
  await page.goto(`http://localhost:5173/#${route === "home" ? "/" : route}`);
  await page.waitForTimeout(2500);
  const name = route.replace(/[^a-z0-9]+/gi, "_") || "home";
  await page.screenshot({ path: `${outDir}/${name}_top.png` });
  await page.screenshot({ path: `${outDir}/${name}_full.png`, fullPage: true });
  console.log("shot", route);
}
await browser.close();
