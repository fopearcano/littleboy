# LittleBoy temporal model (v0.7)

> **An action cannot be ethically judged only at the instant it occurs.** An
> action is ethically *unstable* if it reduces visible coercion now while
> creating hidden, cumulative, irreversible, or delayed coercion later.

## Why time matters ethically

LittleBoy's foundational axiom is that the fundamental ethical evil is coercion.
But coercion is rarely confined to the moment of action. It can be **delayed**
(invisible now, severe later), **cumulative** (trivial once, systemic when
repeated), **irreversible** (cheap to start, impossible to undo), or **ongoing**
(allowed to continue by inaction). Judging only the instant of action would let
an action that looks gentle now but entrenches control later pass as acceptable —
and would treat doing nothing as automatically innocent. The temporal module
exists to judge an action **across time**, not at a single frozen instant.

## What the module adds

The `littleboy.temporal` package is a set of **pure, typed data structures**
(depending only on `core.enums`, so `core.models` can embed them with no import
cycle) plus deterministic scoring functions. Nothing here predicts the future or
calls a model; every number is an **operational estimate under uncertainty**, and
the result always carries its own uncertainty, warnings, and missing data.

An `ActionCase` may now carry four optional temporal inputs:

- `consequences` — a `ConsequenceSet` of per-horizon `ConsequenceEstimate`s
  (see [`CONSEQUENCE_MODELING.md`](CONSEQUENCE_MODELING.md));
- `temporal_profile` — coarse, directly-supplied per-horizon coercion estimates;
- `reversibility_profile` — how fully, at what cost, and with what residual harm
  the action could be undone over time;
- `cumulative_coercion_profile` — how a single small coercion could become
  serious if repeated or normalised (see
  [`CUMULATIVE_COERCION.md`](CUMULATIVE_COERCION.md)).

A case may also be flagged `is_inaction = True`, so that *not acting* can be
judged as a choice rather than a neutral default.

## Time horizons

`TimeHorizon` is **semantic, not a fixed duration**: `immediate`, `short_term`,
`medium_term`, `long_term`, and `unknown`. Per-horizon coercion is computed as

```
coercion(horizon) = clamp( base_coercion + Σ (delta × probability) )
```

over the consequences at that horizon, then raised (never lowered) by any
directly-supplied `temporal_profile` phase. The horizons are combined into an
`expected_total_coercion` with deliberate, documented weights (immediate 0.30,
short 0.25, medium 0.20, long 0.25 — see `horizon.py`), and the cumulative score
can only raise that total, never lower it.

## The temporal patterns it distinguishes

`project_temporal` produces a `TemporalProjectionResult` that names the ethically
important shapes a coercion-over-time curve can take:

- **trend** — `rising` (long-term exceeds immediate by > 0.10), `falling`,
  `stable`, or `unknown`. A *rising* trend with low immediate coercion is the
  signature of the unstable action in the thesis above.
- **`prevents_greater_future_coercion`** — a credible, adequately-evidenced
  future *reduction* in coercion (an action that hurts now to prevent worse).
- **`creates_long_term_dependency`** — the cumulative profile shows real
  dependency-creation risk.
- **`reversible_now_irreversible_later`** — reversible at the moment but with
  medium/long-term consequences that are hard to undo.
- **`high_risk_unknowns`** and **`uncertainty`** — high-impact claims resting on
  weak evidence, so the projection refuses to look certain.

## How it integrates (it does not replace the evaluator)

The `EthicalEvaluator` computes the immediate coercion score exactly as before,
then calls `project_temporal(base_coercion=…, consequences=…, …)` and attaches a
`temporal_projection` to the report. Six rules consume it (inert — `NOT_APPLICABLE`
— whenever a case has no temporal data, so every pre-v0.7 case behaves
identically):

| Rule | Name | What it does |
|------|------|--------------|
| **LB-R019** | Temporal Consequence | Downgrades when long-term coercion is high (×2) or moderate-and-rising (×1), even if immediate coercion is low. |
| **LB-R020** | Reversibility v2 | Irreversible coercion without justification is downgraded; unknown reversibility lowers confidence (complements, does not replace, LB-R010). |
| **LB-R021** | Cumulative Coercion | Downgrades when repetition/normalisation make cumulative coercion high (×2) or moderate (×1). |
| **LB-R022** | Inaction Is Not Neutral | If a flagged inaction permits coercion to continue or grow, caps the verdict at `ETHICALLY_SUSPICIOUS`. |
| **LB-R023** | Future Coercion Prevention | High present coercion is *qualifiedly* justified only if it credibly prevents greater future coercion **and** meets the Axiom 3 conditions. |
| **LB-R024** | Temporal Uncertainty | High-impact, weakly-evidenced temporal claims reduce confidence (more strongly under stricter policy) and expose the missing data. |

The comparison engine also gains an **immediate-term ranking** and a
**long-term ranking**; when they disagree it sets `rankings_conflict` and warns
that the right choice depends on which time horizon matters most.

## Limitations

- Temporal estimates are **inputs**, not measurements. LittleBoy does not forecast
  consequences; it reasons transparently about the estimates it is given.
- Horizon weights and thresholds are **operational parameters**, not moral
  constants; they live in one place and are auditable.
- A `rising` trend or a low `reversibility_score` is a *flag for scrutiny*, not a
  verdict. The verdict still comes from the full rule synthesis under the policy.
- The module makes **no** prediction-certainty claims and never collapses
  temporal uncertainty into a single confident number.
