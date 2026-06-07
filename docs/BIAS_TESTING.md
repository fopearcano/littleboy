# LittleBoy bias testing (v0.8)

> Bias indicators expose where the **framing** of a case might be tilting the
> judgment. They are *indicators, not measurements* — LittleBoy does not claim to
> detect bias perfectly.

## Why test for bias in the framing

LittleBoy reasons over a description. The same facts, framed differently, can pull
a reasoner toward a conclusion before the reasoning starts: a sympathetic victim,
an authoritative speaker, a beautifully-written pitch, a story told only from one
side. These are *biases of presentation*, distinct from the coercion in the act
itself. The `BiasProfile` makes them visible so they can be discounted — without
pretending they have been measured.

## The ten bias indicators

Each is a transparent 0..1 heuristic over the structured case and (when present)
its language analysis:

| Indicator | What raises it |
|-----------|----------------|
| `agent_bias_risk` | the acting agent is richly described while the affected agents are thin or unnamed |
| `status_bias_risk` | an institution/collective acting on individuals |
| `authority_bias_risk` | authority-capture language, or a collective actor under a power asymmetry |
| `outcome_bias_risk` | leaning on a good *expected outcome* while necessity / alternatives are unestablished |
| `survivorship_bias_risk` | alternatives shown only with their upside (no risk recorded) |
| `availability_bias_risk` | vivid fear / loaded language making one outcome salient |
| `framing_bias_risk` | false-dichotomy / false-necessity / loaded framing |
| `language_beauty_bias_risk` | a mismatch between *form quality* and *content risk* — in **either** direction |
| `sympathy_bias_risk` | emphasised vulnerability plus emotional language |
| `dehumanization_risk` | the affected agent silenced or compressed in the description |

## Why beautiful language can distort judgment

Fluent, polished, confident language is persuasive *as form*, independent of
whether its content is true or fair. A **persuasive counterfeit** — high clarity
and constructiveness wrapped around manipulation or untruth — can buy unearned
trust and pull a verdict toward approval. The audit measures *form quality*
(clarity, specificity, constructiveness) against *content risk* (manipulation,
untruthfulness, linguistic coercion); when form is high and content risk is high,
it raises `language_beauty_bias_risk` and a `serious` finding, and warns that
**persuasive form may be distorting judgment**.

## Why poor expression can hide moral value

The same axis runs the other way. A genuinely benign, low-coercion, honest action
described in clumsy, unpolished, jargon-poor language can be *under*-valued —
penalised for its wording rather than judged on its substance. When form quality
is low but content risk is also low and the action's coercion is low, the audit
raises `language_beauty_bias_risk` and a `warning` finding telling the reader to
**judge the content, not the eloquence**. Symmetry here is the point: LittleBoy
must neither be charmed by beauty nor repelled by awkwardness.

## How bias indicators affect confidence

A high `language_beauty_bias_risk` (≥ 0.6) under an enabled audit adds a warning
that persuasive or poor form may be distorting the judgment, and contributes to
the audit's `requires_explicit_review` flag. Bias findings, like all audit
findings, are surfaced as warnings and (at `serious`/`critical`) as red flags;
they lower confidence rather than silently changing the verdict. The bias profile
never, by itself, flips a verdict — it tells a reader where to be sceptical.

## Why this does not "prove" bias

These indicators are **deliberately conservative heuristics**. `agent_bias_risk`
rising because the affected party is thinly described does not prove the author is
biased — only that the asymmetry exists and is worth noticing. The audit's
contract is honesty about its own limits: it exposes *risk of bias*, names what
triggered the indicator, and asks a question. It does not diagnose motives, and it
can both miss real bias and flag innocent asymmetries.

## Limitations

- Indicators are heuristics over structured fields and a small language lexicon;
  there is no model of intent.
- Several axes (sympathy, agent, status) are necessarily coarse and are kept
  low-confidence on purpose.
- Bias testing complements, and never overrides, the coercion analysis and the
  red-flag detectors (see [`RED_FLAGS.md`](RED_FLAGS.md) and
  [`ADVERSARIAL_AUDIT.md`](ADVERSARIAL_AUDIT.md)).
