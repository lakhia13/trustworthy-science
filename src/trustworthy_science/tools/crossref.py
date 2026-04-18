"""Crossref REST API tools — DOI metadata, funders, Crossmark/retraction signals."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from trustworthy_science.cache.sqlite_cache import get_cache
from trustworthy_science.state import PaperStub

logger = logging.getLogger(__name__)

_BASE = "https://api.crossref.org"
_CACHE_NS = "crossref"
_MAILTO = "trustworthy-science@example.com"  # polite pool


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
                logger.warning("Crossref GET failed: %s", exc)
                return {}
            time.sleep(2 ** attempt)
    return {}


def get_work(doi: str) -> dict[str, Any]:
    """Return the Crossref 'works' record for a DOI."""
    url = f"{_BASE}/works/{doi}"
    data = _get(url)
    return data.get("message", {})


def doi_to_stub(doi: str) -> PaperStub | None:
    """Build a PaperStub from Crossref metadata for a DOI."""
    work = get_work(doi)
    if not work:
        return None
    title_list = work.get("title", [])
    title = title_list[0] if title_list else ""
    authors = []
    for a in work.get("author", []):
        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
        if name:
            authors.append(name)
    container = work.get("container-title", [])
    venue = container[0] if container else ""
    issued = work.get("issued", {}).get("date-parts", [[None]])[0]
    year = issued[0] if issued else None
    issn_list = work.get("ISSN", [])
    issn = issn_list[0] if issn_list else None
    return PaperStub(
        doi=doi,
        title=title,
        authors=authors,
        venue=venue,
        issn=issn,
        year=year,
        source="crossref",
    )


def get_funders(doi: str) -> list[str]:
    """Return funder names for a DOI."""
    work = get_work(doi)
    return [f.get("name", "") for f in work.get("funder", []) if f.get("name")]


def get_submission_acceptance_days(doi: str) -> int | None:
    """Return days between submission and acceptance (from Crossref dates)."""
    work = get_work(doi)
    submitted = work.get("submitted", {}).get("date-parts", [[None]])[0]
    accepted = work.get("accepted", {}).get("date-parts", [[None]])[0]
    if submitted and accepted and submitted[0] and accepted[0]:
        from datetime import date
        try:
            d_sub = date(*submitted[:3])  # type: ignore[arg-type]
            d_acc = date(*accepted[:3])   # type: ignore[arg-type]
            return (d_acc - d_sub).days
        except Exception:
            pass
    return None


def check_crossmark_retraction(doi: str) -> bool:
    """Return True if Crossref Crossmark indicates this DOI has been retracted."""
    work = get_work(doi)
    update_to = work.get("update-to", [])
    for update in update_to:
        if "retract" in update.get("type", "").lower():
            return True
    # Also check `relation` field
    for rel_type, rels in work.get("relation", {}).items():
        if "retract" in rel_type.lower():
            return True
    return False


def search_crossref(query: str, max_results: int = 10) -> list[PaperStub]:
    """Full-text search via Crossref."""
    url = f"{_BASE}/works"
    params = {"query": query, "rows": max_results, "select": "DOI,title,author,container-title,issued,ISSN"}
    data = _get(url, params)
    stubs = []
    for item in data.get("message", {}).get("items", []):
        doi = item.get("DOI")
        if not doi:
            continue
        title_list = item.get("title", [])
        title = title_list[0] if title_list else ""
        authors = [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in item.get("author", [])
        ]
        container = item.get("container-title", [])
        venue = container[0] if container else ""
        issued = item.get("issued", {}).get("date-parts", [[None]])[0]
        year = issued[0] if issued else None
        stubs.append(PaperStub(doi=doi, title=title, authors=authors, venue=venue, year=year, source="crossref"))
    return stubs
