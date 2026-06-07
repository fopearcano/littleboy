"""A minimal command-line interface for LittleBoy.

Usage::

    littleboy evaluate examples/simple_case.json
    littleboy evaluate examples/simple_case.json --format text
    littleboy version

It loads a JSON :class:`~littleboy.core.models.ActionCase`, runs the evaluator,
and prints the resulting report. The CLI is intentionally thin: all reasoning
lives in the library, so the engine can be used without it.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import ValidationError

from littleboy import __version__
from littleboy.core.evaluator import EthicalEvaluator
from littleboy.core.models import ActionCase
from littleboy.reasoning.report import render_json, render_text

app = typer.Typer(
    add_completion=False,
    help="LittleBoy: a transparent ethical evaluation engine (evil = coercion).",
)


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
) -> None:
    """Evaluate a single action case from a JSON file."""
    if output_format not in {"json", "text"}:
        typer.echo(f"Unknown format '{output_format}'; use 'json' or 'text'.", err=True)
        raise typer.Exit(code=2)

    try:
        raw = json.loads(case_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON in {case_path}: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    try:
        case = ActionCase.model_validate(raw)
    except ValidationError as exc:
        typer.echo(f"Invalid ActionCase in {case_path}:\n{exc}", err=True)
        raise typer.Exit(code=2) from exc

    report = EthicalEvaluator().evaluate(case)
    typer.echo(render_text(report) if output_format == "text" else render_json(report))


@app.command()
def version() -> None:
    """Print the LittleBoy version."""
    typer.echo(__version__)


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
