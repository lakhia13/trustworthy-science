"""Methodology & Text Quality agent — LLM critique of methods section."""

from __future__ import annotations

import json
import logging

from trustworthy_science.llm import get_llm
from trustworthy_science.state import EvidenceQuote, Flag, PaperState, SubScore

logger = logging.getLogger(__name__)

_METHODS_RUBRIC_PROMPT = """\
You are a senior peer reviewer evaluating the Methods section of a scientific paper.

Paper title: {title}
Methods section (may be truncated):
---
{methods}
---

Evaluate the methods on these criteria and respond with ONLY valid JSON:
{{
  "sample_size_justified": true/false,
  "controls_described": true/false,
  "blinding_described": true/false,
  "statistics_prespecified": true/false,
  "outcome_clearly_defined": true/false,
  "reproducibility_detail_sufficient": true/false,
  "overall_score": 0.0-1.0,
  "weaknesses": ["list of specific weakness strings, quoting from the text when possible"],
  "strengths": ["list of specific strengths"]
}}

Be critical. Return ONLY the JSON, no markdown, no explanation.
"""


def methodology_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: use an LLM to critique the methods section."""
    cfg = config or {}
    llm_cfg = cfg.get("llm", {})
    max_tokens = int(llm_cfg.get("methods_critique_max_tokens", 1500))

    methods_text = ""
    title = state.stub.title
    if state.parsed:
        methods_text = state.parsed.methods or state.parsed.abstract

    if not methods_text:
        sub = SubScore(
            score=0.5,
            confidence=0.1,
            notes="No methods text available for LLM critique.",
        )
        return {"sub_scores": {"methodology": sub}}

    # Truncate to avoid token blowout
    methods_snippet = methods_text[:3000]

    try:
        result = _call_llm(
            prompt=_METHODS_RUBRIC_PROMPT.format(title=title, methods=methods_snippet),
            max_tokens=max_tokens,
            config=cfg,
        )
        return _process_result(result, state)
    except Exception as exc:
        logger.warning("Methodology LLM critique failed: %s", exc)
        sub = SubScore(score=0.5, confidence=0.1, notes=f"LLM critique failed: {exc}")
        return {"sub_scores": {"methodology": sub}}


def _call_llm(prompt: str, max_tokens: int, config: dict | None = None) -> dict:
    """Call the K2 (OpenAI-compatible) LLM and return parsed JSON response."""
    from trustworthy_science.llm import strip_think_tokens
    llm = get_llm(max_tokens=max_tokens, config=config)

    from langchain_core.messages import HumanMessage
    response = llm.invoke([HumanMessage(content=prompt)])
    raw = strip_think_tokens(response.content)
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def _process_result(result: dict, state: PaperState) -> dict:
    """Convert LLM JSON result to flags and sub-score."""
    soft_flags: list[Flag] = []
    quality_signals: list[Flag] = []

    # Validate that any quoted weakness is in the source text (hallucination guard)
    source_text = ""
    if state.parsed:
        source_text = (state.parsed.methods or "") + " " + (state.parsed.full_text or "")

    weaknesses = result.get("weaknesses", [])
    validated_weaknesses = []
    for w in weaknesses:
        # If shorter than 15 chars or found in text, trust it; otherwise skip
        if len(w) < 15 or any(token in source_text for token in w.split()[:4]):
            validated_weaknesses.append(w)

    strengths = result.get("strengths", [])

    if not result.get("sample_size_justified", True):
        soft_flags.append(Flag(
            tier="soft", code="METHODS_INCOMPLETE",
            message="Methods do not justify sample size adequacy.",
            source_agent="methodology",
        ))
    if not result.get("controls_described", True):
        soft_flags.append(Flag(
            tier="soft", code="METHODS_INCOMPLETE",
            message="Control conditions are not clearly described.",
            source_agent="methodology",
        ))
    if not result.get("reproducibility_detail_sufficient", True):
        soft_flags.append(Flag(
            tier="soft", code="METHODS_INCOMPLETE",
            message="Methods section lacks sufficient detail for independent replication.",
            source_agent="methodology",
        ))

    # Quality bonus if pre-specified stats
    if result.get("statistics_prespecified", False):
        quality_signals.append(Flag(
            tier="quality", code="PREREGISTERED",
            message="Statistics appear to have been pre-specified in the methods.",
            source_agent="methodology",
        ))

    overall = float(result.get("overall_score", 0.5))
    confidence = 0.80 if state.coverage == "full_text" else 0.50

    notes = f"LLM methods score: {overall:.2f}. Weaknesses: {'; '.join(validated_weaknesses[:3]) or 'none detected'}."
    
    reason = f"Strengths: {'; '.join(strengths)}. Weaknesses: {'; '.join(validated_weaknesses)}."

    sub = SubScore(
        score=overall,
        confidence=confidence,
        flags=soft_flags + quality_signals,
        notes=notes,
        reason=reason,
    )

    return {
        "sub_scores": {"methodology": sub},
        "soft_flags": soft_flags,
        "quality_signals": quality_signals,
    }
