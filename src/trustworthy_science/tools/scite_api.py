"""scite.ai API client for citation context analysis."""
from __future__ import annotations
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / '.local' / 'share' / 'trustworthy_science'
_CACHE_TTL = 43200  # 12 hours


def _get_cache_db() -> sqlite3.Connection:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_CACHE_DIR / 'scite_cache.db')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS cache '
        '(key TEXT PRIMARY KEY, value TEXT, ts REAL)'
    )
    conn.commit()
    return conn


def get_citation_contexts(doi: str) -> dict | None:
    """Fetch citation tally and recent contexts from scite.ai."""
    if not doi:
        return None

    cache_key = f'scite:{doi}'
    try:
        conn = _get_cache_db()
        row = conn.execute('SELECT value, ts FROM cache WHERE key=?', (cache_key,)).fetchone()
        if row and (time.time() - row[1]) < _CACHE_TTL:
            return json.loads(row[0])
    except Exception:
        conn = None

    api_key = os.environ.get('SCITE_API_KEY')
    headers = {'Accept': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    # scite.ai paper tallies endpoint
    url = f'https://api.scite.ai/papers/{doi}'
    try:
        resp = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        if resp.status_code in (404, 422):
            logger.debug('[SCITE] Paper not found: %s', doi)
            return None
        if resp.status_code in (401, 403, 429):
            logger.warning('[SCITE] API limit/auth error for %s: HTTP %d', doi, resp.status_code)
            return None
        resp.raise_for_status()
        data = resp.json()

        tallies = data.get('tallies', {})
        supporting = int(tallies.get('supporting', 0))
        mentioning = int(tallies.get('mentioning', 0))
        contrasting = int(tallies.get('contrasting', 0))
        total = supporting + mentioning + contrasting

        # Get recent citation contexts (citations endpoint)
        recent_contexts: list[dict] = []
        try:
            ctx_url = f'https://api.scite.ai/citations?doi={doi}&limit=5'
            ctx_resp = httpx.get(ctx_url, headers=headers, timeout=8)
            if ctx_resp.status_code == 200:
                for cit in ctx_resp.json().get('citations', [])[:5]:
                    recent_contexts.append({
                        'type': cit.get('type', 'mentioning'),
                        'excerpt': cit.get('excerpt', '')[:300],
                        'citing_paper_title': cit.get('source_title', ''),
                    })
        except Exception:
            pass

        result = {
            'supporting': supporting,
            'mentioning': mentioning,
            'contrasting': contrasting,
            'total': total,
            'recent_contexts': recent_contexts,
        }

        # Cache
        try:
            if conn:
                conn.execute(
                    'INSERT OR REPLACE INTO cache VALUES (?,?,?)',
                    (cache_key, json.dumps(result), time.time())
                )
                conn.commit()
        except Exception:
            pass

        return result
    except httpx.TimeoutException:
        logger.warning('[SCITE] Timeout for %s', doi)
        return None
    except Exception as exc:
        logger.warning('[SCITE] Error for %s: %s', doi, exc)
        return None
