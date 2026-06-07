"""Rendering for deliberation reports (JSON for machines, text for terminals)."""

from __future__ import annotations

import json

from littleboy.deliberation.models import (
    ComparisonDeliberationReport,
    DeliberationReport,
    IntakeTranscript,
    MinimalQuestionPlan,
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

    lines.append("")
    if report.smallest_flip_size is None:
        lines.append(
            f"Smallest set of facts that would change the verdict: none "
            f"(robust to combinations up to {report.searched_max_size})"
        )
    else:
        lines.append(
            f"Smallest set of facts that would change the verdict: {report.smallest_flip_size}"
        )
    _section(
        "Minimal flip sets",
        [
            f"{{{', '.join(fs.fields)}}} -> {fs.resulting_verdict.value}  "
            f"[{'; '.join(f'{r.field}: {r.label}' for r in fs.resolution)}]"
            for fs in report.minimal_flip_sets
        ],
    )
    _section("Notes", report.notes)
    return "\n".join(lines)


def render_question_plan_json(report: MinimalQuestionPlan, *, indent: int = 2) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=indent, ensure_ascii=False)


def render_question_plan_text(report: MinimalQuestionPlan) -> str:
    """Render a minimal-sufficient question plan as a readable text block."""
    lines: list[str] = ["MINIMAL QUESTION PLAN (only what could change the verdict)"]
    if report.verdict is not None:
        lines.append(
            f"  current verdict={report.verdict.value}  confidence={report.confidence:.2f}  "
            f"verdict_robust={report.verdict_robust}"
        )
    if report.smallest_flip_size is not None:
        lines.append(f"  smallest sufficient set: {report.smallest_flip_size} question(s)")

    lines.append("")
    lines.append("Questions:")
    if not report.questions:
        lines.append("  (none — no answerable question would change the verdict)")
    for q in report.questions:
        scope = "alone changes the verdict" if q.alone_changes_verdict else "in a minimal set"
        cheap = ", in cheapest set" if q.in_cheapest_set else ""
        lines.append(
            f"  [{q.priority}/{q.category}] {q.question}  "
            f"(value {q.value:.2f}; cost {q.cost:g}; {scope}{cheap})"
        )
        lines.append(f"      why it matters: {q.why_it_matters}")
    if report.cheapest_set:
        lines.append("")
        lines.append(
            f"Cheapest sufficient set: {{{', '.join(report.cheapest_set)}}}"
            + (f"  (total cost {report.cheapest_set_cost:g})" if report.cheapest_set_cost else "")
        )

    if report.notes:
        lines.append("")
        lines.append("Notes:")
        for n in report.notes:
            lines.append(f"  - {n}")
    return "\n".join(lines)


def render_intake_json(report: IntakeTranscript, *, indent: int = 2) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=indent, ensure_ascii=False)


def render_intake_text(report: IntakeTranscript) -> str:
    """Render an interactive minimal-intake transcript as a readable text block."""
    lines: list[str] = ["MINIMAL INTAKE TRANSCRIPT"]
    initial = report.initial_verdict.value if report.initial_verdict else "n/a"
    final = report.final_verdict.value if report.final_verdict else "n/a"
    conf = f"{report.final_confidence:.2f}" if report.final_confidence is not None else "n/a"
    lines.append(
        f"  {initial} -> {final}  (final confidence {conf}; "
        f"{report.questions_asked} question(s) asked; settled={report.settled})"
    )
    lines.append("")
    lines.append("Steps:")
    if not report.steps:
        lines.append("  (none — the verdict was already settled)")
    for i, s in enumerate(report.steps, 1):
        after = s.verdict_after.value if s.verdict_after else "n/a"
        flag = "  <-- verdict changed" if s.verdict_changed else ""
        lines.append(f"  {i}. {s.question}")
        lines.append(f"     answer: {s.answer}  ->  {after}{flag}")
    if report.notes:
        lines.append("")
        for n in report.notes:
            lines.append(f"  - {n}")
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
