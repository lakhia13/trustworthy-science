"""
Trustworthy Science — Live Hackathon Demo
=========================================
Shows 3 real papers scored live:
  1. GOLD  — high-quality open-access RCT
  2. RETRACTED — paper flagged in Retraction Watch
  3. PREDATORY — OMICS publisher journal

Run:
    source .venv/bin/activate
    python demo_live.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

# ---------------------------------------------------------------------------
# Demo papers — curated for reliable, reproducible scoring
# ---------------------------------------------------------------------------
DEMO_PAPERS = [
    {
        "label": "GOLD STANDARD",
        "doi": "10.1371/journal.pmed.1001547",
        "description": "Open-access RCT, PLOS Medicine — preregistered, data available",
        "expected": "Trusted",
    },
    {
        "label": "RETRACTED PAPER",
        "doi": "10.1016/j.canlet.2012.09.019",
        "description": "Retracted cancer biology paper — flagged by Retraction Watch",
        "expected": "Untrusted",
    },
    {
        "label": "PREDATORY VENUE",
        "doi": "10.4172/2329-9096.1000225",
        "description": "OMICS Group journal — known predatory publisher",
        "expected": "Untrusted",
    },
]

_TIER_COLORS = {"Trusted": "green", "Caution": "yellow", "Untrusted": "red"}
_TIER_ICONS  = {"Trusted": "✅", "Caution": "⚠️",  "Untrusted": "❌"}

REGENERON_IMPACT = {
    "Trusted":   "Safe to include as a drug-target hypothesis foundation.",
    "Caution":   "Verify key claims before building a target programme on this.",
    "Untrusted": "Basing a drug-target hypothesis on this paper risks a knockout-mouse failure.",
}


def _score_bar(score: int, width: int = 20) -> str:
    filled = round(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{_TIER_COLORS.get('Trusted', 'white')}]{bar}[/] {score}/100"


def _score_bar_colored(score: int, tier: str, width: int = 20) -> str:
    color  = _TIER_COLORS.get(tier, "white")
    filled = round(score / 100 * width)
    bar    = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/] {score}/100"


def _fmt_flags(flags: list[dict], max_n: int = 3) -> str:
    if not flags:
        return "[dim]None[/]"
    codes = [f.get("code", "?") for f in flags[:max_n]]
    rest  = len(flags) - max_n
    out   = ", ".join(codes)
    if rest > 0:
        out += f" (+{rest} more)"
    return out


def run_demo() -> None:
    console.rule("[bold cyan]Trustworthy Science — Live Hackathon Demo[/]")
    console.print(
        "\n[italic]Regeneron asked: how do we stop bad science from poisoning AI-driven drug discovery?\n"
        "We built the Truth Filter — an AI that reads papers like a skeptical scientist.[/]\n"
    )

    # Load the filter once
    from trustworthy_science.api import TruthFilter
    tf = TruthFilter.from_config()

    results: list[dict] = []

    for meta in DEMO_PAPERS:
        label = meta["label"]
        doi   = meta["doi"]
        desc  = meta["description"]

        console.print(f"\n[bold]Scoring:[/] [cyan]{label}[/] — {desc}")
        console.print(f"         DOI: [dim]{doi}[/]")

        with console.status(f"[blue]Running 9-agent pipeline...[/]"):
            t0  = time.time()
            res = tf.score_single(doi)
            elapsed = time.time() - t0

        if res is None:
            console.print(f"[red]Could not retrieve paper.[/]")
            continue

        results.append({**res, "_meta": meta})

        tier  = res.get("tier", "Unknown")
        score = res.get("score", 0)
        color = _TIER_COLORS.get(tier, "white")
        icon  = _TIER_ICONS.get(tier, "?")
        title = res.get("title") or doi

        hard_flags    = res.get("hard_flags", [])
        soft_flags    = res.get("soft_flags", [])
        quality       = res.get("quality_signals", [])
        coverage      = res.get("coverage", "metadata_only")
        impact_line   = REGENERON_IMPACT.get(tier, "")

        body = (
            f"{_score_bar_colored(score, tier)}\n\n"
            f"[bold {color}]{icon}  Tier: {tier}[/]\n\n"
            f"[bold red]Hard flags:[/]    {_fmt_flags(hard_flags)}\n"
            f"[bold yellow]Soft flags:[/]    {_fmt_flags(soft_flags)}\n"
            f"[bold green]Quality signals:[/] {_fmt_flags(quality)}\n\n"
            f"[dim]Coverage: {coverage} | Scored in {elapsed:.1f}s[/]\n\n"
            f"[italic]{res.get('summary', '')}[/]\n\n"
            f"[bold]Regeneron impact:[/] {impact_line}"
        )
        if coverage == "metadata_only":
            body += "\n[dim yellow]⚠ Full text unavailable — scoring confidence 35%[/]"

        console.print(Panel(body, title=f"[bold]{label} — {title[:60]}[/]", border_style=color))

    # --- Summary table ---
    console.print("\n")
    console.rule("[bold]Summary — Truth Filter Results[/]")

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold blue")
    table.add_column("#",       width=2,  style="dim")
    table.add_column("Paper",   ratio=3)
    table.add_column("Score",   width=7)
    table.add_column("Tier",    width=10)
    table.add_column("AI uses?", width=10)
    table.add_column("Top Risk",  ratio=2)

    tier_order = {"Trusted": 0, "Caution": 1, "Untrusted": 2}

    for i, r in enumerate(results, 1):
        tier   = r.get("tier", "Unknown")
        score  = r.get("score", 0)
        color  = _TIER_COLORS.get(tier, "white")
        include = tier in ("Trusted", "Caution")
        ai_use  = f"[green]YES[/]" if tier == "Trusted" else (f"[yellow]CAUTION[/]" if tier == "Caution" else f"[red]NO — EXCLUDED[/]")
        label   = r["_meta"]["label"]
        top_risk = (r.get("hard_flags", []) or r.get("soft_flags", []) or [{}])[0].get("code", "—")

        table.add_row(
            str(i),
            label,
            f"[{color}]{score}[/]",
            f"[bold {color}]{tier}[/]",
            ai_use,
            f"[{color}]{top_risk}[/]",
        )

    console.print(table)

    # --- The big point ---
    console.print("\n")
    console.print(Panel(
        "[bold]Without the Truth Filter:[/] An AI research assistant would treat all 3 papers equally —\n"
        "citing the retracted paper, the predatory journal, and the gold-standard RCT with the same confidence.\n\n"
        "[bold green]With the Truth Filter:[/] Only the Trusted paper reaches the drug-discovery pipeline.\n"
        "The retracted and predatory papers are [bold red]excluded before they can corrupt a hypothesis.[/]\n\n"
        "[italic]This is how Regeneron's knockout mouse crisis could have been prevented — "
        "before years of failed experiments, not after.[/]",
        title="[bold cyan]Why This Matters[/]",
        border_style="cyan",
    ))


if __name__ == "__main__":
    run_demo()
