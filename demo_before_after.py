"""
Before / After comparison demo for paper-type-aware scoring.

Run from the project root:
    python3.12 demo_before_after.py

Shows side-by-side what the OLD scoring (treats every paper as empirical)
vs the NEW scoring (detects paper type and applies only relevant criteria)
gives for 8 representative paper categories.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Make sure the installed package is importable
_src = Path(__file__).parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from trustworthy_science.state import PaperState, PaperStub, ParsedPaper
from trustworthy_science.agents.paper_classifier import classify_paper_type
from trustworthy_science.agents.reproducibility import reproducibility_agent
from trustworthy_science.agents.stats_integrity import stats_integrity_agent
from trustworthy_science.scoring.rules import compute_composite_score

console = Console()

# ---------------------------------------------------------------------------
# Paper fixtures — 8 representative categories
# ---------------------------------------------------------------------------

PAPERS = [
    {
        "label": "Narrative Review (Biology)",
        "title": "Molecular mechanisms of autophagy: a comprehensive review",
        "abstract": (
            "This review provides a comprehensive overview of autophagy signalling pathways. "
            "We surveyed 200 studies published between 2000 and 2023 and summarise current "
            "understanding of the regulatory mechanisms involved. No original data were generated."
        ),
        "methods": "",
        "results": "",
    },
    {
        "label": "Theoretical Biology",
        "title": "A mathematical framework for modelling population dynamics under environmental stress",
        "abstract": (
            "We develop a theoretical framework based on coupled differential equations "
            "to model population dynamics. We derive analytical solutions and prove "
            "stability conditions. No experimental data were collected."
        ),
        "methods": "We derive a system of ODEs and analyse equilibrium stability analytically.",
        "results": "Theorem 1 establishes that the equilibrium is globally stable when R0 < 1.",
    },
    {
        "label": "Clinical Trial (RCT, with NCT + data)",
        "title": "Efficacy of Drug X in treating Condition Y: a randomized controlled trial",
        "abstract": (
            "Background: Randomized controlled trial. ClinicalTrials.gov: NCT02735707. "
            "Patients randomly assigned 1:1 to Drug X or placebo. "
            "Data deposited at zenodo.org/record/9999. n=120 per arm."
        ),
        "methods": "Randomized double-blind placebo-controlled trial. NCT02735707.",
        "results": "Primary endpoint: HR 0.72 (95% CI 0.55–0.94), p = 0.014.",
    },
    {
        "label": "Systematic Review / Meta-analysis",
        "title": "Antidepressants in treatment-resistant depression: a systematic review and meta-analysis",
        "abstract": (
            "We followed PRISMA guidelines. We searched PubMed, Cochrane, and Embase. "
            "Random-effects meta-analysis on 42 eligible RCTs. "
            "Data extraction sheets available at figshare.com/articles/123. "
            "Analysis code at github.com/lab/meta-antidep."
        ),
        "methods": "PRISMA-compliant systematic search. Two independent reviewers.",
        "results": "Pooled SMD = 0.43 (95% CI 0.28–0.58). I² = 62%.",
    },
    {
        "label": "Empirical Study — GOOD (open data + code)",
        "title": "Single-cell RNA-seq reveals transcriptomic diversity in tumour microenvironment",
        "abstract": (
            "We performed single-cell RNA sequencing on 15 tumour samples. "
            "Raw data deposited at GEO (GSE198234). "
            "Analysis code available at github.com/lab/scrna-tumour."
        ),
        "methods": "scRNA-seq. Data at GSE198234. Code at github.com/lab/scrna-tumour.",
        "results": "Identified 12 distinct cell clusters. p < 0.001 for cluster separation.",
    },
    {
        "label": "Empirical Study — BAD (no data/code/prereg)",
        "title": "Effects of exercise on cognitive function in elderly adults",
        "abstract": (
            "We enrolled 45 participants aged 65–80 in a 12-week exercise intervention. "
            "Cognitive assessments at baseline and follow-up. p < 0.05 for primary outcome. "
            "No data repository. No pre-registration."
        ),
        "methods": "Participants completed 12-week supervised exercise. n=45.",
        "results": "p = 0.03, p = 0.04, p = 0.02. No effect sizes reported.",
    },
    {
        "label": "Case Report",
        "title": "Bilateral pneumothorax following thoracentesis: a case report",
        "abstract": (
            "We report a case of a 45-year-old female who presented with acute respiratory "
            "distress following thoracentesis. We describe the clinical course, diagnostic "
            "workup, and management of this rare complication."
        ),
        "methods": "Clinical case description with imaging and laboratory findings.",
        "results": "Bilateral chest drain insertion resolved pneumothorax within 48 hours.",
    },
    {
        "label": "Computational Methods / Software Tool",
        "title": "SeqPipe: a scalable pipeline for end-to-end RNA-seq analysis",
        "abstract": (
            "We present SeqPipe, a software tool for RNA-seq analysis. "
            "The algorithm implements a novel splice-aware alignment strategy. "
            "Source code at github.com/biolab/seqpipe (MIT licence). "
            "Benchmarked on 10 public datasets."
        ),
        "methods": "Implemented in Python. Full documentation and code at github.com/biolab/seqpipe.",
        "results": "SeqPipe achieves 98.2% alignment accuracy vs 96.1% for STAR on benchmark.",
    },
]


def _build_state(paper: dict, force_type: str | None = None) -> PaperState:
    ft = " ".join(filter(None, [
        paper["abstract"], paper["methods"], paper["results"]
    ]))
    stub = PaperStub(title=paper["title"], abstract=paper["abstract"], year=2023)
    parsed = ParsedPaper(
        full_text=ft,
        abstract=paper["abstract"],
        methods=paper["methods"],
        results=paper["results"],
    )
    state = PaperState(stub=stub, parsed=parsed, coverage="full_text")
    if force_type:
        state.paper_type = force_type
    return state


def _score(state: PaperState) -> dict:
    r1 = reproducibility_agent(state)
    r2 = stats_integrity_agent(state)

    soft  = r1.get("soft_flags", []) + r2.get("soft_flags", [])
    qual  = r1.get("quality_signals", []) + r2.get("quality_signals", [])
    hard  = r1.get("hard_flags", []) + r2.get("hard_flags", [])

    composite, tier = compute_composite_score(hard, soft, qual)
    repro_score = r1["sub_scores"]["reproducibility"].score

    return {
        "paper_type": state.paper_type,
        "soft_flags": [f.code for f in soft],
        "quality_signals": [f.code for f in qual],
        "repro_score": repro_score,
        "composite": composite,
        "tier": tier,
    }


def _tier_color(tier: str) -> str:
    return {"Trusted": "green", "Caution": "yellow", "Untrusted": "red"}.get(tier, "white")


def _flag_list(flags: list[str]) -> str:
    if not flags:
        return "[green]none[/green]"
    # Mark reproducibility-related flags
    repro = {"NO_DATA_DEPOSIT", "NO_CODE_AVAILABILITY", "NO_PREREGISTRATION",
              "MISSING_EFFECT_SIZES", "SMALL_SAMPLE_UNDERPOWERED"}
    parts = []
    for f in flags:
        color = "red" if f in repro else "dark_orange"
        parts.append(f"[{color}]{f}[/{color}]")
    return ", ".join(parts)


def run():
    console.print(Panel.fit(
        "[bold cyan]Paper-Type-Aware Scoring — Before / After Demo[/bold cyan]\n"
        "[dim]Comparing OLD (treats everything as empirical) vs NEW (detects paper type)[/dim]",
        border_style="cyan",
    ))
    console.print()

    for paper in PAPERS:
        # NEW: auto-classify
        state_new = _build_state(paper)
        classify_result = classify_paper_type(state_new)
        state_new.paper_type = classify_result["paper_type"]
        new = _score(state_new)

        # OLD: force empirical_quantitative for everything
        state_old = _build_state(paper, force_type="empirical_quantitative")
        old = _score(state_old)

        # Build comparison table
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold white",
                      title=f"[bold]{paper['label']}[/bold]", title_style="bold cyan",
                      expand=True)
        table.add_column("Metric", style="dim", width=22)
        table.add_column("BEFORE  (all treated as empirical)", justify="center", min_width=36)
        table.add_column("AFTER  (type-aware)", justify="center", min_width=36)

        # Detected type row
        table.add_row(
            "Detected paper type",
            "[dim]empirical_quantitative[/dim] (hardcoded)",
            f"[bold yellow]{new['paper_type']}[/bold yellow]",
        )

        # Soft flags
        table.add_row(
            "Soft flags",
            _flag_list(old["soft_flags"]),
            _flag_list(new["soft_flags"]),
        )

        # Quality signals
        qs_old = "[green]" + ", ".join(old["quality_signals"]) + "[/green]" if old["quality_signals"] else "[dim]none[/dim]"
        qs_new = "[green]" + ", ".join(new["quality_signals"]) + "[/green]" if new["quality_signals"] else "[dim]none[/dim]"
        table.add_row("Quality signals", qs_old, qs_new)

        # Repro score
        def repro_fmt(s: float) -> str:
            color = "green" if s >= 0.8 else ("yellow" if s >= 0.6 else "red")
            return f"[{color}]{s:.2f}[/{color}]"

        table.add_row("Repro sub-score", repro_fmt(old["repro_score"]), repro_fmt(new["repro_score"]))

        # Composite score + tier
        old_tier_col = _tier_color(old["tier"])
        new_tier_col = _tier_color(new["tier"])
        table.add_row(
            "Composite score / tier",
            f"[{old_tier_col}]{old['composite']} ({old['tier']})[/{old_tier_col}]",
            f"[{new_tier_col}]{new['composite']} ({new['tier']})[/{new_tier_col}]",
        )

        console.print(table)
        console.print()

    console.print(Panel.fit(
        "[bold green]Legend[/bold green]\n"
        "[red]Red flags[/red] = reproducibility penalties  "
        "[green]Green[/green] = quality bonuses  "
        "[yellow]Yellow[/yellow] = caution tier  "
        "[green]Green score[/green] = trusted (≥70)  "
        "[red]Red score[/red] = untrusted (<45)",
        border_style="dim",
    ))


if __name__ == "__main__":
    run()
