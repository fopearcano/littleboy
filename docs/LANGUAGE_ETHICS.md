# LittleBoy language ethics (v0.5)

> **Language is ethically decisive because it can either expand or restrict the
> field in which will, consent, and self-understanding become possible.**

## Why language is ethically relevant

LittleBoy's foundational axiom is that the fundamental ethical evil is coercion.
Language is not ethically neutral, because language is one of the most powerful
ways to *coerce* — or to *free*. The same words can:

- **clarify** or **obscure**;
- **disclose** or **omit**;
- **make alternatives visible** or **hide them** ("you have no choice");
- **invite reply** or **silence** it;
- **respect** a person's own account or **compress and dismiss** it;
- **support** genuine consent or **manufacture** it under pressure.

So language bears directly on the axioms: it can restrict the field of choice
(Axiom 2), manufacture or undermine consent, and replace a subject's own framing
of their will with someone else's.

## How language can become coercive

The module models linguistic coercion as a profile
(`LanguageEthicsProfile`) with **quality** axes (clarity, truthfulness,
specificity, context completeness, agency respect, consent support, constructive
potential — higher is better) and **risk** axes (manipulation risk, shame
pressure, fear pressure, false necessity, false dichotomy, loaded language,
omission risk, ambiguity, silencing effect — higher is worse).

A `LanguageContext` (medium, power asymmetry, urgency, target vulnerability,
stakes, reversibility, audience scope) does not make words coercive on its own,
but it **amplifies** them: the same sentence is far more coercive said to a
vulnerable person, under a power asymmetry, at high stakes.

See [`docs/LINGUISTIC_COERCION.md`](LINGUISTIC_COERCION.md) for the specific
manipulation dimensions (false necessity, false dichotomy, shame/fear pressure,
authority capture, semantic compression, testimonial injustice, obfuscation,
persuasive counterfeit) and how they are detected and scored.

## How constructive language is assessed

Constructive language is language that **expands** the field of will. A
`ConstructiveLanguageAssessment` scores: clarifying effect, agency support,
consent support, uncertainty transparency, alternative visibility, and an
overall constructive score, plus a deterministic, templated
`recommended_rewrite` (no LLM rewriting). Constructive language increases
clarity, preserves agency, makes alternatives visible, reduces unnecessary
fear/shame, distinguishes facts from interpretation and certainty from
uncertainty, exposes missing data, allows disagreement, improves consent and
self-expression, and makes the subject **more** visible rather than less.

## How linguistic coercion affects consent

Consent obtained through unclear, manipulative, incomplete, or high-pressure
language is consent of **reduced quality**. LittleBoy treats this directly:

- the language analysis flags `affects_consent`;
- rule **LB-R015 (Consent-Language Integrity)** reduces consent quality and,
  when consent is reported as *given* on top of manipulative language, **caps the
  verdict** so there is no confident approval.

## How language integrates with the main coercion model

If a case contains a `language_act`, the evaluator:

1. analyses it (`analyze_language`) into a full, auditable `LanguageAnalysis`;
2. **folds its linguistic coercion into the main `CoercionProfile`** via
   `language_to_coercion_profile` + `merge_coercion_profiles` (deception/omission
   raise `informational_manipulation`; shame/fear/silencing raise
   `psychological_pressure`; the merge can only *raise* coercion, never lower it);
3. runs the six language rules (LB-R013 .. LB-R018) alongside the rest;
4. records the analysis in the report (`language_analysis`) and surfaces its
   warnings, missing data, and recommended questions.

So manipulative language is treated as the coercion it is — it flows through the
same axioms, rule engine, policy profiles, and reasoning trace as any other
coercion.

## Limitations of deterministic, non-LLM analysis

- Detection of manipulation from raw text uses a **small, transparent lexicon**
  of literal phrases (see `littleboy/language/manipulation.py`). It will miss
  paraphrases and can misfire on quotation or discussion of those phrases.
- The primary, reliable input is the **explicitly supplied**
  `LanguageEthicsProfile`; text detection only *raises* indicators and always
  reports the exact phrase that triggered it.
- The scores are **heuristic indicators, not measurements** and not absolute
  moral truths.
- LittleBoy makes **no legal, medical, clinical, or linguistic-forensic claims**.

## Future direction

A later version may offer **optional** LLM-assisted indicator extraction — but
only behind an explicit flag, with the model's suggested indicators shown,
attributed, and editable, so the audit trail (which phrase raised which
indicator, and why) is preserved. The deterministic core must remain usable and
authoritative on its own.
