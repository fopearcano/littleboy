# LittleBoy adversarial audit (v0.8)

> **A rational ethical engine must not merely evaluate actions. It must also
> evaluate the conditions under which the action is being described.**
> LittleBoy must judge not only the action, but also the description through
> which the action becomes visible.

## Why audit the description, not only the action

Every verdict LittleBoy produces is only as good as the case it was given. But a
case is a *description*, and descriptions can be shaped — honestly or
adversarially — to lead a conclusion. A coercive action can be framed as gentle;
consent can be recorded where none was freely given; alternatives can be hidden;
vulnerability can be omitted; weak evidence can be presented as settled fact; and
fluent, confident language can make a manipulative message feel trustworthy. An
engine that judged only the supplied fields, taking them at face value, would be
trivially manipulable.

The `littleboy.audit` module is LittleBoy auditing *itself against its inputs*. It
asks: **if someone were trying to lead this verdict, what would the description
look like — and does it look like that?** It is deterministic, typed, and fully
auditable; there is no NLP/ML and no hidden classifier. Every finding cites what
it saw and what to ask next. The indicators are **risk flags, not proofs**.

## What it inspects

Given an `ActionCase` (and, where available, the language analysis, evidence,
temporal projection, or a whole comparison), the audit produces:

- **`AuditFinding`s** — named, severity-graded observations
  (`info` / `warning` / `serious` / `critical`), each with the fields it concerns,
  *why it matters*, and recommended questions. Findings at `serious`/`critical`
  are surfaced as **red flags**. See [`RED_FLAGS.md`](RED_FLAGS.md).
- **`AdversarialRiskProfile`** — twelve 0..1 indicators of *leading* description:
  leading language, missing counterevidence, one-sided description, false
  necessity / dichotomy, fake alternatives, hidden power asymmetry, hidden
  vulnerability, consent contamination, ideological capture, overconfidence, and
  data laundering.
- **`BiasProfile`** — ten 0..1 indicators that the *framing* may tilt the
  judgment. See [`BIAS_TESTING.md`](BIAS_TESTING.md).
- **`StressTestResult`s** — adversarial 'what if' questions (below).

## Adversarial stress tests

The `AdversarialStressTester` turns the risk profile into concrete questions a
sceptic would ask, each with a plausibility and whether the verdict *could change*
if the assumption held:

- What if the acting agent is **underreporting the coercion**?
- What if the **consent is contaminated** (uninformed, involuntary, coerced)?
- What if the **affected agent's testimony is missing**?
- What if **less-coercive alternatives exist but were not disclosed**?
- What if the **description is worded to lead** LittleBoy toward a verdict?
- What if the **long-term consequences are worse** than described?
- What if an option is "least coercive" **only because data about it are missing**?

It does not assert the assumption is true; it asks whether the judgment would
survive it, and names the data that would settle the question.

## Ideological-capture checks

LittleBoy's axiom is *evil = coercion*. The audit also checks whether that axiom
is being **applied too narrowly or as a slogan** — distorted application, not the
axiom itself. Using a small, documented phrase lexicon (so every hit cites its
phrase), it flags: coercion modelled as *only* physical force while the narrative
names economic / social / informational / dependency pressure; "care" or
"protection" used to justify paternalism; "freedom" language over real social
pressure; "safety"/"security" used to normalise standing domination;
"natural"/"traditional" used to excuse coercion; "autonomy"/"they agreed" used to
wave away vulnerability; and "the greater good" used to hide individual coercion.

## How the audit affects a verdict

The audit is **opt-in** (`evaluate(case, audit=True)`), so default evaluation —
and every pre-v0.8 case — is unchanged. When enabled, the rule-engine trace is
left intact and the audit is recorded as a separate, clearly-labelled layer
(`report.audit_report`, plus `[audit]` warnings). A *critical* red flag then
bears on the verdict, deterministically (see
`audit.adversarial.audit_adjusted_verdict`):

| Condition | Effect |
|-----------|--------|
| critical red flag + high coercion | cannot confidently approve (capped at `ETHICALLY_SUSPICIOUS`) |
| critical red flag + irreversible action | blocked: `INSUFFICIENT_DATA` |
| critical red flag + consent central | consent-integrity warning; treat consent as unestablished |
| high ideological-capture risk | requires explicit human review |
| high language-beauty bias risk | warns that persuasive (or poor) form may be distorting judgment |

Any critical finding marks the judgment **unstable** and crushes confidence: the
report says so in plain language rather than presenting a settled verdict.

## How it integrates

The audit is usable from each layer: `EthicalEvaluator.evaluate(case, audit=True)`,
`ComparisonEngine.compare(set, audit=True)` (see below), `CaseBuilder.audit(case)`,
and the CLI: `littleboy audit <case.json>`, `littleboy evaluate … --audit`,
`littleboy compare … --audit`.

For comparisons, the audit runs per option **and** across the set: it flags a
top-ranked option with unresolved blockers, a ranking that depends on missing
data, an option that may lead only because negative data about it are absent, a
better-evidenced option ranked lower (framing bias), and options compared as
equivalents despite different goals. **If the best option wins mostly because data
about its competitors are missing, the ranking is marked unstable.**

## Limitations

- These are **indicators, not proofs**. A red flag means "look here", not "this is
  manipulation/bias". The audit can both miss and misfire.
- Phrase-lexicon checks (ideological capture, manipulation) match literal
  substrings; they miss paraphrase and can trip on quotation.
- The verdict adjustments are deliberate, documented heuristics, not moral
  constants; they only apply when the audit is explicitly enabled.
- The goal is to make LittleBoy **harder to manipulate, not more dogmatic**: the
  audit exposes risk and asks questions; it does not impose a conclusion.
