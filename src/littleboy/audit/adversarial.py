"""Adversarial-risk profiling, ideological-capture checks, and verdict adjustment.

This module asks the audit's sharpest question: *has this case been described so
as to lead LittleBoy toward a desired verdict?* It produces an
:class:`~littleboy.audit.models.AdversarialRiskProfile`, runs the
ideological-capture checks (is the coercion axiom being applied too narrowly or
as a slogan?), and provides :func:`audit_adjusted_verdict`, the deterministic,
transparent rule that lets a *critical* audit finding bear on the verdict when
the audit is enabled.

Ideological-capture detection uses a small, documented phrase lexicon (like the
language module's), so every finding can cite the phrase that triggered it. It
does **not** replace the core axiom; it detects distorted *application* of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from littleboy.audit.models import (
    AdversarialRiskProfile,
    AuditCategory,
    AuditFinding,
    AuditReport,
    AuditSeverity,
)
from littleboy.audit.red_flags import (
    _finding,
    _form_quality,
    _no_counterevidence,
    _only_self_sourced,
    amplifiers,
    case_text,
    evidence_is_weak,
)
from littleboy.core.enums import Verdict

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


# A small, transparent lexicon of phrases that can *signal* a distorted application
# of the coercion axiom. A match is a prompt to look closer, never a conviction.
_IDEOLOGICAL_LEXICON: dict[str, tuple[str, ...]] = {
    "care_as_control": (
        "for your own good",
        "we know what's best",
        "i know what's best",
        "it's for your benefit",
        "because we care",
        "trust us to decide",
        "we are protecting you",
        "we're protecting you",
    ),
    "freedom_as_pressure": (
        "you're free to choose",
        "you are free to choose",
        "no one is forcing you",
        "nobody is forcing you",
        "it's entirely your choice",
        "of your own free will",
        "freely choose",
    ),
    "safety_as_domination": (
        "for your safety",
        "for security reasons",
        "to keep you safe",
        "in the name of safety",
        "security requires",
    ),
    "natural_or_traditional": (
        "it's only natural",
        "that's just how it's always been",
        "the natural order",
        "traditional values require",
        "it's tradition",
        "the way it's always been",
    ),
    "autonomy_ignores_vulnerability": (
        "they agreed",
        "they signed",
        "it was their choice",
        "nobody made them",
        "they consented",
    ),
    "utility_hides_coercion": (
        "for the greater good",
        "the greater good",
        "net benefit to society",
        "overall it's better",
        "the ends justify",
    ),
}

_IDEOLOGICAL_META = {
    "care_as_control": (
        "Care language may conceal control",
        "'Care' or 'protection' framing can mask paternalistic control over a competent agent.",
    ),
    "freedom_as_pressure": (
        "Freedom language may conceal social pressure",
        "Insisting an act is 'free' can paper over real social or economic pressure to comply.",
    ),
    "safety_as_domination": (
        "Safety language may conceal domination",
        "'Safety'/'security' framing can normalise standing coercion that is never lifted.",
    ),
    "natural_or_traditional": (
        "'Natural'/'traditional' framing may normalise coercion",
        "Calling a coercive arrangement natural or traditional can excuse it from scrutiny.",
    ),
    "autonomy_ignores_vulnerability": (
        "Autonomy framing may ignore vulnerability",
        "'They agreed' can be used to wave away the vulnerability that made agreement unfree.",
    ),
    "utility_hides_coercion": (
        "Utility framing may hide individual coercion",
        "'The greater good' can hide coercion imposed on specific individuals.",
    ),
}

# Words suggesting non-physical coercion channels (for the tunnel-vision check).
_NONPHYSICAL_TERMS = (
    "economic",
    "financial",
    "money",
    "wage",
    "debt",
    "rent",
    "job",
    "social pressure",
    "reputation",
    "shame",
    "shun",
    "exclude",
    "information",
    "informational",
    "mislead",
    "withhold",
    "dependent",
    "dependency",
    "institution",
    "policy",
    "bureaucr",
)


def ideological_capture_findings(
    case: ActionCase, *, coercion_score: float = 0.0
) -> list[AuditFinding]:
    """Detect distorted *application* of the coercion axiom (transparent lexicon)."""
    findings: list[AuditFinding] = []
    text = case_text(case)
    power, vuln = amplifiers(case)
    cp = case.coercion_profile
    coercive = coercion_score >= 0.3 or (cp is not None and cp.severity >= 0.4)
    social = cp.social_pressure if cp is not None else 0.0

    for category, phrases in _IDEOLOGICAL_LEXICON.items():
        matched = [p for p in phrases if p in text]
        if not matched:
            continue
        title, why = _IDEOLOGICAL_META[category]
        severity = _S.WARNING
        if category == "care_as_control" and coercive and (vuln >= 0.5 or power >= 0.5):
            severity = _S.SERIOUS
        elif category == "freedom_as_pressure" and (social >= 0.4 or power >= 0.5):
            severity = _S.SERIOUS
        elif category == "safety_as_domination" and coercion_score >= 0.5:
            severity = _S.SERIOUS
        elif category == "autonomy_ignores_vulnerability" and vuln >= 0.5:
            severity = _S.SERIOUS
        elif category == "utility_hides_coercion" and coercive:
            severity = _S.SERIOUS
        elif category == "natural_or_traditional" and coercive:
            severity = _S.SERIOUS
        findings.append(
            _finding(
                f"AUD-IDEOLOGY-{category.upper()}",
                title,
                f"{title}. Detected phrasing: " + "; ".join(f'"{m}"' for m in matched),
                severity=severity,
                category=_C.IDEOLOGICAL_CAPTURE,
                why=why + " The audit flags distorted application of the axiom, not the axiom "
                "itself.",
                fields=["description", "language_act"],
                evidence=matched,
                questions=[
                    "Set the framing aside: is anyone being coerced here, and is it justified?"
                ],
                confidence=0.5,
            )
        )

    # Tunnel vision: only physical force is modelled though the narrative names other channels.
    if cp is not None and cp.physical_force > 0.0:
        nonphysical_named = any(term in text for term in _NONPHYSICAL_TERMS)
        nonphysical_modelled = max(
            cp.economic_pressure,
            cp.social_pressure,
            cp.informational_manipulation,
            cp.psychological_pressure,
            cp.legal_constraint,
        )
        if nonphysical_named and nonphysical_modelled < 0.2:
            findings.append(
                _finding(
                    "AUD-IDEOLOGY-PHYSICAL-TUNNEL-VISION",
                    "Coercion may be modelled too narrowly (only physical force counted)",
                    "The narrative mentions economic/social/informational/dependency pressure, "
                    "but the coercion profile records only physical force.",
                    severity=_S.SERIOUS,
                    category=_C.IDEOLOGICAL_CAPTURE,
                    why="Coercion is not only physical; treating it as such under-counts language, "
                    "economic, institutional, dependency, and informational coercion.",
                    fields=["coercion_profile"],
                    questions=["Are the non-physical channels of coercion modelled at all?"],
                    confidence=0.5,
                )
            )

    return findings


def assess_adversarial_risk(
    case: ActionCase,
    *,
    analysis: LanguageAnalysis | None = None,
    report: EvaluationReport | None = None,
    coercion_score: float = 0.0,
    coercion_moderate: float = 0.30,
) -> tuple[AdversarialRiskProfile, list[AuditFinding]]:
    """Return the adversarial-risk profile plus ideological-capture findings."""
    power, vuln = amplifiers(case)
    cp = case.coercion_profile
    ev = case.evidence
    coercive = coercion_score >= coercion_moderate or (cp is not None and cp.severity >= 0.5)

    # Language-derived risks.
    leading = 0.0
    false_necessity = 0.0
    false_dichotomy = 0.0
    if analysis is not None:
        p = analysis.profile
        form = _form_quality(p)
        content_risk = max(
            analysis.linguistic_coercion_score, p.manipulation_risk, 1.0 - p.truthfulness
        )
        leading = max(
            p.manipulation_risk,
            p.false_necessity,
            p.false_dichotomy,
            p.loaded_language,
            form * content_risk,
        )
        false_necessity = p.false_necessity
        false_dichotomy = p.false_dichotomy

    # Evidence-derived risks.
    no_counter = _no_counterevidence(ev)
    self_sourced = _only_self_sourced(ev)
    missing_counter = 0.6 if (coercive and no_counter) else (0.4 if no_counter else 0.0)
    one_sided = max(0.6 if self_sourced else 0.0, 0.4 if no_counter and coercive else 0.0)
    if self_sourced:
        data_laundering = 0.6
    elif evidence_is_weak(case) and coercive:
        data_laundering = 0.4
    else:
        data_laundering = 0.0

    # Alternatives.
    alts = case.available_alternatives
    fake_alt = 0.0
    just = case.justification
    if alts:
        if all(a.feasibility < 0.3 for a in alts):
            fake_alt = 0.6  # alternatives are listed but none is feasible
    elif just is not None and just.necessity.is_affirmative:
        fake_alt = 0.6  # necessity asserted with no alternatives analysed at all

    # Power / vulnerability that may be present but unscrutinised.
    hidden_power = power if power >= 0.5 else 0.0
    hidden_vuln = vuln if vuln >= 0.5 else 0.0
    if case.agency_profile is None and coercive:
        hidden_vuln = max(hidden_vuln, 0.4)  # vulnerability never characterised

    # Consent contamination.
    consent_contamination = 0.0
    if case.effective_consent_status().value == "GIVEN":
        if analysis is not None and analysis.affects_consent:
            consent_contamination = max(consent_contamination, 0.6)
        if max(power, vuln) >= 0.5:
            consent_contamination = max(consent_contamination, 0.4)

    ideological_findings = ideological_capture_findings(case, coercion_score=coercion_score)
    ideological_risk = _soft_or(
        [0.7 if f.severity == _S.SERIOUS else 0.5 for f in ideological_findings]
    )

    # Overconfidence: a confident, approving verdict despite real adversarial risk.
    overconfidence = 0.0
    if report is not None:
        approving = report.verdict in {
            Verdict.ACCEPTABLE,
            Verdict.ACCEPTABLE_WITH_RESERVATIONS,
        }
        peak = max(leading, missing_counter, one_sided, consent_contamination, ideological_risk)
        if approving and report.confidence >= 0.6 and peak >= 0.5:
            overconfidence = round(min(1.0, 0.4 + peak / 2.0), 4)

    profile = AdversarialRiskProfile(
        leading_language_risk=round(leading, 4),
        missing_counterevidence_risk=round(missing_counter, 4),
        one_sided_description_risk=round(one_sided, 4),
        false_necessity_risk=round(false_necessity, 4),
        false_dichotomy_risk=round(false_dichotomy, 4),
        fake_alternative_risk=round(fake_alt, 4),
        hidden_power_asymmetry_risk=round(hidden_power, 4),
        hidden_vulnerability_risk=round(hidden_vuln, 4),
        consent_contamination_risk=round(consent_contamination, 4),
        ideological_capture_risk=round(ideological_risk, 4),
        overconfidence_risk=overconfidence,
        data_laundering_risk=round(data_laundering, 4),
    )

    findings = list(ideological_findings)
    if overconfidence >= 0.6 and report is not None:
        findings.append(
            _finding(
                "AUD-ADV-OVERCONFIDENCE",
                "Confident approval despite material adversarial risk",
                f"The verdict is {report.verdict.value} at confidence {report.confidence:.2f}, "
                "while the description carries material adversarial risk.",
                severity=_S.SERIOUS,
                category=_C.OVERCONFIDENCE,
                why="High confidence is itself a claim; it should fall, not hold, when the "
                "description is the kind that could be leading the verdict.",
                fields=["confidence", "verdict"],
                questions=["Is this confidence warranted given what the description might hide?"],
                confidence=0.55,
            )
        )

    return profile, findings


# =============================================================================
# Verdict adjustment (only applied when audit is enabled)
# =============================================================================


def audit_adjusted_verdict(
    *,
    verdict: Verdict,
    confidence: float,
    audit: AuditReport,
    coercion_score: float,
    irreversible: bool,
    coercion_moderate: float,
) -> tuple[Verdict, float, list[str]]:
    """Return a possibly-adjusted ``(verdict, confidence, notes)`` given the audit.

    This is the deterministic rule the brief specifies. It is applied **only when
    audit is enabled**, so default evaluation is unchanged. The reasoning trace is
    untouched; these notes are recorded separately as audit warnings, keeping the
    rule-engine verdict and the description-audit clearly distinct.
    """
    notes: list[str] = []
    arp = audit.adversarial_risk_profile
    consent_central = any(
        f.category == AuditCategory.CONSENT and f.severity == AuditSeverity.CRITICAL
        for f in audit.findings
    )

    if audit.has_critical:
        notes.append(
            "adversarial audit found a critical red flag; this judgment is UNSTABLE and should "
            "not be treated as settled"
        )
        confidence = min(confidence, 0.4) - 0.05
        if irreversible:
            verdict = Verdict.INSUFFICIENT_DATA
            notes.append(
                "critical red flag on an effectively irreversible action: blocked pending review "
                "(treated as insufficient data)"
            )
        elif coercion_score >= coercion_moderate and verdict in {
            Verdict.ACCEPTABLE,
            Verdict.ACCEPTABLE_WITH_RESERVATIONS,
        }:
            verdict = Verdict.ETHICALLY_SUSPICIOUS
            notes.append(
                "critical red flag with non-trivial coercion: cannot confidently approve "
                "(capped at ethically suspicious)"
            )
        if consent_central:
            notes.append(
                "consent is central here and may be contaminated: treat consent as unestablished "
                "until re-checked"
            )

    if arp.ideological_capture_risk >= 0.6:
        notes.append(
            "high ideological-capture risk: requires explicit human review of how the coercion "
            "axiom is being applied"
        )
    if audit.bias_profile.language_beauty_bias_risk >= 0.6:
        notes.append(
            "high language-beauty bias risk: persuasive (or poor) form may be distorting the "
            "judgment -- weigh content over expression"
        )

    return verdict, round(max(0.0, confidence), 4), notes
