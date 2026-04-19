"""Beall's List crosscheck tool — identifies predatory publishers and journals.

Primary source: live scrape of https://beallslist.net (cached for 7 days).
Fallback: bundled config/bealls_known.csv (used when scraping fails or is unavailable).

Exposed API
-----------
is_on_bealls_list(venue_name: str) -> bool
    Return True if the venue name matches any Beall's List entry.
reload_bealls_cache() -> int
    Force a fresh scrape and return the number of entries loaded.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import sqlite3
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

_CACHE_DIR = Path.home() / ".local" / "share" / "trustworthy_science"
_BEALLS_DB = _CACHE_DIR / "bealls_cache.db"
_FALLBACK_CSV = Path(__file__).parent.parent.parent.parent / "config" / "bealls_known.csv"

_SCRAPE_URL = "https://beallslist.net"
_CACHE_NS = "bealls_entries"
_CACHE_TTL = 7 * 24 * 3600  # 7 days

# Minimum character length for a token to be used in fuzzy matching
# (avoids false positives from short common words like "of", "the", "and")
_MIN_TOKEN_LEN = 5

# Known-legitimate publishers — never flag these even if a token matches
_WHITELIST = frozenset([
    "nature", "science", "cell", "lancet", "plos", "elsevier", "springer",
    "wiley", "oxford", "cambridge", "taylor", "routledge", "sage", "karger",
    "biomed central", "bmc", "frontiers", "mdpi", "pubmed", "pubmed central",
    "pmc", "nejm", "jama", "bmj", "annals", "jci", "embo", "asm", "acs",
    "royal society", "american chemical society", "american physical society",
    "american heart association", "american cancer society",
])


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_db() -> sqlite3.Connection:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_BEALLS_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache "
        "(key TEXT PRIMARY KEY, value TEXT, ts REAL)"
    )
    conn.commit()
    return conn


def _cache_get(key: str) -> list[str] | None:
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT value, ts FROM cache WHERE key=?", (key,)
        ).fetchone()
        if row and (time.time() - row[1]) < _CACHE_TTL:
            return json.loads(row[0])
    except Exception as exc:
        logger.debug("[BEALLS] Cache read error: %s", exc)
    return None


def _cache_set(key: str, entries: list[str]) -> None:
    try:
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO cache VALUES (?,?,?)",
            (key, json.dumps(entries), time.time()),
        )
        conn.commit()
    except Exception as exc:
        logger.debug("[BEALLS] Cache write error: %s", exc)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase, strip punctuation/extra whitespace for fuzzy comparison."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _meaningful_tokens(text: str) -> list[str]:
    """Return tokens of sufficient length, excluding stop words."""
    stop = {"international", "journal", "research", "science", "sciences",
            "open", "access", "review", "medical", "academic", "global",
            "advanced", "applied", "studies", "technology", "engineering",
            "management", "business", "social"}
    return [t for t in _normalise(text).split()
            if len(t) >= _MIN_TOKEN_LEN and t not in stop]


# ---------------------------------------------------------------------------
# Loading functions
# ---------------------------------------------------------------------------

def _load_from_csv() -> list[str]:
    """Load the bundled fallback CSV and return a list of normalised names."""
    entries: list[str] = []
    if not _FALLBACK_CSV.exists():
        logger.warning("[BEALLS] Fallback CSV not found at %s", _FALLBACK_CSV)
        return entries
    try:
        with open(_FALLBACK_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").strip()
                if name:
                    entries.append(_normalise(name))
        logger.info("[BEALLS] Loaded %d entries from fallback CSV", len(entries))
    except Exception as exc:
        logger.warning("[BEALLS] Failed to load fallback CSV: %s", exc)
    return entries


def _scrape_bealls() -> list[str]:
    """Scrape beallslist.net and return normalised publisher/journal names."""
    entries: list[str] = []
    try:
        resp = httpx.get(_SCRAPE_URL, timeout=15, follow_redirects=True,
                         headers={"User-Agent": "TrustworthyScience/0.1 research-tool"})
        if resp.status_code != 200:
            logger.warning("[BEALLS] Scrape failed: HTTP %d", resp.status_code)
            return entries

        # Extract list items — Beall's List uses <li> elements in <ul>/<ol> blocks
        # Look for <li> tags that contain substantial text (>= 5 chars) and are
        # not navigation/UI elements (no class, or class contains "list-item")
        li_pattern = re.compile(r"<li[^>]*>(.*?)</li>", re.DOTALL | re.IGNORECASE)
        tag_strip = re.compile(r"<[^>]+>")

        for m in li_pattern.finditer(resp.text):
            raw = tag_strip.sub("", m.group(1)).strip()
            # Filter out nav/short items
            if len(raw) >= 8 and not raw.startswith("©") and "\n" not in raw[:50]:
                entries.append(_normalise(raw[:200]))

        logger.info("[BEALLS] Scraped %d candidate entries from beallslist.net", len(entries))

    except httpx.TimeoutException:
        logger.warning("[BEALLS] Scrape timed out")
    except Exception as exc:
        logger.warning("[BEALLS] Scrape error: %s", exc)

    return entries


def _get_entries() -> list[str]:
    """Return the cached Beall's List entries, loading/scraping as needed."""
    cached = _cache_get(_CACHE_NS)
    if cached is not None:
        return cached

    # Try live scrape first
    scraped = _scrape_bealls()
    if len(scraped) >= 50:  # sanity check — real list has 400+ entries
        combined = list(set(scraped + _load_from_csv()))
        _cache_set(_CACHE_NS, combined)
        logger.info("[BEALLS] Using scraped list (%d entries)", len(combined))
        return combined

    # Fall back to bundled CSV
    csv_entries = _load_from_csv()
    if csv_entries:
        _cache_set(_CACHE_NS, csv_entries)
    return csv_entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_on_bealls_list(venue_name: str) -> bool:
    """Return True if venue_name matches any Beall's List entry.

    Uses token-level fuzzy matching: both the query and each entry are
    normalised and split into meaningful tokens; a match is declared when
    two or more meaningful tokens overlap with a single Beall's entry,
    OR when the entire normalised venue string is a substring of an entry
    (or vice versa).

    Whitelisted legitimate publishers always return False.
    """
    if not venue_name or not venue_name.strip():
        return False

    norm_venue = _normalise(venue_name)

    # Whitelist check first
    for w in _WHITELIST:
        if w in norm_venue:
            logger.debug("[BEALLS] Venue '%s' is whitelisted (%s)", venue_name, w)
            return False

    venue_tokens = set(_meaningful_tokens(venue_name))
    if not venue_tokens:
        return False

    entries = _get_entries()

    for entry in entries:
        # Exact substring match (either direction)
        if norm_venue in entry or entry in norm_venue:
            logger.info("[BEALLS] Match (substring): '%s' ~ '%s'", venue_name, entry)
            return True

        # Token overlap — require at least 2 meaningful tokens to match
        entry_tokens = set(_meaningful_tokens(entry))
        common = venue_tokens & entry_tokens
        if len(common) >= 2:
            logger.info("[BEALLS] Match (tokens %s): '%s' ~ '%s'",
                        common, venue_name, entry)
            return True

    return False


def reload_bealls_cache() -> int:
    """Force a fresh scrape of Beall's List and return the number of entries loaded."""
    # Invalidate existing cache
    try:
        conn = _get_db()
        conn.execute("DELETE FROM cache WHERE key=?", (_CACHE_NS,))
        conn.commit()
    except Exception:
        pass

    entries = _get_entries()
    logger.info("[BEALLS] Cache reloaded: %d entries", len(entries))
    return len(entries)
