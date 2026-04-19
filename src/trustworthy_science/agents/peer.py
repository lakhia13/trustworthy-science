"""Peer Agent — Adversarial Red-Teaming + Citation Context analysis."""
from __future__ import annotations
import json
import logging
import re
from trustworthy_science.state import Flag, PaperState, SubScore
from trustworthy_science.llm import get_llm, strip_think_tokens

logger = logging.getLogger(__name__)

_LIMITATIONS_KEYWORDS = [
    'limitation', 'weakness', 'bias', 'confound', 'cannot conclude',
    'further study', 'future work', 'should be noted', 'caution',
]


def peer_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: Adversarial Red-Teaming + Citation Context (scite.ai) analysis."""
    hard_flags: list[Flag] = []
    soft_flags: list[Flag] = []
    quality_signals: list[Flag] = []
    reason_parts = []
    score = 0.70  # neutral
    confidence = 0.30  # low default

    # --- Skill A: Adversarial Red-Teaming ---
    abstract = (state.parsed.abstract if state.parsed else None) or state.stub.abstract
    discussion = state.parsed.discussion if state.parsed else ''
    full_text = state.parsed.full_text if state.parsed else ''

    if abstract:
        confidence = 0.55
        overreach, confounders = _adversarial_red_team(abstract, discussion or full_text[:1000], config)
        if overreach:
            soft_flags.append(Flag(
                tier='soft',
                code='CLAIM_OVERREACH',
                message=f'Adversarial review detected conclusion overreach: {overreach[:200]}',
                source_agent='peer',
            ))
            score -= 0.20
            reason_parts.append(f'Conclusion overreach identified. Confounders: {confounders[:150]}')
            logger.info('[PEER] CLAIM_OVERREACH flagged: %s', overreach[:80])
        else:
            reason_parts.append('No conclusion overreach detected by adversarial review.')

        # DEEP_LIMITATIONS check
        text_for_limits = (discussion or '') + ' ' + (full_text or '')[:2000]
        if _check_deep_limitations(text_for_limits):
            quality_signals.append(Flag(
                tier='quality',
                code='DEEP_LIMITATIONS',
                message='Paper contains a thorough self-critical limitations section.',
                source_agent='peer',
            ))
            score += 0.05
            reason_parts.append('Thorough limitations section detected.')

    # --- Skill B: Citation Context (gated on SCITE_API_KEY or config) ---
    scite_cfg = (config or {}).get('scite', {})
    import os
    scite_enabled = bool(os.environ.get('SCITE_API_KEY') or scite_cfg.get('api_key'))

    doi = state.stub.doi
    if scite_enabled and doi:
        from trustworthy_science.tools.scite_api import get_citation_contexts
        scite_data = get_citation_contexts(doi)
        if scite_data:
            confidence = 0.80
            total = scite_data.get('total', 0)
            supporting = scite_data.get('supporting', 0)
            reason_parts.append(
                f'scite.ai: {supporting} supporting / {total} total citations.'
            )

            # SUPPORTING_CITATIONS bonus
            if total >= 3 and supporting / total >= 0.50:
                quality_signals.append(Flag(
                    tier='quality',
                    code='SUPPORTING_CITATIONS',
                    message=f'{supporting}/{total} citations are "supporting" on scite.ai.',
                    source_agent='peer',
                ))
                score += 0.10

            # Sentiment analysis on recent contexts
            if scite_data.get('recent_contexts'):
                sentiment = _analyze_citation_sentiment(scite_data['recent_contexts'], config)
                if sentiment == 'contested':
                    # Deduplicate — only add if CLAIM_OVERREACH not already raised by Skill A
                    already_flagged = any(f.code == 'CLAIM_OVERREACH' for f in soft_flags)
                    if not already_flagged:
                        soft_flags.append(Flag(
                            tier='soft',
                            code='CLAIM_OVERREACH',
                            message='Citation context analysis shows contested reception in the literature.',
                            source_agent='peer',
                        ))
                        score -= 0.15
                        logger.info('[PEER] CLAIM_OVERREACH from citation sentiment: contested')

    score = max(0.0, min(1.0, score))
    reason = ' '.join(filter(None, reason_parts)) or 'Peer review analysis completed.'

    peer_sub = SubScore(
        score=score,
        confidence=confidence,
        notes=f'skills_run=adversarial,{"citation_context" if scite_enabled and doi else "no_scite"}',
        reason=reason[:400],
    )

    return {
        'sub_scores': {'peer': peer_sub},
        'hard_flags': hard_flags,
        'soft_flags': soft_flags,
        'quality_signals': quality_signals,
    }


def _adversarial_red_team(
    abstract: str, discussion: str, config: dict | None
) -> tuple[str | None, str]:
    """LLM hostile peer reviewer. Returns (overreach_detail or None, confounders_str)."""
    prompt = (
        f'Abstract:\n{abstract[:700]}\n\nDiscussion/Results:\n{discussion[:600]}\n\n'
        'You are a hostile peer reviewer. Your job is to find fatal flaws.\n'
        '1. Identify up to three specific confounding variables the authors have NOT addressed.\n'
        '2. Are the conclusions FULLY justified by the reported statistics? '
        'Consider effect sizes, sample sizes, and statistical power.\n\n'
        'Output ONLY valid JSON (no markdown):\n'
        '{"confounders": ["list", "of", "confounders"], '
        '"conclusion_overreach": true or false, '
        '"overreach_detail": "one sentence explaining the overreach, or null"}'
    )
    try:
        llm = get_llm(max_tokens=350, config=config)
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = strip_think_tokens(response.content)
        m = re.search(r'\{[\s\S]*\}', raw)
        if not m:
            return None, ''
        data = json.loads(m.group(0))
        confounders = ', '.join(data.get('confounders', [])[:3])
        if data.get('conclusion_overreach') and data.get('overreach_detail'):
            return str(data['overreach_detail'])[:300], confounders
        return None, confounders
    except Exception as exc:
        logger.debug('[PEER] Adversarial red-team failed: %s', exc)
        return None, ''


def _check_deep_limitations(text: str) -> bool:
    """Check if paper has a self-critical limitations section (>= 3 sentences with keywords)."""
    if not text:
        return False
    sentences = re.split(r'[.!?]+', text.lower())
    limit_sentences = [
        s for s in sentences
        if any(kw in s for kw in _LIMITATIONS_KEYWORDS)
    ]
    return len(limit_sentences) >= 3


def _analyze_citation_sentiment(contexts: list[dict], config: dict | None) -> str:
    """LLM: classify community reception as supporting_finding, contested, or inconclusive."""
    excerpts = '\n---\n'.join(
        f"[{c.get('type','?')}] {c.get('excerpt','')[:200]}" for c in contexts[:5]
    )
    prompt = (
        f'These are recent citation excerpts for a scientific paper:\n{excerpts}\n\n'
        'Based on these excerpts, classify the scientific community reception as:\n'
        '- "supporting_finding": most citations affirm the results\n'
        '- "contested": citations express doubt, disagreement, or failed replication\n'
        '- "inconclusive": mixed or neutral citations\n\n'
        'Output ONLY JSON: {"sentiment": "supporting_finding" or "contested" or "inconclusive", '
        '"reason": "one sentence"}'
    )
    try:
        llm = get_llm(max_tokens=120, config=config)
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = strip_think_tokens(response.content)
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            data = json.loads(m.group(0))
            return str(data.get('sentiment', 'inconclusive'))
    except Exception as exc:
        logger.debug('[PEER] Citation sentiment analysis failed: %s', exc)
    return 'inconclusive'
