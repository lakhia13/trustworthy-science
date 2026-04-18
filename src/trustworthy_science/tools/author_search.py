"""Author-profile full-text retrieval via Semantic Scholar Open API."""

from __future__ import annotations

import logging

import httpx

from trustworthy_science.cache.sqlite_cache import get_cache
from trustworthy_science.tools.pdf_parse import pdf_bytes_to_text

logger = logging.getLogger(__name__)

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_CACHE_NS = "semantic_scholar"


def _s2_get(url: str, params: dict | None = None) -> dict:
    cache = get_cache()
    cached = cache.get(_CACHE_NS, url, **(params or {}))
    if cached is not None:
        return cached
    try:
        r = httpx.get(url, params=params, timeout=15,
                      headers={"User-Agent": "TrustworthyScience/0.1"})
        if r.status_code == 429:
            logger.debug("Semantic Scholar rate limited")
            return {}
        r.raise_for_status()
        data = r.json()
        cache.set(_CACHE_NS, data, url, **(params or {}))
        return data
    except Exception as exc:
        logger.debug("Semantic Scholar GET failed: %s", exc)
        return {}


def fetch_author_fulltext(doi: str) -> str:
    """Try to get full text for a paper via Semantic Scholar open-access links.

    Semantic Scholar indexes open-access PDFs hosted on author/institution pages,
    arXiv, and other repositories. This is a legal, public API — no scraping.

    Returns extracted plain text, or empty string if not available.
    """
    # Look up the paper by DOI
    url = f"{_S2_BASE}/paper/DOI:{doi}"
    params = {"fields": "externalIds,openAccessPdf,title"}
    data = _s2_get(url, params)
    if not data:
        return ""

    # Try the open-access PDF URL provided by Semantic Scholar
    oa = data.get("openAccessPdf") or {}
    pdf_url = oa.get("url")
    if pdf_url:
        text = _fetch_pdf(pdf_url)
        if text:
            logger.debug("Got Semantic Scholar OA PDF for DOI %s", doi)
            return text

    # Try arXiv if the paper has an arXiv ID
    arxiv_id = (data.get("externalIds") or {}).get("ArXiv")
    if arxiv_id:
        arxiv_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        text = _fetch_pdf(arxiv_url)
        if text:
            logger.debug("Got arXiv PDF for DOI %s (arXiv:%s)", doi, arxiv_id)
            return text

    return ""


def _fetch_pdf(url: str) -> str:
    """Download a URL and return extracted text if it's a PDF."""
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True)
        if r.status_code != 200:
            return ""
        ct = r.headers.get("content-type", "")
        if "pdf" in ct or url.lower().endswith(".pdf"):
            return pdf_bytes_to_text(r.content)
    except Exception as exc:
        logger.debug("PDF fetch failed for %s: %s", url, exc)
    return ""
