# LittleBoy architecture (v0.2)

LittleBoy is a small, layered, dependency-light reasoning engine. Every layer is
independently testable, and nothing about a verdict is hidden: each report
carries the axioms it invoked and the reasoning behind every score.

## Layering and dependency direction

```text
enums  ─────────────────────────────────────────────┐  (no internal deps)
                                                      │
data/evidence  ── depends on ──> enums                │
                                                      ▼
core/models  ── depends on ──> enums, data/evidence       (pure data structures)
                                                      │
        ┌──────────────┬───────────────┬─────────────┤
        ▼              ▼               ▼             ▼
core/scoring    data/quality     core/axioms    core/agency        (logic over models)
        │              │               │             │
        └──────────────┴───────┬───────┴─────────────┘
                               ▼
                       core/alternatives, core/gates
                               │
                               ▼
                        core/evaluator            (orchestration -> EvaluationReport)
                               │
                               ▼
                   reasoning/experiment, reasoning/report, cli
```

The one deliberate inversion is `core/models` importing `EvidenceSet` from
`data/evidence`; `data/evidence` depends only on `enums`, so there is no cycle.
The evaluator is the single orchestration point; the experiment runner sits
*above* it (it calls the evaluator, never the reverse), which keeps the
report's embedded experiment summary free of import cycles.

## Modules

| Module | Responsibility |
|--------|----------------|
| `core/enums.py` | Closed vocabularies: `AgentType`, `EpistemicStatus`, `SourceType`, `ConsentStatus`, `Verdict`, `UncertaintyLevel`. |
| `core/models.py` | All Pydantic data structures: agents, profiles, justification, alternatives, the `ActionCase` input, and the `EvaluationReport` output (plus embedded result models). No logic. |
| `core/scoring.py` | The transparent coercion-score heuristic. |
| `core/axioms.py` | The axioms as citable data, the Axiom 4 duty rule, and `evaluate_coercion_justification` (Axiom 3). |
| `core/agency.py` | `assess_consent` and `assess_agency`. |
| `core/alternatives.py` | Feasibility-aware comparison of the action against alternatives (Axiom 2). |
| `core/gates.py` | `detect_missing_critical_data` and `recommended_next_questions` — one source of truth for critical-data gaps. |
| `core/evaluator.py` | `EthicalEvaluator`: combines everything into a verdict, confidence, and a fully-explained report. |
| `data/quality.py` | Data-quality scoring, the epistemic-basis blend, confidence, and uncertainty. |
| `data/evidence.py` | `EvidenceItem` / `EvidenceSet` and their transparent scoring. |
| `reasoning/experiment.py` | `EthicalExperiment` runner: falsificatory (contradictions) + heuristic (judgeability, open questions). |
| `reasoning/report.py` | JSON (machine-readable) and text (human-readable) rendering. |
| `cli.py` | `littleboy evaluate` / `experiment` / `version`. |

## Evaluation pipeline

`EthicalEvaluator.evaluate(case)` runs, in order:

1. **Coercion** — score `coercion_profile` (`score_coercion`).
2. **Epistemics** — score data quality and evidence, then blend into a single
   `epistemic_score` (`combine_epistemic_score`).
3. **Consent & agency** — `assess_consent`, `assess_agency`.
4. **Justification & alternatives** — `evaluate_coercion_justification`,
   `analyse_alternatives`.
5. **Unknowns, missing data, confidence** — count structural unknowns, gather
   the critical-data gate output, and compute confidence and uncertainty.
6. **Decision** — gates first (insufficient data; irreversible-on-weak-evidence),
   then the coercion-driven core rule, then consent / vulnerability / alternative
   downgrades.
7. **Narratives** — reasons, warnings, a built-in `ExperimentSummary`, and a
   plain-language `explanation`.

## Backward compatibility

v0.1 inputs still validate and evaluate identically. New structures
(`ConsentProfile`, `AgencyProfile`, `EvidenceSet`, the epistemic
`CoercionJustification`, `AlternativeAction`) are *additive*; when a richer field
is supplied it takes precedence over its v0.1 counterpart (e.g.
`consent_profile.status` over `consent`). The new decision rules only activate
when their inputs are present, so a v0.1 case produces a v0.1-equivalent verdict.

## Determinism and transparency

The engine is fully deterministic and contains no model/LLM calls. Every numeric
score returns its own reasoning trace, and the evaluator records which axioms it
invoked. The scores are explicitly labelled heuristics, not measurements.
