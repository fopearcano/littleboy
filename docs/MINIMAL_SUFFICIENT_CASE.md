# LittleBoy minimal-sufficient-case planning (v0.10)

> Don't ask for everything that is missing — ask only for **what could change the
> verdict**, smallest set first, in priority order.

## Why "minimal sufficient" beats "complete"

The case builder (v0.4) asks for everything a case lacks. But many gaps cannot
change the verdict: resolving them only nudges confidence. Asking for them wastes
the user's effort and buries the questions that actually matter. The
minimal-sufficient-case planner uses the value-of-information machinery
(see [`VALUE_OF_INFORMATION.md`](VALUE_OF_INFORMATION.md)) to keep only the
unknowns whose resolution — alone, or in a minimal combination — could flip the
verdict, and orders them by priority.

## Single- and multi-fact value of information

Two searches, both by re-running the **deterministic** evaluator under explicit
counterfactual resolutions (no probabilities invented):

- **single-fact**: for each unknown alone, does resolving it change the verdict?
- **multi-fact**: what is the *smallest set* of unknowns whose **joint**
  resolution changes the verdict? `minimal_flip_sets` searches combinations of
  increasing size and stops at the first size that yields a flip, so every set it
  returns is **minimal** — no proper subset flips the verdict on its own. Some
  verdicts survive every single resolution yet flip when two facts move together;
  those produce a size-2 minimal set.

`smallest_flip_size` is the size of the smallest sufficient set (`None` if no
combination up to the search size changes the verdict — the verdict is *robust*).

## The question plan

`plan_minimal_questions` (exposed as `Deliberator.question_plan` and
`CaseBuilder.minimal_questions`) returns a `MinimalQuestionPlan` of
`PlannedQuestion`s. A question is included only if it could change the verdict:

| Priority | When |
|----------|------|
| **critical** | resolving this unknown *alone* changes the verdict |
| **high** | this unknown is a member of a minimal flip set of size ≥ 2 (it must be answered together with the others in the set) |

Questions that can only move confidence — never the verdict, alone or in any
minimal combination — are **omitted**: answering them cannot settle the case.
Questions are ordered critical-first, then by value of information. Each carries
its `field`, a question-builder `category`, the *why it matters*, the related
axioms, and whether it acts alone or in a set.

```bash
littleboy questions examples/voi_consent_pivotal.json --minimal
```

```text
MINIMAL QUESTION PLAN (only what could change the verdict)
  current verdict=ACCEPTABLE_WITH_RESERVATIONS  confidence=0.52  verdict_robust=False
  smallest sufficient set: 1 question(s)

Questions:
  [critical/consent] Did the affected agent give, or refuse, valid consent?  (value 0.26; alone changes the verdict)
      why it matters: Consent bears directly on coercion (A0/A2) ...
```

When the verdict is robust to every searched combination, the plan is empty and
says so — there is no question worth asking to change the verdict (though some may
still raise confidence).

## Cheapest, not just smallest (v0.11)

Not every answer costs the same to obtain: stating who consented is cheap;
gathering corroborated evidence or forecasting long-term consequences is
expensive. So "smallest set" (fewest questions) is not always "least effort". The
planner attaches a `cost` to each question (`DEFAULT_QUESTION_COSTS`, overridable)
and `cheapest_flip_set` searches *all* sufficient sets up to the size bound for the
one with the **lowest total cost**. Two cheap questions can beat one expensive one:

- `minimal_flip_sets` → `{data_quality}` (one question, but expensive);
- `cheapest_flip_set` → `{consent, reversibility}` (two questions, cheaper total).

The plan exposes `cheapest_set` / `cheapest_set_cost`, marks each question
`in_cheapest_set`, and orders the cheapest-set members first — so following the
plan top-down walks the least-cost path to a settled verdict. With uniform costs
the cheapest set collapses back to the smallest.

## Interactive minimal intake

`run_minimal_intake` (behind `littleboy build-case --minimal --from <case.json>`)
turns the plan into a loop: ask the top (cheapest, verdict-relevant) question,
apply the answer, **re-plan on the updated case**, and repeat until the verdict is
**settled** — no remaining unknown could change it — or a question budget is hit.
Re-planning after each answer matters: resolving one fact can make a second fact
newly decisive (or newly irrelevant), so the next question is chosen against the
*current* state, not a fixed list. The loop is I/O-free (it takes an answer
callback), so it is deterministic and testable; the CLI supplies a prompt, tests
supply a script. Each step records the answer and the verdict after it, and the
transcript says why it stopped.

## How it connects to the case builder

`CaseBuilder.minimal_questions(case)` delegates to the planner (lazily, to avoid
an import cycle with the evaluator). So the same builder that asks "what is
missing?" (`generate_questions`) can now ask "what is *worth asking*?"
(`minimal_questions`), and `build-case --minimal` drives the interactive loop. The
completeness report remains for exhaustive intake; the minimal plan is for getting
to a decision with the fewest (or cheapest) answers.

## Limitations

- The search is over the finite, documented probe set (consent, agent type,
  reversibility, alternatives, data quality, the Axiom 3 conditions, and the
  consequence profile) and combinations up to a small bound (default 3), so it
  will not find a sufficient set larger than that bound, nor one involving an
  unknown without a probe.
- Probes are independent transforms over distinct fields; the search assumes their
  resolutions compose cleanly (they touch different parts of the case).
- "Could change the verdict" is judged against the discrete verdict labels; a
  large confidence swing that does not cross a verdict boundary is, by design, not
  counted as a flip.
- The question costs are **operational defaults**, not measured effort; they exist
  to order questions and are meant to be overridden per use.
- The interactive loop re-plans greedily after each answer (it asks the current
  cheapest question, not a globally cost-optimal questionnaire), and a free-text
  answer it cannot parse leaves the case unchanged, so that field is asked at most
  once.
