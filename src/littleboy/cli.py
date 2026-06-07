"""A minimal command-line interface for LittleBoy.

Usage::

    littleboy evaluate examples/high_coercion_missing_consent.json
    littleboy evaluate examples/simple_case.json --format text
    littleboy experiment examples/manipulative_language_case.json
    littleboy version

It loads a JSON :class:`~littleboy.core.models.ActionCase`, runs the evaluator
(or the ethical-experiment runner), and prints the result. The CLI is
intentionally thin: all reasoning lives in the library, so the engine can be
used without it. Malformed input fails gracefully with an explanation.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import ValidationError

from littleboy import __version__
from littleboy.core.enums import PolicyMode
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.models import ActionCase
from littleboy.reasoning.experiment import EthicalExperiment
from littleboy.reasoning.report import render_json, render_text

_POLICY_CHOICES = ", ".join(m.value for m in PolicyMode)

app = typer.Typer(
    add_completion=False,
    help="LittleBoy: a transparent ethical evaluation engine (evil = coercion).",
)


def _load_case(case_path: Path) -> ActionCase:
    """Load and validate an ActionCase from JSON, exiting gracefully on error."""
    try:
        raw = json.loads(case_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON in {case_path}: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    try:
        return ActionCase.model_validate(raw)
    except ValidationError as exc:
        typer.echo(f"Invalid ActionCase in {case_path}:\n{exc}", err=True)
        raise typer.Exit(code=2) from exc


@app.command()
def evaluate(
    case_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON file describing the ActionCase.",
    ),
    output_format: str = typer.Option(
        "json", "--format", "-f", help="Output format: 'json' or 'text'."
    ),
    policy: str = typer.Option(
        "standard", "--policy", "-p", help=f"Policy strictness: {_POLICY_CHOICES}."
    ),
) -> None:
    """Evaluate a single action case from a JSON file under a policy profile."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)
    try:
        policy_mode = PolicyMode(policy)
    except ValueError as exc:
        typer.echo(f"Unknown policy '{policy}'; use one of: {_POLICY_CHOICES}.", err=True)
        raise typer.Exit(code=2) from exc

    case = _load_case(case_path)
    report = EthicalEvaluator(policy_mode).evaluate(case)
    typer.echo(render_text(report) if output_format == "text" else render_json(report))


@app.command()
def experiment(
    case_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a JSON file describing the ActionCase.",
    ),
) -> None:
    """Run an ethical experiment (falsificatory + heuristic) over a case."""
    case = _load_case(case_path)
    result = EthicalExperiment().run(case)
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


@app.command()
def version() -> None:
    """Print the LittleBoy version."""
    typer.echo(__version__)


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
