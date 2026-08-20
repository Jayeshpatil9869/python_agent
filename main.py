"""Website Intelligence Agent CLI."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

from agent.orchestrator import WebsiteAnalysisAgent
from config.settings import AnalysisOptions, Settings

load_dotenv()

console = Console()
PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


def _ensure_runtime(ai_enabled: bool) -> None:
    """Verify required packages and guide user if using wrong Python."""
    missing: list[str] = []
    for module, package in (
        ("playwright", "playwright"),
        ("bs4", "beautifulsoup4"),
        ("jinja2", "Jinja2"),
    ):
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if ai_enabled:
        try:
            __import__("httpx")
        except ImportError:
            missing.append("httpx")

    if missing:
        console.print("[bold red]Missing Python packages:[/bold red]", ", ".join(missing))
        console.print("\n[yellow]You are likely running system Python instead of the project venv.[/yellow]")
        console.print("Use one of these:\n")
        console.print("  .venv\\Scripts\\activate")
        console.print("  python main.py ...\n")
        console.print("Or install deps into the current Python:")
        console.print("  pip install -r requirements.txt")
        raise typer.Exit(1)

    if sys.prefix == sys.base_prefix and VENV_PYTHON.exists():
        console.print(
            "[yellow]Tip:[/yellow] Project venv detected. Prefer:\n"
            "  .venv\\Scripts\\python main.py <url> --ai\n"
        )


def main(
    url: str = typer.Argument(..., help="Website URL to analyze"),
    depth: int = typer.Option(2, "--depth", help="Crawl depth"),
    max_pages: int = typer.Option(10, "--max-pages", help="Maximum pages to analyze"),
    timeout: int = typer.Option(30000, "--timeout", help="Page timeout in ms"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run headless"),
    browser: str = typer.Option("chromium", "--browser", help="Browser engine"),
    mobile: bool = typer.Option(True, "--mobile/--no-mobile", help="Include mobile analysis"),
    desktop: bool = typer.Option(True, "--desktop/--no-desktop", help="Include desktop analysis"),
    tablet: bool = typer.Option(False, "--tablet", help="Include tablet viewports (with --deep)"),
    animations: bool = typer.Option(False, "--animations", help="Enable animation analysis"),
    interactions: bool = typer.Option(False, "--interactions", help="Enable interaction testing"),
    ai: bool = typer.Option(False, "--ai", help="Enable AI interpretation"),
    deep: bool = typer.Option(False, "--deep", help="Deep analysis mode"),
    output: Optional[Path] = typer.Option(None, "--output", help="Output directory"),
    same_origin: bool = typer.Option(True, "--same-origin/--all-domains", help="Same-origin only"),
) -> None:
    """Website Reverse-Engineering / Design Intelligence Agent."""
    _ensure_runtime(ai_enabled=ai)

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    settings = Settings()
    options = AnalysisOptions(
        url=url,
        depth=depth,
        max_pages=max_pages or settings.max_pages,
        timeout=timeout or settings.default_timeout,
        headless=headless,
        browser=browser or settings.browser_type,
        mobile=mobile,
        desktop=desktop,
        tablet=tablet,
        animations=animations,
        interactions=interactions,
        ai=ai,
        deep=deep,
        output=output or settings.output_dir,
        same_origin=same_origin,
    )

    console.print("\n[bold cyan]Website Intelligence Agent[/bold cyan]")
    console.print(f"Target: [green]{url}[/green]")
    console.print(f"Mode: {'DEEP' if deep else 'FAST'}{' + AI' if ai else ''}\n")

    agent = WebsiteAnalysisAgent(options, settings)

    try:
        intelligence = asyncio.run(agent.run())
        console.print("\n[bold green]Analysis complete![/bold green]")
        console.print(f"Output: [blue]{agent.output_dir}[/blue]")
        console.print(f"Pages analyzed: {len(intelligence.pages)}")
        console.print(f"Technologies: {len(intelligence.technologies)}")
    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis interrupted.[/yellow]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"\n[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)


def run() -> None:
    typer.run(main)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        typer.run(main)
    else:
        run()
