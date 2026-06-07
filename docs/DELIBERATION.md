# LittleBoy deliberation (v0.9)

> A verdict is not an explanation. LittleBoy should be able to say **why** the
> verdict (or the winning option) came out as it did, and **what single fact
> would most change it.**

## Why narrate, and why value the unknowns

A bare verdict — `NOT_ACCEPTABLE`, confidence 0.71 — hides the reasoning that
produced it and the fragility of the data underneath it. Two failures follow: a
reader cannot tell *which* factor was decisive (was it the coercion level, the
refused consent, or the missing alternative?), and they cannot tell *how close*
the verdict was to flipping. The `littleboy.deliberation` layer addresses both.
It is built **on top of** the existing evaluator and comparison engine (it does
not replace them) and adds nothing to the verdict itself; it only explains and
probes it.

## Narration: ordering the factors

`narrate_evaluation` reads the report the engine already produced and orders the
factors that drove the verdict into three kinds:

- **decisive** — the rules that actually capped or downgraded the verdict
  (blockers, verdict caps, downgrades), taken straight from the reasoning trace;
- **supporting** — the coercion level, the consent status, the Axiom 3
  justification result, and whether a feasible less-coercive alternative exists;
- **context** — the confidence and uncertainty level.

It then composes a one-line `headline` (e.g. *"NOT_ACCEPTABLE because coercion
exceeds the acceptable threshold and is not established as justified"*). For a
comparison, `narrate_comparison` says why the top option ranks first and names
the **first lexicographic layer** on which the runner-up lost (its
`downgrade_reason`) — the decisive layer of the ranking.

## Value of information: the fact that would most change the verdict

The novel capability is the **value of information** (VoI): among the things
LittleBoy does not currently know, which one — if resolved — would most change the
outcome? See [`VALUE_OF_INFORMATION.md`](VALUE_OF_INFORMATION.md) for the method.
In short: each genuine unknown is resolved to each plausible value, the
deterministic evaluator is re-run, and the swing in verdict and confidence is
measured. The unknown with the largest swing is the `most_informative` one, and
the report records the exact counterfactual resolutions (e.g. *"consent = GIVEN →
ACCEPTABLE_WITH_RESERVATIONS; consent = REFUSED → ETHICALLY_SUSPICIOUS"*).

A `DeliberationReport` therefore carries: the `headline`, the ordered `steps`, the
`decisive_factors`, the ranked `information_values`, the `most_informative`
unknown, and `stable_under_information` — `True` when **no single** resolvable
unknown would change the verdict. A comparison's `ComparisonDeliberationReport`
adds `why_top_wins`, the `decisive_layer`, and `ranking_robust`.

## How it relates to the case builder and the audit

The case builder asks *what is missing*; the audit asks *whether the description
is leading*; deliberation asks *which missing fact matters most and how close the
call is*. The three are complementary: the builder's questions become sharper when
ordered by value of information, and a high-VoI unknown on a coercive action is
exactly where an adversarial describer would be tempted to leave a gap.

## CLI

```bash
littleboy deliberate examples/voi_consent_pivotal.json            # a single case
littleboy deliberate examples/comparison_voi_pivotal.json -c      # a comparison set
littleboy deliberate examples/voi_consent_pivotal.json --format json --policy strict
```

The text output shows the headline, why the verdict holds, the most informative
unknown with its swing, the ranked value of information, and the counterfactual
resolutions that would change the verdict.

## Limitations

- Narration **reports**; it never introduces a judgment the engine did not make.
- The value of information is computed against an explicit, finite set of
  *probes* (consent, agent type, reversibility, alternatives, data quality, the
  Axiom 3 conditions, and the consequence profile). It does not enumerate every
  conceivable fact, and it treats each unknown independently — it does not search
  for *combinations* of facts that jointly flip the verdict.
- The resolutions tried are deliberate, documented counterfactuals (e.g. consent
  GIVEN vs REFUSED), not a probability distribution; VoI is a decision-relevance
  measure, not an expected-information-gain in bits.
