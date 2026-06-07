# LittleBoy scenario templates (v0.4)

A **scenario template** (`ScenarioTemplate`) captures the *shape* of a common
kind of ethical case. It tells the case builder which fields usually matter,
which coercion dimensions are typical, what evidence is usually needed, what
alternatives to consider, and which extra questions are worth asking.

Templates do two things to question generation:

1. they **raise the priority** of the categories they emphasise (e.g. the
   medical template bumps consent/alternatives/vulnerability/reversibility); and
2. they **add their own questions** (e.g. the language-manipulation template asks
   directly about misleading or manipulative information).

> These are **ethical** templates only. They make **no** legal, medical,
> clinical, or regulatory claims. The `medical_decision` template asks about
> consent and alternatives as *ethical* matters (is the will of the affected
> person respected, is there a less-coercive option?), not about standards of
> care.

## The ten templates

| Template | What it is for | Emphasises |
|----------|----------------|------------|
| `generic_action` | Any action with no special structure (the base questions). | — |
| `medical_decision` | A care decision affecting a patient. | consent, alternatives, vulnerability, reversibility |
| `legal_or_institutional_constraint` | An institution applying a rule or sanction. | justification, alternatives, consequences |
| `emergency_intervention` | A time-critical intervention to stop imminent harm. | justification, alternatives, reversibility |
| `speech_or_language_manipulation` | Action through misleading/deceptive language. | coercion (informational manipulation), consent, evidence |
| `economic_pressure` | Action through financial leverage or dependency. | coercion, alternatives, vulnerability |
| `caregiving_or_dependency` | A caregiver acting toward a dependent person. | vulnerability, consent, alternatives |
| `self_regarding_action` | An action whose effects fall mainly on the actor. | affected agents, consent |
| `collective_policy` | A rule applied to many agents at once. | affected agents, alternatives, consequences |
| `ai_or_algorithmic_decision` | A decision made or mediated by an automated system. | acting agent, affected agents, coercion, evidence |

## How a template changes the questions

Use one with the `questions` command or the wizard:

```bash
littleboy questions examples/partial_language_manipulation_case.json \
    --template speech_or_language_manipulation
littleboy build-case --template medical_decision
```

For example, the `speech_or_language_manipulation` template adds:

> *"Does the action use misleading, deceptive, or manipulative information to
> steer the affected agents' choices? To what degree (0–1)?"* — because
> informational manipulation is a coercion channel: deceiving someone into a
> choice overrides their will (Axioms 0, 2). It is coercion, not merely "bad
> communication".

And the `ai_or_algorithmic_decision` template asks which **Type II** agent is
accountable for deploying a Type I system, because duties bind only Type II
agents (Axiom 4).

## Each template defines

- `required_fields` — the fields most important for this case type;
- `typical_coercion_dimensions` — which coercion channels usually apply (these
  also drive which coercion prompts the wizard asks);
- `emphasized_categories` — question categories whose priority is raised;
- `typical_evidence_needs` and `typical_alternatives` — guidance for the author;
- `special_warnings` — scope caveats (e.g. "not medical advice");
- `extra_questions` — template-specific questions, each with its own
  `why_it_matters` and related axioms.

## Listing templates

```bash
littleboy templates
```

```python
from littleboy import list_templates, get_template
list_templates()
get_template("medical_decision").special_warnings
```
