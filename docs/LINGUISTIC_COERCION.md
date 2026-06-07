# LittleBoy linguistic coercion (v0.5)

This document lists the manipulation dimensions LittleBoy models, how each is
detected, and how they combine into a linguistic-coercion score. Everything here
is deterministic and transparent — there is no NLP/ML.

## The manipulation dimensions

| Dimension | What it is | Example |
|-----------|------------|---------|
| **Informational manipulation** | False, incomplete, distorted, or selectively framed information that bends the target's will. | omitting the real risks |
| **False necessity** | Presenting an action as unavoidable when alternatives exist. | "You have no choice." |
| **False dichotomy** | Collapsing the field to two options when more exist. | "Either you obey or you destroy everything." |
| **Shame pressure** | Using humiliation, guilt, or moral degradation to force compliance. | "A good person would just do it." |
| **Fear pressure** | Using threat, panic, catastrophe, or exaggerated risk. | "Act now before it's too late." |
| **Authority capture** | Using status, position, jargon, or prestige to suppress questioning. | "You're not qualified to judge this." |
| **Semantic compression** | Reducing a complex human state to a crude label. | "He just wants to die." |
| **Testimonial injustice** | Dismissing a subject's testimony because of status, identity, vulnerability, or illness. | "She's just being dramatic." |
| **Obfuscation** | Being needlessly obscure where clarity is ethically required. | dense legalese on a binding notice |
| **Persuasive counterfeit** | Making weak/harmful content look valuable through rhetorical technique. | hype that dresses up an empty offer |

> The LittleBoy thesis on technique: **technique can make worthless content
> appear precious, and can make precious content disappear if poorly expressed.**
> That is exactly why language is ethically load-bearing.

## How indicators are obtained

Two transparent sources, merged (a detection can only *raise* an indicator):

1. **Explicitly supplied** — a `LanguageEthicsProfile` on the `LanguageAct`
   carries the indicators directly. This is the primary, reliable input.
2. **Detected from text** — a small, documented lexicon
   (`littleboy/language/manipulation.py`) matches literal phrases and maps each
   to risk axes, always reporting the exact phrase as evidence (a
   `ManipulationFinding`).

## How the linguistic-coercion score is computed

`score_linguistic_coercion(profile, context)`:

1. `means` = soft-OR of the nine risk axes plus deception (`1 - truthfulness`)
   and loss of agency (`1 - agency_respect`) — *how coercive the words are*;
2. `amplifier` = `1 + mean(power_asymmetry, target_vulnerability, urgency,
   stakes)` — *context makes the same words more coercive*;
3. `mitigation` from agency respect and consent support pulls it back down;
4. `score = clamp(means × amplifier × (1 − 0.4·mitigation), 0, 1)`.

The score is a heuristic, not a measurement. Some worked consequences:

- high **fear pressure** + high **target vulnerability** + high **power
  asymmetry** → high linguistic coercion;
- low **clarity** + high **stakes** + high **urgency** → warning;
- high **ambiguity** in a consent/legal/educational context → warning;
- high **manipulation risk** + high **power asymmetry** → severe warning;
- high **false necessity** with unknown alternatives → severe warning;
- high **alternative visibility** + high **agency respect** → constructive.

## The language rules (LB-R013 .. LB-R018)

| Rule | Fires when | Effect |
|------|-----------|--------|
| LB-R013 Linguistic Coercion | language materially restricts agency/consent/alternatives/expression | downgrade, counted as coercion |
| LB-R014 Manipulative Framing | false necessity / false dichotomy / shame / fear ≥ 0.5 | downgrade |
| LB-R015 Consent-Language Integrity | consent is sought/affected via unclear or manipulative language | reduce consent quality; **cap** approval if consent is "given" on manipulative language |
| LB-R016 Testimonial Injustice | language dismisses/compresses a vulnerable subject's testimony | warn (downgrade under high vulnerability) |
| LB-R017 Constructive Language Duty | Type II agent, language central, stakes ≥ moderate | expect constructive language; warn if not |
| LB-R018 Obfuscation Under High Stakes | obscure language where clarity is required (consent/legal/educational/high stakes) | downgrade |

These run in the same rule engine, under the same policy profiles, and appear in
the same `reasoning_trace` as every other rule.

## Bridge to the main coercion model

`language_to_coercion_profile` maps the analysis onto a `CoercionProfile`
(deception/omission → `informational_manipulation`; shame/fear/silencing →
`psychological_pressure`; linguistic coercion → `severity`; context →
`reversibility`). `merge_coercion_profiles` merges it with any base profile by
taking the **maximum** per channel — language can only *raise* coercion. The
evaluator then scores the merged profile, so linguistic coercion flows through
the whole engine.
