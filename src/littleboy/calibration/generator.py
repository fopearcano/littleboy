"""A deterministic generator for a large, independently-labelled scoring corpus.

The packaged corpus is small and hand-labelled. To calibrate *at scale* with
labels that are **not derived from the heuristics under test**, this generator
synthesises many cases from latent parameters and labels each case **from those
latent parameters**, never from what the evaluator computes:

- a latent coercion severity ``s`` -> ground-truth ``coercive = s >= 0.5``;
- a latent data adequacy ``d`` -> ground-truth ``adequate_data = d >= 0.5``.

The *observed* coercion profile and data-quality profile are built from ``s`` and
``d``; the scoring detectors then predict from the heuristic over those
observations. Agreement between the independent label and the heuristic detector
is exactly what calibration measures. Generation is fully deterministic given the
seed (a fixed ``random.Random(seed)``); no case is stored on disk, so scale is
free and the corpus is reproducible.
"""

from __future__ import annotations

import random
from collections import Counter

from littleboy.calibration.models import (
    LabelerVerdict,
    LayerExpectation,
    OutcomeCorpus,
    OutcomeEntry,
    ScoringCorpus,
    ScoringCorpusEntry,
)
from littleboy.core.enums import AgentType, ConsentStatus, SourceType, Verdict
from littleboy.core.models import (
    ActionCase,
    CoercionProfile,
    DataQualityProfile,
    MoralAgent,
)
from littleboy.data.evidence import EvidenceItem, EvidenceSet

DEFAULT_N = 120
DEFAULT_SEED = 0
DEFAULT_OUTCOME_N = 160
DEFAULT_OUTCOME_LABELERS = ("lenient", "median", "strict")

_CHANNELS = (
    "physical_force",
    "threat",
    "economic_pressure",
    "psychological_pressure",
    "social_pressure",
)
_CONSENTS = (
    ConsentStatus.GIVEN,
    ConsentStatus.REFUSED,
    ConsentStatus.UNKNOWN,
    ConsentStatus.NOT_APPLICABLE,
)


def generate_scoring_corpus(*, n: int = DEFAULT_N, seed: int = DEFAULT_SEED) -> ScoringCorpus:
    """Deterministically synthesise ``n`` cases with latent (heuristic-independent) labels."""
    rng = random.Random(seed)
    entries: list[ScoringCorpusEntry] = []
    for i in range(n):
        s = rng.random()  # latent coercion severity (ground truth)
        d = rng.random()  # latent data adequacy (ground truth)
        dominant = rng.choice(_CHANNELS)
        reversibility = round(rng.random(), 3)
        consent = rng.choice(_CONSENTS)

        coercion = CoercionProfile(
            **{dominant: round(s, 3)},
            severity=round(s, 3),
            reversibility=reversibility,
        )
        data_quality = DataQualityProfile(
            completeness=round(d, 3),
            source_reliability=round(d, 3),
            specificity=round(d, 3),
            recency=round(d, 3),
            corroboration=round(max(0.0, d - 0.1), 3),
            ambiguity=round(1.0 - d, 3),
        )
        case = ActionCase(
            title=f"generated case {i}",
            acting_agent=MoralAgent(name="Actor", agent_type=AgentType.TYPE_II),
            affected_agents=[MoralAgent(name="Affected", agent_type=AgentType.TYPE_II)],
            coercion_profile=coercion,
            data_quality=data_quality,
            consent=consent,
            available_alternatives=[],
            responds_to_existing_coercion=False,
        )
        entries.append(
            ScoringCorpusEntry(
                id=f"gen-{i:04d}",
                description="deterministically generated; labels from latent parameters",
                case=case,
                expect=LayerExpectation(coercive=(s >= 0.5), adequate_data=(d >= 0.5)),
            )
        )

    return ScoringCorpus(
        title=f"Generated scoring corpus (n={n}, seed={seed})",
        description=(
            "Synthetic cases labelled from latent severity/adequacy parameters, independent of "
            "the scoring heuristics under test. Deterministic given the seed."
        ),
        entries=entries,
    )


def default_generated_scoring_corpus() -> ScoringCorpus:
    """The standard large generated corpus used for golden-file regression."""
    return generate_scoring_corpus(n=DEFAULT_N, seed=DEFAULT_SEED)


# =============================================================================
# Multi-labeller outcome corpus (independent human labelers, at scale)
# =============================================================================
#
# Each labeler is a *different, transparent* judgment rule over the observable case
# (severity, data adequacy, consent), authored separately from the engine and from
# one another. They genuinely disagree on borderline cases, giving a realistic
# inter-labeller agreement < 1 -- the ceiling against which engine reliability is read.


