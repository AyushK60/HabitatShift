/** System: what the pipeline behind the site has actually done. Counts are read from system.json, which
 *  scripts/export_system_showcase.py builds from files on disk. */
import { useEffect, useRef, useState } from "react";
import "../styles/system.css";

interface Bundle {
  counts: Record<string, number | null>;
  size: { training_tiles_gb: number; foundation_weights_gb: number };
  code: { python_lines: number; frontend_lines: number; doc_pages: number };
}

function useCountUp(target: number, run: boolean, ms = 1100) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!run) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setValue(target); return; }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / ms);
      setValue(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, run, ms]);
  return value;
}

function Stat({ value, label, note, run }: { value: number; label: string; note: string; run: boolean }) {
  const shown = useCountUp(value, run);
  return (
    <div className="stat">
      <p className="stat-n">{shown.toLocaleString("en-GB")}</p>
      <p className="stat-l">{label}</p>
      <p className="stat-note">{note}</p>
    </div>
  );
}

const STAGES = [
  { name: "Find", text: "Search the public catalogues for every scene over a place and time, with cloud and snow limits." },
  { name: "Clean", text: "Mask cloud, shadow, snow and radar layover so only usable ground is compared." },
  { name: "Compose", text: "Combine several scenes per period into one median picture and record exactly which scenes." },
  { name: "Test", text: "Measure scene-to-scene noise and keep only changes that are bigger than it." },
  { name: "Check", text: "Compare against independent references: forest-loss maps, radar water frequency, outlines." },
  { name: "Publish", text: "Write portable bundles with checksums, so the site runs with no server." },
];

const SOURCES = [
  ["Sentinel-2 L2A optical", "Earth Search STAC (AWS Open Data)", "10 to 20 m, cloud-masked"],
  ["Sentinel-1 radar (RTC)", "Microsoft Planetary Computer", "10 m, sees through cloud"],
  ["Copernicus GLO-30 elevation", "Microsoft Planetary Computer", "30 m, slope and layover"],
  ["Hi-MAG glacial lakes", "Zenodo 4275164 (CC-BY 4.0)", "Annual outlines 2008 to 2017"],
  ["Hansen Global Forest Change", "University of Maryland (CC-BY 4.0)", "Forest-loss reference"],
  ["Prithvi-EO-2.0 and SSL4EO", "NASA/IBM and SSL4EO-S12", "Foundation-model embeddings"],
];

export function SystemPage() {
  const [data, setData] = useState<Bundle | null>(null);
  const [run, setRun] = useState(false);
  const row = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("./system/system.json").then((r) => (r.ok ? r.json() : null)).then(setData).catch(() => setData(null));
  }, []);
  useEffect(() => {
    const el = row.current;
    if (!el || !data) return;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setRun(true), { threshold: 0.3 });
    io.observe(el);
    return () => io.disconnect();
  }, [data]);

  const c = data?.counts;
  return (
    <main id="main" className="page system">
      <header className="page-head">
        <h1>What the system has done</h1>
        <p className="page-lede">
          Behind every graph is a pipeline that searched catalogues, cleaned scenes, trained models and checked its own work.
          These numbers are counted from the files it produced, not estimated.
        </p>
      </header>

      {c && (
        <div className="stats" ref={row} data-tour="system-stats">
          <Stat run={run} value={c.lakes ?? 0} label="Glacial lakes" note="Nepal, 0.3 to 6 km², picked by a fixed rule" />
          <Stat run={run} value={c.radar_scenes ?? 0} label="Radar scenes in time series" note="Sentinel-1, 2017 to 2026, three pilot lakes" />
          <Stat run={run} value={c.optical_scenes ?? 0} label="Optical scenes in time series" note="Sentinel-2, cloud and ice screened" />
          <Stat run={run} value={c.training_pairs ?? 0} label="Radar and optical pairs" note={`kept from ${(c.pairs_examined ?? 0).toLocaleString("en-GB")} candidates, ${data?.size.training_tiles_gb} GB`} />
          <Stat run={run} value={c.study_areas ?? 0} label="Study areas" note="Coastal, wetland, forest, urban, glacial" />
          <Stat run={run} value={c.tests ?? 0} label="Automated tests" note="Every change to the code re-checks them" />
        </div>
      )}

      <section className="sys-block" aria-labelledby="pipe-h">
        <h2 id="pipe-h">One pipeline, six steps</h2>
        <ol className="pipeline">
          {STAGES.map((s, i) => (
            <li key={s.name} style={{ ["--i" as string]: i }}>
              <h3>{s.name}</h3>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="sys-block two" aria-labelledby="src-h">
        <div>
          <h2 id="src-h">Open data in</h2>
          <table className="sys-table">
            <tbody>
              {SOURCES.map(([a, b, d]) => (
                <tr key={a}><th scope="row">{a}</th><td>{b}<small>{d}</small></td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h2>Models trained and tested</h2>
          <ul className="sys-list">
            <li><b>Prithvi-EO-2.0 (300 M weights)</b> and an SSL4EO ResNet-50 compared against spectral indices on the same noise test.</li>
            <li><b>Radar U-Net (1.9 M weights)</b> trained on radar and optical pairs, with {c?.unet_fold_models ?? 5} lake-held-out models for the cross-validated check.</li>
            <li><b>Conformal intervals</b> that give each lake area a range, tested on lakes the model never saw.</li>
          </ul>
        </div>
      </section>

      <section className="sys-block" aria-labelledby="repro-h">
        <h2 id="repro-h">Built to be re-run</h2>
        <div className="repro">
          <p><b>{data ? data.code.python_lines.toLocaleString("en-GB") : "…"}</b><span>lines of Python for the pipeline and models</span></p>
          <p><b>{data ? data.code.frontend_lines.toLocaleString("en-GB") : "…"}</b><span>lines of interface code</span></p>
          <p><b>{data?.code.doc_pages ?? "…"}</b><span>pages of method and results notes</span></p>
          <p><b>SHA-256</b><span>checksums on model weights and study bundles</span></p>
        </div>
      </section>
    </main>
  );
}
