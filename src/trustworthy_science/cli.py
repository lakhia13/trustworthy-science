"""Trustworthy Science CLI — score, filter, explain, and search scientific papers."""

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
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

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
# search command — text query with live progress
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query")
@click.option("--top-k", default=10, show_default=True, help="Number of papers to retrieve and score.")
@click.option("--min-tier", type=click.Choice(["Trusted", "Caution", "Untrusted"]), default="Untrusted",
              show_default=True, help="Only display papers at or above this tier.")
@click.option("--output", type=click.Choice(["table", "json"]), default="table", show_default=True)
@click.pass_context
def search(ctx: click.Context, query: str, top_k: int, min_tier: str, output: str) -> None:
    """Search PubMed for QUERY, score all results and display a credibility table.

    Example:

      trustworthy-science search "CRISPR cancer therapy" --top-k 5
    """
    from trustworthy_science.tools.pubmed import search_pubmed, fetch_pubmed_metadata
    from trustworthy_science.state import PaperState
    from trustworthy_science.graph import _make_paper_graph

    tf = _load_filter(ctx.obj["config"])

    console.print(f"\n[bold blue]Searching PubMed:[/] [italic]{query}[/]")

    with console.status("[blue]Fetching paper list from PubMed...[/]"):
        try:
            pmids = search_pubmed(query, max_results=top_k)
            stubs = fetch_pubmed_metadata(pmids)
        except Exception as exc:
            console.print(f"[red]PubMed search failed: {exc}[/]")
            sys.exit(1)

    if not stubs:
        console.print("[yellow]No papers found for that query.[/]")
        sys.exit(0)

    console.print(f"[dim]Retrieved {len(stubs)} papers. Scoring...[/]\n")

    paper_graph = _make_paper_graph(tf._config)
    results: list[dict] = []

    tier_order = {"Trusted": 2, "Caution": 1, "Untrusted": 0}
    min_tier_val = tier_order.get(min_tier, 0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Scoring papers", total=len(stubs))
        for stub in stubs:
            progress.update(task, description=f"Scoring: {stub.title[:55]}..." if stub.title else "Scoring...")
            paper_state = PaperState(stub=stub)
            try:
                final_state = paper_graph.invoke(paper_state)
                ps = PaperState(**final_state)
            except Exception as exc:
                logging.getLogger(__name__).warning("Scoring failed for %s: %s", stub.uid, exc)
                progress.advance(task)
                continue

            if ps.final:
                results.append({
                    "title": ps.stub.title,
                    "doi": ps.stub.doi,
                    "pmid": ps.stub.pmid,
                    "year": ps.stub.year,
                    "venue": ps.stub.venue,
                    "score": ps.final.composite_score,
                    "tier": ps.final.tier,
                    "include": tier_order.get(ps.final.tier, 0) >= min_tier_val,
                    "coverage": ps.final.coverage,
                    "fetch_source": ps.parsed.fetch_source if ps.parsed else "unknown",
                    "summary": ps.final.summary,
                    "hard_flags": [f.code for f in ps.final.hard_flags],
                    "soft_flags": [f.code for f in ps.final.soft_flags],
                    "quality_signals": [f.code for f in ps.final.quality_signals],
                    "per_dimension": ps.final.per_dimension,
                    "structured_report": ps.final.structured_report,
                })
            progress.advance(task)

    if not results:
        console.print("[yellow]No papers could be scored.[/]")
        sys.exit(0)

    results.sort(key=lambda x: x["score"], reverse=True)
    filtered = [r for r in results if r.get("include", True)]

    console.print()
    if output == "json":
        # Serialize structured_report as dict
        for r in results:
            if r.get("structured_report") is not None:
                r["structured_report"] = r["structured_report"].model_dump()
            r["per_dimension"] = [d.model_dump() if hasattr(d, "model_dump") else d for d in r.get("per_dimension", [])]
        console.print_json(json.dumps(results, indent=2, default=str))
        return

    console.print(f"[bold]Results for:[/] [italic]{query}[/]")
    console.print(f"[dim]{len(filtered)}/{len(results)} papers meet minimum tier '{min_tier}'[/]\n")
    _print_results_table(filtered if filtered else results)


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
# explain command — structured multi-section output
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--doi", default=None, help="DOI of the paper to explain.")
@click.option("--pmid", default=None, help="PMID of the paper to explain. Uses BioC JSON full-text (PMC OA) when available.")
@click.pass_context
def explain(ctx: click.Context, doi: str | None, pmid: str | None) -> None:
    """Show a detailed per-dimension credibility report for a single paper.

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

    _render_structured_report(result, doi or pmid)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_structured_report(result: dict, identifier: str | None) -> None:
    """Render a full structured credibility report to the terminal."""
    tier = result.get("tier", "Unknown")
    score_val = result.get("score", 0)
    color = _TIER_COLORS.get(tier, "white")
    coverage = result.get("coverage", "metadata_only")
    fetch_source = result.get("fetch_source", "unknown")

    # Coverage note
    if coverage == "full_text" and fetch_source == "bioc":
        coverage_note = (
            "[bold green]Full text via BioC JSON (PMC Open Access)[/] — "
            "structured sections used for maximum analysis accuracy."
        )
    elif coverage == "metadata_only":
        coverage_note = (
            "[bold yellow]Metadata-only scoring (35% confidence)[/] — "
            "full text was unavailable (paywalled or not open-access)."
        )
    elif coverage == "abstract_only":
        coverage_note = (
            "[dim yellow]Abstract-only scoring (60% confidence)[/] — "
            "full text unavailable; statistical and methods checks are limited."
        )
    else:
        coverage_note = f"[dim]Coverage: {coverage} | Source: {fetch_source}[/]"

    # ASCII score bar
    filled = round(score_val / 100 * 20)
    score_bar = f"[{color}]{'█' * filled}{'░' * (20 - filled)}[/] {score_val}/100"

    # ── Header Panel ────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        f"[bold]{result.get('title', identifier)}[/]\n"
        f"[dim]{result.get('venue', '')} | {result.get('year', '')}[/]\n\n"
        f"[bold {color}]Tier: {tier}[/]   {score_bar}\n\n"
        f"{coverage_note}",
        title="Credibility Report",
        border_style=color,
    ))

    # Retrieve structured report (may be a dict from API or a Pydantic model)
    sr = result.get("structured_report")

    # Normalise: accept both Pydantic model and plain dict
    if sr is not None and hasattr(sr, "model_dump"):
        sr = sr.model_dump()

    if sr:
        # ── Overall Verdict ──────────────────────────────────────────────────
        if sr.get("overall_verdict"):
            console.print(Panel(
                sr["overall_verdict"],
                title="Overall Verdict",
                border_style=color,
                padding=(0, 1),
            ))

        # ── Score Breakdown Table ────────────────────────────────────────────
        breakdown = sr.get("score_breakdown", [])
        if breakdown:
            tbl = Table(
                title="Score Breakdown",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold blue",
                expand=False,
            )
            tbl.add_column("Dimension", style="bold", min_width=20)
            tbl.add_column("Score", width=8, justify="center")
            tbl.add_column("Rationale", ratio=1)

            for entry in breakdown:
                dim = entry.get("dimension", "")
                pct = entry.get("score_pct", 0)
                rationale = entry.get("rationale", "")
                if pct >= 70:
                    row_color = "green"
                elif pct >= 45:
                    row_color = "yellow"
                else:
                    row_color = "red"
                tbl.add_row(
                    dim,
                    f"[{row_color}]{pct}%[/]",
                    rationale,
                )
            console.print()
            console.print(tbl)

        # ── Key Concerns ─────────────────────────────────────────────────────
        concerns = sr.get("key_concerns", [])
        if concerns:
            concerns_text = "\n".join(f"  • {c}" for c in concerns)
            console.print()
            console.print(Panel(
                concerns_text,
                title="Key Concerns",
                border_style="red",
                padding=(0, 1),
            ))

        # ── Positive Signals ─────────────────────────────────────────────────
        positives = sr.get("positive_signals", [])
        if positives:
            positives_text = "\n".join(f"  • {p}" for p in positives)
            console.print()
            console.print(Panel(
                positives_text,
                title="Positive Signals",
                border_style="green",
                padding=(0, 1),
            ))

        # ── Recommendation ───────────────────────────────────────────────────
        recommendation = sr.get("recommendation", "")
        if recommendation:
            console.print()
            console.print(Panel(
                f"[bold]{recommendation}[/]",
                title="Recommendation",
                border_style=color,
                padding=(0, 1),
            ))
    else:
        # Fallback: render the flat summary and old-style flag lists
        summary = result.get("summary", "")
        if summary:
            console.print(Panel(summary, title="Verdict", border_style=color, padding=(0, 1)))

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
