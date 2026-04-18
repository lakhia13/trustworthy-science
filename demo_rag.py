"""
Trustworthy Science — Before/After RAG Comparison Demo
=======================================================
Demonstrates how the Truth Filter changes the quality of AI-generated
research summaries by filtering out low-credibility papers before they
reach the language model.

Scenario: A drug-discovery team asks about PCSK9 inhibitors — exactly
the kind of cardiovascular biology question Regeneron researchers tackle.

Run:
    source .venv/bin/activate
    python demo_rag.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

RESEARCH_QUESTION = (
    "What is the clinical evidence that PCSK9 inhibitors reduce "
    "cardiovascular events, and are they safe for long-term use?"
)

_NAIVE_SYSTEM = (
    "You are a drug-discovery research assistant. "
    "Summarise the following abstracts to answer the question. "
    "Be concise (4-6 sentences). Focus on clinical significance."
)

_FILTERED_SYSTEM = (
    "You are a rigorous drug-discovery research assistant at Regeneron. "
    "Summarise the following pre-screened, high-credibility abstracts to answer the question. "
    "Be concise (4-6 sentences). Focus on clinical significance and actionable findings."
)

_TIER_COLORS = {"Trusted": "green", "Caution": "yellow", "Untrusted": "red"}


def _build_context(papers: list[dict], include_tier: bool = False) -> str:
    """Turn a list of paper dicts into an LLM-readable context block."""
    parts: list[str] = []
    for i, p in enumerate(papers, 1):
        title   = p.get("title") or p.get("doi", "Unknown")
        abstract = p.get("abstract") or p.get("summary") or "(no abstract available)"
        tier    = p.get("tier", "?")
        year    = p.get("year") or ""
        venue   = p.get("venue") or ""

        header = f"[{i}] {title} ({venue} {year})"
        if include_tier:
            header += f"  [Tier: {tier}]"
        parts.append(f"{header}\n{abstract[:800]}")

    return "\n\n---\n\n".join(parts)


def _call_llm(system: str, question: str, context: str, config: dict) -> str:
    """Call the K2 LLM and return its text response."""
    from trustworthy_science.llm import get_llm
    from langchain_core.messages import SystemMessage, HumanMessage

    prompt = (
        f"Research question: {question}\n\n"
        f"Abstracts:\n\n{context}\n\n"
        "Your summary:"
    )
    try:
        llm  = get_llm(max_tokens=400, config=config)
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        return resp.content.strip()
    except Exception as exc:
        return f"[LLM unavailable: {exc}]"


def _print_paper_table(papers: list[dict], title: str) -> None:
    table = Table(title=title, box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("#",       width=2,  style="dim")
    table.add_column("Score",   width=6)
    table.add_column("Tier",    width=10)
    table.add_column("Title",   ratio=3)
    table.add_column("Flags",   ratio=2)

    for i, p in enumerate(papers, 1):
        tier   = p.get("tier", "?")
        score  = p.get("score", 0)
        color  = _TIER_COLORS.get(tier, "white")
        hard   = [f.get("code") for f in p.get("hard_flags", [])]
        soft   = [f.get("code") for f in p.get("soft_flags", [])]
        all_flags = (hard + soft)[:2]
        flag_str  = ", ".join(all_flags) if all_flags else "—"
        title_str = (p.get("title") or p.get("doi") or "?")[:55]

        table.add_row(
            str(i),
            f"[{color}]{score}[/]",
            f"[bold {color}]{tier}[/]",
            title_str,
            f"[{color}]{flag_str}[/]",
        )

    console.print(table)


def run_demo() -> None:
    console.rule("[bold cyan]Trustworthy Science — Before vs After RAG[/]")
    console.print(
        f"\n[bold]Research question:[/] [italic]{RESEARCH_QUESTION}[/]\n"
    )

    # ---- Step 1: Load filter and retrieve papers ----
    from trustworthy_science.api import TruthFilter
    import yaml

    config_path = Path(__file__).parent / "config" / "scoring.yaml"
    with config_path.open() as f:
        config = yaml.safe_load(f)

    tf = TruthFilter.from_config(config_path)

    console.print("[bold]Step 1:[/] Retrieving papers from PubMed / bioRxiv...")
    with console.status("[blue]Searching and scoring papers...[/]"):
        all_papers = tf.score_papers(query=RESEARCH_QUESTION, top_k=8)

    if not all_papers:
        console.print("[red]No papers retrieved. Check your API keys and network.[/]")
        return

    # ---- Step 2: Split into naive vs filtered ----
    trusted_caution = [p for p in all_papers if p.get("tier") in ("Trusted", "Caution")]
    untrusted       = [p for p in all_papers if p.get("tier") == "Untrusted"]

    console.print(f"\n[bold]Retrieved {len(all_papers)} papers.[/]  "
                  f"[green]{len(trusted_caution)} pass the Truth Filter[/]  |  "
                  f"[red]{len(untrusted)} excluded[/]\n")

    # Show naive corpus (all papers)
    _print_paper_table(all_papers, "NAIVE RAG — all papers fed to AI (unfiltered)")

    console.print()

    # Show filtered corpus
    _print_paper_table(trusted_caution, "TRUTH-FILTERED RAG — only credible papers")

    # ---- Step 3: Call LLM twice ----
    console.print("\n[bold]Step 2:[/] Asking the AI to answer the research question...\n")

    naive_context    = _build_context(all_papers, include_tier=False)
    filtered_context = _build_context(trusted_caution, include_tier=False)

    with console.status("[blue]Generating NAIVE answer (unfiltered papers)...[/]"):
        naive_answer = _call_llm(_NAIVE_SYSTEM, RESEARCH_QUESTION, naive_context, config)

    with console.status("[blue]Generating FILTERED answer (Truth-Filter applied)...[/]"):
        filtered_answer = _call_llm(_FILTERED_SYSTEM, RESEARCH_QUESTION, filtered_context, config)

    # ---- Step 4: Side-by-side display ----
    console.print("\n")
    console.rule("[bold]AI Research Summaries — Side by Side[/]")
    console.print()

    naive_panel = Panel(
        textwrap.fill(naive_answer, width=55),
        title="[bold red]WITHOUT Truth Filter[/]",
        subtitle=f"[dim]Based on {len(all_papers)} papers (including low-quality)[/]",
        border_style="red",
        padding=(1, 2),
    )
    filtered_panel = Panel(
        textwrap.fill(filtered_answer, width=55),
        title="[bold green]WITH Truth Filter[/]",
        subtitle=f"[dim]Based on {len(trusted_caution)} credible papers only[/]",
        border_style="green",
        padding=(1, 2),
    )

    console.print(Columns([naive_panel, filtered_panel], equal=True, expand=True))

    # ---- Step 5: The punchline ----
    console.print("\n")
    excluded_flags = []
    for p in untrusted:
        for f in p.get("hard_flags", []) + p.get("soft_flags", []):
            excluded_flags.append(f.get("code", "?"))

    excluded_summary = ", ".join(set(excluded_flags[:5])) if excluded_flags else "low quality signals"

    console.print(Panel(
        f"[bold red]Excluded {len(untrusted)} paper(s)[/] from the AI's context due to: [red]{excluded_summary}[/]\n\n"
        "[bold green]The filtered answer is grounded in {n} pre-screened papers[/] — "
        "papers that passed retraction checks, statistical integrity analysis, "
        "reproducibility checks, and venue verification.\n\n"
        "[italic]A drug-discovery hypothesis built on the filtered answer has a "
        "dramatically lower risk of replication failure — "
        "the exact problem Regeneron experienced with knockout mouse studies.[/]".format(
            n=len(trusted_caution)
        ),
        title="[bold cyan]What the Truth Filter Changed[/]",
        border_style="cyan",
    ))


if __name__ == "__main__":
    run_demo()
