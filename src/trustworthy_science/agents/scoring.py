"""Scoring & Verdict agent — fuses sub-scores into a final TrustReport."""

from __future__ import annotations

import logging

from trustworthy_science.llm import get_llm
from trustworthy_science.scoring.rules import compute_composite_score
from trustworthy_science.state import PaperState, TrustReport

logger = logging.getLogger(__name__)

_NARRATIVE_PROMPT = """\
You are writing a concise peer-review verdict for a scientific paper credibility tool.

Paper: "{title}" ({year})

Composite trust score: {score}/100 — Tier: {tier}

Hard flags raised:
{hard_flags}

Soft flags raised:
{soft_flags}

Quality signals:
{quality_signals}

Per-dimension scores:
{per_dimension}

In 3-5 sentences, explain the verdict to a research scientist. 
- Use "signals of concern" rather than "fraud" or "fake".
- Be specific — mention the strongest piece of evidence.
- End with a practical recommendation (e.g. "cite with caution", "safe to include", "exclude from analysis").
Respond with plain text only.
"""


def scoring_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: compute composite score, assign tier, generate narrative summary."""
    logger.info("[SCORING_AGENT] Starting final scoring for: %s",
                state.stub.title[:60] if state.stub.title else "Unknown")
    logger.info("[SCORING_AGENT] Inputs — hard_flags: %d | soft_flags: %d | quality_signals: %d | sub_scores: %s",
                len(state.hard_flags), len(state.soft_flags), len(state.quality_signals),
                list(state.sub_scores.keys()))

    methods_score: float | None = None
    if "methodology" in state.sub_scores:
        methods_score = state.sub_scores["methodology"].score
        logger.info("[SCORING_AGENT] LLM methodology score: %.2f", methods_score)
    else:
        logger.info("[SCORING_AGENT] No LLM methodology score available")

    score, tier = compute_composite_score(
        hard_flags=state.hard_flags,
        soft_flags=state.soft_flags,
        quality_signals=state.quality_signals,
        methods_score=methods_score,
        config=config,
    )

    per_dimension = {
        name: round(sub.score, 3)
        for name, sub in state.sub_scores.items()
    }

    # --- Generate narrative summary ---
    summary = _generate_narrative(state, score, tier, per_dimension, config)

    report = TrustReport(
        composite_score=score,
        tier=tier,
        summary=summary,
        hard_flags=state.hard_flags,
        soft_flags=state.soft_flags,
        quality_signals=state.quality_signals,
        per_dimension=per_dimension,
        coverage=state.coverage,
    )

    return {"final": report}


def _generate_narrative(
    state: PaperState,
    score: int,
    tier: str,
    per_dimension: dict[str, float],
    config: dict | None,
) -> str:
    """Use LLM to write a 3-5 sentence verdict narrative."""
    def _fmt_flags(flags):
        if not flags:
            return "None"
        return "; ".join(f"{f.code}: {f.message[:80]}" for f in flags[:5])

    prompt = _NARRATIVE_PROMPT.format(
        title=state.stub.title or "Unknown",
        year=state.stub.year or "unknown year",
        score=score,
        tier=tier,
        hard_flags=_fmt_flags(state.hard_flags),
        soft_flags=_fmt_flags(state.soft_flags),
        quality_signals=_fmt_flags(state.quality_signals),
        per_dimension="\n".join(f"  {k}: {v:.2f}" for k, v in per_dimension.items()),
    )

    try:
        llm = get_llm(max_tokens=300, config=config)
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as exc:
        logger.warning("Narrative generation failed: %s", exc)
        return _fallback_narrative(score, tier, state)


def _fallback_narrative(score: int, tier: str, state: PaperState) -> str:
    """Deterministic fallback narrative when LLM is unavailable."""
    hard = [f.code for f in state.hard_flags]
    soft = [f.code for f in state.soft_flags]
    quality = [f.code for f in state.quality_signals]

    parts = [f"Composite trust score: {score}/100 (Tier: {tier})."]

    if hard:
        parts.append(f"Critical issues detected: {', '.join(hard)}.")
    if soft:
        parts.append(f"Concerns raised: {', '.join(soft[:4])}.")
    if quality:
        parts.append(f"Positive signals: {', '.join(quality[:3])}.")

    if tier == "Trusted":
        parts.append("Recommendation: Safe to include in analysis.")
    elif tier == "Caution":
        parts.append("Recommendation: Cite with caution; verify key claims independently.")
    else:
        parts.append("Recommendation: Exclude from analysis or flag prominently.")

    return " ".join(parts)
