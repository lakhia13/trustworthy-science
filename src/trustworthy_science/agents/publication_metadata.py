"""Publication Metadata agent — venue reputation, review speed, predatory journal check."""

from __future__ import annotations

import logging
import re
import time

import httpx

from trustworthy_science.cache.sqlite_cache import get_cache
from trustworthy_science.state import EvidenceQuote, Flag, PaperState, SubScore
from trustworthy_science.tools.crossref import get_submission_acceptance_days, get_work

logger = logging.getLogger(__name__)

_CACHE_NS = "pub_meta"
_FAST_REVIEW_DAYS = 14  # < 14 days submission → acceptance is suspicious

# DOAJ API (free, no auth)
_DOAJ_URL = "https://doaj.org/api/search/journals/{issn}"


def _check_doaj(issn: str) -> bool | None:
    """Return True if ISSN is in DOAJ (open, legitimate), False if not, None if unknown."""
    if not issn:
        return None
    cache = get_cache()
    cached = cache.get(_CACHE_NS, "doaj", issn)
    if cached is not None:
        return cached
    try:
        r = httpx.get(_DOAJ_URL.format(issn=issn.replace("-", "")), timeout=15)
        result = r.status_code == 200 and r.json().get("total", 0) > 0
        cache.set(_CACHE_NS, result, "doaj", issn)
        return result
    except Exception as exc:
        logger.debug("DOAJ check failed: %s", exc)
        return None


def _check_bealls(venue_name: str) -> bool:
    """Heuristic check: search Beall's List known patterns (static keyword list for MVP)."""
    # Full integration would parse the archived Beall's List page.
    # For MVP: flag journals whose names match common predatory patterns.
    suspicious_keywords = [
        "OMICS", "SCIRP", "Hindawi",  # known problematic publishers
        "International Journal of Advanced Research",
        "Global Journal",
        "American Journal of.*Sciences",
    ]
    venue_lower = venue_name.lower()
    for kw in suspicious_keywords:
        if re.search(kw, venue_name, re.IGNORECASE):
            return True
    return False


def publication_metadata_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: evaluate venue reputation and peer-review process speed."""
    hard_flags: list[Flag] = []
    soft_flags: list[Flag] = []
    quality_signals: list[Flag] = []

    stub = state.stub
    issn = stub.issn
    venue = stub.venue or ""
    doi = stub.doi or ""

    # --- Venue reputation ---
    in_doaj = _check_doaj(issn) if issn else None
    is_predatory = _check_bealls(venue)

    if is_predatory:
        f = Flag(
            tier="hard",
            code="PREDATORY_VENUE",
            message=f"Venue '{venue}' matches known predatory publisher patterns.",
            source_agent="publication_metadata",
            evidence=[EvidenceQuote(text=venue, section="metadata")],
        )
        hard_flags.append(f)
    elif in_doaj is True:
        q = Flag(
            tier="quality",
            code="HIGH_IMPACT_VENUE",
            message=f"Journal '{venue}' is indexed in DOAJ (legitimate open-access).",
            source_agent="publication_metadata",
        )
        quality_signals.append(q)
    elif in_doaj is False:
        f = Flag(
            tier="soft",
            code="VENUE_NOT_IN_DOAJ",
            message=f"Journal '{venue}' (ISSN: {issn}) is not in DOAJ. May be paywalled, unclear, or predatory.",
            source_agent="publication_metadata",
        )
        soft_flags.append(f)

    # --- Review speed ---
    review_days = None
    if doi:
        try:
            review_days = get_submission_acceptance_days(doi)
        except Exception as exc:
            logger.debug("Review days lookup failed: %s", exc)

    if review_days is not None and 0 < review_days < _FAST_REVIEW_DAYS:
        f = Flag(
            tier="soft",
            code="FAST_PEER_REVIEW",
            message=f"Peer review completed in {review_days} days (< {_FAST_REVIEW_DAYS} days threshold). May indicate rubber-stamp review.",
            source_agent="publication_metadata",
            evidence=[EvidenceQuote(text=f"Review time: {review_days} days", section="metadata")],
        )
        soft_flags.append(f)

    # --- COI disclosure ---
    coi_text = ""
    if state.parsed:
        coi_text = state.parsed.coi_statement or ""
    if coi_text.strip():
        q = Flag(
            tier="quality",
            code="COI_DISCLOSED",
            message="Conflict of interest statement is present.",
            source_agent="publication_metadata",
        )
        quality_signals.append(q)

        # Check for industry-only funding without COI
        funding = (state.parsed.funding if state.parsed else "") or ""
        industry_terms = r"(pharma|biotech|genentech|pfizer|novartis|amgen|roche|industry|company|corporate|grant\s+from)"
        if re.search(industry_terms, funding + " " + coi_text, re.IGNORECASE):
            independent_terms = r"(no\s+conflict|none|independent|NIH|NSF|Wellcome|MRC|government|university|foundation)"
            if not re.search(independent_terms, coi_text, re.IGNORECASE):
                f = Flag(
                    tier="soft",
                    code="INDUSTRY_ONLY_FUNDING_NO_COI",
                    message="Industry funding detected; no independent funding or COI disclaimer evident.",
                    source_agent="publication_metadata",
                )
                soft_flags.append(f)

    # Compute sub-score
    score = 0.70
    if hard_flags:
        score = 0.10
    else:
        score -= len(soft_flags) * 0.08
        score += len(quality_signals) * 0.08
    score = max(0.0, min(1.0, score))

    all_flags = hard_flags + soft_flags + quality_signals
    sub = SubScore(
        score=score,
        confidence=0.70,
        flags=all_flags,
        notes=f"Venue: {venue}. DOAJ: {in_doaj}. Review days: {review_days}.",
    )

    return {
        "sub_scores": {"publication_metadata": sub},
        "hard_flags": hard_flags,
        "soft_flags": soft_flags,
        "quality_signals": quality_signals,
    }
