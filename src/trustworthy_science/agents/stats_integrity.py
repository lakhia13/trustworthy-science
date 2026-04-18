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
from trustworthy_science.tools.benfords_law import benfords_law_test

logger = logging.getLogger(__name__)

_MIN_PVALS = 5
_BENFORD_MIN_NUMBERS = 30   # need at least 30 data values for a reliable test

# Paper types where sample-size and effect-size checks are not meaningful.
_NON_EMPIRICAL_TYPES = frozenset([
    "review_narrative",
    "systematic_review_meta",
    "theoretical",
    "opinion_commentary",
    "case_report",
])


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

    logger.info("[STATS] Starting stats integrity check | text_length=%d chars | "
                "paper_type=%s", len(text), state.paper_type or "unknown")

    # --- P-values & p-curve ---
    pvalues = extract_pvalues(text)
    logger.info("[STATS] P-values extracted: %d total | values: %s",
                len(pvalues), pvalues[:10] if pvalues else "none")

    pcurve_result = pcurve_analysis(
        pvalues,
        min_required=min_pvals,
        window_lo=window_lo,
        window_hi=window_hi,
        cluster_ratio_threshold=cluster_threshold,
    )
    logger.info("[STATS] P-curve result: phack_suspected=%s | n_in_window=%s/%s | summary: %s",
                pcurve_result.phack_suspected,
                getattr(pcurve_result, 'n_in_window', '?'),
                getattr(pcurve_result, 'n_pvalues', '?'),
                pcurve_result.summary[:100])

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
    skip_sample_checks = (state.paper_type or "empirical_quantitative") in _NON_EMPIRICAL_TYPES
    effect_sizes = extract_effect_sizes(text)
    logger.info("[STATS] Effect sizes found: %d | skip_sample_checks=%s | "
                "will flag missing=%s",
                len(effect_sizes), skip_sample_checks,
                (not skip_sample_checks and not effect_sizes and len(pvalues) >= 3))
    if not skip_sample_checks and not effect_sizes and len(pvalues) >= 3:
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
    logger.info("[STATS] Sample sizes found: %s | min_n=%s", sample_sizes[:5], min_n)
    if not skip_sample_checks and min_n is not None and min_n < 20:
        f = Flag(
            tier="soft",
            code="SMALL_SAMPLE_UNDERPOWERED",
            message=f"Smallest detected sample size N={min_n}; study may be underpowered.",
            source_agent="stats_integrity",
            evidence=[EvidenceQuote(text=f"n = {min_n}", section="methods")],
        )
        soft_flags.append(f)
        flags.append(f)

    # --- Benford's Law — data fabrication detection ---
    # Only run on empirical papers with enough full text to extract data values.
    benford_cfg = (config or {}).get("benfords_law", {})
    benford_min = int(benford_cfg.get("min_numbers", _BENFORD_MIN_NUMBERS))
    benford_threshold = float(benford_cfg.get("p_threshold", 0.05))

    if not skip_sample_checks and text:
        benford_result = benfords_law_test(
            text,
            min_numbers=benford_min,
            p_threshold=benford_threshold,
        )
        logger.info("[STATS] Benford's Law: n=%d numbers | chi2=%.2f | p=%.4f | anomaly=%s",
                    benford_result.n_numbers, benford_result.chi2_stat,
                    benford_result.p_value, benford_result.anomaly_detected)
        if benford_result.anomaly_detected:
            f = Flag(
                tier="soft",
                code="BENFORDS_LAW_ANOMALY",
                message=benford_result.summary,
                source_agent="stats_integrity",
                evidence=[EvidenceQuote(
                    text=f"χ²={benford_result.chi2_stat:.2f}, p={benford_result.p_value:.4f}, "
                         f"n={benford_result.n_numbers} numbers analysed",
                    section="results",
                )],
            )
            soft_flags.append(f)
            flags.append(f)
    else:
        logger.info("[STATS] Benford's Law: skipped (non-empirical type or no text)")

    # Compute sub-score: start at 1.0, penalise flags
    score = 1.0
    if any(f.code == "P_HACKING_CLUSTER" for f in hard_flags):
        score -= 0.6
    if any(f.code == "MISSING_EFFECT_SIZES" for f in soft_flags):
        score -= 0.15
    if any(f.code == "SMALL_SAMPLE_UNDERPOWERED" for f in soft_flags):
        score -= 0.10
    if any(f.code == "BENFORDS_LAW_ANOMALY" for f in soft_flags):
        score -= 0.20
    score = max(0.0, min(1.0, score))

    # Confidence depends on how much text we had
    confidence = 0.85 if state.coverage == "full_text" else (0.60 if state.coverage == "abstract_only" else 0.35)

    notes = pcurve_result.summary
    if not pvalues:
        notes = "No p-values detected in available text; statistical analysis skipped."
        confidence = 0.20

    logger.info("[STATS] Sub-score: %.2f | Confidence: %.2f | Hard flags: %d | Soft flags: %d",
                score, confidence, len(hard_flags), len(soft_flags))

    sub = SubScore(score=score, confidence=confidence, flags=flags, notes=notes)

    return {
        "sub_scores": {"stats_integrity": sub},
        "hard_flags": hard_flags,
        "soft_flags": soft_flags,
        "quality_signals": quality_signals,
    }
