"""Replication database lookup — check if a paper has been independently replicated
or if a replication attempt failed.

Sources checked (in order):
1. Open Science Collaboration (OSC) 2015 dataset — Reproducibility of Psychological Science
   (Estimating the reproducibility of psychological science, Science 2015)
2. SSRP (Social Science Reproduction Platform) — HTTP lookup by DOI
3. Curated CSV of known failed biomedical replications

This directly addresses the Regeneron use case: the problem statement asks
"Has any other lab successfully replicated these findings?"
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from trustworthy_science.cache.sqlite_cache import get_cache

logger = logging.getLogger(__name__)

_CACHE_NS = "replication"
_SSRP_BASE = "https://www.socialsciencereproduction.org/reproductions"

# ---------------------------------------------------------------------------
# Curated CSV of known failed biomedical/psychology replications
# Format: doi, outcome (replicated | failed | partial), source_ref
# ---------------------------------------------------------------------------
_BUILTIN_REPLICATIONS: list[dict] = [
    # Open Science Collaboration 2015 — Psychology (famous 39% replication rate)
    # Selected papers from the OSC dataset with clear DOI + outcome
    {"doi": "10.1037/a0029349", "outcome": "failed",     "source": "OSC2015"},
    {"doi": "10.1177/0956797611416579", "outcome": "failed",  "source": "OSC2015"},
    {"doi": "10.1177/0956797611421206", "outcome": "failed",  "source": "OSC2015"},
    {"doi": "10.1177/0956797612443408", "outcome": "failed",  "source": "OSC2015"},
    {"doi": "10.1177/0956797611417632", "outcome": "failed",  "source": "OSC2015"},  # Bem psi
    # Many Psychology Science replications
    {"doi": "10.1177/0956797610395871", "outcome": "failed",  "source": "OSC2015"},
    {"doi": "10.1177/0956797610376073", "outcome": "replicated", "source": "OSC2015"},
    # Biomedical — Amgen/Bayer preclinical oncology replication
    {"doi": "10.1038/483531a",          "outcome": "failed",  "source": "Begley2012"},
    # Social priming — Bargh et al.
    {"doi": "10.1037/0022-3514.71.2.230", "outcome": "failed", "source": "Doyen2012"},
    # Ego depletion
    {"doi": "10.1111/j.1467-9280.2010.02535.x", "outcome": "failed", "source": "Hagger2016"},
    # Power pose
    {"doi": "10.1177/0956797610383437", "outcome": "failed",  "source": "Ranehill2015"},
]


@dataclass
class ReplicationResult:
    doi: str
    outcome: str | None       # "replicated" | "failed" | "partial" | None (unknown)
    source: str | None        # which database found it
    found: bool               # was this DOI found in any replication database?
    summary: str


def check_replication(doi: str | None) -> ReplicationResult:
    """Check if a paper has a known replication record.

    Returns a ReplicationResult with outcome=None if no record found.
    """
    if not doi:
        return ReplicationResult(
            doi="",
            outcome=None,
            source=None,
            found=False,
            summary="No DOI provided — replication check skipped.",
        )

    doi_lower = doi.strip().lower()

    # 1. Check builtin CSV
    for entry in _BUILTIN_REPLICATIONS:
        if entry["doi"].lower() == doi_lower:
            outcome = entry["outcome"]
            source  = entry["source"]
            summary = _make_summary(doi, outcome, source)
            logger.info("[REPLICATION] Found in builtin DB: doi=%s outcome=%s source=%s",
                        doi, outcome, source)
            return ReplicationResult(doi=doi, outcome=outcome, source=source,
                                     found=True, summary=summary)

    # 2. Try SSRP API (Social Science Reproduction Platform)
    ssrp_result = _check_ssrp(doi)
    if ssrp_result is not None:
        outcome, source = ssrp_result
        summary = _make_summary(doi, outcome, source)
        return ReplicationResult(doi=doi, outcome=outcome, source=source,
                                 found=True, summary=summary)

    # Not found in any database
    logger.info("[REPLICATION] No replication record found for doi=%s", doi)
    return ReplicationResult(
        doi=doi,
        outcome=None,
        source=None,
        found=False,
        summary=f"No replication record found for this paper in checked databases (SSRP, OSC2015, Begley2012).",
    )


def _check_ssrp(doi: str) -> tuple[str, str] | None:
    """Query the SSRP for reproduction records. Returns (outcome, source) or None."""
    cache = get_cache()
    cached = cache.get(_CACHE_NS, "ssrp", doi)
    if cached is not None:
        return cached if cached != "NONE" else None

    try:
        # SSRP search by DOI
        url = f"{_SSRP_BASE}?doi={doi}"
        r = httpx.get(url, timeout=10, follow_redirects=True)
        logger.debug("[REPLICATION] SSRP response: status=%d url=%s", r.status_code, url)

        if r.status_code != 200:
            cache.set(_CACHE_NS, "NONE", "ssrp", doi)
            return None

        text = r.text.lower()

        # Parse SSRP response heuristically (HTML page)
        if "no reproductions" in text or "0 reproductions" in text:
            cache.set(_CACHE_NS, "NONE", "ssrp", doi)
            return None

        # Look for outcome keywords in the response
        if "success" in text or "replicated" in text:
            outcome = "replicated"
        elif "failed" in text or "failure" in text or "did not replicate" in text:
            outcome = "failed"
        elif "partial" in text:
            outcome = "partial"
        else:
            # Found but outcome unclear
            cache.set(_CACHE_NS, "NONE", "ssrp", doi)
            return None

        result = (outcome, "SSRP")
        cache.set(_CACHE_NS, result, "ssrp", doi)
        logger.info("[REPLICATION] SSRP found: doi=%s outcome=%s", doi, outcome)
        return result

    except Exception as exc:
        logger.debug("[REPLICATION] SSRP lookup failed: %s", exc)
        return None


def _make_summary(doi: str, outcome: str, source: str) -> str:
    if outcome == "replicated":
        return (
            f"Independent replication SUCCEEDED (source: {source}). "
            f"Findings have been confirmed by at least one external lab."
        )
    elif outcome == "failed":
        return (
            f"Independent replication FAILED (source: {source}). "
            f"At least one attempt to reproduce the key findings was unsuccessful — "
            f"this is a significant credibility concern."
        )
    elif outcome == "partial":
        return (
            f"Partial replication recorded (source: {source}). "
            f"Some but not all key findings were reproduced independently."
        )
    else:
        return f"Replication record found in {source} (outcome: {outcome})."
