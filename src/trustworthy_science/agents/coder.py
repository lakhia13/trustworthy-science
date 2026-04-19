"""Coder Agent — reproducibility depth, GitHub repo health, Environmental Viability LLM skill."""
from __future__ import annotations
import logging
import re
from trustworthy_science.state import Flag, PaperState, SubScore
from trustworthy_science.agents.reproducibility import reproducibility_agent
from trustworthy_science.tools.github_api import (
    extract_github_owner_repo, get_repo_health, fetch_readme
)
from trustworthy_science.tools.doi_resolver import verify_doi_accessible
from trustworthy_science.llm import get_llm, strip_think_tokens

logger = logging.getLogger(__name__)

_DOI_BACKED_HOSTS = frozenset([
    'zenodo.org', 'figshare.com', 'datadryad.org', 'dryad.org',
    'dataverse.harvard.edu', 'pangaea.de', 'gigadb.org',
])

_GITHUB_RE = re.compile(r'https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', re.IGNORECASE)
_URL_RE = re.compile(r'https?://[^\s>"]+', re.IGNORECASE)


def coder_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: reproducibility checks + GitHub repo health + Environmental Viability LLM skill."""
    # Run the existing reproducibility_agent
    base_result = reproducibility_agent(state, config)

    soft_flags = list(base_result.get('soft_flags', []))
    quality_signals = list(base_result.get('quality_signals', []))
    hard_flags = list(base_result.get('hard_flags', []))
    repro_sub = base_result.get('sub_scores', {}).get('reproducibility')

    # --- Upgrade OPEN_DATA to OPEN_DATA_PERMANENT or OPEN_DATA_GENERIC ---
    new_quality = []
    for sig in quality_signals:
        if sig.code == 'OPEN_DATA':
            # Check if URL is DOI-backed
            is_permanent = any(
                host in sig.message.lower() for host in _DOI_BACKED_HOSTS
            )
            new_code = 'OPEN_DATA_PERMANENT' if is_permanent else 'OPEN_DATA_GENERIC'
            new_quality.append(Flag(
                tier='quality',
                code=new_code,
                message=sig.message,
                source_agent='coder',
                evidence=sig.evidence,
            ))
            logger.info('[CODER] OPEN_DATA → %s', new_code)
        elif sig.code == 'OPEN_CODE':
            # Will be upgraded below after GitHub check
            new_quality.append(sig)
        else:
            new_quality.append(sig)
    quality_signals = new_quality

    # --- GitHub repo health check + Environmental Viability ---
    text = ''
    if state.parsed:
        text = ' '.join(filter(None, [
            state.parsed.full_text,
            state.parsed.abstract,
            state.parsed.methods,
        ]))

    github_urls = list(set(_GITHUB_RE.findall(text)))
    repo_functional = False

    for github_url in github_urls[:2]:  # check at most 2 repos
        health = get_repo_health(github_url)
        if health is None:
            logger.info('[CODER] GitHub health check failed/unavailable for %s', github_url)
            continue

        if health.get('archived'):
            logger.info('[CODER] Repo is archived: %s', github_url)
            continue

        # Check last push within 24 months
        last_push = health.get('last_push', '')
        is_recent = False
        if last_push:
            try:
                from datetime import datetime, timezone, timedelta
                pushed = datetime.fromisoformat(last_push.rstrip('Z')).replace(tzinfo=timezone.utc)
                is_recent = (datetime.now(timezone.utc) - pushed).days < 730
            except Exception:
                is_recent = True  # assume recent if parse fails

        if not is_recent:
            logger.info('[CODER] Repo not updated in 24+ months: %s', github_url)
            continue

        # Environmental Viability LLM skill
        parsed = extract_github_owner_repo(github_url)
        if parsed:
            owner, repo = parsed
            branch = health.get('default_branch', 'main')
            readme_text = fetch_readme(owner, repo, branch)
            if readme_text:
                is_viable = _environmental_viability_check(readme_text, config)
                if is_viable:
                    repo_functional = True
                    logger.info('[CODER] Environmental Viability: PASS for %s/%s', owner, repo)
                    break

        # Health checks passed even without README LLM
        if health.get('size_kb', 0) > 10:
            repo_functional = True
            break

    # Upgrade OPEN_CODE → OPEN_CODE_FUNCTIONAL based on repo health
    upgraded_quality = []
    for sig in quality_signals:
        if sig.code == 'OPEN_CODE':
            if repo_functional:
                upgraded_quality.append(Flag(
                    tier='quality',
                    code='OPEN_CODE_FUNCTIONAL',
                    message=sig.message + ' [Repo health verified]',
                    source_agent='coder',
                    evidence=sig.evidence,
                ))
                logger.info('[CODER] OPEN_CODE → OPEN_CODE_FUNCTIONAL')
            else:
                upgraded_quality.append(sig)  # keep original OPEN_CODE signal
        else:
            upgraded_quality.append(sig)
    quality_signals = upgraded_quality

    # --- DATA_LINK_BROKEN check on extracted URLs ---
    urls_to_check = _extract_data_urls(text)
    broken_urls = []
    for url in urls_to_check[:3]:  # limit to 3 checks per paper
        if not verify_doi_accessible(url):
            broken_urls.append(url)

    if broken_urls:
        broken_flag = Flag(
            tier='soft',
            code='DATA_LINK_BROKEN',
            message=f'Data/code URL(s) return 404 or are inaccessible: {broken_urls[0][:80]}',
            source_agent='coder',
        )
        soft_flags.append(broken_flag)
        logger.warning('[CODER] Broken data/code link(s): %s', broken_urls)
        # Cancel any OPEN_DATA_* or OPEN_CODE_* signals for broken links
        quality_signals = [
            sig for sig in quality_signals
            if sig.code not in ('OPEN_DATA_PERMANENT', 'OPEN_DATA_GENERIC', 'OPEN_CODE_FUNCTIONAL', 'OPEN_CODE')
        ]

    # Build coder sub-score
    base_score = repro_sub.score if repro_sub else 0.7
    reason_parts = [repro_sub.reason if repro_sub and repro_sub.reason else '']
    if repo_functional:
        reason_parts.append('Code repository is functional and recently maintained.')
    if broken_urls:
        base_score -= 0.20
        reason_parts.append('Broken data/code links detected.')
    base_score = max(0.0, min(1.0, base_score))

    coder_sub = SubScore(
        score=base_score,
        confidence=repro_sub.confidence if repro_sub else 0.5,
        notes=repro_sub.notes if repro_sub else '',
        reason=' '.join(filter(None, reason_parts))[:400],
    )

    return {
        'sub_scores': {'coder': coder_sub},
        'hard_flags': hard_flags,
        'soft_flags': soft_flags,
        'quality_signals': quality_signals,
    }


def _environmental_viability_check(readme_text: str, config: dict | None) -> bool:
    """LLM skill: check if README has clear installation instructions and dependency spec."""
    prompt = (
        f'README content:\n{readme_text[:2000]}\n\n'
        'Does this README contain:\n'
        '1. Clear installation instructions (pip install, conda, docker, or similar)?\n'
        '2. A complete dependency specification (requirements.txt, environment.yml, Dockerfile, or inline)?\n'
        'Answer ONLY with JSON: {"viable": true or false, "reason": "one sentence"}'
    )
    try:
        llm = get_llm(max_tokens=100, config=config)
        from langchain_core.messages import HumanMessage
        import json, re
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = strip_think_tokens(response.content)
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            data = json.loads(m.group(0))
            return bool(data.get('viable', False))
    except Exception as exc:
        logger.debug('[CODER] Environmental viability check failed: %s', exc)
    return False


def _extract_data_urls(text: str) -> list[str]:
    """Extract data/code URLs from text that are not known-stable hosts."""
    all_urls = _URL_RE.findall(text)
    from trustworthy_science.tools.doi_resolver import _STABLE_HOSTS
    result = []
    seen = set()
    for url in all_urls:
        if len(url) < 15 or url in seen:
            continue
        domain_m = re.search(r'https?://([^/]+)', url)
        if domain_m and any(s in domain_m.group(1) for s in _STABLE_HOSTS):
            continue  # skip stable hosts
        if 'doi.org' in url or 'ncbi.nlm.nih.gov' in url or 'pubmed' in url:
            continue  # skip DOI resolvers and PubMed
        if url.endswith(('.pdf', '.html', '.php', '.aspx')):
            continue  # skip non-data resources
        seen.add(url)
        result.append(url)
    return result[:5]
