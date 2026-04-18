"""bioRxiv / medRxiv preprint server API tools."""

from __future__ import annotations

import logging
import time

import httpx

from trustworthy_science.cache.sqlite_cache import get_cache
from trustworthy_science.state import PaperStub

logger = logging.getLogger(__name__)

_BASE = "https://api.biorxiv.org"
_CACHE_NS = "biorxiv"


def _get_json(url: str) -> dict:
    cache = get_cache()
    cached = cache.get(_CACHE_NS, url)
    if cached is not None:
        return cached
    for attempt in range(3):
        try:
            r = httpx.get(url, timeout=20)
            r.raise_for_status()
            data = r.json()
            cache.set(_CACHE_NS, data, url)
            return data
        except Exception as exc:
            if attempt == 2:
                logger.warning("bioRxiv GET failed: %s", exc)
                return {}
            time.sleep(2 ** attempt)
    return {}


def search_biorxiv(query: str, max_results: int = 10) -> list[PaperStub]:
    """Search bioRxiv for *query* and return PaperStub list."""
    # bioRxiv doesn't have a free-text search endpoint in their REST API;
    # we use the details endpoint via cursor-based listing as a fallback
    # and the published/preprint mapping for DOI lookup.
    # For MVP, we use the Crossref/Europe PMC full-text search as a proxy.
    url = f"https://api.europepmc.org/EUROPEPMC/webservices/rest/search?query={query}+source%3APPR&format=json&pageSize={max_results}"
    try:
        r = httpx.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.warning("bioRxiv/EuropePMC search failed: %s", exc)
        return []

    stubs = []
    for result in data.get("resultList", {}).get("result", []):
        doi = result.get("doi")
        stubs.append(
            PaperStub(
                doi=doi,
                title=result.get("title", ""),
                authors=[a.get("fullName", "") for a in result.get("authorList", {}).get("author", [])],
                venue=result.get("journalTitle", "bioRxiv/medRxiv"),
                year=int(result.get("pubYear", 0)) or None,
                abstract=result.get("abstractText", ""),
                source="biorxiv",
            )
        )
    return stubs[:max_results]


def fetch_biorxiv_by_doi(doi: str) -> PaperStub | None:
    """Fetch preprint metadata from bioRxiv by DOI."""
    url = f"{_BASE}/details/biorxiv/{doi}/na/json"
    data = _get_json(url)
    collection = data.get("collection", [])
    if not collection:
        # try medrxiv
        url2 = f"{_BASE}/details/medrxiv/{doi}/na/json"
        data2 = _get_json(url2)
        collection = data2.get("collection", [])
    if not collection:
        return None
    rec = collection[-1]  # most recent version
    return PaperStub(
        doi=rec.get("doi"),
        title=rec.get("title", ""),
        authors=rec.get("authors", "").split("; "),
        venue=rec.get("server", "bioRxiv"),
        year=int(rec.get("date", "0")[:4]) if rec.get("date") else None,
        abstract=rec.get("abstract", ""),
        pdf_url=f"https://www.biorxiv.org/content/{rec.get('doi')}.full.pdf",
        source="biorxiv",
    )
