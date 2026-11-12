import { chromium } from "playwright";
import fs from "node:fs";
const dir = "../../docs/figures/";
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 860, height: 600 }, deviceScaleFactor: 2 });
for (const f of fs.readdirSync(dir).filter((n) => n.endsWith(".svg"))) {
  await p.setContent(`<body style="margin:0">${fs.readFileSync(dir + f, "utf8")}</body>`);
  const el = await p.locator("svg"); await el.screenshot({ path: dir + f.replace(".svg", ".png") });
}
await b.close();
