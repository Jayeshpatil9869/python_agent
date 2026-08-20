"""Validate analysis output directory."""

import json
import sys
from pathlib import Path

import typer

from intelligence.validation import validate_analysis_output

app = typer.Typer(add_completion=False)


@app.command()
def main(output_path: Path = typer.Argument(..., help="Path to analysis output directory")) -> None:
    """Validate website intelligence output evidence."""
    if not output_path.exists():
        typer.echo(f"Output directory not found: {output_path}", err=True)
        raise typer.Exit(1)

    result = validate_analysis_output(output_path)
    typer.echo(json.dumps(result, indent=2))
    status = result.get("overall_status", "FAIL")
    typer.echo(f"\nValidation: {status}")
    if status == "FAIL":
        raise typer.Exit(2)
    if status == "PARTIAL":
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
