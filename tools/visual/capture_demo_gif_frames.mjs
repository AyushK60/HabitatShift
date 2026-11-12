// Records frames of a short demo interaction (landing -> swipe -> change -> probe chart).
import { chromium } from "playwright";
import fs from "node:fs";
const BASE = process.env.HS_URL ?? "http://127.0.0.1:8098/";
const DIR = process.env.FRAMES_DIR;
fs.mkdirSync(DIR, { recursive: true });
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 760 } });
let n = 0;
const f = async (hold = 1) => { for (let i = 0; i < hold; i++) await p.screenshot({ path: `${DIR}/${String(n++).padStart(3, "0")}.png` }); };
await p.goto(BASE + "#/", { waitUntil: "domcontentloaded" }); await p.waitForTimeout(3000); await f(4);
await p.goto(BASE + "#/workstation/chilika_wetland", { waitUntil: "domcontentloaded" }); await p.waitForTimeout(4500); await f(3);
const h = p.locator(".maplibregl-compare-swiper, .swipe-handle, [class*=swipe] [class*=handle]").first();
let box = null; try { box = await h.boundingBox({ timeout: 1500 }); } catch {}
const y = 520;
const x0 = box ? box.x + box.width / 2 : 506, y0 = box ? box.y + box.height / 2 : 578;
await p.mouse.move(x0, y0); await p.mouse.down();
for (const x of [440, 380, 320, 400, 520, 620, 700, 600, 500]) { await p.mouse.move(x, y0, { steps: 4 }); await f(1); }
await p.mouse.up();
await p.getByRole("button", { name: "Change", exact: true }).click(); await p.waitForTimeout(2500); await f(4);
await p.getByRole("button", { name: "Quality", exact: true }).click(); await p.waitForTimeout(2000); await f(3);
await p.getByRole("button", { name: "Historical", exact: true }).click(); await p.waitForTimeout(1500);
await p.evaluate(() => document.querySelector(".dock-toggle")?.click()); await p.waitForTimeout(1200); await f(4);
await p.goto(BASE + "#/experiments", { waitUntil: "domcontentloaded" }); await p.waitForTimeout(2500); await f(4);
await b.close(); console.log("frames", n);
