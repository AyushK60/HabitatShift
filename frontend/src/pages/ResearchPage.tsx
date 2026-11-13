/** Research: the version 3 question and its three results, with every number read from the recorded outputs
 *  (frontend/public/research/v3.json, written by scripts/export_research_showcase.py). */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { DotPlot, type DotRow } from "../components/DotPlot";
import { Explain } from "../components/Explain";
import "../styles/research.css";

interface Row { id: string; label: string; kind: "index" | "bands" | "model"; ap: number; auc: number; ap_ci: [number, number] | null; is_reference: boolean }
interface Forest { title: string; counts: { eligible_patches: number; positives: number; negatives: number; base_rate: number }; rows: Row[]; scenes: { earlier: string[]; later: string[] } }
interface CoverageRow { target: number; achieved: number; worst_lake: number; lakes_below_target: number }
interface Bundle {
  forest: Record<string, Forest>;
  lakes: { counts: { positives: number; negatives: number; base_rate: number }; rows: Row[] };
  unet: {
    seeds: number;
    sets: Record<string, { label: string; unet_mean: number; unet_sd: number | null; otsu: number; n_pairs: number }>;
    cv?: { n_pairs: number; median_relative_area_error: number; tile_mean_iou: number; coverage: Record<string, CoverageRow> };
    single_split_coverage_unseen_lakes: Record<string, number[]>;
  };
}

const toRows = (rows: Row[]): DotRow[] =>
  rows.map((r) => ({ id: r.id, label: r.label, value: r.ap, interval: r.ap_ci, kind: r.kind, isBaseline: r.is_reference }));

