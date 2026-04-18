"""Retraction Watch database lookup via local CSV mirror + Crossref Crossmark."""

from __future__ import annotations

import csv
import io
import logging
import os
from pathlib import Path

import httpx

from trustworthy_science.cache.sqlite_cache import get_cache

logger = logging.getLogger(__name__)

_CACHE_NS = "retraction_watch"
# The Retraction Watch CSV is hosted by the CrossRef / COPE partnership.
# URL subject to change; we cache it aggressively (TTL = 24h effectively from SQLiteCache default).
_RW_CSV_URL = "https://api.labs.crossref.org/data/retractionwatch?email=trustworthy-science@example.com"
_LOCAL_CSV = Path(os.environ.get("RW_CSV_PATH", "")) if os.environ.get("RW_CSV_PATH") else None

_rw_index: dict[str, dict] | None = None  # doi -> record


def _load_rw_index() -> dict[str, dict]:
    """Load Retraction Watch CSV into an in-memory dict keyed by DOI (lowercase)."""
    global _rw_index
    if _rw_index is not None:
        return _rw_index

    cache = get_cache()
    cached = cache.get(_CACHE_NS, "csv_index")
    if cached is not None:
        _rw_index = cached
        return _rw_index

    # Try local file first
    if _LOCAL_CSV and _LOCAL_CSV.exists():
        text = _LOCAL_CSV.read_text(encoding="utf-8", errors="replace")
    else:
        try:
            r = httpx.get(_RW_CSV_URL, timeout=30, follow_redirects=True)
            r.raise_for_status()
            text = r.text
        except Exception as exc:
            logger.warning("Could not load Retraction Watch CSV: %s", exc)
            _rw_index = {}
            return _rw_index

    index: dict[str, dict] = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        doi = (row.get("OriginalPaperDOI") or row.get("DOI") or "").strip().lower()
        if doi:
            index[doi] = row
    cache.set(_CACHE_NS, index, "csv_index")
    _rw_index = index
    logger.info("Loaded %d Retraction Watch records", len(index))
    return _rw_index


def is_retracted(doi: str) -> tuple[bool, dict | None]:
    """Return (is_retracted, record_or_None) for the given DOI."""
    if not doi:
        return False, None
    doi_lower = doi.strip().lower()
    # 1. Crossref Crossmark (fast, real-time)
    from trustworthy_science.tools.crossref import check_crossmark_retraction
    try:
        if check_crossmark_retraction(doi):
            return True, {"source": "crossref_crossmark", "doi": doi}
    except Exception as exc:
        logger.debug("Crossmark check failed: %s", exc)

    # 2. Retraction Watch CSV
    index = _load_rw_index()
    record = index.get(doi_lower)
    if record:
        return True, record
    return False, None
