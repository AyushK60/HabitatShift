/** Shared Evidence Adapter (M4-R3 G0).
 *
 * The single read layer over the versioned Evidence Records
 * (`habitatshift-findings/2` containers with embedded
 * `habitatshift-evidence-record/1` records) that both experiences use:
 *
 *   Explore the Evidence  ─┐
 *                          ├─ Shared Evidence Adapter ─ Evidence Records
 *   Research Mode         ─┘
 *
 * Rules enforced here (M4-R3 brief §2):
 * - No measurement is recomputed anywhere in the UI. Every value displayed
 *   by either experience is read through this module from the same finding
 *   payload, so a change in the evidence record is reflected in both views.
 * - Findings are addressed by their stable content-derived `evidence_id`;
 *   selection state and navigation carry the evidence_id, not array indices.
 * - The completeness boundary (top-five-per-index-direction selection, with
 *   the audited unrecorded-component counts) is read from the generated
 *   disclosure artifact — never invented in the UI.
 * - Nothing is fabricated: missing optional data stays `null`/`undefined`
 *   and callers must render it as explicitly unavailable.
 */
import type {
  BundleFinding,
  BundleFindings,
  EvidenceRecord,
} from "../api/bundle";

/* ------------------------------------------------- selection policy --- */

export interface SelectionPolicyIndexRow {
  recorded_findings: number;
  components_at_or_above_mmu_total: number;
  components_at_or_above_mmu_unrecorded_top5_cap: number;
}

export interface SelectionPolicyExperiment {
  experiment_id: string;
  findings_recorded: number;
  components_at_or_above_mmu_total: number;
  components_at_or_above_mmu_unrecorded_top5_cap: number;
  by_index: Record<string, SelectionPolicyIndexRow>;
}

export interface SelectionPolicy {
  schema: string;
  generated_utc: string;
  policy: {
    rule: string;
    minimum_mapping_unit_px: number;
    recorded_findings_are: string;
    unrecorded_components_are: string;
  };
  source: {
    generator: string;
    audit_artifact: string;
    audit_checks_passed: number | null;
    audit_checks_failed: number | null;
    git_commit: string | null;
  };
  experiments: SelectionPolicyExperiment[];
  totals: {
    experiments: number;
    findings_recorded: number;
    components_at_or_above_mmu_total: number;
    components_at_or_above_mmu_unrecorded_top5_cap: number;
  };
}

/** Load the generated selection-policy disclosure (brief §5).
 *  Returns null when the artifact is unavailable — callers must then show
 *  the disclosure text from the findings container without the counts. */
export async function loadSelectionPolicy(): Promise<SelectionPolicy | null> {
  try {
    const response = await fetch("studies/selection_policy.json");
    if (!response.ok) return null;
    const payload = (await response.json()) as SelectionPolicy;
    return payload.schema === "habitatshift-selection-policy/1" ? payload : null;
  } catch {
    return null;
  }
}

export function selectionForExperiment(
  policy: SelectionPolicy | null,
  experimentId: string
): SelectionPolicyExperiment | null {
  return policy?.experiments.find((row) => row.experiment_id === experimentId) ?? null;
}

/* ------------------------------------------------------ overview --- */

export interface EvidenceOverview {
  study_id: string;
  experiment_id: string;
  evidence_status: string;
  schema: string;
  generated_utc: string;
  findings_total: number;
  by_direction: { decrease: number; increase: number };
  indices: string[];
  /** Per-index candidate counts recorded in the container. */
  per_index: BundleFindings["indices"];
  observation_period: {
    earlier: string;
    later: string;
  };
  common_valid_pixels: number;
  common_valid_fraction_of_aoi: number;
  /** Relationship links recorded inside the evidence records. */
  relationship_link_count: number;
  findings_with_relationships: number;
  no_finding_statement: string | null;
  limitations: string[];
  method: BundleFindings["method"];
  /** Audited completeness boundary; null when the artifact is unavailable. */
  selection: {
    recorded_findings: number;
    components_at_or_above_mmu_total: number;
    components_at_or_above_mmu_unrecorded_top5_cap: number;
    rule: string;
  } | null;
}

