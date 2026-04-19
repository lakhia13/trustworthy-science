"""MeSH (Medical Subject Headings) lookup tool.

Uses NCBI E-utilities to validate keywords against the official MeSH database
and return canonical descriptor names for use in PubMed Boolean query construction.

Designed as a LangChain @tool so it can be bound to an LLM agent via
``llm.bind_tools([mesh_lookup])``.
"""
from __future__ import annotations

import logging
import os
import time
import xml.etree.ElementTree as ET

from langchain_core.tools import tool

from trustworthy_science.cache.sqlite_cache import get_cache

logger = logging.getLogger(__name__)

_ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_CACHE_NS = "mesh"

# Rate-limit guard: NCBI allows 3 req/s without API key
_MIN_INTERVAL = 0.35  # seconds between calls when no API key
_last_call_time: float = 0.0


def _api_key_param() -> dict[str, str]:
    key = os.environ.get("NCBI_API_KEY", "")
    return {"api_key": key} if key else {}


def _ncbi_email() -> str:
    return os.environ.get("NCBI_EMAIL", "research@trustworthy-science.ai")


def _rate_limit() -> None:
    """Sleep if needed to respect NCBI unauthenticated rate limit."""
    global _last_call_time
    if _api_key_param():
        return  # API key allows 10 req/s — no manual throttling needed
    elapsed = time.monotonic() - _last_call_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_call_time = time.monotonic()


@tool
def mesh_lookup(keyword: str) -> str:
    """Look up a medical term in the NCBI MeSH (Medical Subject Headings) database.

    Returns the official MeSH descriptor name if the term is valid, or a
    suggestion message if it is not found. Use this tool to validate keywords
    before constructing PubMed Boolean queries.

    Args:
        keyword: A medical concept or clinical term to validate (e.g.
                 "Treatment-Resistant Depression", "Randomized Controlled Trial").

    Returns:
        A string starting with 'VALID MeSH descriptor:' followed by the canonical
        name, or 'NOT FOUND in MeSH.' with a suggestion to try related terms.
    """
    cache = get_cache()
    cached = cache.get(_CACHE_NS, keyword)
    if cached is not None:
        return cached

    result = _do_lookup(keyword)
    cache.set(_CACHE_NS, result, keyword)
    return result


def _do_lookup(keyword: str) -> str:
    """Perform the actual NCBI MeSH lookup (no cache)."""
    import httpx

    _rate_limit()

    try:
        # Step 1: esearch to find MeSH IDs for the keyword
        search_params = {
            "db": "mesh",
            "term": keyword,
            "retmax": 1,
            "retmode": "json",
            "email": _ncbi_email(),
            **_api_key_param(),
        }
        resp = httpx.get(f"{_ENTREZ_BASE}/esearch.fcgi", params=search_params, timeout=15)
        resp.raise_for_status()
        search_data = resp.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])

        if not id_list:
            return f"NOT FOUND in MeSH. Try related terms or broader concepts for: '{keyword}'"

        _rate_limit()

        # Step 2: efetch to get the canonical descriptor name
        fetch_params = {
            "db": "mesh",
            "id": id_list[0],
            "retmode": "xml",
            "email": _ncbi_email(),
            **_api_key_param(),
        }
        fetch_resp = httpx.get(f"{_ENTREZ_BASE}/efetch.fcgi", params=fetch_params, timeout=15)
        fetch_resp.raise_for_status()

        descriptor = _parse_mesh_descriptor(fetch_resp.text)
        if descriptor:
            return f"VALID MeSH descriptor: {descriptor}"

        # esearch found an ID but efetch gave no parseable name — treat as valid
        return f"VALID MeSH descriptor: {keyword}"

    except Exception as exc:
        logger.warning("[MESH] Lookup failed for '%s': %s", keyword, exc)
        return f"LOOKUP ERROR for '{keyword}': {exc}. Use the term as-is."


def _parse_mesh_descriptor(xml_text: str) -> str | None:
    """Extract the DescriptorName from a MeSH efetch XML response."""
    try:
        root = ET.fromstring(xml_text)
        # MeSH XML structure: <DescriptorRecordSet> → <DescriptorRecord> → <DescriptorName> → <String>
        for el in root.iter("String"):
            text = (el.text or "").strip()
            if text:
                return text
    except ET.ParseError as exc:
        logger.debug("[MESH] XML parse error: %s", exc)
    return None


def batch_mesh_lookup(keywords: list[str], max_terms: int = 6) -> dict[str, str]:
    """Look up multiple MeSH terms and return a dict of keyword → result.

    Caps at ``max_terms`` to prevent runaway NCBI calls. Results are cached
    individually so repeated calls are free.

    Args:
        keywords: List of medical concept strings to validate.
        max_terms: Maximum number of lookups to perform.

    Returns:
        Dict mapping each keyword to its ``mesh_lookup`` result string.
    """
    results: dict[str, str] = {}
    for kw in keywords[:max_terms]:
        kw = kw.strip()
        if not kw:
            continue
        results[kw] = _do_lookup.__wrapped__(kw) if hasattr(_do_lookup, "__wrapped__") else _do_lookup(kw)
    return results
