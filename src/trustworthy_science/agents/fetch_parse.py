"""Fetch & Parse agent — retrieves full text and segments it into sections."""

from __future__ import annotations

import logging

from trustworthy_science.state import ParsedPaper, PaperState
from trustworthy_science.tools.pubmed import fetch_pmc_fulltext
from trustworthy_science.tools.pdf_parse import fetch_pdf_text, segment_sections
from trustworthy_science.tools.biorxiv import fetch_biorxiv_fulltext
from trustworthy_science.tools.author_search import fetch_author_fulltext

logger = logging.getLogger(__name__)


def fetch_and_parse(state: PaperState) -> dict:
    """Node: fetch full text for the paper and segment into sections.

    Updates ``state.parsed`` and ``state.coverage``.
    Returns a dict with the updated fields for LangGraph state merging.
    """
    stub = state.stub
    full_text = ""
    coverage = "metadata_only"
    source_used = "none"

    logger.info("[FETCH] Starting full-text retrieval for: %s (DOI=%s, PMCID=%s)",
                stub.title[:60] if stub.title else "Unknown", stub.doi, stub.pmcid)

    # 1. Try PMC full text (best quality, free)
    if stub.pmcid:
        logger.info("[FETCH] Step 1: Trying PMC (PMCID=%s) ...", stub.pmcid)
        try:
            full_text = fetch_pmc_fulltext(stub.pmcid)
            if full_text.strip():
                coverage = "full_text"
                source_used = "pmc"
                logger.info("[FETCH] ✓ PMC SUCCESS — %d chars retrieved", len(full_text))
            else:
                logger.info("[FETCH] ✗ PMC returned empty text")
        except Exception as exc:
            logger.info("[FETCH] ✗ PMC failed: %s", exc)
    else:
        logger.info("[FETCH] Step 1: Skipped PMC (no PMCID)")

    # 2. Try PDF via pdf_url
    if not full_text and stub.pdf_url:
        logger.info("[FETCH] Step 2: Trying PDF URL: %s ...", stub.pdf_url[:80])
        try:
            full_text = fetch_pdf_text(stub.pdf_url)
            if full_text.strip():
                coverage = "full_text"
                source_used = "pdf_url"
                logger.info("[FETCH] ✓ PDF URL SUCCESS — %d chars retrieved", len(full_text))
            else:
                logger.info("[FETCH] ✗ PDF URL returned empty text")
        except Exception as exc:
            logger.info("[FETCH] ✗ PDF URL failed: %s", exc)
    else:
        if full_text:
            logger.info("[FETCH] Step 2: Skipped PDF URL (already have text)")
        else:
            logger.info("[FETCH] Step 2: Skipped PDF URL (no pdf_url in stub)")

    # 3. Try bioRxiv / medRxiv (preprints and published papers with preprint versions)
    if not full_text and stub.doi:
        logger.info("[FETCH] Step 3: Trying bioRxiv/medRxiv (DOI=%s) ...", stub.doi)
        try:
            full_text = fetch_biorxiv_fulltext(stub.doi)
            if full_text.strip():
                coverage = "full_text"
                source_used = "biorxiv"
                logger.info("[FETCH] ✓ bioRxiv SUCCESS — %d chars retrieved", len(full_text))
            else:
                logger.info("[FETCH] ✗ bioRxiv returned no text")
        except Exception as exc:
            logger.info("[FETCH] ✗ bioRxiv failed: %s", exc)
    else:
        logger.info("[FETCH] Step 3: Skipped bioRxiv (%s)",
                    "already have text" if full_text else "no DOI")

    # 4. Try Semantic Scholar open-access PDF / arXiv mirror
    if not full_text and stub.doi:
        logger.info("[FETCH] Step 4: Trying Semantic Scholar OA PDF (DOI=%s) ...", stub.doi)
        try:
            full_text = fetch_author_fulltext(stub.doi)
            if full_text.strip():
                coverage = "full_text"
                source_used = "semantic_scholar"
                logger.info("[FETCH] ✓ Semantic Scholar SUCCESS — %d chars retrieved", len(full_text))
            else:
                logger.info("[FETCH] ✗ Semantic Scholar: no OA PDF found")
        except Exception as exc:
            logger.info("[FETCH] ✗ Semantic Scholar failed: %s", exc)
    else:
        logger.info("[FETCH] Step 4: Skipped Semantic Scholar (%s)",
                    "already have text" if full_text else "no DOI")

    # 5. Fall back to abstract only
    if not full_text and stub.abstract:
        full_text = stub.abstract
        coverage = "abstract_only"
        source_used = "abstract_fallback"
        logger.info("[FETCH] Step 5: Fell back to ABSTRACT ONLY (%d chars) — "
                    "accuracy will be ~60%% for stats/reproducibility checks", len(full_text))

    if not full_text:
        logger.warning("[FETCH] ✗ NO TEXT retrieved — all sources exhausted. "
                       "Scoring will use metadata only (35%% accuracy)")

    logger.info("[FETCH] RESULT: coverage=%s | source=%s | text_length=%d chars",
                coverage, source_used, len(full_text))

    # Segment into sections
    if full_text:
        sections = segment_sections(full_text)
    else:
        sections = {}

    parsed = ParsedPaper(
        full_text=full_text,
        abstract=sections.get("abstract", stub.abstract),
        methods=sections.get("methods", ""),
        results=sections.get("results", ""),
        discussion=sections.get("discussion", ""),
        funding=sections.get("funding", ""),
        coi_statement=sections.get("coi", ""),
        references=_extract_reference_list(sections.get("references", "")),
    )

    return {"parsed": parsed, "coverage": coverage}


def _extract_reference_list(ref_section: str) -> list[str]:
    """Split a references section into individual reference strings."""
    if not ref_section:
        return []
    # Split on numbered references like "1." or "[1]"
    import re
    refs = re.split(r"\n\s*(?:\[\d+\]|\d+\.)\s+", ref_section)
    return [r.strip() for r in refs if r.strip()][:100]  # cap at 100
