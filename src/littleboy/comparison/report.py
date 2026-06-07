"""Human- and machine-readable rendering of a comparison result.

The explanation is deliberately technical and non-rhetorical. It never claims a
moral fact ("this is objectively best", "LittleBoy has solved it"). It says only
what the engine can support: *under the current policy*, *given the available
evidence*, this option ranks where it does, and the ranking is stable or not.
"""

from __future__ import annotations

import json

from littleboy.comparison.models import ActionComparisonResult


def build_comparison_explanation(result: ActionComparisonResult) -> str:
    """Compose a clear, non-rhetorical summary of the comparison."""
    parts: list[str] = [
        f"Under the {result.policy_mode.value} policy profile, "
        f"{len(result.ranking)} option(s) were compared."
    ]
    if result.best_option_id is not None and result.ranking:
        top = result.ranking[0]
        parts.append(
            f"Given the available evidence, '{result.best_option_title}' is ranked first "
            f"because it is {top.primary_reason}."
        )
    else:
        parts.append(
            "No option is morally viable under this policy; the top-ranked option is the "
            "least-bad available, not an endorsement."
        )
    if result.dominated_options:
        parts.append(
            f"{len(result.dominated_options)} option(s) are strictly dominated by a less "
            "coercive option that is no worse elsewhere."
        )
    if result.data_sensitive:
        reason = (
            result.what_could_change_ranking[0]
            if result.what_could_change_ranking
            else "the top options are close"
        )
        parts.append(f"This ranking is unstable because {reason}.")
        if result.what_could_change_ranking:
            parts.append(
                "Additional data required: " + "; ".join(result.what_could_change_ranking[:3]) + "."
            )
    else:
        parts.append("The ranking is stable under the current evidence.")
    if result.tradeoffs:
        parts.append(
            f"{len(result.tradeoffs)} unresolved trade-off(s) are reported rather than hidden."
        )
    return " ".join(parts)


def comparison_to_dict(result: ActionComparisonResult) -> dict:
    """Return the comparison result as a plain dict (machine-readable, stable)."""
    return result.model_dump(mode="json")


def render_comparison_json(result: ActionComparisonResult, *, indent: int = 2) -> str:
    return json.dumps(comparison_to_dict(result), indent=indent, ensure_ascii=False)


def render_comparison_text(result: ActionComparisonResult) -> str:
    """Render a comparison result as a readable, sectioned text block."""
    lines: list[str] = []
    best = result.best_option_title or "(none morally viable)"
    lines.append(f"BEST OPTION: {best}   [policy: {result.policy_mode.value}]")
    lines.append("")
    lines.append(result.comparison_explanation)

    def _section(title: str, items: list[str]) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not items:
            lines.append("  (none)")
        for item in items:
            lines.append(f"  - {item}")

    lines.append("")
    lines.append("Ranking:")
    for entry in result.ranking:
        viability = (
            "viable"
            if entry.is_morally_viable and not entry.viable_with_reservations
            else "viable (with reservations)"
            if entry.is_morally_viable
            else "NOT viable"
        )
        lines.append(
            f"  #{entry.rank} {entry.title} -- {entry.verdict.value} "
            f"[{viability}] coercion={entry.coercion_score:.2f} confidence={entry.confidence:.2f}"
        )
        lines.append(f"      because: {entry.primary_reason}")
        if entry.downgrade_reason:
            lines.append(f"      {entry.downgrade_reason}")

    _section("Strictly dominated options", result.dominated_options)
    _section("Non-dominated options", result.non_dominated_options)
    _section("Unresolved trade-offs", [t.description for t in result.tradeoffs])

    lines.append("")
    lines.append(
        "Immediate-term order: "
        + (" > ".join(result.immediate_ranking) if result.immediate_ranking else "(n/a)")
    )
    lines.append(
        "Long-term order:      "
        + (" > ".join(result.long_term_ranking) if result.long_term_ranking else "(n/a)")
    )
    lines.append(f"Immediate vs long-term rankings conflict: {result.rankings_conflict}")

    _section("Missing data that could change the ranking", result.what_could_change_ranking)
    _section("Missing temporal data", result.temporal_missing_data)
    _section("Uncertainty warnings", result.uncertainty_warnings)

    if result.audit is not None:
        ca = result.audit
        lines.append("")
        lines.append(
            "Adversarial audit: "
            f"ranking_unstable_due_to_missing_data={ca.ranking_unstable_due_to_missing_data}"
        )
        _section(
            "Audit findings",
            [f"[{f.severity.value}/{f.category.value}] {f.title}" for f in ca.findings],
        )
        _section(
            "Per-option audit",
            [
                f"{oid}: stable={a.judgment_stable}, red_flags={len(a.red_flags)}"
                for oid, a in ca.option_audits.items()
            ],
        )

    return "\n".join(lines)