def _persona_verdict(name: str, s: float, d: float, refused: bool) -> Verdict:
    if name == "lenient":
        if d < 0.2:
            return Verdict.INSUFFICIENT_DATA
        if s >= 0.8 or (refused and s >= 0.6):
            return Verdict.NOT_ACCEPTABLE
        if s >= 0.55:
            return Verdict.ACCEPTABLE_WITH_RESERVATIONS
        return Verdict.ACCEPTABLE
    if name == "median":
        if d < 0.3:
            return Verdict.INSUFFICIENT_DATA
        if s >= 0.6 or (refused and s >= 0.45):
            return Verdict.NOT_ACCEPTABLE
        if s >= 0.4:
            return Verdict.ACCEPTABLE_WITH_RESERVATIONS
        return Verdict.ACCEPTABLE
    # strict
    if d < 0.45:
        return Verdict.INSUFFICIENT_DATA
    if refused or s >= 0.45:
        return Verdict.NOT_ACCEPTABLE
    if s >= 0.3:
        return Verdict.ETHICALLY_SUSPICIOUS
    if s >= 0.15:
        return Verdict.ACCEPTABLE_WITH_RESERVATIONS
    return Verdict.ACCEPTABLE


def _consensus(labels: list[LabelerVerdict]) -> Verdict:
    counts = Counter(lv.verdict for lv in labels)
    top, n_top = counts.most_common(1)[0]
    if sum(1 for v in counts.values() if v == n_top) > 1:
        # no majority -> defer to the median labeler
        return next(lv.verdict for lv in labels if lv.labeler == "median")
    return top


def generate_outcome_corpus(
    *,
    n: int = DEFAULT_OUTCOME_N,
    seed: int = DEFAULT_SEED,
    labelers: tuple[str, ...] = DEFAULT_OUTCOME_LABELERS,
) -> OutcomeCorpus:
    """Deterministically synthesise ``n`` cases, each labelled by a panel of personas.

    The panel's verdicts give both the consensus (``human_verdict``) and the raw
    labels (for inter-labeller agreement). Cases alternate between dev and holdout.
    """
    rng = random.Random(seed)
    entries: list[OutcomeEntry] = []
    for i in range(n):
        s = rng.random()
        # Fully specify the epistemics (good data + evidence + consent + reversibility) so the
        # data gate never fires and the verdict is driven by coercion vs the *policy threshold*.
        # That is what makes the policies -- and so the per-stakeholder recommendations -- diverge.
        d = round(0.8 + 0.2 * rng.random(), 3)  # [0.8, 1.0], always adequate
        reversibility = round(0.7 + 0.3 * rng.random(), 3)  # [0.7, 1.0], reversible
        dominant = rng.choice(_CHANNELS)
        refused = False  # consent is given here; coercion severity is the variable of interest

        case = ActionCase(
            title=f"outcome case {i}",
            acting_agent=MoralAgent(name="Actor", agent_type=AgentType.TYPE_II),
            affected_agents=[MoralAgent(name="Affected", agent_type=AgentType.TYPE_II)],
            coercion_profile=CoercionProfile(
                **{dominant: round(s, 3)}, severity=round(s, 3), reversibility=reversibility
            ),
            data_quality=DataQualityProfile(
                completeness=d,
                source_reliability=d,
                specificity=d,
                recency=d,
                corroboration=round(max(0.0, d - 0.1), 3),
                ambiguity=round(1.0 - d, 3),
            ),
            evidence=EvidenceSet(
                items=[
                    EvidenceItem(
                        claim="independently corroborated account of the action",
                        source_type=SourceType.EXPERT_REPORT,
                        reliability=0.85,
                        specificity=0.85,
                        recency=0.85,
                        corroboration=0.85,
                    )
                ]
            ),
            consent=ConsentStatus.GIVEN,
            available_alternatives=[],
            responds_to_existing_coercion=False,
        )
        labels = [
            LabelerVerdict(labeler=name, verdict=_persona_verdict(name, s, d, refused))
            for name in labelers
        ]
        entries.append(
            OutcomeEntry(
                id=f"gen-out-{i:04d}",
                description="generated case, labelled by an independent persona panel",
                case=case,
                split="dev" if i % 2 == 0 else "holdout",
                human_verdict=_consensus(labels),
                labeler="consensus",
                labels=labels,
            )
        )

    return OutcomeCorpus(
        title=f"Generated multi-labeller outcome corpus (n={n}, seed={seed})",
        description=(
            "Synthetic cases each judged by an independent panel of transparent labeler "
            "personas (lenient / median / strict), authored separately from the engine. "
            "Deterministic given the seed."
        ),
        entries=entries,
    )


def default_labelled_outcome_corpus() -> OutcomeCorpus:
    """The standard large multi-labeller outcome corpus used for reliability at scale."""
    return generate_outcome_corpus(n=DEFAULT_OUTCOME_N, seed=DEFAULT_SEED)
