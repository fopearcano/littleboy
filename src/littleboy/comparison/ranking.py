"""Layered, transparent ranking of options.

Ranking is deliberately **not** a single weighted score. It is a lexicographic,
auditable preorder: viable options first, then least coercion, then consent
integrity, vulnerability protection, reversibility-under-uncertainty, lower
uncertainty, fewer feasible less-coercive alternatives, and constructive over
manipulative language. Coercion is compared in coarse bands so that genuine
trade-offs (e.g. slightly less coercion vs. much better evidence) surface on a
later criterion instead of being decided by noise.

The policy profile modulates the weights (e.g. precautionary weighs
irreversibility and vulnerability more heavily), so the same set can rank
differently under different policies.
"""

from __future__ import annotations

from littleboy.comparison.models import ActionRankingEntry
from littleboy.core.enums import PolicyMode
from littleboy.rules.policy import PolicyProfile

# Comparison-specific policy weights (the rule policy carries the rest).
_VULN_WEIGHT = {
    PolicyMode.PERMISSIVE: 1.0,
    PolicyMode.STANDARD: 2.0,
    PolicyMode.STRICT: 3.0,
    PolicyMode.PRECAUTIONARY: 4.0,
}
_LANG_WEIGHT = {
    PolicyMode.PERMISSIVE: 0.0,
    PolicyMode.STANDARD: 1.0,
    PolicyMode.STRICT: 2.0,
    PolicyMode.PRECAUTIONARY: 2.0,
}
# Below this confidence, an irreversible option is penalised (more cautious = higher).
_IRREV_CONFIDENCE_FLOOR = {
    PolicyMode.PERMISSIVE: 0.4,
    PolicyMode.STANDARD: 0.6,
    PolicyMode.STRICT: 0.75,
    PolicyMode.PRECAUTIONARY: 0.85,
}

# Human labels for each key component, used to explain downgrades (in order).
_KEY_LABELS = (
    "moral viability",
    "coercion level",
    "consent integrity",
    "protection of vulnerable agents",
    "reversibility under uncertainty",
    "uncertainty",
    "availability of a less-coercive alternative",
    "constructive vs. manipulative language",
)


def _consent_penalty(entry: ActionRankingEntry, policy: PolicyProfile) -> int:
    status = (entry.consent_status or "").upper()
    if status in {"REFUSED", "COERCED", "DISPUTED"}:
        return 2
    if status == "UNKNOWN":
        return 2 if policy.unknown_consent_is_blocker else 1
    # Consent given/NA, but manipulative language can still taint it.
    if entry.linguistic_coercion_score >= policy.coercion_moderate:
        return 1
    return 0


def ranking_key(entry: ActionRankingEntry, policy: PolicyProfile) -> tuple:
    """Compute the lexicographic ranking key for an option (lower is better)."""
    mode = policy.mode

    if entry.is_morally_viable and not entry.viable_with_reservations:
        viability_tier = 0
    elif entry.is_morally_viable:
        viability_tier = 1
    else:
        viability_tier = 2

    coercion_band = round(entry.coercion_score * 10)

    consent_penalty = _consent_penalty(entry, policy)

    vulnerability_penalty = round((entry.vulnerability_risk or 0.0) * _VULN_WEIGHT[mode])

    irr = entry.irreversibility or 0.0
    if irr >= 0.5 and entry.confidence < _IRREV_CONFIDENCE_FLOOR[mode]:
        irrev_penalty = 2
    elif irr >= 0.5 and entry.confidence < 0.7:
        irrev_penalty = 1
    else:
        irrev_penalty = 0

    uncertainty_band = round((1.0 - entry.confidence) * 5)
    alternative_penalty = 1 if entry.has_feasible_less_coercive else 0
    language_penalty = round(entry.linguistic_coercion_score * _LANG_WEIGHT[mode])

    return (
        viability_tier,
        coercion_band,
        consent_penalty,
        vulnerability_penalty,
        irrev_penalty,
        uncertainty_band,
        alternative_penalty,
        language_penalty,
        round(1.0 - entry.confidence, 4),
        round(1.0 - entry.data_quality_score, 4),
        entry.option_id,
    )


def _primary_reason(entry: ActionRankingEntry) -> str:
    if not entry.is_morally_viable:
        return f"not morally viable under this policy (verdict {entry.verdict.value})"
    qualifier = " (with reservations)" if entry.viable_with_reservations else ""
    return (
        f"morally viable{qualifier}; coercion {entry.coercion_score:.2f}, "
        f"confidence {entry.confidence:.2f}"
    )


def _downgrade_reason(
    entry: ActionRankingEntry, top: ActionRankingEntry, policy: PolicyProfile
) -> str | None:
    """Name the first ranking dimension on which ``entry`` is worse than ``top``."""
    if entry.option_id == top.option_id:
        return None
    ke, kt = ranking_key(entry, policy), ranking_key(top, policy)
    for idx, label in enumerate(_KEY_LABELS):
        if ke[idx] > kt[idx]:
            return f"ranked below '{top.title}' on {label}"
    return f"ranked below '{top.title}' on a fine-grained tiebreaker (uncertainty/data quality)"


def rank_options(
    entries: list[ActionRankingEntry], policy: PolicyProfile
) -> list[ActionRankingEntry]:
    """Sort entries by the layered key, set rank/primary_reason/downgrade_reason."""
    ordered = sorted(entries, key=lambda e: ranking_key(e, policy))
    top = ordered[0] if ordered else None

    prev_key: tuple | None = None
    prev_rank = 0
    for position, entry in enumerate(ordered, start=1):
        key_wo_id = ranking_key(entry, policy)[:-1]
        if prev_key is not None and key_wo_id == prev_key:
            entry.rank = prev_rank  # tie with the previous option
        else:
            entry.rank = position
            prev_rank = position
        prev_key = key_wo_id
        entry.primary_reason = _primary_reason(entry)
        entry.downgrade_reason = _downgrade_reason(entry, top, policy) if top else None
    return ordered


def is_data_sensitive(ordered: list[ActionRankingEntry], policy: PolicyProfile) -> bool:
    """True if the top two options are close enough that more data could reorder them."""
    if len(ordered) < 2:
        return False
    k0 = ranking_key(ordered[0], policy)
    k1 = ranking_key(ordered[1], policy)
    # Same viability tier and same coercion band => the lead rests on softer criteria.
    return k0[0] == k1[0] and k0[1] == k1[1]
