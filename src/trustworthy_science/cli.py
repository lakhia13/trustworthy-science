"""Trustworthy Science CLI — score, filter, and explain scientific papers."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

_TIER_COLORS = {
    "Trusted": "green",
    "Caution": "yellow",
    "Untrusted": "red",
}

# Resolve config path relative to the repo root (two levels up from this file,
# which lives inside src/trustworthy_science/).
_REPO_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_CONFIG = str(_REPO_ROOT / "config" / "scoring.yaml")


def _load_filter(config_path: str) -> "TruthFilter":
    from trustworthy_science.api import TruthFilter
    return TruthFilter.from_config(config_path)


@click.group()
@click.option("--config", default=_DEFAULT_CONFIG, show_default=True, help="Path to scoring config YAML.")
@click.option("--log-level", default="WARNING", show_default=True,
              type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False))
@click.option("-v", "--verbose", is_flag=True, default=False,
              help="Enable verbose agent logs (shorthand for --log-level INFO).")
@click.pass_context
def cli(ctx: click.Context, config: str, log_level: str, verbose: bool) -> None:
    """Trustworthy Science — AI-powered credibility filter for scientific literature."""
    if verbose:
        log_level = "INFO"
    fmt = "%(message)s" if log_level == "INFO" else "%(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.WARNING), format=fmt)
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


# ---------------------------------------------------------------------------
# score command
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--doi", multiple=True, help="DOI(s) to score. Can be repeated.")
@click.option("--pmid", multiple=True, help="PMID(s) to score. Can be repeated. Uses BioC JSON full-text when available.")
@click.option("--query", default=None, help="Natural-language query to retrieve papers.")
@click.option("--top-k", default=10, show_default=True, help="Maximum number of papers to retrieve.")
@click.option("--output", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def score(ctx: click.Context, doi: tuple[str], pmid: tuple[str], query: str | None, top_k: int, output: str) -> None:
    """Score papers by DOI, PMID, or query and display credibility report."""
    tf = _load_filter(ctx.obj["config"])

    results: list = []
    with console.status("[bold blue]Scoring papers...[/]"):
        # Score individual PMIDs directly (enables BioC full-text fetch)
        for p in pmid:
            r = tf.score_single_by_pmid(p)
            if r:
                results.append(r)
        # Score DOIs / query via the multi-paper graph
        if doi or query:
            results += tf.score_papers(
                dois=list(doi) if doi else None,
                query=query,
                top_k=top_k,
            )

    if not results:
        console.print("[yellow]No papers found.[/]")
        sys.exit(0)

    if output == "json":
        console.print_json(json.dumps(results, indent=2, default=str))
        return

    _print_results_table(results)


# ---------------------------------------------------------------------------
# filter command
# ---------------------------------------------------------------------------

@cli.command(name="filter")
@click.option("--query", required=True, help="Research question to retrieve papers for.")
@click.option("--top-k", default=20, show_default=True)
@click.option("--min-tier", type=click.Choice(["Trusted", "Caution", "Untrusted"]), default="Caution", show_default=True)
@click.option("--output", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def filter_cmd(ctx: click.Context, query: str, top_k: int, min_tier: str, output: str) -> None:
    """Retrieve papers for a research question and apply the Truth Filter."""
    tf = _load_filter(ctx.obj["config"])

    with console.status("[bold blue]Retrieving and filtering papers...[/]"):
        results = tf.filter_for_rag(query=query, top_k=top_k, min_tier=min_tier)

    if not results:
        console.print(f"[yellow]No papers met the minimum tier '{min_tier}'.[/]")
        sys.exit(0)

    if output == "json":
        console.print_json(json.dumps(results, indent=2, default=str))
        return

    console.print(f"\n[bold]Truth-filtered results for:[/] [italic]{query}[/]")
    console.print(f"[dim]Minimum tier: {min_tier} | Showing {len(results)} qualifying papers[/]\n")
    _print_results_table(results)


# ---------------------------------------------------------------------------
# explain command
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--doi", default=None, help="DOI of the paper to explain.")
@click.option("--pmid", default=None, help="PMID of the paper to explain. Uses BioC JSON full-text (PMC OA) when available.")
@click.pass_context
def explain(ctx: click.Context, doi: str | None, pmid: str | None) -> None:
    """Show a detailed per-dimension credibility explanation for a single paper.

    Accepts either a DOI or a PMID.  When a PMID is supplied, full text is
    fetched via the BioC JSON API (Step 1 of the cascade), which provides
    pre-segmented, unicode-clean sections for the highest analysis quality.

    Examples:

      trustworthy-science explain --doi 10.1038/s41586-020-2748-1

      trustworthy-science explain --pmid 23193264
    """
    if not doi and not pmid:
        console.print("[red]Error: provide either --doi or --pmid.[/]")
        sys.exit(1)
    if doi and pmid:
        console.print("[red]Error: provide only one of --doi or --pmid, not both.[/]")
        sys.exit(1)

    tf = _load_filter(ctx.obj["config"])

    identifier = pmid or doi
    with console.status(f"[bold blue]Scoring {identifier}...[/]"):
        if pmid:
            result = tf.score_single_by_pmid(pmid)
        else:
            result = tf.score_single(doi)

    if result is None:
        label = f"PMID: {pmid}" if pmid else f"DOI: {doi}"
        console.print(f"[red]Could not score paper with {label}[/]")
        sys.exit(1)

    tier = result.get("tier", "Unknown")
    score_val = result.get("score", 0)
    color = _TIER_COLORS.get(tier, "white")
    coverage = result.get("coverage", "metadata_only")
    fetch_source = result.get("fetch_source", "unknown")

    # Coverage warning — shown when full text could not be retrieved
    coverage_warning = ""
    if coverage == "full_text" and fetch_source == "bioc":
        coverage_warning = (
            "\n[bold green]✓ Full text via BioC JSON (PMID, PMC Open Access)[/] — "
            "structured sections used for maximum analysis accuracy."
        )
    elif coverage == "metadata_only":
        coverage_warning = (
            "\n[bold yellow]⚠ Metadata-only scoring (35% confidence)[/] — "
            "full text was unavailable (paywalled or not open-access). "
            "Scores may underestimate quality; open-access papers score more accurately."
        )
    elif coverage == "abstract_only":
        coverage_warning = (
            "\n[dim yellow]△ Abstract-only scoring (60% confidence)[/] — "
            "full text unavailable; statistical and methods checks are limited."
        )

    # ASCII score bar
    filled = round(score_val / 100 * 20)
    score_bar = f"[{color}]{'█' * filled}{'░' * (20 - filled)}[/] {score_val}/100"

    console.print()
    console.print(Panel(
        f"[bold]{result.get('title', doi)}[/]\n"
        f"[dim]{result.get('venue', '')} | {result.get('year', '')}[/]\n\n"
        f"[bold {color}]Tier: {tier}[/]   {score_bar}\n\n"
        f"{result.get('summary', '')}"
        f"{coverage_warning}",
        title="Credibility Report",
        border_style=color,
    ))

    if result.get("hard_flags"):
        console.print("\n[bold red]Hard Flags (critical)[/]")
        for flag in result["hard_flags"]:
            console.print(f"  [red]HARD[/] {flag}")

    if result.get("soft_flags"):
        console.print("\n[bold yellow]Soft Flags (concerns)[/]")
        for flag in result["soft_flags"]:
            console.print(f"  [yellow]SOFT[/] {flag}")

    if result.get("quality_signals"):
        console.print("\n[bold green]Quality Signals (positive)[/]")
        for flag in result["quality_signals"]:
            console.print(f"  [green]GOOD[/] {flag}")

    console.print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_results_table(results: list[dict]) -> None:
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold blue")
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", width=6)
    table.add_column("Tier", width=10)
    table.add_column("Title", ratio=3)
    table.add_column("Venue / Year", ratio=1)
    table.add_column("Top Flags", ratio=2)

    for i, r in enumerate(results, 1):
        tier = r.get("tier", "Unknown")
        color = _TIER_COLORS.get(tier, "white")
        all_flags = r.get("hard_flags", []) + r.get("soft_flags", [])
        flag_str = ", ".join(all_flags[:3])
        venue_year = f"{r.get('venue', '')} {r.get('year', '') or ''}".strip()

        table.add_row(
            str(i),
            f"[{color}]{r.get('score', 0)}[/]",
            f"[bold {color}]{tier}[/]",
            r.get("title", r.get("doi", "—")),
            venue_year,
            f"[{color}]{flag_str}[/]" if flag_str else "[dim]—[/]",
        )

    console.print(table)


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
