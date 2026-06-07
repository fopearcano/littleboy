"""LittleBoy's scenario builder / case-input wizard (v0.4).

LittleBoy should not only judge finished cases; it should help *construct* a
morally evaluable case by detecting what is missing and asking precise,
prioritised questions -- so that moral judgment is not made prematurely under
weak data (Axiom 5).
"""

from __future__ import annotations

from littleboy.case_builder.builder import CaseBuilder
from littleboy.case_builder.completeness import completeness_report
from littleboy.case_builder.questions import generate_questions
from littleboy.case_builder.session import (
    WizardPrompt,
    build_case_from_answers,
    wizard_prompts,
)
from littleboy.case_builder.templates import (
    ScenarioTemplate,
    all_templates,
    get_template,
    list_templates,
)

__all__ = [
    "CaseBuilder",
    "ScenarioTemplate",
    "WizardPrompt",
    "all_templates",
    "build_case_from_answers",
    "completeness_report",
    "generate_questions",
    "get_template",
    "list_templates",
    "wizard_prompts",
]
