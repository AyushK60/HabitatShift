// Captures curated portfolio screenshots + GIF frames from a running instance.
import { chromium } from "playwright";
import fs from "node:fs";
const BASE = process.env.HS_URL ?? "http://127.0.0.1:8098/";
const OUT = "../../docs/screenshots/";
const FRAMES = "../../docs/screenshots/_frames/";
fs.mkdirSync(FRAMES, { recursive: true });
const browser = await chromium.launch();
const shot = async (page, name) => { await page.screenshot({ path: OUT + name }); console.log("saved", name); };
const d = await browser.newPage({ viewport: { width: 1440, height: 900 } });
let n = 0;
const frame = async (page) => { await page.screenshot({ path: FRAMES + String(n++).padStart(3, "0") + ".png" }); };

await d.goto(BASE + "#/", { waitUntil: "domcontentloaded" }); await d.waitForTimeout(3000);
await shot(d, "01_landing.png"); await frame(d);
await d.mouse.wheel(0, 900); await d.waitForTimeout(1200);
await shot(d, "02_study_gallery.png"); await frame(d);

for (const [id, name] of [["chilika_wetland", "03_workstation_chilika.png"], ["kathmandu_urban", "04_workstation_kathmandu.png"]]) {
  await d.goto(BASE + `#/workstation/${id}`, { waitUntil: "domcontentloaded" }); await d.waitForTimeout(4500);
  await shot(d, name); await frame(d);
  if (id === "chilika_wetland") {
    await d.evaluate(() => document.querySelector(".dock-toggle")?.click()); await d.waitForTimeout(1200);
    await shot(d, "05_pixel_probe_chart.png"); await frame(d);
  }
}
for (const [path, name] of [["#/experiments", "06_experiments.png"], ["#/methods", "07_methods.png"]]) {
  await d.goto(BASE + path, { waitUntil: "domcontentloaded" }); await d.waitForTimeout(3000);
  await shot(d, name); await frame(d);
}
const m = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
await m.goto(BASE + "#/", { waitUntil: "domcontentloaded" }); await m.waitForTimeout(3000);
await shot(m, "08_mobile_landing.png");
await browser.close();
