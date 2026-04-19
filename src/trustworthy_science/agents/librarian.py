"""Librarian Agent — metadata lineage, venue legitimacy, author consistency audit."""
from __future__ import annotations
import logging
from trustworthy_science.state import Flag, PaperState, SubScore
from trustworthy_science.agents.publication_metadata import publication_metadata_agent
from trustworthy_science.llm import get_llm, strip_think_tokens

logger = logging.getLogger(__name__)

def librarian_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: venue/funding/COI checks + Author Consistency Audit LLM skill."""
    # Run the existing publication_metadata_agent for all existing flag logic
    base_result = publication_metadata_agent(state, config)

    # Build a sub-score from the flags raised
    hard_flags = base_result.get('hard_flags', [])
    soft_flags = base_result.get('soft_flags', [])
    quality_signals = base_result.get('quality_signals', [])

    score = 0.70  # neutral baseline
    reason_parts = []

    # Adjust score from base flags
    if any(f.code == 'PREDATORY_VENUE' for f in hard_flags):
        score -= 0.40
        reason_parts.append('Predatory venue detected.')
    if any(f.code == 'HIGH_IMPACT_VENUE' for f in quality_signals):
        score += 0.10
        reason_parts.append('Venue indexed in DOAJ.')
    if any(f.code == 'VENUE_NOT_IN_DOAJ' for f in soft_flags):
        reason_parts.append('Venue not in DOAJ.')
    if any(f.code == 'FAST_PEER_REVIEW' for f in soft_flags):
        score -= 0.10
        reason_parts.append('Fast peer review (<14 days).')
    if any(f.code == 'INDUSTRY_ONLY_FUNDING_NO_COI' for f in soft_flags):
        score -= 0.10
        reason_parts.append('Industry funding without COI disclosure.')

    # Author Consistency Audit LLM skill
    author_mismatch = _run_author_consistency_audit(state, config)
    if author_mismatch:
        score -= 0.20
        reason_parts.append(f'Author-venue mismatch: {author_mismatch}')

    score = max(0.0, min(1.0, score))
    reason = ' '.join(reason_parts) if reason_parts else 'No major lineage concerns detected.'

    sub = SubScore(
        score=score,
        confidence=0.75,
        notes=f'venue_flags={[f.code for f in hard_flags+soft_flags+quality_signals]}',
        reason=reason,
    )

    result = dict(base_result)
    result['sub_scores'] = {'librarian': sub}
    return result


def _run_author_consistency_audit(state: PaperState, config: dict | None) -> str | None:
    """LLM skill: detect author-topic-venue mismatch. Returns mismatch description or None."""
    if not state.stub.abstract or not state.stub.venue:
        return None

    authors = ', '.join(state.stub.authors[:5]) if state.stub.authors else 'Unknown'
    prompt = (
        f'Paper venue: "{state.stub.venue}"\n'
        f'Authors: {authors}\n'
        f'Abstract: {state.stub.abstract[:800]}\n\n'
        'Does the research topic in this abstract match the scope of the publishing venue?\n'
        'Is there any sign this paper is out-of-scope for the venue (paper mill indicator)?\n'
        'Respond with ONLY a JSON object: {{"mismatch": true/false, "reason": "one sentence or null"}}'
    )
    try:
        llm = get_llm(max_tokens=150, config=config)
        from langchain_core.messages import HumanMessage
        import json, re
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = strip_think_tokens(response.content)
        # Extract JSON
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))
        if data.get('mismatch') and data.get('reason'):
            logger.info('[LIBRARIAN] Author-venue mismatch detected: %s', data['reason'])
            return str(data['reason'])[:200]
    except Exception as exc:
        logger.debug('[LIBRARIAN] Author consistency audit failed: %s', exc)
    return None
