"""Detective Agent — statistical integrity + Shadow Data Verification LLM skill."""
from __future__ import annotations
import json
import logging
import re
from trustworthy_science.state import Flag, PaperState, SubScore
from trustworthy_science.agents.stats_integrity import stats_integrity_agent
from trustworthy_science.llm import get_llm, strip_think_tokens

logger = logging.getLogger(__name__)

_INDUSTRY_KEYWORDS = [
    'Pfizer', 'Novartis', 'Roche', 'AstraZeneca', 'Merck', 'Johnson & Johnson',
    'Sanofi', 'GlaxoSmithKline', 'GSK', 'Abbott', 'Medtronic', 'Stryker',
    'industry funded', 'industry supported', 'pharmaceutical company',
    'biotech', 'device manufacturer', 'medical device company'
]

def detective_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: statistical integrity + Shadow Data Verification + funding COI check."""
    # Run existing stats_integrity_agent
    base_result = stats_integrity_agent(state, config)

    hard_flags = list(base_result.get('hard_flags', []))
    soft_flags = list(base_result.get('soft_flags', []))
    quality_signals = list(base_result.get('quality_signals', []))
    sub_scores = dict(base_result.get('sub_scores', {}))

    # Rename stats_integrity sub-score to detective
    stats_sub = sub_scores.pop('stats_integrity', None)

    # Shadow Data Verification LLM skill
    inconsistency_flag = _shadow_data_verification(state, config)
    if inconsistency_flag:
        soft_flags.append(inconsistency_flag)

    # Industry COI check
    coi_flag = _check_industry_coi_unstated(state)
    if coi_flag:
        soft_flags.append(coi_flag)

    # Build detective sub-score
    base_score = stats_sub.score if stats_sub else 0.7
    reason_parts = [stats_sub.reason if stats_sub and stats_sub.reason else stats_sub.notes if stats_sub else '']
    if inconsistency_flag:
        base_score -= 0.20
        reason_parts.append('Internal data inconsistency detected between abstract and results.')
    if coi_flag:
        base_score -= 0.10
        reason_parts.append('Industry funding without explicit COI statement.')
    base_score = max(0.0, min(1.0, base_score))

    detective_sub = SubScore(
        score=base_score,
        confidence=stats_sub.confidence if stats_sub else 0.5,
        notes=stats_sub.notes if stats_sub else '',
        reason=' '.join(filter(None, reason_parts))[:400],
    )
    sub_scores['detective'] = detective_sub

    return {
        'sub_scores': sub_scores,
        'hard_flags': hard_flags,
        'soft_flags': soft_flags,
        'quality_signals': quality_signals,
    }


def _shadow_data_verification(state: PaperState, config: dict | None) -> Flag | None:
    """LLM skill: cross-reference N/p-values/effect sizes between Abstract and Results."""
    if not state.parsed:
        return None
    abstract = state.parsed.abstract or state.stub.abstract
    results = state.parsed.results or ''
    if not abstract or not results:
        return None

    prompt = (
        f'Abstract:\n{abstract[:600]}\n\nResults section:\n{results[:800]}\n\n'
        'Extract every explicitly reported sample size (N=...), p-value (p=..., p<...), and '
        'primary effect size (OR, HR, RR, Cohen d, r=...) from BOTH sections.\n'
        'Check if any key numeric value appears in the Abstract but differs by more than 10% '
        'in the Results, or appears in one section but not the other.\n'
        'Respond ONLY with valid JSON: '
        '{"abstract_n": [list of N values as numbers], '
        '"results_n": [list of N values as numbers], '
        '"mismatch": true or false, '
        '"mismatch_detail": "one sentence describing the mismatch or null"}'
    )
    try:
        llm = get_llm(max_tokens=300, config=config)
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = strip_think_tokens(response.content)
        m = re.search(r'\{[\s\S]*\}', raw)
        if not m:
            return None
        data = json.loads(m.group(0))
        mismatch = data.get('mismatch', False)
        detail = data.get('mismatch_detail') or ''
        # Hallucination guard: detail must reference at least one number
        if mismatch and detail and re.search(r'\d+(\.\d+)?', detail):
            logger.info('[DETECTIVE] Internal inconsistency detected: %s', detail[:100])
            return Flag(
                tier='soft',
                code='INTERNAL_INCONSISTENCY',
                message=f'Abstract/Results numeric inconsistency: {detail[:200]}',
                source_agent='detective',
            )
    except Exception as exc:
        logger.debug('[DETECTIVE] Shadow data verification failed: %s', exc)
    return None


def _check_industry_coi_unstated(state: PaperState) -> Flag | None:
    """Check for industry funding keywords without an explicit COI statement."""
    if not state.parsed:
        return None
    funding = (state.parsed.funding or '').lower()
    coi = (state.parsed.coi_statement or '').lower()
    full = (state.parsed.full_text or '')[:2000].lower()

    text_to_check = funding + ' ' + full
    has_industry = any(kw.lower() in text_to_check for kw in _INDUSTRY_KEYWORDS)
    has_coi = bool(coi) or any(phrase in text_to_check for phrase in [
        'conflict of interest', 'coi', 'competing interest', 'no financial interest',
        'no competing', 'declared no', 'nothing to disclose'
    ])

    if has_industry and not has_coi:
        return Flag(
            tier='soft',
            code='INDUSTRY_COI_UNSTATED',
            message='Industry funding detected but no explicit conflict-of-interest statement found.',
            source_agent='detective',
        )
    return None
