# LittleBoy cumulative coercion (v0.7)

> A coercion that is trivial once can be **systemic** when it repeats, normalises,
> creates dependency, sets precedent, escalates, or spreads to more people.

## Why a small coercion can still be serious

Judged in isolation, a single mild nudge, fee, or restriction may look
negligible. But the same act can become ethically serious over time if it is
*designed or likely to recur* and to **entrench**. A one-off becomes a norm; a
norm becomes a policy; a policy becomes an institution that trains people to
accept coercion as ordinary. LittleBoy models this explicitly so that "it's only
a small thing each time" cannot launder an action whose real ethical weight lives
in its repetition.

## The cumulative profile

`CumulativeCoercionProfile` separates the **base** coercion from the
**amplifiers** that make repetition dangerous:

| Field | What it captures |
|-------|------------------|
| `single_action_coercion` | the coercion of one instance, `[0, 1]` |
| `repetition_likelihood` | how likely the action is to recur, `[0, 1]` |
| `normalization_risk` | risk it becomes an accepted norm |
| `precedent_risk` | risk it sets an institutional precedent |
| `dependency_creation_risk` | risk affected agents become dependent |
| `institutionalization_risk` | risk it hardens into standing policy |
| `escalation_risk` | risk it grows more coercive over time |
| `affected_population_growth` | risk it spreads to more agents |

## How it is scored

`score_cumulative_coercion` is deliberately simple and transparent:

```
amplifiers = soft_or(normalization, precedent, dependency,
                     institutionalization, escalation, population_growth)
repetition_gate = 0.5 + 0.5 × repetition_likelihood
score = single + (1 − single) × amplifiers × repetition_gate      (clamped 0..1)
```

The design choices are intentional:

- **`single` is the floor.** Cumulative coercion is never *less* than the
  single-action coercion; repetition can only add to it.
- **`soft_or` combines the amplifiers** as independent risks
  (`1 − Π(1 − vᵢ)`), so several moderate systemic risks compound the way real
  entrenchment does, instead of being averaged away.
- **Repetition gates the amplifiers.** With no repetition, the systemic risks
  still count for half (a precedent matters even if rarely invoked); with high
  repetition they count fully. Repetition alone, with no amplifiers, barely moves
  the score — recurrence is dangerous *because* of what it entrenches.

So an action with `single = 0.15` but high repetition, normalisation, precedent,
and institutionalisation scores well above 0.5 — systemic — even though any one
instance is mild.

## How it enters a verdict

The score becomes the projection's `cumulative_coercion` and can only **raise**
the `expected_total_coercion`, never lower it. Rule **LB-R021 (Cumulative
Coercion Rule)** then acts on it under the active policy:

- `cumulative ≥ max_coercion_for_acceptable` → **downgrade ×2** (a small coercion
  has become systemic);
- `cumulative ≥ coercion_moderate` → **downgrade ×1**;
- otherwise present-but-low → a warning, not a downgrade.

`dependency_creation_risk ≥ 0.5` additionally sets the projection's
`creates_long_term_dependency` flag and a corresponding warning, because creating
dependency is one of the most durable ways to entrench coercion.

The worked example is
[`examples/temporal_cumulative_policy_risk.json`](../examples/temporal_cumulative_policy_risk.json):
a `social_pressure = 0.15` institutional action that, once its repetition and
normalisation are considered, is judged `NOT_ACCEPTABLE`.

## Limitations

- The amplifier values are **estimates supplied to** LittleBoy. It reasons about
  the entrenchment risk you describe; it does not predict adoption curves.
- The gate and weights are operational parameters in one auditable function, not
  moral constants.
- A high cumulative score is a flag that an action's ethical weight lies in its
  *pattern*, not its instance — it is an input to the verdict, not the verdict.
