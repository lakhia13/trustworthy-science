"""Statistical Integrity agent — detect p-hacking and missing effect sizes."""

from __future__ import annotations

import logging

from trustworthy_science.state import EvidenceQuote, Flag, PaperState, SubScore
from trustworthy_science.tools.pvalue_extract import (
    extract_effect_sizes,
    extract_pvalues,
    extract_sample_sizes,
)
from trustworthy_science.tools.pcurve import pcurve_analysis

logger = logging.getLogger(__name__)

_MIN_PVALS = 5


def stats_integrity_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: analyse p-values, effect sizes, and sample sizes for red flags."""
    cfg = config or {}
    pcfg = cfg.get("pcurve", {})
    min_pvals = int(pcfg.get("min_pvalues_required", _MIN_PVALS))
    cluster_threshold = float(pcfg.get("cluster_ratio_threshold", 0.40))
    window_lo = float(pcfg.get("phack_window_lo", 0.04))
    window_hi = float(pcfg.get("phack_window_hi", 0.05))

    # Build text corpus from full text / abstract / results
    text_parts = []
    if state.parsed:
        for section in (state.parsed.full_text, state.parsed.results, state.parsed.abstract):
            if section:
                text_parts.append(section)
    text = " ".join(text_parts)

    flags: list[Flag] = []
    hard_flags: list[Flag] = []
    soft_flags: list[Flag] = []
    quality_signals: list[Flag] = []

    # --- P-values & p-curve ---
    pvalues = extract_pvalues(text)
    pcurve_result = pcurve_analysis(
        pvalues,
        min_required=min_pvals,
        window_lo=window_lo,
        window_hi=window_hi,
        cluster_ratio_threshold=cluster_threshold,
    )

    if pcurve_result.phack_suspected:
        f = Flag(
            tier="hard",
            code="P_HACKING_CLUSTER",
            message=pcurve_result.summary,
            source_agent="stats_integrity",
            evidence=[EvidenceQuote(
                text=f"P-value cluster: {pcurve_result.n_in_window}/{pcurve_result.n_pvalues} in ({window_lo},{window_hi}]",
                section="results",
            )],
        )
        hard_flags.append(f)
        flags.append(f)

    # --- Effect sizes ---
    effect_sizes = extract_effect_sizes(text)
    if not effect_sizes and len(pvalues) >= 3:
        f = Flag(
            tier="soft",
            code="MISSING_EFFECT_SIZES",
            message="Paper reports p-values but no quantitative effect sizes (Cohen's d, OR, HR, CI) were detected.",
            source_agent="stats_integrity",
        )
        soft_flags.append(f)
        flags.append(f)

    # --- Sample sizes ---
    sample_sizes = extract_sample_sizes(text)
    min_n = min(sample_sizes) if sample_sizes else None
    if min_n is not None and min_n < 20:
        f = Flag(
            tier="soft",
            code="SMALL_SAMPLE_UNDERPOWERED",
            message=f"Smallest detected sample size N={min_n}; study may be underpowered.",
            source_agent="stats_integrity",
            evidence=[EvidenceQuote(text=f"n = {min_n}", section="methods")],
        )
        soft_flags.append(f)
        flags.append(f)

    # Compute sub-score: start at 1.0, penalise flags
    score = 1.0
    if any(f.code == "P_HACKING_CLUSTER" for f in hard_flags):
        score -= 0.6
    if any(f.code == "MISSING_EFFECT_SIZES" for f in soft_flags):
        score -= 0.15
    if any(f.code == "SMALL_SAMPLE_UNDERPOWERED" for f in soft_flags):
        score -= 0.10
    score = max(0.0, min(1.0, score))

    # Confidence depends on how much text we had
    confidence = 0.85 if state.coverage == "full_text" else (0.60 if state.coverage == "abstract_only" else 0.35)

    notes = pcurve_result.summary
    if not pvalues:
        notes = "No p-values detected in available text; statistical analysis skipped."
        confidence = 0.20

    sub = SubScore(score=score, confidence=confidence, flags=flags, notes=notes)

    return {
        "sub_scores": {"stats_integrity": sub},
        "hard_flags": hard_flags,
        "soft_flags": soft_flags,
        "quality_signals": quality_signals,
    }
