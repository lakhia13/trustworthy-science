"""Unpaywall API — find free legal copies of paywalled papers."""

from __future__ import annotations

import logging
import os

import httpx

from trustworthy_science.cache.sqlite_cache import get_cache
from trustworthy_science.tools.pdf_parse import pdf_bytes_to_text

logger = logging.getLogger(__name__)

_BASE = "https://api.unpaywall.org/v2"
_CACHE_NS = "unpaywall"
# Unpaywall requires an email for their polite pool
_EMAIL = os.environ.get("UNPAYWALL_EMAIL", "trustworthy-science@example.com")


def _get_unpaywall_record(doi: str) -> dict:
    """Fetch the Unpaywall record for a DOI (cached)."""
    cache = get_cache()
    cached = cache.get(_CACHE_NS, doi)
    if cached is not None:
        return cached
    url = f"{_BASE}/{doi}"
    try:
        r = httpx.get(url, params={"email": _EMAIL}, timeout=15)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        data = r.json()
        cache.set(_CACHE_NS, data, doi)
        return data
    except Exception as exc:
        logger.debug("Unpaywall record fetch failed for %s: %s", doi, exc)
        return {}


def fetch_unpaywall_fulltext(doi: str) -> str:
    """Try to get full text for a DOI via Unpaywall's free OA locations.

    Tries open-access locations in priority order:
    1. Publisher HTML/PDF (best_oa_location)
    2. Repository PDFs (institutional repos, PubMed Central, etc.)

    Returns extracted plain text, or empty string if nothing found.
    """
    record = _get_unpaywall_record(doi)
    if not record or not record.get("is_oa"):
        logger.debug("No OA version found via Unpaywall for %s", doi)
        return ""

    # Collect candidate URLs in priority order
    candidates: list[str] = []

    best = record.get("best_oa_location") or {}
    for field in ("url_for_pdf", "url"):
        val = best.get(field)
        if val:
            candidates.append(val)

    for loc in record.get("oa_locations", []):
        for field in ("url_for_pdf", "url"):
            val = loc.get(field)
            if val and val not in candidates:
                candidates.append(val)

    for url in candidates:
        try:
            r = httpx.get(url, timeout=30, follow_redirects=True)
            if r.status_code != 200:
                continue
            ct = r.headers.get("content-type", "")
            if "pdf" in ct or url.lower().endswith(".pdf"):
                text = pdf_bytes_to_text(r.content)
            else:
                # HTML page — strip tags
                import re
                text = re.sub(r"<[^>]+>", " ", r.text)
                text = re.sub(r"\s+", " ", text).strip()
            if len(text) > 500:
                logger.debug("Got Unpaywall full text for %s via %s", doi, url)
                return text
        except Exception as exc:
            logger.debug("Unpaywall URL fetch failed (%s): %s", url, exc)

    return ""
