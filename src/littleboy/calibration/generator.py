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

from littleboy.calibration.models import (
    LayerExpectation,
    ScoringCorpus,
    ScoringCorpusEntry,
)
from littleboy.core.enums import AgentType, ConsentStatus
from littleboy.core.models import (
    ActionCase,
    CoercionProfile,
    DataQualityProfile,
    MoralAgent,
)

DEFAULT_N = 120
DEFAULT_SEED = 0

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
