# HabitatShift — methodology

The scientific methodology is **hybrid by design**:

> Mathematical/statistical change detection is the baseline.
> Machine learning is an additional method, used only where appropriate
> independent training and validation data exist.

```mermaid
flowchart TB
    subgraph Common["Shared front end (audited M1 chain)"]
        A["Sentinel-2 L2A\nbounded COG reads"] --> B["Radiometry verification\n(declared convention vs\nempirical physical floor)"]
        B --> C["SCL masking\n(cloud/shadow/cirrus excluded)"]
        C --> D["Median composites\nper matched season"]
    end

    D --> M["Mathematical baseline"]
    D --> S["Supervised ML (label-gated)"]
    D --> U["Exploratory clustering"]

    subgraph M["Mathematical baseline (all studies)"]
        M1["Δ-index maps\nNDVI · NDWI · MNDWI · NDSI · NDBI"]
        M2["Threshold classification\nsymmetric ±t on common-valid footprint"]
        M3["Connected components\n4-connectivity, MMU 25 px,\ntop-5 per index/direction"]
        M4["Threshold sensitivity\nt±0.05 neighbours per finding"]
        M5["Uncertainty\nspatial block bootstrap,\nestimator families, area cross-checks"]
    end

    subgraph S["Supervised ML (M5, gated)"]
        S1["Label gate:\nPASS ×3 · PARTIAL ×1 · BLOCKED ×2"]
        S2["2021-epoch training imagery\nthrough the same audited chain"]
        S3["Random Forest\n300 trees · 1 km block folds"]
        S4["Agreement with reference product\n(NOT ground-truth accuracy)"]
    end

    M --> E["Sealed evidence records\n(habitatshift-evidence-record/1)"]
    S --> E2["Additive ML layer\n(never overwrites a measured finding)"]
    U --> E3["Exploratory artifacts\n(clusters are spectral groups,\nnever classes or change)"]
```

## 1. Mathematical change detection (baseline)

Documented in full in [`SCIENCE_PROTOCOL.md`](SCIENCE_PROTOCOL.md). Key
rules: matched seasonal windows, ≥ 1 (typically 3) usable observations per
period, per-pixel valid masks (SCL + finite reflectance), common-valid
intersection as the denominator, symmetric inclusive thresholds, area as
projected UTM pixel area with a geodesic cross-check, minimum mapping unit
25 px (0.25 ha at 10 m), findings addressed by content-derived `evidence_id`
with per-finding threshold-sensitivity neighbours.

## 2. Uncertainty (five separate categories, never one score)

1. **Measurement uncertainty** — spatial block bootstrap CIs (Coringa M2;
   block-size sensitivity measured in M5).
2. **Observation-selection uncertainty** — estimator families
   (single pairs, leave-one-out, composite mean/median).
3. **Threshold sensitivity** — sweeps 0.05–0.25 + per-finding ±0.05 neighbours.
4. **Classification uncertainty** — M5 per-class metrics, support gating,
   geographic hold-out ranges.
5. **Reference-label uncertainty** — agreement framing, label provenance,
   recorded source disagreements (Coringa mangrove).

## 3. Machine learning (M5, strictly label-gated)

`M5_ML_LABEL_FEASIBILITY.md` → `M5_ML_METHODOLOGY.md` →
`M5_EXPERIMENT_RESULTS.md`. In short: Random Forests are implemented only
for the studies whose reference labels passed the feasibility gate; features
are the audited reflectance/indices; the split is 1 km block folds (no
pixel ever crosses folds); every metric is "agreement with the ESA
WorldCover v200 reference product"; classes below 50 test pixels are not
reported; application to 2020/2025 epochs is a recorded assumption, not a
verified fact. Both Himalayan studies deliberately have no classifier.

## 4. Interpretation guardrails (in-product, audited)

- Findings are **candidate spectral signals**, never verified environmental
  change.
- ML outputs are **model predictions against reference labels**, marked as
  such everywhere they appear (`evidence_status:
  MODEL_OUTPUT_AGAINST_REFERENCE`).
- An independent negation-aware disclosure audit scans every ML surface for
  unqualified accuracy or ground-truth claims (`audit_m5ml_disclosure.py`,
  96/96).
- PARTIAL-evidence studies carry prominent in-product notes.
