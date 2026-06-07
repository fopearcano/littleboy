# LittleBoy consequence modeling (v0.7)

> Consequences are estimated, signed, and **uncertain** — so they are summarised
> transparently, never presented as certain predictions.

## What a consequence is

The basic unit is a `ConsequenceEstimate`: one estimated effect of an action at
some time horizon. Its central field is a **signed** `coercion_delta` in
`[-1, 1]`:

- **negative** → the consequence *reduces* coercion (e.g. averting a worse harm);
- **positive** → it *increases* coercion (e.g. entrenching control);
- **0** → neutral or unknown.

Every estimate is qualified by how much we can trust it:

| Field | Meaning |
|-------|---------|
| `horizon` | when it lands (`immediate` … `long_term`, or `unknown`) |
| `coercion_delta` | signed change in coercion, `[-1, 1]` |
| `severity` | how bad it is if it happens, `[0, 1]` |
| `probability` | how likely it is, `[0, 1]` |
| `confidence` | how well-founded the estimate itself is, `[0, 1]` |
| `reversibility` | how undoable this consequence is, `[0, 1]` |
| `duration` | how long it persists, `[0, 1]` |
| `evidence_quality` | the quality of the basis for the claim, `[0, 1]` |
| `affected_agents` | names of the agents it falls on |

A `ConsequenceSet` is just a list of these across horizons. Affected agents are
referred to by **name** (strings); the fully-typed agents live on the
surrounding `ActionCase`, which keeps these models free of any import cycle.

## How a consequence set is summarised

`assess_consequences` reduces a set to a transparent `TemporalConsequenceReport`
without hiding anything behind one number:

- **`expected_coercion_delta`** — the probability-weighted net change:
  `Σ (coercion_delta × probability)`, clamped to `[-1, 1]`. This is the
  single most useful summary, but it is deliberately paired with the spread
  below so the average never conceals the extremes.
- **`worst_plausible_increase`** — the largest *positive* delta among
  consequences above a plausibility floor (`probability ≥ 0.2`).
- **`best_plausible_reduction`** — the largest *reduction* among plausible
  consequences.
- **`uncertainty_level`** — `1 − mean(confidence)` across the set.
- **`high_impact_low_confidence`** — descriptions of consequences that are
  high-impact (`|delta| ≥ 0.5`) but weakly founded (`confidence < 0.5`). These
  are exactly the claims that should *not* drive a confident verdict, so they are
  surfaced by name.
- **`irreversible_consequences`** — coercion-increasing consequences that are
  hard to undo (`reversibility ≤ 0.3`).
- **`reasoning`** — a plain-language trace of how the summary was produced.

The expected-value, worst-case, best-case, and uncertainty figures are reported
**together** precisely so a high average cannot bury a catastrophic tail, and a
hopeful tail cannot disguise a likely harm.

## How it feeds the projection

`project_temporal` uses the consequence set twice. First, per-horizon coercion is
`base + Σ(delta × probability)` over the consequences at that horizon, so a
future harm raises that horizon's coercion and a future *reduction* lowers it.
Second, the report's `expected_coercion_delta`, `high_impact_low_confidence`, and
`irreversible_consequences` flow into the projection's `trend`, `high_risk_unknowns`,
`warnings`, and `uncertainty`. A credible future reduction
(`delta ≤ −0.3`, `probability ≥ 0.3`, `confidence ≥ 0.4`) sets
`prevents_greater_future_coercion`, which is what rule **LB-R023** needs to treat
present coercion as *qualifiedly* justified.

## How the rules use it

- **LB-R019 (Temporal Consequence)** acts on the per-horizon coercion and trend —
  high long-term coercion downgrades even when the immediate score is low.
- **LB-R024 (Temporal Uncertainty)** acts on `high_risk_unknowns` and
  `uncertainty` — high-impact but weakly-evidenced consequences lower confidence
  (more under stricter policy) and expose the missing data, rather than letting a
  shaky estimate masquerade as a firm result.

## Limitations

- These are **estimates supplied to** LittleBoy, not forecasts produced by it.
- `probability` and `confidence` are distinct on purpose: a consequence can be
  *likely* yet *poorly evidenced*, or *unlikely* yet *well-understood*.
- A consequence set is never required. Its absence simply leaves the projection
  inert and records the missing data; it does not fabricate a temporal picture.
