"""Rendering for deliberation reports (JSON for machines, text for terminals)."""

from __future__ import annotations

import json

from littleboy.deliberation.models import (
    ComparisonDeliberationReport,
    DeliberationReport,
)


def render_deliberation_json(report: DeliberationReport, *, indent: int = 2) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=indent, ensure_ascii=False)


def render_deliberation_text(report: DeliberationReport) -> str:
    """Render a single-case deliberation as a readable, sectioned text block."""
    lines: list[str] = [f"DELIBERATION: {report.headline}"]
    if report.verdict is not None:
        lines.append(
            f"  verdict={report.verdict.value}  confidence={report.confidence:.2f}  "
            f"stable_under_information={report.stable_under_information}"
        )

    def _section(title: str, items: list[str]) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not items:
            lines.append("  (none)")
        for item in items:
            lines.append(f"  - {item}")

    _section(
        "Why this verdict",
        [f"[{s.kind}] {s.claim}  ({s.basis})" for s in report.steps],
    )
    _section("Decisive factors", report.decisive_factors)

    lines.append("")
    if report.most_informative is not None:
        mi = report.most_informative
        lines.append(f"Most informative unknown: {mi.field}  (value {mi.value:.2f})")
        lines.append(f"  question: {mi.question}")
        lines.append(f"  swing:    {mi.swing}")
    else:
        lines.append("Most informative unknown: (none — the case is information-stable)")

    _section(
        "Value of information (ranked)",
        [
            f"{iv.field}: value {iv.value:.2f}; changes_verdict={iv.changes_verdict}; {iv.swing}"
            for iv in report.information_values
        ],
    )
    if report.most_informative is not None and report.most_informative.resolutions:
        _section(
            f"Resolutions of '{report.most_informative.field}'",
            [
                f"{r.label} -> {r.verdict.value} (confidence {r.confidence:.2f})"
                for r in report.most_informative.resolutions
            ],
        )
    _section("Notes", report.notes)
    return "\n".join(lines)


def render_comparison_deliberation_json(
    report: ComparisonDeliberationReport, *, indent: int = 2
) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=indent, ensure_ascii=False)


def render_comparison_deliberation_text(report: ComparisonDeliberationReport) -> str:
    """Render a comparison deliberation as a readable, sectioned text block."""
    lines: list[str] = [f"DELIBERATION: {report.headline}"]
    lines.append(
        f"  best={report.best_option_id}  runner_up={report.runner_up_id}  "
        f"ranking_robust={report.ranking_robust}"
    )

    def _section(title: str, items: list[str]) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not items:
            lines.append("  (none)")
        for item in items:
            lines.append(f"  - {item}")

    _section("Why the top option wins", report.why_top_wins)
    if report.decisive_layer:
        lines.append("")
        lines.append(f"Decisive layer vs runner-up: {report.decisive_layer}")

    lines.append("")
    if report.most_informative is not None:
        mi = report.most_informative
        lines.append(f"Most informative unknown: {mi.option_id}.{mi.field}  (value {mi.value:.2f})")
        lines.append(f"  question: {mi.question}")
        lines.append(f"  swing:    {mi.swing}")
    else:
        lines.append("Most informative unknown: (none — the ranking is information-robust)")

    _section(
        "Value of information (ranked)",
        [
            f"{iv.option_id}.{iv.field}: value {iv.value:.2f}; "
            f"changes_best_option={iv.changes_best_option}; {iv.swing}"
            for iv in report.information_values
        ],
    )
    _section("Notes", report.notes)
    return "\n".join(lines)
