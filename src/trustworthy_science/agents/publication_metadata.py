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

    # --- COI disclosure & funding source analysis ---
    coi_text = ""
    funding_text = ""
    if state.parsed:
        coi_text    = state.parsed.coi_statement or ""
        funding_text = state.parsed.funding or ""

    combined_text = f"{funding_text} {coi_text}".strip()

    # Named industry funders — more specific than generic "industry" pattern
    _INDUSTRY_FUNDERS = [
        "Pfizer", "Merck", "AstraZeneca", "Novartis", "Roche", "Johnson & Johnson",
        "J&J", "GSK", "GlaxoSmithKline", "Eli Lilly", "Sanofi", "Bayer", "Gilead",
        "Amgen", "AbbVie", "Bristol.Myers", "BMS", "Biogen", "Genentech",
        "Regeneron", "Moderna", "Boehringer", "Takeda", "Astellas",
        r"\bpharma(?:ceutical)?\b", r"\bbiotech\b",
        r"\bindustry\s+(?:funded|grant|support)\b",
        r"\bcorporate\s+(?:funded|grant|sponsor)\b",
        r"\bgrant\s+from\s+[A-Z]",   # "grant from Pfizer" etc.
    ]
    _INDEPENDENT_TERMS = re.compile(
        r"(no\s+conflict|none\s+declared|no\s+competing|no\s+financial|"
        r"independent|NIH|NSF|Wellcome|MRC|UKRI|government|university|"
        r"foundation|charitable|non.profit|public\s+funding|NCI|NHLBI|"
        r"European\s+Research|Horizon\s+2020|CIHR)",
        re.IGNORECASE,
    )

    # Find which industry funders are named
    found_funders: list[str] = []
    for pattern in _INDUSTRY_FUNDERS:
        m = re.search(pattern, combined_text, re.IGNORECASE)
        if m:
            found_funders.append(m.group(0))

    has_industry_funding = len(found_funders) > 0
    has_independent      = bool(_INDEPENDENT_TERMS.search(coi_text)) if coi_text else False
    has_coi_statement    = bool(coi_text.strip())

    if has_coi_statement:
        funder_detail = f" Funders identified: {', '.join(set(found_funders[:5]))}." if found_funders else ""
        q = Flag(
            tier="quality",
            code="COI_DISCLOSED",
            message=f"Conflict of interest statement is present.{funder_detail}",
            source_agent="publication_metadata",
            evidence=[EvidenceQuote(text=coi_text[:200], section="coi_statement")] if coi_text else [],
        )
        quality_signals.append(q)

    # Flag industry funding without independent oversight or COI disclaimer
    if has_industry_funding and not has_independent:
        funder_names = ", ".join(set(found_funders[:4])) if found_funders else "industry source"
        f = Flag(
            tier="soft",
            code="INDUSTRY_ONLY_FUNDING_NO_COI",
            message=(
                f"Industry funding detected ({funder_names}) with no independent funding "
                f"or conflict-of-interest disclaimer evident. Results may be subject to "
                f"publication bias."
            ),
            source_agent="publication_metadata",
            evidence=[EvidenceQuote(
                text=combined_text[:200],
                section="funding",
            )],
        )
        soft_flags.append(f)
    elif not has_coi_statement and not combined_text.strip():
        # No funding or COI info at all — mild concern
        logger.debug("[PUB_META] No COI or funding text found in parsed paper")

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
