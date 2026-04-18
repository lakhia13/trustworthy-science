"""Citation Network agent — compute institutional diversity and self-citation ratio."""

from __future__ import annotations

import logging

from trustworthy_science.state import EvidenceQuote, Flag, PaperState, SubScore
from trustworthy_science.tools.openalex import citation_diversity_score

logger = logging.getLogger(__name__)

_SELF_CITE_THRESHOLD = 0.30   # > 30% self-citations triggers flag
_DIVERSITY_THRESHOLD = 0.50   # < 50% institutional diversity triggers flag


def citation_network_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: analyse citation diversity and self-citation ratio via OpenAlex."""
    cfg = (config or {}).get("citation_network", {})
    self_threshold = float(cfg.get("self_citation_ratio_threshold", _SELF_CITE_THRESHOLD))
    div_threshold = float(cfg.get("diversity_threshold", _DIVERSITY_THRESHOLD))

    doi = state.stub.doi
    hard_flags: list[Flag] = []
    soft_flags: list[Flag] = []
    quality_signals: list[Flag] = []

    if not doi:
        sub = SubScore(score=0.7, confidence=0.1, notes="No DOI available; citation network analysis skipped.")
        return {"sub_scores": {"citation_network": sub}}

    try:
        diversity, n_citations, self_ratio = citation_diversity_score(doi)
    except Exception as exc:
        logger.warning("Citation network analysis failed for %s: %s", doi, exc)
        sub = SubScore(score=0.7, confidence=0.1, notes=f"Citation lookup failed: {exc}")
        return {"sub_scores": {"citation_network": sub}}

    score = 0.7  # neutral baseline

    # Self-citation check
    if self_ratio > self_threshold:
        f = Flag(
            tier="soft",
            code="HIGH_SELF_CITATION",
            message=f"{self_ratio:.0%} of citing papers share an author with the original ({n_citations} total citations). Threshold: {self_threshold:.0%}.",
            source_agent="citation_network",
            evidence=[EvidenceQuote(
                text=f"Self-citation ratio: {self_ratio:.2f} ({n_citations} citations)",
                section="metadata",
            )],
        )
        soft_flags.append(f)
        score -= 0.15

    # Diversity check
    if n_citations >= 5:
        if diversity >= div_threshold:
            f = Flag(
                tier="quality",
                code="DIVERSE_CITATIONS",
                message=f"Paper is cited by institutionally diverse researchers ({diversity:.0%} diversity across {n_citations} citations).",
                source_agent="citation_network",
            )
            quality_signals.append(f)
            score += 0.10
        else:
            f = Flag(
                tier="soft",
                code="LOW_CITATION_DIVERSITY",
                message=f"Low institutional diversity among citing papers ({diversity:.0%} < {div_threshold:.0%}; {n_citations} citations).",
                source_agent="citation_network",
            )
            soft_flags.append(f)
            score -= 0.08

    score = max(0.0, min(1.0, score))
    confidence = 0.80 if n_citations >= 10 else (0.50 if n_citations >= 3 else 0.25)

    all_flags = hard_flags + soft_flags + quality_signals
    sub = SubScore(
        score=score,
        confidence=confidence,
        flags=all_flags,
        notes=f"Total citations: {n_citations}. Diversity: {diversity:.0%}. Self-citation ratio: {self_ratio:.0%}.",
    )

    return {
        "sub_scores": {"citation_network": sub},
        "hard_flags": hard_flags,
        "soft_flags": soft_flags,
        "quality_signals": quality_signals,
    }