/** Derive the study-level overview strictly from the recorded container. */
export function buildEvidenceOverview(
  payload: BundleFindings,
  selection: SelectionPolicyExperiment | null = null
): EvidenceOverview {
  let relationship_link_count = 0;
  let findings_with_relationships = 0;
  for (const finding of payload.findings) {
    const links = finding.evidence?.relationships?.links ?? [];
    if (links.length > 0) findings_with_relationships += 1;
    relationship_link_count += links.length;
  }
  const rule = selection
    ? payload.method.max_regions_per_index_direction > 0
      ? `top ${payload.method.max_regions_per_index_direction} components per index × direction by area`
      : "deterministic component selection"
    : "deterministic component selection";
  return {
    study_id: payload.study_id,
    experiment_id: payload.experiment_id,
    evidence_status: payload.evidence_status,
    schema: payload.schema,
    generated_utc: payload.generated_utc,
    findings_total: payload.overview.findings_total,
    by_direction: payload.overview.by_direction,
    indices: Object.keys(payload.indices),
    per_index: payload.indices,
    observation_period: {
      earlier: payload.periods.earlier.anchor_date,
      later: payload.periods.later.anchor_date,
    },
    common_valid_pixels: payload.common_valid_pixels,
    common_valid_fraction_of_aoi: payload.common_valid_fraction_of_aoi,
    relationship_link_count,
    findings_with_relationships,
    no_finding_statement: payload.overview.no_finding_statement,
    limitations: payload.limitations,
    method: payload.method,
    selection: selection
      ? {
          recorded_findings: selection.findings_recorded,
          components_at_or_above_mmu_total: selection.components_at_or_above_mmu_total,
          components_at_or_above_mmu_unrecorded_top5_cap:
            selection.components_at_or_above_mmu_unrecorded_top5_cap,
          rule,
        }
      : null,
  };
}

/* ------------------------------------------------------ findings --- */

/** Resolve a finding by its stable evidence_id (the cross-view join key). */
export function findingByEvidenceId(
  payload: BundleFindings,
  evidenceId: string
): BundleFinding | undefined {
  return payload.findings.find((finding) => finding.evidence_id === evidenceId);
}

export interface RelatedFindingLink {
  relation: "same-direction-overlap" | "opposite-direction-overlap";
  indices: string[];
  overlap_percent_of_smaller: number;
  finding: BundleFinding;
}

/** Resolve a finding's recorded relationship links to actual findings.
 *  Links that reference an unknown evidence_id are skipped, never guessed. */
export function relatedFindingsFor(
  payload: BundleFindings,
  finding: BundleFinding
): RelatedFindingLink[] {
  const links = finding.evidence?.relationships?.links ?? [];
  const resolved: RelatedFindingLink[] = [];
  for (const link of links) {
    const target = findingByEvidenceId(payload, link.with_evidence_id);
    if (target) {
      resolved.push({
        relation: link.relation,
        indices: link.indices,
        overlap_percent_of_smaller: link.overlap_percent_of_smaller,
        finding: target,
      });
    }
  }
  return resolved;
}

/* --------------------------------------------------- sensitivity --- */

export interface ThresholdSensitivity {
  status: string;
  method: string;
  neighbour_delta: number;
  neighbours: Record<
    string,
    {
      component_pixels: number;
      retained_fraction_of_region: number;
      component_growth_factor: number;
    }
  >;
  label: string;
  label_rules: string;
}

/** Typed accessor for the recorded threshold-sensitivity result.
 *  The label is a transparency category, NOT a confidence score. */
export function thresholdSensitivity(
  record: EvidenceRecord
): ThresholdSensitivity | null {
  const raw = (
    record.evidence_quality as {
      threshold_sensitivity?: ThresholdSensitivity;
    }
  )?.threshold_sensitivity;
  return raw ?? null;
}

/* ------------------------------------------------------ helpers --- */

export function directionTerm(direction: "decrease" | "increase"): string {
  return direction === "decrease" ? "candidate decrease" : "candidate increase";
}

export function formatHa(areaHectares: number): string {
  return `${areaHectares.toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ha`;
}

export function formatPercent(fraction: number, digits = 2): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

export function formatIndexName(index: string): string {
  return index.toUpperCase();
}
