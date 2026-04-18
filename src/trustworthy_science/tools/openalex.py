"""OpenAlex API tools — citations, author h-index, institution diversity."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from trustworthy_science.cache.sqlite_cache import get_cache

logger = logging.getLogger(__name__)

_BASE = "https://api.openalex.org"
_CACHE_NS = "openalex"
_MAILTO = "trustworthy-science@example.com"


def _get(url: str, params: dict | None = None) -> dict:
    cache = get_cache()
    cached = cache.get(_CACHE_NS, url, **(params or {}))
    if cached is not None:
        return cached
    headers = {"User-Agent": f"TrustworthyScience/0.1 (mailto:{_MAILTO})"}
    for attempt in range(3):
        try:
            r = httpx.get(url, params=params, headers=headers, timeout=20)
            r.raise_for_status()
            data = r.json()
            cache.set(_CACHE_NS, data, url, **(params or {}))
            return data
        except Exception as exc:
            if attempt == 2:
                logger.warning("OpenAlex GET failed: %s", exc)
                return {}
            time.sleep(2 ** attempt)
    return {}


# ---------------------------------------------------------------------------
# Works
# ---------------------------------------------------------------------------

def get_work_by_doi(doi: str) -> dict[str, Any]:
    """Return OpenAlex work record for a DOI."""
    url = f"{_BASE}/works/doi:{doi}"
    return _get(url)


def get_citations(doi: str, max_results: int = 200) -> list[dict[str, Any]]:
    """Return works that cite the given DOI."""
    work = get_work_by_doi(doi)
    openalex_id = work.get("id", "")
    if not openalex_id:
        return []
    url = f"{_BASE}/works"
    params = {
        "filter": f"cites:{openalex_id.split('/')[-1]}",
        "per-page": min(max_results, 200),
        "select": "id,doi,authorships,institutions,publication_year",
        "mailto": _MAILTO,
    }
    data = _get(url, params)
    return data.get("results", [])


def citation_diversity_score(doi: str) -> tuple[float, int, float]:
    """Return (institutional_diversity_ratio, total_citations, self_citation_ratio).

    institutional_diversity_ratio: unique institutions / total citing works (capped at 1)
    self_citation_ratio: works where >=1 author overlaps with original / total citing works
    """
    work = get_work_by_doi(doi)
    original_authors = set()
    for auth in work.get("authorships", []):
        a_id = auth.get("author", {}).get("id", "")
        if a_id:
            original_authors.add(a_id)

    citing = get_citations(doi)
    if not citing:
        return 0.0, 0, 0.0

    institutions: set[str] = set()
    self_cite_count = 0
    for c in citing:
        for auth in c.get("authorships", []):
            for inst in auth.get("institutions", []):
                inst_id = inst.get("id", "")
                if inst_id:
                    institutions.add(inst_id)
            a_id = auth.get("author", {}).get("id", "")
            if a_id and a_id in original_authors:
                self_cite_count += 1
                break  # count paper once

    n = len(citing)
    diversity = min(len(institutions) / n, 1.0) if n else 0.0
    self_ratio = self_cite_count / n if n else 0.0
    return diversity, n, self_ratio


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------

def get_author(name_or_orcid: str) -> dict[str, Any]:
    """Look up an OpenAlex author by display name or ORCID."""
    if name_or_orcid.startswith("0000-"):
        url = f"{_BASE}/authors/orcid:{name_or_orcid}"
    else:
        url = f"{_BASE}/authors"
        params = {"search": name_or_orcid, "per-page": 1}
        data = _get(url, params)
        results = data.get("results", [])
        return results[0] if results else {}
    return _get(url)


def get_author_h_index(name_or_orcid: str) -> int | None:
    """Return h-index for an author (or None if not found)."""
    author = get_author(name_or_orcid)
    summary = author.get("summary_stats", {})
    return summary.get("h_index")


# ---------------------------------------------------------------------------
# Venues / journals
# ---------------------------------------------------------------------------

def get_venue_by_issn(issn: str) -> dict[str, Any]:
    url = f"{_BASE}/sources"
    params = {"filter": f"issn:{issn}", "per-page": 1}
    data = _get(url, params)
    results = data.get("results", [])
    return results[0] if results else {}


def search_openalex(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Free-text search of OpenAlex works."""
    url = f"{_BASE}/works"
    params = {
        "search": query,
        "per-page": min(max_results, 25),
        "select": "id,doi,title,authorships,publication_year,host_venue,abstract_inverted_index",
        "mailto": _MAILTO,
    }
    data = _get(url, params)
    return data.get("results", [])
