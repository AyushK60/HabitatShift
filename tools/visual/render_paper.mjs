import { chromium } from "playwright";
import path from "node:path";
import { pathToFileURL } from "node:url";
const src = path.resolve("../../docs/paper/habitatshift_report.html");
const b = await chromium.launch(); const p = await b.newPage();
await p.goto(pathToFileURL(src).href, { waitUntil: "load" });
await p.pdf({ path: path.resolve("../../docs/paper/HabitatShift_Technical_Report.pdf"), format: "A4", printBackground: true, margin: { top: "20mm", bottom: "20mm", left: "18mm", right: "18mm" } });
await b.close(); console.log("pdf written");
