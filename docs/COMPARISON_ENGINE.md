# LittleBoy comparison engine (v0.6)

> Choose the **least coercive morally viable path** under the available
> evidence, while exposing uncertainty, missing data, trade-offs, and possible
> contradictions.

## Why compare instead of judging in isolation

Judging one action alone answers "is this acceptable?" — but real ethical
decisions are *choices among options*. An action can be acceptable yet still be
the worst available choice if a less coercive option achieves the same goal. The
comparison engine evaluates several candidate actions and identifies the most
rationally defensible one **without** pretending there is always a clean winner.

It is built **on top of** the existing `EthicalEvaluator` (it does not replace
it): every option's `ActionCase` is evaluated normally, and the full
`EvaluationReport` for each option is preserved in the result.

## What "least coercive morally viable path" means

First **viability**, then **least coercion**. An option is *morally viable* only
if it is not `NOT_ACCEPTABLE`; not blocked by unresolved critical data
(`INSUFFICIENT_DATA`); free of unjustified high coercion; not dependent on
coerced/disputed consent where consent is central; not carrying an unresolved
contradiction; and adequately evidenced for the policy. An option can be **viable
with reservations** (e.g. `ETHICALLY_SUSPICIOUS`, or carrying a feasible
less-coercive alternative, or low confidence). "Viable" never means "morally
perfect."

Among viable options, the engine prefers the least coercive — but exposes the
trade-offs rather than letting a tiny coercion difference silently decide
everything (see below).

## How dominance works

`compare_dominance` compares two options pairwise:

- **strict dominance** (A over B): same/equivalent goal, A is *strictly less
  coercive*, and **no worse** on data quality, evidence, confidence, verdict,
  blockers, or feasibility;
- **partial dominance**: A is better on some dimensions but worse on others — a
  trade-off, reported not resolved;
- **none**: roughly equivalent, or different declared goals;
- **incomparable**: one option rests on insufficient data.

Strictly dominated options are listed in `dominated_options`; the rest form the
`non_dominated_options` frontier.

## How ranking works

Ranking is **not** a single weighted score. It is a transparent, lexicographic
(layered) preorder:

1. moral viability (viable, then viable-with-reservations, then non-viable);
2. lower coercion (compared in coarse bands, so close calls fall to later layers);
3. consent integrity;
4. protection of vulnerable agents;
5. reversibility under uncertainty;
6. lower uncertainty (confidence, evidence);
7. fewer feasible less-coercive alternatives;
8. constructive over manipulative language;
9. fine-grained tiebreakers (confidence, data quality).

Each ranking entry records its `primary_reason`, and each non-top option records
a `downgrade_reason` naming the first layer on which it lost to the top option.

## How policy profiles affect comparison

The same set can rank differently under different policies. The policy
(`permissive` / `standard` / `strict` / `precautionary`) changes what counts as
viable (e.g. whether unknown consent is a blocker), how heavily irreversibility
under uncertainty, vulnerability, and linguistic coercion weigh, and the
data/evidence bars. For example, an option may be viable under `permissive` but
non-viable under `strict`, and an irreversible option is penalised more under
`precautionary`.

```bash
littleboy compare examples/comparison_irreversible_vs_reversible.json --policy permissive
littleboy compare examples/comparison_irreversible_vs_reversible.json --policy precautionary
```

## Why missing data can make a ranking unstable

If the top two options are close (same viability tier and coercion band), or any
option rests on insufficient data, the ranking is marked **data-sensitive** and
`ranking_stable = False`. The result then lists `what_could_change_ranking` — the
specific missing facts that, if resolved, could reorder the options. LittleBoy
will refuse to present an unstable order as if it were settled.

## Why trade-offs are exposed, not hidden

When no option dominates — lower coercion but weaker evidence, reversible but
less effective, consent present but language manipulative — the engine reports
the tension as an explicit `TradeoffAnalysis` rather than burying it in a score.
See [`docs/TRADEOFF_ANALYSIS.md`](TRADEOFF_ANALYSIS.md).

## Output

`ActionComparisonResult` carries: `best_option_id` (or `None` if nothing is
viable), the full `ranking`, `dominated`/`non_dominated` options, all pairwise
`dominance_results`, the `tradeoffs`, `ranking_stable` / `data_sensitive` /
`what_could_change_ranking`, `uncertainty_warnings`, `missing_data_summary`, a
non-rhetorical `comparison_explanation`, and the `individual_reports` for every
option. JSON output is stable and machine-readable; text output shows the best
option, the ranking with reasons, dominance, trade-offs, and the missing data
that could change the result.
