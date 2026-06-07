# LittleBoy value of information (v0.9)

> Among the things LittleBoy does not know, **which single one — if resolved —
> would most change the verdict?** Answered not by guessing, but by re-running the
> deterministic evaluator under explicit counterfactual resolutions.

## The idea

When a verdict rests on an unknown, the honest next question is not "what is my
confidence?" but "*what would I most need to learn?*". The value of information
(VoI) ranks the case's unknowns by how much resolving each would move the
outcome. Crucially, LittleBoy does not estimate this with a probability model — it
**measures** it, by actually resolving each unknown to each plausible value and
re-evaluating. Every number traces to a concrete, auditable re-run; nothing is
invented.

## Probes

A *probe* is one unknown plus the concrete resolutions to try. A probe fires only
when the fact is **genuinely unknown**, so a fully-specified case yields no probes
and is reported as information-stable. The built-in probes are:

| Probe | Fires when | Resolutions tried |
|-------|-----------|-------------------|
| `acting_agent.agent_type` | the agent type is unknown | Type II / Type I |
| `consent` | consent is `UNKNOWN` | GIVEN / REFUSED |
| `coercion.reversibility` | a coercion profile has unknown reversibility | 1.0 / 0.0 |
| `available_alternatives` | alternatives were never analysed | a feasible less-coercive option / none |
| `data_quality` | neither a data-quality profile nor evidence was supplied | a good profile |
| `justification` | a justification has unresolved Axiom 3 conditions | all established / refuted |
| `consequences` | a coercive action has no temporal/consequence model | worse long-term / benign long-term |

Each probe mutates a **copy** of the case (the original is never touched) and
hands it to the same `EthicalEvaluator`.

## Scoring the swing

For a probe, let the baseline verdict/confidence be the case as given. For each
resolution we re-evaluate and measure:

- **verdict distance** — a 0..1 ordinal gap between verdicts
  (`ACCEPTABLE` 0 … `NOT_ACCEPTABLE` 3, scaled by 3); crossing into or out of
  `INSUFFICIENT_DATA` counts as the maximal 1.0, because resolving the data gate
  is a categorical change;
- **confidence distance** — the absolute change in confidence.

The probe's value is `0.7 × max(verdict_distance) + 0.3 × max(confidence_distance)`
over its resolutions, clamped to `[0, 1]`. The unknown with the highest value is
the `most_informative` one; ties break toward whichever actually *changes* the
verdict. The report records, per probe, every resolution's verdict and confidence
and a one-line `swing` summary (e.g. *"verdict can move from
ACCEPTABLE_WITH_RESERVATIONS to ETHICALLY_SUSPICIOUS depending on the
resolution"*).

## Multi-fact value of information (v0.10)

Single-fact VoI treats each unknown alone. But a verdict can survive every single
resolution yet flip when two (or more) facts move **together**. `minimal_flip_sets`
finds the *smallest combination* of unknowns whose joint resolution changes the
verdict:

- probes expose their resolutions as *transforms* (`case -> case`) over distinct
  fields, so resolutions of different unknowns **compose**;
- the search tries combinations of increasing size (1, 2, … up to a small bound)
  and, for each, the cartesian product of the chosen unknowns' resolutions,
  re-evaluating each joint counterfactual;
- it **stops at the first size that yields a flip**, so every returned set is
  *minimal*: no proper subset flips the verdict on its own. A single pivotal fact
  yields a size-1 set; a genuinely interacting pair yields a size-2 set.

`smallest_flip_size` is the size of the smallest sufficient set, or `None` when no
combination up to the bound changes the verdict (the verdict is *robust to
combinations*). This drives the minimal-sufficient-case planner
(see [`MINIMAL_SUFFICIENT_CASE.md`](MINIMAL_SUFFICIENT_CASE.md)).

## Comparisons

For a comparison, the same probes are applied to each option's case; the comparison
is re-run with that one option mutated, and the value reflects whether the
**winner changes** (1.0), whether the ranking merely reorders (0.4), or neither
(0.0). The result is the single (option, fact) pair whose resolution would most
change the recommended choice — a precise version of the comparison engine's
"what could change the ranking". **If the most informative fact changes the
winner, the ranking is reported as not robust.**

## Worked example

`examples/voi_consent_pivotal.json` is moderate-coercion, well-evidenced,
reversible, and fully specified **except** for consent. Deliberation reports
`consent` as the single most informative unknown: GIVEN →
`ACCEPTABLE_WITH_RESERVATIONS`, REFUSED → `ETHICALLY_SUSPICIOUS`. In
`examples/comparison_voi_pivotal.json`, resolving one option's unknown flips which
option wins, so the ranking is reported as not robust.

## Limitations

- VoI is computed over a **finite, documented set of probes**. Single-fact VoI
  ranks each unknown alone; multi-fact search finds minimal *combinations* up to a
  small size bound (default 3), but will not find a sufficient set larger than the
  bound, nor one involving an unknown that has no probe.
- The resolutions are deliberate counterfactuals, not a calibrated probability
  distribution; the value is a decision-relevance score, not expected information
  gain in bits.
- Probing re-runs the evaluator many times (and the multi-fact search re-runs it
  over subsets and their joint resolutions); it is intended for one case (or a
  small comparison set) at a time, not bulk scoring.
