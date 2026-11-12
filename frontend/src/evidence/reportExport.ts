/** Study report + provenance export (portfolio/release item "export research
 * report and machine-readable provenance manifest").
 *
 * Works entirely from the already-loaded recorded artefacts, so it runs in
 * showcase mode with no backend. Nothing is computed: every number is copied
 * from the bundle summary / findings container / ML record, and anything not
 * recorded is written as "not recorded" rather than inferred.
 */
import type { StudyBundle } from "../api/bundle";
import type { M1Summary } from "../api/types";
import type { MlContainer } from "./adapter";

export interface ExportInput {
  bundle: StudyBundle;
  summary: M1Summary;
  experimentIndex: number;
  ml: MlContainer | null;
  generatedAtIso: string;
}

const fmt = (value: unknown, digits = 2): string =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "not recorded";

export function buildProvenanceManifest(input: ExportInput): Record<string, unknown> {
  const { bundle, summary, experimentIndex, ml } = input;
  const experiment = bundle.experiments[experimentIndex];
  return {
    schema: "habitatshift-report-provenance/1",
    generated_utc: input.generatedAtIso,
    note: "Assembled in the browser from recorded artefacts; no value is recomputed.",
    study_id: bundle.study_id,
    evidence_status: bundle.evidence_status,
    experiment: {
      experiment_id: experiment?.experiment_id ?? summary.experiment_id,
      config_sha256: experiment?.config_sha256 ?? null,
      summary_sha256: experiment?.summary_sha256 ?? null,
    },
    grid: summary.grid,
    periods: summary.periods.map((period) => ({
      period_id: period.period_id,
      anchor_date: period.anchor_date,
      observation_dates: period.observation_dates,
      scene_ids: period.item_ids,
      composite_method: period.composite_method,
      valid_fraction_of_aoi: period.valid_fraction,
    })),
    bundle_schema: bundle.schema,
    bundle_version: bundle.bundle_version,
    preview_assets: bundle.assets,
    ml_reference: ml
      ? {
          schema: ml.schema,
          evidence_status: ml.evidence_status,
          reference_dataset: ml.ml_record.reference?.dataset ?? null,
          reference_licence: ml.ml_record.reference?.license ?? null,
          source_result_sha256:
            (ml.ml_record as unknown as { identification?: { source_result_sha256?: string } }).identification
              ?.source_result_sha256 ?? null,
          frozen_findings_sha256: ml.references.mathematical_findings_container.sha256,
        }
      : null,
    attribution: bundle.attribution,
  };
}

export function buildReportMarkdown(input: ExportInput): string {
  const { bundle, summary, ml } = input;
  const lines: string[] = [];
  const push = (line = "") => lines.push(line);

  push(`# ${bundle.study.title}`);
  push();
  push(
    `*Exported from HabitatShift on ${input.generatedAtIso}. Candidate spectral signals between two fixed past dates; ` +
      `not verified environmental change.*`
  );
  push();
  push(`**Question.** ${summary.study.question}`);
  push();
  push("## Observations");
  push();
  push("| Period | Anchor date | Observations | Composite | Valid share of AOI |");
  push("|---|---|---|---|---|");
  for (const period of summary.periods) {
    push(
      `| ${period.period_id} | ${period.anchor_date} | ${period.observation_count} | ${period.composite_method} | ${fmt(
        period.valid_fraction * 100,
        1
      )} % |`
    );
  }
  push();
  push("Scene identifiers:");
  for (const period of summary.periods) {
    push(`- ${period.period_id}: ${period.item_ids.join(", ")}`);
  }
  push();
  push(
    `Analysis grid: ${summary.grid.resolution_m} m, ${summary.grid.crs}, ${summary.grid.width} x ${summary.grid.height} px (signature ${summary.grid.signature}).`
  );
  push();
  push("## Index change at the primary threshold");
  push();
  push("| Index | Threshold | Lower (ha) | Higher (ha) | Common-valid area (ha) |");
  push("|---|---|---|---|---|");
  for (const block of Object.values(summary.change ?? {})) {
    push(
      `| ${block.label} | ±${fmt(block.primary_threshold)} | ${fmt(block.primary.decrease_area_ha)} | ${fmt(
        block.primary.increase_area_ha
      )} | ${fmt(block.common_valid_area_ha)} |`
    );
  }
  push();
  push(
    "Areas are projected UTM pixel areas on the shared-valid footprint. The values are index differences, not land-cover verdicts."
  );
  push();
  push("## What this can and cannot conclude");
  push();
  push("**Can conclude**");
  for (const item of bundle.interpretation.can_conclude) push(`- ${item}`);
  push();
  push("**Cannot conclude**");
  for (const item of bundle.interpretation.cannot_conclude) push(`- ${item}`);
  push();
  if (ml) {
    const record = ml.ml_record;
    push("## Additional ML reference experiment");
    push();
    push(
      `Random Forest agreement with ${record.reference?.dataset ?? "the reference product"}: overall agreement ${fmt(
        record.evaluation?.overall_agreement,
        3
      )}, macro-F1 over supported classes ${fmt(record.evaluation?.macro_f1_supported_classes, 3)}.`
    );
    push();
    push(
      "These are agreement figures against a reference product, not accuracy against ground truth. Classes with too little test support are not reported."
    );
    push();
  }
  push("## Limitations");
  push();
  for (const item of summary.limitations ?? []) push(`- ${item}`);
  push();
  push("## Attribution");
  push();
  push(String(bundle.attribution));
  push();
  return lines.join("\n");
}

export function downloadText(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function exportStudyReport(input: ExportInput): void {
  const stem = `${input.bundle.study_id}_${input.summary.experiment_id}`;
  downloadText(`${stem}_report.md`, buildReportMarkdown(input), "text/markdown");
  downloadText(`${stem}_provenance.json`, JSON.stringify(buildProvenanceManifest(input), null, 2), "application/json");
}
