/* Render docs/paper/v3/paper.html to a PDF preview, typesetting the maths with KaTeX.
 *   node tools/visual/render_paper_v3.mjs
 */
import { chromium } from "playwright";
import katex from "katex";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const dir = path.resolve("../../docs/paper/v3");
let html = fs.readFileSync(path.join(dir, "paper.html"), "utf8");
const decode = (s) => s.replace(/&quot;/g, '"').replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#x27;/g, "'");
html = html.replace(/<span class="(math-[id])" data-tex="([^"]*)"><\/span>/g, (_, cls, tex) =>
  katex.renderToString(decode(tex), { displayMode: cls === "math-d", throwOnError: false }));
const css = fs.readFileSync(path.resolve("node_modules/katex/dist/katex.min.css"), "utf8")
  .replace(/url\(fonts\//g, `url(${pathToFileURL(path.resolve("node_modules/katex/dist/fonts")).href}/`);
html = html.replace("</head>", `<style>${css}</style></head>`);
const out = path.join(dir, "paper_preview.html");
fs.writeFileSync(out, html);
const b = await chromium.launch();
const p = await b.newPage();
await p.goto(pathToFileURL(out).href, { waitUntil: "load" });
await p.pdf({ path: path.join(dir, "HabitatShift_V3_paper_preview.pdf"), format: "A4", printBackground: true, margin: { top: "20mm", bottom: "20mm", left: "18mm", right: "18mm" } });
await b.close();
if (process.env.PAPER_PNG) { const b2 = await chromium.launch(); const p2 = await b2.newPage({ viewport: { width: 820, height: 1160 } }); await p2.goto(pathToFileURL(out).href); await p2.screenshot({ path: process.env.PAPER_PNG, fullPage: true }); await b2.close(); }
fs.unlinkSync(out);
console.log("pdf written");
