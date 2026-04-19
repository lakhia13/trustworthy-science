"""GitHub REST API client for repository health checks."""
from __future__ import annotations
import logging
import os
import re
import sqlite3
import json
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_CACHE_DIR = Path.home() / '.local' / 'share' / 'trustworthy_science'
_CACHE_TTL = 86400  # 24 hours

_GITHUB_URL_RE = re.compile(
    r'github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)',
    re.IGNORECASE,
)


def _get_cache_db() -> sqlite3.Connection:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_CACHE_DIR / 'github_cache.db')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS cache '
        '(key TEXT PRIMARY KEY, value TEXT, ts REAL)'
    )
    conn.commit()
    return conn


def extract_github_owner_repo(url: str) -> tuple[str, str] | None:
    m = _GITHUB_URL_RE.search(url)
    if m:
        return m.group(1), m.group(2)
    return None


def get_repo_health(github_url: str) -> dict | None:
    parsed = extract_github_owner_repo(github_url)
    if not parsed:
        return None
    owner, repo = parsed
    cache_key = f'github_repo:{owner}/{repo}'

    # Check cache
    try:
        conn = _get_cache_db()
        row = conn.execute('SELECT value, ts FROM cache WHERE key=?', (cache_key,)).fetchone()
        if row and (time.time() - row[1]) < _CACHE_TTL:
            return json.loads(row[0])
    except Exception:
        conn = None

    token = os.environ.get('GITHUB_TOKEN')
    headers = {'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'

    api_url = f'https://api.github.com/repos/{owner}/{repo}'
    try:
        resp = httpx.get(api_url, headers=headers, timeout=10, follow_redirects=True)
        if resp.status_code in (403, 429):
            logger.warning('[GITHUB] Rate limited for %s/%s', owner, repo)
            return None
        if resp.status_code == 404:
            logger.info('[GITHUB] Repo not found: %s/%s', owner, repo)
            return None
        resp.raise_for_status()
        data = resp.json()
        result = {
            'stars': data.get('stargazers_count', 0),
            'open_issues': data.get('open_issues_count', 0),
            'last_push': data.get('pushed_at', ''),
            'has_readme': True,  # assume True; README check via raw URL
            'archived': data.get('archived', False),
            'size_kb': data.get('size', 0),
            'default_branch': data.get('default_branch', 'main'),
        }
        # Cache result
        try:
            if conn is None:
                conn = _get_cache_db()
            conn.execute(
                'INSERT OR REPLACE INTO cache VALUES (?,?,?)',
                (cache_key, json.dumps(result), time.time())
            )
            conn.commit()
        except Exception:
            pass
        return result
    except httpx.TimeoutException:
        logger.warning('[GITHUB] Timeout for %s/%s', owner, repo)
        return None
    except Exception as exc:
        logger.warning('[GITHUB] Error for %s/%s: %s', owner, repo, exc)
        return None


def fetch_readme(owner: str, repo: str, branch: str = 'main') -> str | None:
    """Fetch raw README content."""
    for branch_try in [branch, 'master']:
        url = f'https://raw.githubusercontent.com/{owner}/{repo}/{branch_try}/README.md'
        try:
            resp = httpx.get(url, timeout=8, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text[:3000]
        except Exception:
            pass
    return None
