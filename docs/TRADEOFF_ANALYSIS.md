# LittleBoy trade-off analysis (v0.6)

When no option strictly dominates the others, there is a genuine **trade-off**.
LittleBoy's priority is *not* to manufacture a winner but to expose the most
rationally defensible action under uncertainty — which means making the
trade-offs visible instead of hiding them behind a single number.

## Where trade-offs come from

1. **Partial dominance pairs.** Whenever `compare_dominance` returns `partial`
   (A better on some dimensions, B on others), the engine emits a
   `TradeoffAnalysis` describing the contrast concretely.
2. **Intrinsic, single-option tensions.** Some tensions live inside one option,
   e.g. consent is present but the language is manipulative, or the action is
   largely irreversible yet the judgment is uncertain.

## Trade-offs the engine detects and explains

- lower coercion but lower evidence/data quality;
- lower coercion but lower confidence (less certain judgment);
- one option more reversible than another;
- one option less feasible than another;
- affected agents more vulnerable in one option than the other;
- **consent present but language appears manipulative** (consent quality in doubt);
- **irreversibility vs certainty** (largely irreversible yet uncertain);
- higher coercion but stronger justification (when one option is justified and
  another is not, this shows up as a verdict/coercion contrast).

Each `TradeoffAnalysis` records the two option ids (the same id twice for an
intrinsic tension), a `dimension` label, and a plain-language `description`.

## How trade-offs interact with the ranking

A trade-off does **not** silently decide the ranking. The layered ranking still
produces an order, but:

- the order is marked `data_sensitive` / `ranking_stable = False` when the top
  options are close, and
- `what_could_change_ranking` lists the missing data that could flip it, and
- the `comparison_explanation` says, in plain terms, *"this ranking is unstable
  because ..."* and *"additional data required: ..."*.

This way the reader sees both the engine's best current ordering **and** the
tension that the ordering does not resolve.

## Example

`examples/comparison_irreversible_vs_reversible.json` pits an irreversible,
better-evidenced option against a reversible, less-certain one at similar
coercion. There is no clean winner: the engine reports the reversibility-vs-
certainty trade-off, and the ranking shifts with the policy profile (an
irreversible option is penalised more under `precautionary`). The result says so
explicitly rather than presenting one option as "the answer".
