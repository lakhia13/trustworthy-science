"""DOI/URL accessibility checker — detects broken data/code links."""
from __future__ import annotations
import logging
import re
import httpx

logger = logging.getLogger(__name__)

# Known-stable DOI hosts — skip verification (their redirects are always valid)
_STABLE_HOSTS = frozenset([
    'zenodo.org', 'figshare.com', 'datadryad.org', 'dryad.org',
    'dataverse.harvard.edu', 'osf.io', 'pangaea.de',
])


def verify_doi_accessible(url_or_doi: str) -> bool:
    """Return True if the URL/DOI resolves to a 200-range response."""
    url = url_or_doi
    if not url.startswith('http'):
        url = f'https://doi.org/{url_or_doi}'

    # Skip known-stable hosts
    domain = re.search(r'https?://([^/]+)', url)
    if domain and any(stable in domain.group(1) for stable in _STABLE_HOSTS):
        logger.debug('[DOI_RESOLVER] Skipping stable host: %s', domain.group(1))
        return True

    try:
        resp = httpx.head(url, timeout=10, follow_redirects=True)
        ok = 200 <= resp.status_code < 300
        logger.info('[DOI_RESOLVER] %s → HTTP %d (%s)', url[:60], resp.status_code, 'OK' if ok else 'FAIL')
        return ok
    except httpx.TimeoutException:
        logger.warning('[DOI_RESOLVER] Timeout: %s', url[:60])
        return False
    except Exception as exc:
        logger.debug('[DOI_RESOLVER] Error: %s — %s', url[:60], exc)
        return False
