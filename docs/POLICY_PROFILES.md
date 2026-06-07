# LittleBoy policy profiles (v0.3)

A **policy profile** (`littleboy.rules.policy.PolicyProfile`) is a bundle of
*operational parameters* — thresholds and toggles — that control how strict the
rule engine is. A policy changes how the axioms are **applied** to uncertain,
real-world data; it never changes the axioms themselves.

> These numbers are deliberate, documented defaults, **not** claims of absolute
> moral truth. They let the same case be examined under different risk postures.

## The four modes

| Mode | Posture |
|------|---------|
| `permissive` | Tolerant: higher coercion tolerated, lower data bars, unknowns rarely block. For low-stakes or exploratory use. |
| `standard` *(default)* | Balanced. Reproduces the v0.2 evaluator behaviour. |
| `strict` | Cautious: lower coercion ceiling, higher data/evidence/confidence bars, unknown consent blocks. |
| `precautionary` | Most cautious: the strictest thresholds; treats uncertainty as strongly disfavouring approval. |

## What a policy controls

| Parameter | Meaning |
|-----------|---------|
| `min_data_quality_for_approval` | Epistemic basis below this → `INSUFFICIENT_DATA`. |
| `min_evidence_quality_for_approval` | Evidence below this is flagged and lowers confidence. |
| `min_confidence` | Final confidence below this → `INSUFFICIENT_DATA`. |
| `data_quality_good` | At/above this the epistemic basis counts as "good" (needed for `ACCEPTABLE`). |
| `max_coercion_for_acceptable` | Above this, coercion is unacceptable unless justified (the "high" threshold). |
| `coercion_moderate` | Above this, coercion is non-trivial and triggers scrutiny of alternatives/justification. |
| `irreversible_requires_high_certainty` | Whether an irreversible act demands a strong epistemic basis. |
| `irreversible_min_epistemic` | The epistemic bar for an irreversible act. |
| `unknown_consent_is_blocker` | Whether unknown consent blocks confident approval (vs. only lowering confidence). |
| `vulnerability_confidence_penalty` | How strongly high vulnerability lowers confidence. |
| `alternative_downgrade_steps` | How many notches a feasible less-coercive alternative downgrades the verdict. |
| `informational_manipulation_severe` | Whether informational manipulation is treated as severe coercion. |

## Default values

| Parameter | permissive | standard | strict | precautionary |
|-----------|:---:|:---:|:---:|:---:|
| min_data_quality_for_approval | 0.25 | 0.35 | 0.50 | 0.60 |
| min_evidence_quality_for_approval | 0.20 | 0.30 | 0.45 | 0.55 |
| min_confidence | 0.20 | 0.30 | 0.45 | 0.55 |
| data_quality_good | 0.60 | 0.70 | 0.80 | 0.85 |
| max_coercion_for_acceptable | 0.75 | 0.60 | 0.45 | 0.35 |
| coercion_moderate | 0.40 | 0.30 | 0.20 | 0.15 |
| irreversible_requires_high_certainty | false | true | true | true |
| irreversible_min_epistemic | 0.40 | 0.50 | 0.65 | 0.75 |
| unknown_consent_is_blocker | false | false | true | true |
| vulnerability_confidence_penalty | 0.10 | 0.15 | 0.25 | 0.30 |
| alternative_downgrade_steps | 1 | 1 | 2 | 2 |
| informational_manipulation_severe | false | true | true | true |

## How profiles change strictness — worked examples

- `examples/policy_permissive_case.json` (firm but reversible mandate, coercion
  ≈ 0.65): **`NOT_ACCEPTABLE` under `standard`** (above its 0.60 ceiling, no
  justification) but **`ACCEPTABLE_WITH_RESERVATIONS` under `permissive`** (below
  its 0.75 ceiling).
- `examples/policy_strict_case.json` (mild coercion, **unknown consent**):
  **`ACCEPTABLE_WITH_RESERVATIONS` under `standard`** (unknown consent only lowers
  confidence) but **`ETHICALLY_SUSPICIOUS` under `strict`** (unknown consent is a
  blocker).

## Choosing a policy

```bash
littleboy evaluate examples/policy_strict_case.json --policy strict
littleboy evaluate examples/policy_strict_case.json --policy strict --format text
```

```python
from littleboy import EthicalEvaluator, PolicyMode
report = EthicalEvaluator(PolicyMode.STRICT).evaluate(case)
```

You can also pass a fully custom `PolicyProfile` to `EthicalEvaluator(...)` if you
need parameters between the built-in modes. The chosen mode is recorded on every
report (`policy_mode`) and in the reasoning trace, so a verdict is never
separable from the policy that produced it.
