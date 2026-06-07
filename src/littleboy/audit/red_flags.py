"""Deterministic red-flag detection for the adversarial audit.

A red flag is a *transparent, rule-based observation* about the way a case is
described or evidenced -- never a hidden classifier. Each detector reads an
:class:`~littleboy.core.models.ActionCase` (and, where available, its language
analysis, evidence, temporal projection, or a comparison result) and returns
:class:`~littleboy.audit.models.AuditFinding` objects that name what was seen,
which fields it concerns, and what to ask next.

To avoid an import cycle (``core.models`` embeds an ``AuditReport``), this module
imports ``core.models`` only for type hints (under ``TYPE_CHECKING``); the rare
helper that needs runtime logic (``score_coercion``) is imported lazily inside
the function that uses it. Detectors only *read* attributes off the instances
they are given and *construct* audit models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from littleboy.audit.models import AuditCategory, AuditFinding, AuditSeverity
from littleboy.core.enums import ConsentStatus, EpistemicStatus, SourceType

if TYPE_CHECKING:  # pragma: no cover - typing only
    from littleboy.comparison.models import ActionComparisonResult, ActionOption
    from littleboy.core.models import ActionCase
    from littleboy.language.models import LanguageAnalysis
    from littleboy.temporal.models import TemporalProjectionResult

_S = AuditSeverity
_C = AuditCategory


# =============================================================================
# Shared case-inspection helpers (used across the audit package)
# =============================================================================


def case_text(case: ActionCase) -> str:
    """Concatenate the free-text surfaces of a case, lower-cased, for lexicon scans."""
    parts: list[str] = [case.title, case.description, case.context_notes]
    for attr in ("intended_goal", "expected_consequences", "prior_coercion_description"):
        value = getattr(case, attr, None)
        if value:
            parts.append(value)
    if case.justification is not None and case.justification.justification_notes:
        parts.append(case.justification.justification_notes)
    la = case.language_act
    if la is not None:
        parts.append(la.text or "")
        if la.declared_intent:
            parts.append(la.declared_intent)
    return " ".join(p for p in parts if p).lower()


def amplifiers(case: ActionCase) -> tuple[float, float]:
    """Return ``(power_asymmetry, vulnerability)`` gathered from agency + language context."""
    power = 0.0
    vuln = 0.0
    if case.agency_profile is not None:
        vuln = case.agency_profile.vulnerability_level
    la = case.language_act
    if la is not None and la.context is not None:
        power = max(power, la.context.power_asymmetry)
        vuln = max(vuln, la.context.target_vulnerability)
    return power, vuln


def stakes(case: ActionCase) -> float:
    """A 0..1 stakes estimate from coercion severity and any language context."""
    s = 0.0
    if case.coercion_profile is not None:
        s = max(s, case.coercion_profile.severity)
    la = case.language_act
    if la is not None and la.context is not None:
        s = max(s, la.context.stakes)
    return s


def bare_coercion_score(case: ActionCase) -> float:
    """Score the case's *own* coercion profile, ignoring any language contribution.

    Imported lazily because ``core.scoring`` imports ``core.models`` at module
    top, which would cycle if imported while ``core.models`` is still loading.
    """
    if case.coercion_profile is None:
        return 0.0
    from littleboy.core.scoring import score_coercion

    return score_coercion(case.coercion_profile).score


def is_irreversible(case: ActionCase, threshold: float = 0.30) -> bool:
    cp = case.coercion_profile
    if cp is not None and cp.reversibility is not None and cp.reversibility < threshold:
        return True
    rp = case.reversibility_profile
    return rp is not None and rp.reversibility_score < threshold


def evidence_is_weak(case: ActionCase) -> bool:
    ev = case.evidence
    return ev is None or ev.is_empty or ev.overall_evidence_score() < 0.34


def _n_unknown_consent_dims(cp) -> int:
    return sum(
        1 for dim in (cp.informed, cp.voluntary, cp.specific, cp.revocable) if dim.is_unresolved
    )


def _finding(
    finding_id: str,
    title: str,
    description: str,
    *,
    severity: AuditSeverity,
    category: AuditCategory,
    why: str,
    fields: list[str] | None = None,
    evidence: list[str] | None = None,
    questions: list[str] | None = None,
    confidence: float = 0.5,
) -> AuditFinding:
    return AuditFinding(
        finding_id=finding_id,
        title=title,
        description=description,
        severity=severity,
        category=category,
        evidence=evidence or [],
        affected_fields=fields or [],
        why_it_matters=why,
        recommended_questions=questions or [],
        confidence=confidence,
    )


# =============================================================================
# Consent red flags
# =============================================================================


def consent_red_flags(
    case: ActionCase, *, analysis: LanguageAnalysis | None = None
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    status = case.effective_consent_status()
    power, vuln = amplifiers(case)
    cp = case.consent_profile
    affects_consent = bool(
        analysis is not None
        and analysis.affects_consent
        and analysis.linguistic_coercion_score >= 0.3
    )

    if status != ConsentStatus.GIVEN:
        return findings

    # Dimensions unknown.
    if cp is None or _n_unknown_consent_dims(cp) >= 1:
        findings.append(
            _finding(
                "AUD-CONSENT-DIMENSIONS",
                "Consent asserted but its quality is unestablished",
                "Consent is reported as given, but one or more of "
                "informed/voluntary/specific/revocable is unknown.",
                severity=_S.SERIOUS if vuln >= 0.6 else _S.WARNING,
                category=_C.CONSENT,
                why="Valid consent is informed, voluntary, specific, and revocable; an "
                "unqualified 'yes' can hide the absence of these.",
                fields=["consent_profile"],
                questions=[
                    "Was consent informed, voluntary, specific, and revocable?",
                    "How was each of those four conditions established?",
                ],
                confidence=0.6,
            )
        )

    # Communicated by someone other than the affected agent.
    if cp is not None and cp.communicated_by_agent is False:
        findings.append(
            _finding(
                "AUD-CONSENT-NOT-BY-AGENT",
                "Consent was not communicated by the affected agent",
                "Consent is attributed to a party other than the affected agent.",
                severity=_S.CRITICAL,
                category=_C.CONSENT,
                why="Consent given on someone else's behalf is not their consent; this is a "
                "classic route to false consent.",
                fields=["consent_profile.communicated_by_agent"],
                questions=["Did the affected agent themselves consent, in their own words?"],
                confidence=0.7,
            )
        )

    # High power asymmetry.
    if power >= 0.6:
        findings.append(
            _finding(
                "AUD-CONSENT-POWER",
                "Consent obtained under a high power asymmetry",
                "Consent is reported under a strong power imbalance between the parties.",
                severity=_S.SERIOUS if vuln >= 0.6 else _S.WARNING,
                category=_C.CONSENT,
                why="Under a steep power asymmetry, an apparent 'yes' may not be voluntary.",
                fields=["language_act.context.power_asymmetry", "consent"],
                questions=["Could the affected agent have refused without penalty?"],
                confidence=0.55,
            )
        )

    # High vulnerability.
    if vuln >= 0.6:
        findings.append(
            _finding(
                "AUD-CONSENT-VULNERABILITY",
                "Consent obtained from a highly vulnerable agent",
                "Consent is reported from an agent flagged as highly vulnerable.",
                severity=_S.SERIOUS,
                category=_C.VULNERABILITY,
                why="Vulnerability undermines the voluntariness and informedness of consent.",
                fields=["agency_profile.vulnerability_level", "consent"],
                questions=["Was the affected agent able to understand and freely decline?"],
                confidence=0.6,
            )
        )

    # Contaminated by unclear / manipulative language under pressure -> false consent.
    if affects_consent and (power >= 0.5 or vuln >= 0.5):
        findings.append(
            _finding(
                "AUD-CONSENT-CONTAMINATION",
                "Consent may be contaminated by manipulative or unclear language",
                "The language affecting consent is manipulative or unclear, under pressure or "
                "vulnerability -- the consent may be false.",
                severity=_S.CRITICAL,
                category=_C.CONSENT,
                why="Consent extracted through manipulation, fear, or confusion is not valid "
                "consent, however clearly a 'yes' was recorded.",
                fields=["language_act", "consent"],
                evidence=list(analysis.dominant_indicators) if analysis else [],
                questions=[
                    "Would the affected agent have consented to a clear, pressure-free version?",
                    "What exactly were they told, and what was omitted?",
                ],
                confidence=0.6,
            )
        )

    return findings


# =============================================================================
# Coercion red flags
# =============================================================================


def coercion_red_flags(
    case: ActionCase,
    *,
    analysis: LanguageAnalysis | None = None,
    coercion_moderate: float = 0.30,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []

    # Low structured coercion but highly manipulative language (an inconsistency).
    if analysis is not None and analysis.linguistic_coercion_score >= 0.5:
        bare = bare_coercion_score(case)
        if bare < coercion_moderate:
            findings.append(
                _finding(
                    "AUD-COERCION-LANG-INCONSISTENCY",
                    "Structured coercion looks low, but the language is highly manipulative",
                    f"The supplied coercion profile scores {bare:.2f}, yet the linguistic "
                    f"coercion is {analysis.linguistic_coercion_score:.2f}.",
                    severity=_S.SERIOUS,
                    category=_C.COERCION,
                    why="A describer can downplay coercion in the structured fields while the "
                    "actual wording does the coercing; the two must be reconciled.",
                    fields=["coercion_profile", "language_act"],
                    questions=[
                        "Does the coercion profile reflect the pressure in the actual wording?"
                    ],
                    confidence=0.6,
                )
            )

    just = case.justification
    if just is not None:
        # Justified coercion without a cessation condition.
        if just.cessation_condition_defined.is_unresolved or (
            just.cessation_condition_defined == EpistemicStatus.DISPUTED
        ):
            findings.append(
                _finding(
                    "AUD-COERCION-NO-CESSATION",
                    "Coercion is justified without a defined cessation condition",
                    "A coercion justification is offered, but the condition under which the "
                    "coercion will stop is unknown or disputed.",
                    severity=_S.SERIOUS,
                    category=_C.COERCION,
                    why="Axiom 3 requires a defined cessation condition; open-ended 'justified' "
                    "coercion tends to become permanent.",
                    fields=["justification.cessation_condition_defined"],
                    questions=["Exactly when and how does this coercion end?"],
                    confidence=0.65,
                )
            )
        # Necessity claimed while alternatives were never analysed.
        if just.necessity.is_affirmative and case.available_alternatives is None:
            findings.append(
                _finding(
                    "AUD-COERCION-NECESSITY-NO-ALT",
                    "Coercion claimed necessary while alternatives were never analysed",
                    "Necessity is asserted, but no less-coercive alternatives were considered.",
                    severity=_S.SERIOUS,
                    category=_C.ALTERNATIVES,
                    why="'Necessary' is unprovable without having looked for a less coercive "
                    "option; this is a common rhetorical shortcut.",
                    fields=["justification.necessity", "available_alternatives"],
                    questions=["What less-coercive alternatives were considered and ruled out?"],
                    confidence=0.6,
                )
            )
        # Claimed temporary/reversible but reversibility unknown.
        cp = case.coercion_profile
        reversibility_unknown = (
            cp is None or not cp.reversibility_is_known
        ) and case.reversibility_profile is None
        if just.reversibility.is_affirmative and reversibility_unknown:
            findings.append(
                _finding(
                    "AUD-COERCION-TEMP-NO-REV",
                    "Coercion claimed reversible but reversibility is unknown",
                    "The justification asserts reversibility, yet no reversibility is "
                    "characterised on the action.",
                    severity=_S.WARNING,
                    category=_C.COERCION,
                    why="'Temporary' or 'reversible' is an assurance, not a fact, until the cost "
                    "and completeness of reversal are established.",
                    fields=["justification.reversibility", "reversibility_profile"],
                    questions=["How, at what cost, and how completely can this be undone?"],
                    confidence=0.55,
                )
            )

    return findings


# =============================================================================
# Evidence red flags
# =============================================================================


def _only_self_sourced(ev) -> bool:
    if ev is None or ev.is_empty:
        return False
    return all(i.source_type in (SourceType.USER_STATEMENT, SourceType.UNKNOWN) for i in ev.items)


def _no_counterevidence(ev) -> bool:
    if ev is None or ev.is_empty:
        return True
    no_contest = not ev.contested_claims()
    weak_corro = max((i.corroboration for i in ev.items), default=0.0) < 0.3
    return no_contest and weak_corro


def evidence_red_flags(
    case: ActionCase, *, coercion_score: float = 0.0, coercion_moderate: float = 0.30
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    ev = case.evidence
    weak = evidence_is_weak(case)
    irreversible = is_irreversible(case)
    coercive = coercion_score >= coercion_moderate or (
        case.coercion_profile is not None and case.coercion_profile.severity >= 0.5
    )

    if stakes(case) >= 0.6 and weak:
        findings.append(
            _finding(
                "AUD-EVID-HIGH-STAKES-WEAK",
                "High-stakes claim rests on weak or absent evidence",
                "The stakes are high but the evidence is weak, absent, or unsupplied.",
                severity=_S.SERIOUS,
                category=_C.EVIDENCE,
                why="The higher the stakes, the stronger the evidence ought to be (Axiom 5).",
                fields=["evidence", "data_quality"],
                questions=["What independent evidence supports the high-stakes claims here?"],
                confidence=0.6,
            )
        )

    if ev is not None and ev.contested_claims():
        findings.append(
            _finding(
                "AUD-EVID-CONTESTED",
                "Contested evidence is present",
                "One or more claims are actively contested; ensure they were not waved through.",
                severity=_S.WARNING,
                category=_C.EVIDENCE,
                why="Contested claims must lower confidence, not be quietly resolved in favour "
                "of the desired conclusion.",
                fields=["evidence"],
                evidence=list(ev.contested_claims()),
                questions=["How was each contested claim adjudicated?"],
                confidence=0.6,
            )
        )

    if irreversible and weak:
        findings.append(
            _finding(
                "AUD-EVID-IRREVERSIBLE-WEAK",
                "An irreversible action rests on weak or absent evidence",
                "The action is effectively irreversible, yet the evidence is weak or missing.",
                severity=_S.CRITICAL,
                category=_C.EVIDENCE,
                why="Irreversibility plus weak data is the most dangerous epistemic combination: "
                "a mistake cannot be undone.",
                fields=["coercion_profile.reversibility", "evidence"],
                questions=["Is there enough trustworthy evidence to justify an irreversible step?"],
                confidence=0.7,
            )
        )

    if _only_self_sourced(ev):
        findings.append(
            _finding(
                "AUD-EVID-SELF-SOURCED",
                "All evidence comes from the acting agent",
                "Every evidence item is a user statement or unknown source -- no independent "
                "corroboration.",
                severity=_S.SERIOUS,
                category=_C.EVIDENCE,
                why="A case sourced only from the actor under scrutiny can launder a one-sided "
                "account into apparent fact.",
                fields=["evidence"],
                questions=["Is there any source independent of the acting agent?"],
                confidence=0.6,
            )
        )

    if coercive and _no_counterevidence(ev):
        findings.append(
            _finding(
                "AUD-EVID-NO-COUNTER",
                "No counterevidence or independent corroboration was supplied",
                "A coercive action is described without any contesting or corroborating evidence.",
                severity=_S.SERIOUS,
                category=_C.EVIDENCE,
                why="The absence of counterevidence is not the same as its absence in reality; "
                "a one-sided record can make a weak case look settled.",
                fields=["evidence"],
                questions=[
                    "What would the affected agent say?",
                    "What evidence would count against this action?",
                ],
                confidence=0.55,
            )
        )

    return findings


# =============================================================================
# Language red flags
# =============================================================================


def _form_quality(profile) -> float:
    return (profile.clarity + profile.specificity + profile.constructive_potential) / 3.0


def language_red_flags(case: ActionCase, analysis: LanguageAnalysis | None) -> list[AuditFinding]:
    if analysis is None:
        return []
    findings: list[AuditFinding] = []
    p = analysis.profile
    power, vuln = amplifiers(case)
    amp = max(power, vuln)
    indicators = {f.indicator for f in analysis.manipulation_findings}

    checks = [
        (
            "false_necessity",
            p.false_necessity,
            "False necessity",
            "false_necessity",
            "Asserting 'there is no choice' hides alternatives that may exist.",
        ),
        (
            "false_dichotomy",
            p.false_dichotomy,
            "False dichotomy",
            "false_dichotomy",
            "Framing only two options conceals the full range of choices.",
        ),
        (
            "shame_pressure",
            p.shame_pressure,
            "Shame pressure",
            "shame_pressure",
            "Shame is used to override the agent's own judgment.",
        ),
        (
            "fear_pressure",
            p.fear_pressure,
            "Fear pressure",
            "fear_pressure",
            "Fear is used to rush or coerce a decision.",
        ),
    ]
    for key, value, title, indicator, why in checks:
        if value >= 0.5 or key in indicators:
            findings.append(
                _finding(
                    f"AUD-LANG-{key.upper()}",
                    f"Language uses {title.lower()}",
                    f"{title} detected in the language act.",
                    severity=_S.SERIOUS if amp >= 0.5 else _S.WARNING,
                    category=_C.LANGUAGE,
                    why=why,
                    fields=["language_act"],
                    evidence=[
                        f.evidence
                        for f in analysis.manipulation_findings
                        if f.indicator == indicator
                    ],
                    questions=["Were the omitted options or the real risks disclosed?"],
                    confidence=0.6,
                )
            )

    if (
        analysis.replaces_subject_framing
        or "semantic_compression" in indicators
        or "testimonial_injustice" in indicators
    ):
        findings.append(
            _finding(
                "AUD-LANG-FRAMING-REPLACEMENT",
                "Language may replace the subject's own framing (semantic compression / "
                "testimonial injustice)",
                "The wording compresses or dismisses the subject's own account of their will.",
                severity=_S.SERIOUS,
                category=_C.LANGUAGE,
                why="Replacing a person's framing of their own situation is a subtle but serious "
                "coercion of meaning.",
                fields=["language_act"],
                questions=["What did the subject actually say, in full, in their own words?"],
                confidence=0.6,
            )
        )

    if "authority_capture" in indicators or (
        p.silencing_effect >= 0.6 and "silencing" in indicators
    ):
        findings.append(
            _finding(
                "AUD-LANG-AUTHORITY-CAPTURE",
                "Authority is used to suppress questioning",
                "The language leans on the speaker's authority to shut down scrutiny "
                "('trust me', 'you're not qualified').",
                severity=_S.SERIOUS,
                category=_C.LANGUAGE,
                why="Authority capture replaces reasons with status, discouraging the very "
                "questioning an ethical check requires.",
                fields=["language_act"],
                evidence=[
                    f.evidence
                    for f in analysis.manipulation_findings
                    if f.indicator == "authority_capture"
                ],
                questions=["Are the claims defensible on their merits, without appeal to status?"],
                confidence=0.6,
            )
        )

    # Persuasive counterfeit: polished form carrying high manipulation / low truthfulness.
    form = _form_quality(p)
    content_risk = max(
        analysis.linguistic_coercion_score, p.manipulation_risk, 1.0 - p.truthfulness
    )
    if form >= 0.6 and content_risk >= 0.5:
        findings.append(
            _finding(
                "AUD-LANG-PERSUASIVE-COUNTERFEIT",
                "Persuasive counterfeit: appealing form, manipulative content",
                f"The language is well-formed (form {form:.2f}) but carries high manipulation / "
                f"low truthfulness (content risk {content_risk:.2f}).",
                severity=_S.SERIOUS,
                category=_C.LANGUAGE,
                why="Polished, fluent language can make a manipulative message feel trustworthy; "
                "form is not evidence.",
                fields=["language_act"],
                questions=["Strip the style: do the underlying claims hold up?"],
                confidence=0.6,
            )
        )

    return findings


# =============================================================================
# Temporal red flags
# =============================================================================


def temporal_red_flags(
    case: ActionCase,
    temporal: TemporalProjectionResult | None,
    *,
    coercion_score: float = 0.0,
    coercion_moderate: float = 0.30,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    coercive = coercion_score >= coercion_moderate or (
        case.coercion_profile is not None and case.coercion_profile.severity >= 0.4
    )

    if temporal is not None and temporal.has_temporal_data:
        if temporal.trend == "rising" and temporal.immediate_coercion < temporal.long_term_coercion:
            findings.append(
                _finding(
                    "AUD-TEMPORAL-HIDDEN-LONG-TERM",
                    "Immediate framing may hide higher long-term coercion",
                    f"Coercion rises from {temporal.immediate_coercion:.2f} now to "
                    f"{temporal.long_term_coercion:.2f} long-term.",
                    severity=_S.SERIOUS,
                    category=_C.TEMPORAL,
                    why="A low immediate cost can be used to sell an action whose real cost lands "
                    "later.",
                    fields=["consequences", "temporal_profile"],
                    questions=["What does this look like over the long term, not just now?"],
                    confidence=0.6,
                )
            )
        if temporal.high_risk_unknowns:
            findings.append(
                _finding(
                    "AUD-TEMPORAL-LOWCONF-PREDICTION",
                    "Long-term consequences are weakly evidenced",
                    "High-impact long-term consequences rest on low-confidence estimates.",
                    severity=_S.WARNING,
                    category=_C.TEMPORAL,
                    why="Confident long-term claims on weak evidence can manufacture either alarm "
                    "or false reassurance.",
                    fields=["consequences"],
                    questions=["How well-founded are the long-term predictions?"],
                    confidence=0.55,
                )
            )
        if temporal.reversible_now_irreversible_later:
            findings.append(
                _finding(
                    "AUD-TEMPORAL-REV-NOW-IRREV-LATER",
                    "Reversible now but may become irreversible later",
                    "The action is reversible at present but has effects that harden over time.",
                    severity=_S.SERIOUS,
                    category=_C.TEMPORAL,
                    why="'You can always undo it' may be true today and false next year.",
                    fields=["reversibility_profile", "consequences"],
                    questions=["Until when, exactly, can this still be undone?"],
                    confidence=0.55,
                )
            )
    elif coercive:
        findings.append(
            _finding(
                "AUD-TEMPORAL-CUMULATIVE-IGNORED",
                "No temporal or cumulative analysis for a coercive action",
                "A coercive action is described with no consequence, reversibility, or "
                "cumulative-coercion modelling.",
                severity=_S.WARNING,
                category=_C.TEMPORAL,
                why="Coercion that is mild once can become serious if it repeats, normalises, or "
                "compounds -- which an instant-only description hides.",
                fields=["consequences", "cumulative_coercion_profile"],
                questions=["What happens if this repeats or becomes normal?"],
                confidence=0.5,
            )
        )

    if case.is_inaction and (temporal is None or not temporal.has_temporal_data):
        findings.append(
            _finding(
                "AUD-TEMPORAL-INACTION-NEUTRAL",
                "Inaction is treated as neutral without evidence",
                "The case is an inaction but carries no evidence about what the inaction permits.",
                severity=_S.WARNING,
                category=_C.TEMPORAL,
                why="Inaction is a choice; treating it as automatically neutral can hide the "
                "coercion it allows to continue.",
                fields=["is_inaction", "consequences"],
                questions=["What coercion does doing nothing allow to continue or grow?"],
                confidence=0.55,
            )
        )

    return findings


# =============================================================================
# Comparison red flags (cross-option)
# =============================================================================


def comparison_red_flags(
    result: ActionComparisonResult, options_by_id: dict[str, ActionOption]
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    ranking = result.ranking
    if not ranking:
        return findings
    top = ranking[0]
    others = ranking[1:]

    if top.blockers:
        findings.append(
            _finding(
                "AUD-CMP-TOP-BLOCKERS",
                "The top-ranked option has unresolved blockers",
                f"'{top.title}' ranks first but still carries blockers: {', '.join(top.blockers)}.",
                severity=_S.SERIOUS,
                category=_C.COMPARISON,
                why="A 'best' option that is itself blocked is least-bad, not endorsed.",
                fields=["ranking"],
                questions=["Should any option with an unresolved blocker be recommended at all?"],
                confidence=0.65,
            )
        )

    if result.data_sensitive or not result.ranking_stable:
        findings.append(
            _finding(
                "AUD-CMP-DATA-SENSITIVE",
                "The ranking depends on missing or close data",
                "Resolving missing data, or a close call between the leaders, could reorder the "
                "ranking.",
                severity=_S.WARNING,
                category=_C.COMPARISON,
                why="A ranking presented as settled while resting on missing data is itself "
                "misleading.",
                fields=["data_sensitive", "ranking_stable"],
                questions=["Which missing facts would change the order?"],
                confidence=0.6,
            )
        )

    # The top option may rank first only because less is known about it.
    if others and top.is_morally_viable:
        fewest_other = min(len(o.missing_data) for o in others)
        if len(top.missing_data) > fewest_other:
            findings.append(
                _finding(
                    "AUD-CMP-ADVANTAGED-BY-MISSING-DATA",
                    "The top option may benefit from absent negative data",
                    "The leading option has more missing data than a competitor; its lead may "
                    "reflect what is unknown rather than what is good.",
                    severity=_S.SERIOUS,
                    category=_C.COMPARISON,
                    why="Negative information that was never gathered cannot lower a score; "
                    "absence of data can masquerade as absence of problems.",
                    fields=["ranking", "missing_data"],
                    questions=["What is not yet known about the leading option?"],
                    confidence=0.55,
                )
            )

    # A lower-ranked option is better evidenced and not more coercive.
    for o in others:
        better_evidenced = o.evidence_score > top.evidence_score + 0.15
        not_more_coercive = o.coercion_score <= top.coercion_score + 0.05
        if better_evidenced and not_more_coercive:
            findings.append(
                _finding(
                    "AUD-CMP-FRAMING-BIAS",
                    "A lower-ranked option is better evidenced and not more coercive",
                    f"'{o.title}' is better evidenced than the leader and no more coercive, yet "
                    "ranks lower -- check for framing bias.",
                    severity=_S.SERIOUS,
                    category=_C.FRAMING,
                    why="Better-expressed or better-evidenced does not mean better; presentation "
                    "should not outrank substance.",
                    fields=["ranking"],
                    questions=["Is the leader winning on substance, or on presentation?"],
                    confidence=0.5,
                )
            )
            break

    # Options pursue different declared goals.
    goals = {opt.declared_goal for opt in options_by_id.values() if opt.declared_goal}
    if len(goals) > 1:
        findings.append(
            _finding(
                "AUD-CMP-GOALS-NOT-EQUIVALENT",
                "Options pursue different declared goals",
                "The options do not share a single declared goal, so comparing them as "
                "equivalents may be misleading.",
                severity=_S.WARNING,
                category=_C.COMPARISON,
                why="Comparing options for different ends as if interchangeable can smuggle in a "
                "preferred outcome.",
                fields=["options.declared_goal"],
                questions=["Are these options really alternatives for the same goal?"],
                confidence=0.5,
            )
        )

    return findings
