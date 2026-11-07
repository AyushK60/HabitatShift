/* HabitatShift M2 research experiments section.
 *
 * Everything here renders values from `/api/experiments/<id>/latest`, which
 * reads a recorded run's result.json verbatim.  There is no client-side
 * recomputation: if the backend has no recorded run the section states that
 * plainly instead of inventing content.
 */
(function () {
  "use strict";

  const sectionEl = document.getElementById("experiments");
  const ledeEl = document.getElementById("exp-lede");
  const factsEl = document.getElementById("exp-facts");
  const verdictsEl = document.getElementById("exp-verdicts");
  const indexSwitchEl = document.getElementById("exp-index-switch");
  const thresholdSwitchEl = document.getElementById("exp-threshold-switch");
  const thresholdTableEl = document.getElementById("exp-threshold-table");
  const responseChartEl = document.getElementById("exp-response-chart");
  const responseNoteEl = document.getElementById("exp-response-note");
  const methodNoteEl = document.getElementById("exp-method-note");
  const methodTableEl = document.getElementById("exp-method-table");
  const compareChartEl = document.getElementById("exp-compare-chart");
  const uncertaintyEl = document.getElementById("exp-uncertainty");
  const bootstrapChartEl = document.getElementById("exp-bootstrap-chart");
  const guardrailsEl = document.getElementById("exp-guardrails");
  const exportsEl = document.getElementById("exp-exports");
  const manifestNoteEl = document.getElementById("exp-manifest-note");

  const state = {
    summary: null,
    index: "ndvi",
    threshold: null,
  };

  const ha = (value) =>
    `${Number(value || 0).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })} ha`;
  const pct = (value) => `${Number(value || 0).toFixed(2)}%`;
  const short = (value) => Number(value).toFixed(4);

  function row(label, value) {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = label;
    const td = document.createElement("td");
    td.textContent = value;
    tr.append(th, td);
    return tr;
  }

  function verdictChip(verdict) {
    const chip = document.createElement("span");
    chip.className = `verdict verdict-${verdict}`;
    chip.textContent = verdict.replace("_", " ");
    chip.title = "Computed by the runner from measured numbers only";
    return chip;
  }

  function segmentedButtons(container, values, active, format) {
    container.textContent = "";
    for (const value of values) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.value = String(value);
      button.textContent = format ? format(value) : String(value);
      button.setAttribute("aria-pressed", String(value === active));
      if (value === active) button.classList.add("is-active");
      container.append(button);
    }
  }

  function chartImage(src, alt) {
    const chart = document.createElement("img");
    chart.src = src;
    chart.alt = alt;
    chart.loading = "lazy";
    return chart;
  }

  function renderOverview(summary) {
    const config = summary.config;
    factsEl.textContent = "";
    factsEl.append(
      row("Experiment", summary.experiment_id),
      row("Study", summary.study_id),
      row("Run", `${summary.run_id} (${summary.generated_utc})`),
      row("Fingerprint", `${String(summary.fingerprint).slice(0, 16)}…`),
      row(
        "Valid footprint",
        `${summary.coverage.aoi_pixels.toLocaleString()} AOI px · ${ha(
          (summary.coverage.pixel_area_m2 * summary.coverage.aoi_pixels) / 10000,
        )}`,
      ),
      row(
        "Common-valid coverage",
        `${pct(summary.coverage.minimum_common_valid_fraction_of_aoi * 100)} of AOI (all indices)`,
      ),
      row(
        "Composite method",
        `M1 ${config.m1_composite_method} · ${config.indices.join(", ")}`,
      ),
      row(
        "Bootstrap",
        `${config.bootstrap_iterations} iters · ${config.block_size_px} px blocks · seed ${config.bootstrap_seed}`,
      ),
    );

    verdictsEl.textContent = "";
    for (const verdict of summary.hypothesis_verdicts) {
      const line = document.createElement("p");
      line.className = "verdict-line";
      const code = document.createElement("strong");
      code.textContent = verdict.id;
      line.append(code, document.createTextNode(" "), verdictChip(verdict.verdict));
      const detail = document.createElement("span");
      detail.textContent = ` ${verdict.statement.split(". ")[0]}.`;
      line.append(detail);
      verdictsEl.append(line);
    }
  }

  function renderThresholdExplorer(summary) {
    const config = summary.config;
    segmentedButtons(indexSwitchEl, config.indices, state.index);
    segmentedButtons(
      thresholdSwitchEl,
      config.thresholds,
      state.threshold,
      (value) => Number(value).toFixed(2),
    );

    const rows = (summary.primary_threshold_rows[state.index] || [])
      .slice()
      .sort((a, b) => a.threshold - b.threshold);
    const current = rows.find(
      (item) => Math.abs(item.threshold - state.threshold) < 1e-9,
    );
    thresholdTableEl.textContent = "";
    if (!current) {
      thresholdTableEl.append(row("Status", "no recorded row for this threshold"));
      return;
    }
    thresholdTableEl.append(
      row(
        "Threshold",
        `±${current.threshold.toFixed(2)} on Δ${state.index.toUpperCase()}`,
      ),
      row(
        "Candidate decrease",
        `${ha(current.decrease_area_ha)} · ${pct(current.decrease_percent_of_common)}`,
      ),
      row(
        "Unchanged (stable)",
        `${ha(current.stable_area_ha)} · ${pct(current.stable_percent_of_common)}`,
      ),
      row(
        "Candidate increase",
        `${ha(current.increase_area_ha)} · ${pct(current.increase_percent_of_common)}`,
      ),
      row("Valid footprint", ha(current.valid_area_ha)),
      row(
        "Area conservation",
        current.area_conservation.ok ? "holds (0 px residual)" : "FAILED — see run log",
      ),
    );

    const chartUrl = summary.artifacts.charts.threshold_response;
    responseChartEl.hidden = !chartUrl;
    if (chartUrl) {
      responseChartEl.replaceChildren(
        chartImage(chartUrl, "Threshold response chart"),
      );
      const stats = summary.temporal_robustness[state.index];
      const match = stats?.available
        ? stats.rows.find(
            (item) => Math.abs(item.threshold - state.threshold) < 1e-9,
          )
        : null;
      responseNoteEl.textContent = match
        ? `Across ${match.decrease_percent_of_common.count} observation selections the ` +
          `decrease fraction spans ${pct(match.decrease_percent_of_common.min)}–` +
          `${pct(match.decrease_percent_of_common.max)} at ±${state.threshold.toFixed(2)}.`
        : "Candidate-change fraction versus threshold, from the recorded sweep.";
    }
  }

  function renderMethodComparison(summary) {
    const rows = summary.estimators_at_primary
      .filter((item) => item.index === state.index)
      .sort(
        (a, b) =>
          a.family.localeCompare(b.family) ||
          a.estimator_id.localeCompare(b.estimator_id),
      );
    methodNoteEl.textContent =
      `${rows.length} estimators for ${state.index.toUpperCase()} at ` +
      `±${Number(summary.config.primary_threshold).toFixed(2)}, all from the same recorded run.`;
    methodTableEl.textContent = "";
    for (const item of rows) {
      const label = document.createElement("th");
      label.scope = "row";
      label.textContent = item.label;
      const cell = document.createElement("td");
      const mean = document.createElement("span");
      mean.textContent = `Δ ${short(item.delta_mean)} · `;
      const dec = document.createElement("span");
      dec.className = "value-decrease";
      dec.textContent = `↓ ${ha(item.decrease_area_ha)} (${pct(item.decrease_percent_of_common)}) · `;
      const inc = document.createElement("span");
      inc.className = "value-increase";
      inc.textContent = `↑ ${ha(item.increase_area_ha)} (${pct(item.increase_percent_of_common)})`;
      cell.append(mean, dec, inc);
      const tr = document.createElement("tr");
      tr.append(label, cell);
      methodTableEl.append(tr);
    }

    const chartUrl = summary.artifacts.charts[`estimator_comparison_${state.index}`];
    compareChartEl.hidden = !chartUrl;
    if (chartUrl) {
      compareChartEl.replaceChildren(
        chartImage(chartUrl, `Estimator comparison chart for ${state.index}`),
      );
    }
  }

  function renderUncertainty(summary) {
    const config = summary.config;
    const bootstrap = summary.bootstrap[state.index];
    uncertaintyEl.textContent = "";
    const table = document.createElement("table");
    table.className = "meta";
    table.append(
      row("Method", "spatial block bootstrap (documented assumptions in the run)"),
      row(
        "Blocks",
        `${bootstrap.blocks_total} total · ${bootstrap.blocks_with_valid_data} with data · ` +
          `${config.block_size_px} px (${Number(bootstrap.block_size_m).toFixed(0)} m)`,
      ),
      row(
        "Resamples",
        `${bootstrap.iterations_used} of ${bootstrap.iterations_requested} requested · seed ${bootstrap.seed}`,
      ),
    );
    const current = (bootstrap.thresholds || []).find(
      (item) => Math.abs(item.threshold - config.primary_threshold) < 1e-9,
    );
    if (current) {
      table.append(
        row(
          `Decrease fraction ±${current.threshold.toFixed(2)}`,
          `${pct(current.decrease_fraction * 100)} · 95% range ` +
            `${pct(current.decrease_fraction_ci95.p2_5 * 100)}–` +
            `${pct(current.decrease_fraction_ci95.p97_5 * 100)}`,
        ),
        row(
          `Increase fraction ±${current.threshold.toFixed(2)}`,
          `${pct(current.increase_fraction * 100)} · 95% range ` +
            `${pct(current.increase_fraction_ci95.p2_5 * 100)}–` +
            `${pct(current.increase_fraction_ci95.p97_5 * 100)}`,
        ),
      );
    }
    const cross = summary.cross_pipeline;
    if (cross?.available) {
      table.append(
        row(
          "M0 ↔ M1 anchor agreement",
          `${cross.pixels_identical_within_1e_9.toLocaleString()}/${cross.shared_pixels.toLocaleString()} shared NDVI pixels identical`,
        ),
      );
    }
    uncertaintyEl.append(table);

    const chartUrl = summary.artifacts.charts[`bootstrap_${state.index}`];
    bootstrapChartEl.hidden = !chartUrl;
    if (chartUrl) {
      bootstrapChartEl.replaceChildren(
        chartImage(chartUrl, `Block bootstrap intervals for ${state.index}`),
      );
    }
  }

  function renderGuardrailsAndExports(summary) {
    guardrailsEl.textContent = "";
    for (const guardrail of summary.guardrails) {
      guardrailsEl.append(
        Object.assign(document.createElement("li"), { textContent: guardrail }),
      );
    }
    const periods = (summary.coverage.periods || [])
      .map(
        (period) =>
          `${period.period_id}: ${period.observation_count} obs (${period.dates.join(", ")})`,
      )
      .join(" · ");
    guardrailsEl.append(
      Object.assign(document.createElement("li"), {
        textContent: `Observation counts behind every estimator — ${periods}.`,
      }),
    );

    exportsEl.textContent = "";
    const links = [
      ["Full result JSON", summary.artifacts.result],
      ["Run manifest (hashes, versions, git commit)", summary.artifacts.manifest],
      ["Estimator × threshold CSV", summary.artifacts.estimator_thresholds_csv],
      ["Threshold sensitivity CSV", summary.artifacts.threshold_sensitivity_csv],
    ];
    for (const [label, url] of links) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = url;
      link.textContent = label;
      link.target = "_blank";
      link.rel = "noopener";
      item.append(link);
      exportsEl.append(item);
    }
    manifestNoteEl.textContent =
      `Values in this section come from run ${summary.run_id}; re-running ` +
      `scripts/run_experiment.py with unchanged inputs reproduces the same ` +
      `fingerprint and is served from this recorded run.`;
  }

  function render() {
    if (!state.summary) return;
    renderOverview(state.summary);
    renderThresholdExplorer(state.summary);
    renderMethodComparison(state.summary);
    renderUncertainty(state.summary);
    renderGuardrailsAndExports(state.summary);
  }

  async function load() {
    let payload;
    try {
      const response = await fetch("/api/experiments/coringa_m2/latest");
      if (response.status === 404) {
        ledeEl.textContent =
          "No recorded experiment run. Start the backend and run " +
          "`python scripts/run_experiment.py --config studies/experiments/coringa_m2.yaml`.";
        sectionEl.hidden = false;
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      payload = await response.json();
    } catch (error) {
      ledeEl.textContent = `Could not load recorded experiments: ${error.message}`;
      sectionEl.hidden = false;
      return;
    }
    state.summary = payload;
    state.index = payload.config.indices[0];
    state.threshold = payload.config.primary_threshold;
    ledeEl.textContent =
      `Recorded run ${payload.run_id} · ${payload.estimators_at_primary.length} estimator surfaces · ` +
      `thresholds ${payload.config.thresholds.map((t) => Number(t).toFixed(2)).join(", ")} · ` +
      `no supervised labels were used anywhere in this run.`;
    sectionEl.hidden = false;
    render();
  }

  indexSwitchEl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    state.index = button.dataset.value;
    renderThresholdExplorer(state.summary);
    renderMethodComparison(state.summary);
    renderUncertainty(state.summary);
  });

  thresholdSwitchEl.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    state.threshold = Number(button.dataset.value);
    renderThresholdExplorer(state.summary);
  });

  load();
})();
