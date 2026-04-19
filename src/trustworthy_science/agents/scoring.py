"""Scoring & Verdict agent — fuses sub-scores into a final TrustReport."""

from __future__ import annotations

import logging
import re

from trustworthy_science.llm import get_llm, strip_think_tokens
from trustworthy_science.scoring.rules import compute_composite_score
from trustworthy_science.state import (
    Flag,
    PaperState,
    ScoreBreakdownEntry,
    StructuredReport,
    TrustReport,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured report prompt
# ---------------------------------------------------------------------------

_STRUCTURED_REPORT_PROMPT = """\
You are a scientific paper credibility analyst writing a structured peer-review \
verdict for a research scientist.

Paper: "{title}" ({year})
Composite trust score: {score}/100 — Tier: {tier}

Hard flags raised:
{hard_flags}

Soft flags raised:
{soft_flags}

Quality signals:
{quality_signals}

Per-dimension scores and sub-agent notes (0.0 = poor, 1.0 = excellent):
{per_dimension}

Sub-agent dimensions: librarian (venue/COI), detective (statistical integrity), \
coder (reproducibility/code health), peer (adversarial review/citations), \
methodology (LLM methods critique), citation_network (self-citation diversity).

Write a structured credibility report using EXACTLY the following section headings \
(in ALL CAPS) with no markdown, no asterisks, no bullet dashes other than the \
hyphen-dash shown below. Do not include any section other than these five.

OVERALL VERDICT
One sentence summarising why this paper received its score and tier. \
Use "signals of concern" not "fraud" or "fake".

SCORE BREAKDOWN
One line per dimension in the format: DimensionName | ScorePct | One-sentence rationale.
ScorePct is the dimension score multiplied by 100 and rounded to the nearest integer.
Base your rationale on the sub-agent notes provided above.

KEY CONCERNS
Each concern on its own line starting with "- ". List only the most significant \
hard and soft flags with a brief plain-English explanation. \
Write "None" if there are no concerns.

POSITIVE SIGNALS
Each signal on its own line starting with "- ". List quality signals with a brief \
plain-English explanation. Write "None" if there are no positive signals.

RECOMMENDATION
One sentence only. Do NOT explain your reasoning here. \
State only your final recommendation: whether to cite with caution, \
safely include, or exclude the paper.
"""


def scoring_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: compute composite score, assign tier, generate structured report."""
    logger.info("[SCORING_AGENT] Starting final scoring for: %s",
                state.stub.title[:60] if state.stub.title else "Unknown")
    logger.info(
        "[SCORING_AGENT] Inputs — hard_flags: %d | soft_flags: %d | "
        "quality_signals: %d | sub_scores: %s",
        len(state.hard_flags), len(state.soft_flags), len(state.quality_signals),
        list(state.sub_scores.keys()),
    )

    # --- Soft flag deduplication: keep first occurrence with longest message per code ---
    deduplicated_soft: list[Flag] = []
    seen_soft_codes: dict[str, int] = {}  # code -> index in deduplicated_soft
    for f in state.soft_flags:
        if f.code not in seen_soft_codes:
            seen_soft_codes[f.code] = len(deduplicated_soft)
            deduplicated_soft.append(f)
        else:
            # Keep the one with the longer message (more informative)
            idx = seen_soft_codes[f.code]
            if len(f.message) > len(deduplicated_soft[idx].message):
                deduplicated_soft[idx] = f
    soft_flags_final = deduplicated_soft

    # --- DATA_FABRICATION_SIGNS composition ---
    # If both BENFORDS_LAW_ANOMALY and INTERNAL_INCONSISTENCY are present as soft flags,
    # synthesize a DATA_FABRICATION_SIGNS hard flag
    soft_codes = {f.code for f in soft_flags_final}
    hard_flags_final = list(state.hard_flags)
    already_has_fabrication = any(f.code == 'DATA_FABRICATION_SIGNS' for f in hard_flags_final)
    if (
        not already_has_fabrication
        and 'BENFORDS_LAW_ANOMALY' in soft_codes
        and 'INTERNAL_INCONSISTENCY' in soft_codes
    ):
        fabrication_flag = Flag(
            tier='hard',
            code='DATA_FABRICATION_SIGNS',
            message=(
                'Composite fabrication signal: both Benford\'s Law anomaly and '
                'Abstract/Results numeric inconsistency detected simultaneously.'
            ),
            source_agent='scoring',
        )
        hard_flags_final.append(fabrication_flag)
        logger.warning(
            '[SCORING_AGENT] DATA_FABRICATION_SIGNS hard flag synthesized '
            '(BENFORDS_LAW_ANOMALY + INTERNAL_INCONSISTENCY both present)'
        )

    methods_score: float | None = None
    if "methodology" in state.sub_scores:
        methods_score = state.sub_scores["methodology"].score
        logger.info("[SCORING_AGENT] LLM methodology score: %.2f", methods_score)
    else:
        logger.info("[SCORING_AGENT] No LLM methodology score available")

    score, tier = compute_composite_score(
        hard_flags=hard_flags_final,
        soft_flags=soft_flags_final,
        quality_signals=state.quality_signals,
        methods_score=methods_score,
        config=config,
    )

    per_dimension = [
        {
            "dimension": name,
            "score": round(sub.score, 3),
            "reason": sub.reason,
        }
        for name, sub in state.sub_scores.items()
    ]

    # Generate structured report via LLM (falls back to deterministic if unavailable)
    # Pass the full per_dimension list (with reason strings) so the LLM prompt is grounded
    structured = _generate_structured_report(
        state, score, tier,
        per_dimension,   # full list[dict] with dimension/score/reason
        config,
        hard_flags=hard_flags_final,
        soft_flags=soft_flags_final,
    )

    # Backward-compatible flat summary = overall verdict + recommendation
    summary = " ".join(filter(None, [structured.overall_verdict, structured.recommendation]))

    report = TrustReport(
        composite_score=score,
        tier=tier,
        summary=summary,
        hard_flags=hard_flags_final,
        soft_flags=soft_flags_final,
        quality_signals=state.quality_signals,
        per_dimension=per_dimension,
        coverage=state.coverage,
        structured_report=structured,
    )

    return {"final": report}


# ---------------------------------------------------------------------------
# LLM-based structured report generation
# ---------------------------------------------------------------------------

def _generate_structured_report(
    state: PaperState,
    score: int,
    tier: str,
    per_dimension: list[dict],  # full list with dimension/score/reason
    config: dict | None,
    *,
    hard_flags: list | None = None,
    soft_flags: list | None = None,
) -> StructuredReport:
    """Use LLM to generate a structured, section-by-section credibility report."""

    # Use provided flags (deduplicated/augmented) or fall back to state flags
    effective_hard = hard_flags if hard_flags is not None else state.hard_flags
    effective_soft = soft_flags if soft_flags is not None else state.soft_flags

    def _fmt_flags(flags):
        if not flags:
            return "None"
        return "; ".join(f"{f.code}: {f.message[:80]}" for f in flags[:6])

    # Format per-dimension with sub-agent reason strings for prompt grounding
    def _fmt_per_dimension(dims: list[dict]) -> str:
        lines = []
        for d in dims:
            name = d.get("dimension", "unknown")
            sc = d.get("score", 0.0)
            reason = d.get("reason", "").strip()
            if reason:
                lines.append(f"  {name}: {sc:.2f}  — Sub-agent note: {reason[:200]}")
            else:
                lines.append(f"  {name}: {sc:.2f}")
        return "\n".join(lines) if lines else "None"

    # Build a lookup dict for fallback path
    per_dim_lookup = {d["dimension"]: d for d in per_dimension}

    prompt = _STRUCTURED_REPORT_PROMPT.format(
        title=state.stub.title or "Unknown",
        year=state.stub.year or "unknown year",
        score=score,
        tier=tier,
        hard_flags=_fmt_flags(effective_hard),
        soft_flags=_fmt_flags(effective_soft),
        quality_signals=_fmt_flags(state.quality_signals),
        per_dimension=_fmt_per_dimension(per_dimension),
    )

    try:
        llm = get_llm(max_tokens=900, config=config)
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = strip_think_tokens(response.content)
        return _parse_structured_report(raw, score, tier, per_dim_lookup, state, effective_hard, effective_soft)
    except Exception as exc:
        logger.warning("Structured report generation failed: %s", exc)
        return _fallback_structured_report(score, tier, state, per_dim_lookup, effective_hard, effective_soft)


# ---------------------------------------------------------------------------
# Structured report parser
# ---------------------------------------------------------------------------

# Section header regex anchors
_SECTION_RE = re.compile(
    r"(OVERALL VERDICT|SCORE BREAKDOWN|KEY CONCERNS|POSITIVE SIGNALS|RECOMMENDATION)",
    re.IGNORECASE,
)


def _parse_structured_report(
    raw: str,
    score: int,
    tier: str,
    per_dim_lookup: dict[str, dict],  # dimension -> {dimension, score, reason}
    state: PaperState,
    effective_hard: list | None = None,
    effective_soft: list | None = None,
) -> StructuredReport:
    """Tolerantly parse LLM section output into a StructuredReport.

    Falls back gracefully to deterministic values for any missing or
    malformed section — never raises.
    """
    hard_flags_use = effective_hard if effective_hard is not None else state.hard_flags
    soft_flags_use = effective_soft if effective_soft is not None else state.soft_flags

    # Split into sections keyed by heading
    sections: dict[str, str] = {}
    current_key: str | None = None
    buffer: list[str] = []

    for line in raw.splitlines():
        match = _SECTION_RE.match(line.strip())
        if match:
            if current_key is not None:
                sections[current_key.upper()] = "\n".join(buffer).strip()
            current_key = match.group(1).upper()
            buffer = []
        else:
            buffer.append(line)
    if current_key is not None:
        sections[current_key] = "\n".join(buffer).strip()

    # --- Overall verdict ---
    overall_verdict = sections.get("OVERALL VERDICT", "").strip()
    if not overall_verdict:
        overall_verdict = f"Trust score {score}/100 ({tier})."

    # --- Score breakdown ---
    breakdown: list[ScoreBreakdownEntry] = []
    breakdown_raw = sections.get("SCORE BREAKDOWN", "")
    for line in breakdown_raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            try:
                pct = int(re.sub(r"[^\d]", "", parts[1])) if parts[1] else 50
                breakdown.append(ScoreBreakdownEntry(
                    dimension=parts[0],
                    score_pct=min(max(pct, 0), 100),
                    rationale=parts[2],
                ))
            except (ValueError, IndexError):
                pass

    # Fill from per_dimension data if LLM breakdown was empty / malformed
    # Use sub-agent reason strings so the fallback table is also informative
    if not breakdown:
        for dim_name, dim_data in per_dim_lookup.items():
            fallback_reason = dim_data.get("reason", "").strip()
            breakdown.append(ScoreBreakdownEntry(
                dimension=dim_name,
                score_pct=round(dim_data.get("score", 0.0) * 100),
                rationale=fallback_reason,
            ))

    # --- Key concerns ---
    concerns: list[str] = []
    concerns_raw = sections.get("KEY CONCERNS", "")
    for line in concerns_raw.splitlines():
        line = line.strip().lstrip("-").strip()
        if line and line.lower() != "none":
            concerns.append(line)
    if not concerns:
        for f in hard_flags_use[:3]:
            concerns.append(f"{f.code}: {f.message}")
        for f in soft_flags_use[:3]:
            concerns.append(f"{f.code}: {f.message}")

    # --- Positive signals ---
    positives: list[str] = []
    positives_raw = sections.get("POSITIVE SIGNALS", "")
    for line in positives_raw.splitlines():
        line = line.strip().lstrip("-").strip()
        if line and line.lower() != "none":
            positives.append(line)
    if not positives:
        for f in state.quality_signals[:3]:
            positives.append(f"{f.code}: {f.message}")

    # --- Recommendation ---
    recommendation = sections.get("RECOMMENDATION", "").strip()
    if not recommendation:
        if tier == "Trusted":
            recommendation = "Safe to include in analysis."
        elif tier == "Caution":
            recommendation = "Cite with caution; verify key claims independently."
        else:
            recommendation = "Exclude from analysis or flag prominently."

    return StructuredReport(
        overall_verdict=overall_verdict,
        score_breakdown=breakdown,
        key_concerns=concerns,
        positive_signals=positives,
        recommendation=recommendation,
        raw_score=score,
        tier=tier,
    )


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------

def _fallback_structured_report(
    score: int,
    tier: str,
    state: PaperState,
    per_dim_lookup: dict[str, dict],  # dimension -> {dimension, score, reason}
    effective_hard: list | None = None,
    effective_soft: list | None = None,
) -> StructuredReport:
    """Produce a StructuredReport deterministically when the LLM is unavailable."""
    hard_flags_use = effective_hard if effective_hard is not None else state.hard_flags
    soft_flags_use = effective_soft if effective_soft is not None else state.soft_flags
    hard = [f.code for f in hard_flags_use]
    soft = [f.code for f in soft_flags_use]

    if hard:
        overall_verdict = (
            f"Trust score {score}/100 ({tier}). Critical issues: {', '.join(hard[:3])}."
        )
    elif soft:
        overall_verdict = (
            f"Trust score {score}/100 ({tier}). Concerns: {', '.join(soft[:3])}."
        )
    else:
        overall_verdict = f"Trust score {score}/100 ({tier}). No critical issues detected."

    breakdown = [
        ScoreBreakdownEntry(
            dimension=dim,
            score_pct=round(data.get("score", 0.0) * 100),
            # Prefer sub_scores reason (freshest), fall back to stored reason in lookup
            rationale=(
                state.sub_scores[dim].reason
                if dim in state.sub_scores
                else data.get("reason", "")
            ),
        )
        for dim, data in per_dim_lookup.items()
    ]

    concerns = [f"{f.code}: {f.message}" for f in (hard_flags_use + soft_flags_use)[:5]]
    positives = [f"{f.code}: {f.message}" for f in state.quality_signals[:3]]

    if tier == "Trusted":
        recommendation = "Safe to include in analysis."
    elif tier == "Caution":
        recommendation = "Cite with caution; verify key claims independently."
    else:
        recommendation = "Exclude from analysis or flag prominently."

    return StructuredReport(
        overall_verdict=overall_verdict,
        score_breakdown=breakdown,
        key_concerns=concerns,
        positive_signals=positives,
        recommendation=recommendation,
        raw_score=score,
        tier=tier,
    )
