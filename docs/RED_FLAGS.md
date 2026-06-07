# LittleBoy red flags (v0.8)

> A red flag is a **transparent, rule-based observation** about how a case is
> described or evidenced — never a hidden classifier. It names what was seen,
> which fields it concerns, why it matters, and what to ask next.

## What a red flag is

Every red flag is an `AuditFinding`: a `finding_id`, a title and description, a
`severity` (`info` / `warning` / `serious` / `critical`), a `category`, the
`evidence` and `affected_fields` it rests on, a *why it matters*, recommended
questions, and a confidence (how sure the audit is the risk is real — an
indicator, not a proof). Findings at `serious` or `critical` are the report's
**red flags**; a `critical` flag marks the judgment **unstable**. The detectors
are pure functions over an `ActionCase` (and, where available, its language
analysis, evidence, temporal projection, or a comparison result): they only
*read* attributes and *construct* findings.

## Consent red flags

- **Dimensions unestablished** — consent is "given" but one or more of
  informed/voluntary/specific/revocable is unknown (`AUD-CONSENT-DIMENSIONS`).
- **Not communicated by the agent** — consent attributed to someone other than
  the affected agent (`AUD-CONSENT-NOT-BY-AGENT`, **critical**).
- **Under a power asymmetry** — consent given under a steep power imbalance
  (`AUD-CONSENT-POWER`).
- **Under high vulnerability** — consent from a highly vulnerable agent
  (`AUD-CONSENT-VULNERABILITY`).
- **Contaminated by language** — consent affected by manipulative or unclear
  language under pressure: possible *false consent* (`AUD-CONSENT-CONTAMINATION`,
  **critical**).

## Coercion red flags

- **Low coercion, manipulative language** — the structured coercion profile looks
  low while the actual wording is highly manipulative (`AUD-COERCION-LANG-INCONSISTENCY`).
- **No cessation condition** — a coercion justification with no defined stopping
  point (`AUD-COERCION-NO-CESSATION`).
- **Necessity without alternatives** — coercion claimed "necessary" though no
  less-coercive alternative was analysed (`AUD-COERCION-NECESSITY-NO-ALT`).
- **Temporary but reversibility unknown** — coercion claimed reversible while
  reversibility is uncharacterised (`AUD-COERCION-TEMP-NO-REV`).

## Evidence red flags

- **High stakes, weak evidence** (`AUD-EVID-HIGH-STAKES-WEAK`).
- **Contested evidence present** — ensure it was not waved through (`AUD-EVID-CONTESTED`).
- **Irreversible action, weak evidence** — the most dangerous combination
  (`AUD-EVID-IRREVERSIBLE-WEAK`, **critical**).
- **Only self-sourced** — every item comes from the acting agent (`AUD-EVID-SELF-SOURCED`).
- **No counterevidence** — a coercive action with nothing contesting or
  corroborating it (`AUD-EVID-NO-COUNTER`).

## Language red flags

False necessity, false dichotomy, shame pressure, fear pressure
(`AUD-LANG-*`); framing replacement via semantic compression or testimonial
injustice (`AUD-LANG-FRAMING-REPLACEMENT`); authority used to suppress
questioning (`AUD-LANG-AUTHORITY-CAPTURE`); and the **persuasive counterfeit** —
appealing form carrying manipulative content (`AUD-LANG-PERSUASIVE-COUNTERFEIT`).
Severity rises with the context amplifiers (power asymmetry, vulnerability).

## Temporal red flags

- **Hidden long-term coercion** — a low immediate cost over a rising long-term
  trend (`AUD-TEMPORAL-HIDDEN-LONG-TERM`).
- **Cumulative risk ignored** — a coercive action with no temporal/cumulative
  modelling (`AUD-TEMPORAL-CUMULATIVE-IGNORED`).
- **Inaction treated as neutral** — without evidence of what it permits
  (`AUD-TEMPORAL-INACTION-NEUTRAL`).
- **Reversible now, irreversible later** (`AUD-TEMPORAL-REV-NOW-IRREV-LATER`).
- **Low-confidence long-term predictions** (`AUD-TEMPORAL-LOWCONF-PREDICTION`).

## Comparison red flags

- **Top option has blockers** (`AUD-CMP-TOP-BLOCKERS`).
- **Ranking depends on missing/close data** (`AUD-CMP-DATA-SENSITIVE`).
- **Advantaged by missing data** — the leader has more gaps than a competitor; its
  lead may reflect what is unknown (`AUD-CMP-ADVANTAGED-BY-MISSING-DATA`).
- **Framing bias** — a lower-ranked option is better evidenced and no more coercive
  (`AUD-CMP-FRAMING-BIAS`); or the leader shows high language-beauty bias
  (`AUD-CMP-TOP-BEAUTY-BIAS`).
- **Goals not equivalent** — options for different declared goals compared as if
  interchangeable (`AUD-CMP-GOALS-NOT-EQUIVALENT`).

## Ideological-capture red flags

Distorted *application* of the coercion axiom (category `ideological_capture`):
care-as-control, freedom-as-pressure, safety-as-domination,
natural/traditional normalisation, autonomy-ignoring-vulnerability,
utility-hiding-coercion, and physical-force tunnel vision. Each cites the phrase
or structural fact that triggered it. See
[`ADVERSARIAL_AUDIT.md`](ADVERSARIAL_AUDIT.md).

## How red flags reach the verdict

Red flags are surfaced as `[audit]` warnings on the report. Under an enabled
audit, a **critical** flag is what can change the verdict (block an irreversible
action, cap a coercive one at suspicious, flag consent as unestablished) and marks
the judgment unstable. Everything below critical informs and lowers confidence
rather than overriding the rule engine. The detectors are conservative on purpose:
the aim is to make LittleBoy harder to manipulate, not to convict every case.
