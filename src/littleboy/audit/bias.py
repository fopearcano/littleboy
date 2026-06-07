"""Bias indicators for the adversarial audit.

These are **indicators, not measurements**, and the audit explicitly does not
claim to detect bias perfectly. Each axis is a transparent heuristic over the
structured case and (when present) its language analysis. The point is to expose
*where the framing of a case might be tilting the judgment* -- including the two
symmetric failures the brief names: being over-impressed by beautiful language,
and under-valuing a good action that is described poorly.

Imports ``core.models`` only for type hints; it reads attributes off the
instances it is given and constructs only audit models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from littleboy.audit.models import AuditCategory, AuditFinding, AuditSeverity, BiasProfile
from littleboy.audit.red_flags import _finding, _form_quality, amplifiers

if TYPE_CHECKING:  # pragma: no cover - typing only
    from littleboy.core.models import ActionCase, EvaluationReport
    from littleboy.language.models import LanguageAnalysis

_S = AuditSeverity
_C = AuditCategory


def _soft_or(values: list[float]) -> float:
    product = 1.0
    for v in values:
        product *= 1.0 - max(0.0, min(1.0, v))
    return 1.0 - product


def assess_bias(
    case: ActionCase,
    *,
    analysis: LanguageAnalysis | None = None,
    report: EvaluationReport | None = None,
    coercion_score: float = 0.0,
) -> tuple[BiasProfile, list[AuditFinding]]:
    """Return a :class:`BiasProfile` of indicators plus any bias-category findings."""
    power, vuln = amplifiers(case)
    p = analysis.profile if analysis is not None else None

    # Language-derived framing indicators.
    framing = _soft_or([p.false_dichotomy, p.false_necessity, p.loaded_language]) if p else 0.0
    availability = max(p.fear_pressure, p.loaded_language) if p else 0.0
    emotional = max(p.fear_pressure, p.shame_pressure) if p else 0.0
    dehumanization = 0.0
    if p is not None:
        compression = p.omission_risk if analysis.replaces_subject_framing else 0.0
        dehumanization = _soft_or([p.silencing_effect, compression])

    # Authority bias: authority capture, or a collective actor under a power asymmetry.
    authority = 0.0
    if analysis is not None:
        if any(f.indicator == "authority_capture" for f in analysis.manipulation_findings):
            authority = 0.6
    if case.acting_agent is not None and case.acting_agent.is_collective and power >= 0.5:
        authority = max(authority, 0.5)

    # Status bias: an institution acting on individuals.
    status = 0.0
    if case.acting_agent is not None and case.acting_agent.is_collective:
        affected_individual = any(not a.is_collective for a in case.affected_agents)
        if affected_individual:
            status = 0.5

    # Outcome bias: leaning on a good expected outcome while process conditions are unknown.
    outcome = 0.0
    just = case.justification
    if just is not None and just.expected_total_coercion_reduction is not None:
        if just.expected_total_coercion_reduction > 0 and (
            just.necessity.is_unresolved
            or just.no_less_coercive_alternative_available.is_unresolved
        ):
            outcome = 0.6

    # Survivorship bias: only the upside of alternatives is shown (no risk recorded).
    survivorship = 0.0
    alts = case.available_alternatives
    if alts:
        if all(a.expected_risk is None for a in alts) and all(a.feasibility >= 0.7 for a in alts):
            survivorship = 0.5

    # Agent bias: actor richly described, affected agents thin.
    agent = 0.0
    if case.acting_agent is not None and case.acting_agent.description:
        affected_thin = (not case.affected_agents) or any(
            a.agent_type is None or not a.description for a in case.affected_agents
        )
        if affected_thin:
            agent = 0.5

    # Sympathy bias: emphasised vulnerability plus emotional language.
    sympathy = round(vuln * (0.5 + 0.5 * emotional), 4) if vuln >= 0.5 else 0.0

    # Language-beauty bias: a mismatch between form quality and content risk, either way.
    beauty = 0.0
    if p is not None:
        form = _form_quality(p)
        content_risk = max(
            analysis.linguistic_coercion_score, p.manipulation_risk, 1.0 - p.truthfulness
        )
        beautiful_bad = form * content_risk
        ugly_good = (1.0 - form) * (1.0 - content_risk) * (1.0 - min(1.0, coercion_score))
        beauty = round(max(beautiful_bad, ugly_good), 4)

    profile = BiasProfile(
        agent_bias_risk=round(agent, 4),
        status_bias_risk=round(status, 4),
        authority_bias_risk=round(authority, 4),
        outcome_bias_risk=round(outcome, 4),
        survivorship_bias_risk=round(survivorship, 4),
        availability_bias_risk=round(availability, 4),
        framing_bias_risk=round(framing, 4),
        language_beauty_bias_risk=beauty,
        sympathy_bias_risk=sympathy,
        dehumanization_risk=round(dehumanization, 4),
    )

    findings = _bias_findings(profile, case, analysis, coercion_score)
    return profile, findings


def _bias_findings(
    profile: BiasProfile,
    case: ActionCase,
    analysis: LanguageAnalysis | None,
    coercion_score: float,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []

    # Language-beauty bias is reported in both directions, because both distort.
    if profile.language_beauty_bias_risk >= 0.5 and analysis is not None:
        p = analysis.profile
        form = _form_quality(p)
        content_risk = max(
            analysis.linguistic_coercion_score, p.manipulation_risk, 1.0 - p.truthfulness
        )
        if form >= 0.55 and content_risk >= 0.45:
            findings.append(
                _finding(
                    "AUD-BIAS-BEAUTY-OVERCREDIT",
                    "Beautiful language may over-credit a weak message",
                    "The language is polished but its content is manipulative or untruthful; "
                    "fluent form can buy unearned trust.",
                    severity=_S.SERIOUS,
                    category=_C.BIAS,
                    why="Persuasive form is not evidence; an attractive description can distort "
                    "judgment toward approval.",
                    fields=["language_act"],
                    questions=["Would this message survive being stated plainly and flatly?"],
                    confidence=0.55,
                )
            )
        else:
            findings.append(
                _finding(
                    "AUD-BIAS-BEAUTY-UNDERCREDIT",
                    "Poor expression may cause a good action to be undervalued",
                    "The language is clumsy or unpolished but not manipulative, and the action's "
                    "coercion is low; weak expression can hide moral value.",
                    severity=_S.WARNING,
                    category=_C.BIAS,
                    why="Judging form over content can penalise an honest but poorly-worded "
                    "case; LittleBoy must weigh substance, not eloquence.",
                    fields=["language_act"],
                    questions=[
                        "Judge the content, not the wording: is the action actually low-"
                        "coercion and honest?"
                    ],
                    confidence=0.55,
                )
            )

    if profile.framing_bias_risk >= 0.6:
        findings.append(
            _finding(
                "AUD-BIAS-FRAMING",
                "The framing of the case may bias the judgment",
                "Strong framing language (false dichotomy / false necessity / loaded terms) is "
                "present.",
                severity=_S.WARNING,
                category=_C.BIAS,
                why="Framing sets the conclusion before the reasoning starts.",
                fields=["language_act"],
                questions=["What would a neutral restatement of the situation look like?"],
                confidence=0.55,
            )
        )

    if profile.outcome_bias_risk >= 0.6:
        findings.append(
            _finding(
                "AUD-BIAS-OUTCOME",
                "Outcome framing leans on a good result while process is unestablished",
                "A favourable expected outcome is asserted while necessity or the alternatives "
                "analysis is unknown.",
                severity=_S.WARNING,
                category=_C.BIAS,
                why="A good projected outcome cannot retroactively justify a coercive process "
                "whose necessity was never shown.",
                fields=["justification"],
                questions=["Is the process justified independently of the hoped-for outcome?"],
                confidence=0.5,
            )
        )

    if profile.dehumanization_risk >= 0.6:
        findings.append(
            _finding(
                "AUD-BIAS-DEHUMANIZATION",
                "The affected agent may be silenced or compressed in the description",
                "The language silences or compresses the affected agent's own account.",
                severity=_S.SERIOUS,
                category=_C.BIAS,
                why="When the affected party is reduced to an object of the description, their "
                "coercion becomes invisible.",
                fields=["language_act", "affected_agents"],
                questions=["How would the affected agent describe this in their own words?"],
                confidence=0.55,
            )
        )

    return findings