function Bars({ unet }: { unet: Bundle["unet"] }) {
  const sets = Object.values(unet.sets);
  return (
    <div className="iou" role="img" aria-label="Mask agreement of the trained model and the plain radar rule on two test sets">
      {sets.map((s) => (
        <div className="iou-group" key={s.label}>
          <p className="iou-title">{s.label}<span>{s.n_pairs} scenes</span></p>
          <div className="iou-row">
            <span>Trained U-Net</span>
            <div className="iou-track"><i className="is-model" style={{ width: `${s.unet_mean * 100}%` }} /></div>
            <b>{s.unet_mean.toFixed(2)}{s.unet_sd !== null ? ` ± ${s.unet_sd.toFixed(2)}` : ""}</b>
          </div>
          <div className="iou-row">
            <span>Plain radar rule</span>
            <div className="iou-track"><i className="is-plain" style={{ width: `${s.otsu * 100}%` }} /></div>
            <b>{s.otsu.toFixed(2)}</b>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ResearchPage() {
  const [data, setData] = useState<Bundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [area, setArea] = useState("bastar_forest");

  useEffect(() => {
    fetch("./research/v3.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`research/v3.json: ${r.status}`))))
      .then(setData)
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  if (error) return <main id="main" className="page"><p className="error-note">{error}</p></main>;
  if (!data) return <main id="main" className="page" aria-busy="true"><p className="mono-label">Loading results…</p></main>;
  const forest = data.forest[area];
  const cv = data.unet.cv;
  const single = data.unet.single_split_coverage_unseen_lakes["alpha_0.1"];

  return (
    <main id="main" className="page research">
      <header className="page-head">
        <h1>Do AI models spot change better than simple formulas?</h1>
        <p className="page-lede">
          Two satellite foundation models were tested against standard formulas on forest loss and glacial lakes. Every
          method is judged against the same scene-to-scene noise, and every score is agreement with a reference product,
          not measured accuracy.
        </p>
      </header>

      <section className="verdicts" data-tour="findings" aria-label="Short answers">
        <article className="verdict">
          <p className="verdict-tag is-neg">Forest loss</p>
          <h2>No model beat a simple formula</h2>
          <p>A signed vegetation-decrease formula matched or beat both AI models in two forest areas.</p>
          <a href="#forest">See the evidence</a>
        </article>
        <article className="verdict">
          <p className="verdict-tag is-mix">Glacial lakes</p>
          <h2>Models beat the water formula, but so do raw bands</h2>
          <p>The AI gain over the standard water index is real here, but plain reflectance did just as well.</p>
          <a href="#lakes">See the evidence</a>
        </article>
        <article className="verdict">
          <p className="verdict-tag is-pos">Trained radar model</p>
          <h2>Good overall, unreliable for a few lakes</h2>
          <p>A small U-Net beats the plain radar rule. Its area error bars hold on average, but fail badly for a few lakes.</p>
          <a href="#unet">See the evidence</a>
        </article>
      </section>

      <section id="forest" className="finding">
        <div className="finding-head">
          <h2>Forest loss, checked against Hansen</h2>
          <div className="seg" role="tablist" aria-label="Study area">
            {Object.entries(data.forest).map(([id, f]) => (
              <button key={id} role="tab" type="button" aria-selected={area === id} className={area === id ? "is-on" : ""} onClick={() => setArea(id)}>
                {f.title}
              </button>
            ))}
          </div>
        </div>
        <p className="finding-sub">
          {forest.counts.positives} patches lost forest in 2022 to 2024, {forest.counts.negatives} clearly did not. Each row is how
          well a method ranks the lost patches above the intact ones (average precision, higher is better; chance is{" "}
          {forest.counts.base_rate.toFixed(2)}).
        </p>
        <div className="plate">
          <DotPlot rows={toRows(forest.rows)} baselineLabel="signed NDVI decrease" chanceLevel={forest.counts.base_rate}
                   caption={`Forest loss agreement with Hansen, ${forest.title}`} />
          <Explain
            plain={<>The simple formula that asks "did the plants get less green?" is as good as the AI models at finding forest loss. In Odisha both AI models are clearly worse.</>}
            howToRead="Dots further right are better. The bar is the plausible range; overlapping bars mean we cannot tell the methods apart."
            technical={<>
              <p>Reference: Hansen Global Forest Change v1.12. Positive: at least 10% of a 160 m patch lost in 2022 to 2024. Clean negative: under 2% lost in 2021 to 2024. Scores use the noise-calibrated distance z. Intervals are 95% from a spatial block bootstrap (1.28 km blocks).</p>
              <p>Scenes: {forest.scenes.earlier.join(", ")} against {forest.scenes.later.join(", ")}.</p>
            </>}
          />
        </div>
      </section>

      <section id="lakes" className="finding">
        <div className="finding-head"><h2>Glacial lakes, checked against Sentinel-1 radar</h2></div>
        <p className="finding-sub">
          Three Nepal lakes, October to November 2018 against 2024. {data.lakes.counts.positives} patches changed water state; effectively
          one growing lake (Imja Tsho) carries the result, so the ranges are wide.
        </p>
        <div className="plate">
          <DotPlot rows={toRows(data.lakes.rows)} baselineLabel="MNDWI water index" chanceLevel={data.lakes.counts.base_rate}
                   caption="Glacial lake change agreement with radar" />
          <Explain
            plain={<>Both the foundation model and plain raw bands find changed lake areas better than the standard water index. They are tied with each other, so the AI is not adding anything beyond the raw colours.</>}
            howToRead="The dashed line is the water index. Dots to its right beat it."
            technical={<>
              <p>Reference: Sentinel-1 water-frequency change per 160 m patch, radar scenes within 20 days of each window. Positive: at least 25% of the patch changed water state; negative: under 5%. Paired bootstrap against MNDWI: Prithvi and raw bands exclude zero, the RGB model and NDVI do not.</p>
              <p>Noise calibration matters here: raw bands score 0.755 with the noise-calibrated score and 0.183 with raw distance.</p>
            </>}
          />
        </div>
      </section>

      <section id="unet" className="finding">
        <div className="finding-head"><h2>A small radar model, and how far to trust its error bars</h2></div>
        <p className="finding-sub">
          A 1.9 million weight U-Net learned lake outlines from radar (VV, VH and slope), using optical water maps as the target. Its
          mask overlap (intersection over union) with the optical map is compared with the plain radar threshold rule.
        </p>
        <div className="plate">
          <Bars unet={data.unet} />
          <Explain
            plain={<>The trained model agrees with the optical map clearly better than the simple radar rule, on new dates and on lakes it never saw. It does worse on unseen lakes than on new dates, so it generalises across time better than across places.</>}
            technical={<>
              <p>Mean IoU over scenes, mean ± sd over {data.unet.seeds} training seeds. Split by whole lakes (20 train, 4 calibrate, 6 test) and by time (2022 held out on the training lakes). Weak optical labels with under 3 dB of radar contrast were dropped. Scores are agreement with the optical rule, not accuracy.</p></>}
          />
        </div>
        <div className="plate coverage">
          <h3>Do the area intervals mean what they say?</h3>
          <p>
            For each lake scene the model also gives a range for the lake area, built so that 90% of true areas should fall inside. With one
            calibration split, that held on new dates but only {Math.round(Math.min(...single) * 100)} to {Math.round(Math.max(...single) * 100)}% of
            unseen-lake areas fell inside.
          </p>
          {cv ? (
            <>
              <table className="cov-table">
                <thead><tr><th>Promised</th><th>Achieved across all 30 lakes</th><th>Worst single lake</th><th>Lakes more than 10 points short</th></tr></thead>
                <tbody>
                  {Object.values(cv.coverage).map((c) => (
                    <tr key={c.target}>
                      <td>{Math.round(c.target * 100)}%</td>
                      <td>{Math.round(c.achieved * 100)}%</td>
                      <td>{Math.round(c.worst_lake * 100)}%</td>
                      <td>{c.lakes_below_target}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Explain
                plain={<>When every lake is held out in turn and the ranges are calibrated on the other lakes, the overall coverage is close to what is promised, but some individual lakes are still badly covered. Treat a range as typical for lakes like these, not as a guarantee for one new lake.</>}
                technical={<>Five folds of whole lakes. Each fold's model never saw its lakes; intervals are calibrated on the out-of-fold relative errors of the other four folds (split conformal, relative error with a 0.1 km² floor) and checked on the fold left out. {cv.n_pairs} scenes; median relative area error {Math.round(cv.median_relative_area_error * 100)}%.</>}
              />
            </>
          ) : (
            <p className="mono-label">Cross-validated check not yet exported.</p>
          )}
        </div>
      </section>

      <section className="limits plate">
        <h2>What this does not show</h2>
        <ul>
          <li>Two forest areas and effectively one changing lake do not settle the question; urban and wetland fields are not tested.</li>
          <li>Every reference (Hansen, radar water frequency, optical masks) is another model's output. Scores are agreement, not accuracy.</li>
          <li>A foundation model gives no direction of change, which is a real limit for loss detection.</li>
        </ul>
        <p><Link to="/lakes">Follow the lakes through every month</Link> or <Link to="/methods">read the methods</Link>.</p>
      </section>
    </main>
  );
}
