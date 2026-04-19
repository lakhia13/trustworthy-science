"""Fetch & Parse agent — retrieves full text and segments it into sections."""

from __future__ import annotations

import logging

from trustworthy_science.state import ParsedPaper, PaperState
from trustworthy_science.tools.pubmed import fetch_bioc_fulltext, fetch_pmc_fulltext
from trustworthy_science.tools.pdf_parse import fetch_pdf_text, segment_sections
from trustworthy_science.tools.biorxiv import fetch_biorxiv_fulltext, europepmc_pmcid_for_doi
from trustworthy_science.tools.author_search import fetch_author_fulltext

logger = logging.getLogger(__name__)


def fetch_and_parse(state: PaperState) -> dict:
    """Node: fetch full text for the paper and segment into sections.

    Updates ``state.parsed`` and ``state.coverage``.
    Returns a dict with the updated fields for LangGraph state merging.

    Fetch order:
      1. BioC JSON via PMID (best quality — structured sections, unicode)
      2. PMC efetch XML via PMCID (fallback for OA papers without a PMID)
      3. PDF via pdf_url (direct link)
      4. EuropePMC PMCID discovery + PMC efetch (DOI-only stubs)
      5. bioRxiv / medRxiv full text
      6. Semantic Scholar OA PDF / arXiv mirror
      7. Abstract-only fallback
    """
    stub = state.stub
    full_text = ""
    sections: dict[str, str] = {}
    coverage = "metadata_only"
    source_used = "none"

    logger.info("[FETCH] Starting full-text retrieval for: %s (DOI=%s, PMID=%s, PMCID=%s)",
                stub.title[:60] if stub.title else "Unknown", stub.doi, stub.pmid, stub.pmcid)

    # ------------------------------------------------------------------
    # Step 1: BioC JSON via PMID — gold-standard structured full text
    # ------------------------------------------------------------------
    if stub.pmid:
        logger.info("[FETCH] Step 1: Trying BioC JSON (PMID=%s) ...", stub.pmid)
        try:
            bioc_text, bioc_sections = fetch_bioc_fulltext(stub.pmid)
            if bioc_text.strip():
                full_text = bioc_text
                sections = bioc_sections
                coverage = "full_text"
                source_used = "bioc"
                logger.info("[FETCH] ✓ BioC SUCCESS — %d chars, sections: %s",
                            len(full_text), list(sections.keys()))
            else:
                logger.info("[FETCH] ✗ BioC returned empty text for PMID=%s "
                            "(paper may not be in PMC OA subset)", stub.pmid)
        except Exception as exc:
            logger.info("[FETCH] ✗ BioC failed: %s", exc)
    else:
        logger.info("[FETCH] Step 1: Skipped BioC (no PMID)")

    # ------------------------------------------------------------------
    # Step 2: PMC efetch XML via PMCID (fallback)
    # ------------------------------------------------------------------
    if not full_text and stub.pmcid:
        logger.info("[FETCH] Step 2: Trying PMC efetch (PMCID=%s) ...", stub.pmcid)
        try:
            full_text = fetch_pmc_fulltext(stub.pmcid)
            if full_text.strip():
                coverage = "full_text"
                source_used = "pmc"
                logger.info("[FETCH] ✓ PMC efetch SUCCESS — %d chars retrieved", len(full_text))
            else:
                logger.info("[FETCH] ✗ PMC efetch returned empty text")
        except Exception as exc:
            logger.info("[FETCH] ✗ PMC efetch failed: %s", exc)
    else:
        logger.info("[FETCH] Step 2: Skipped PMC efetch (%s)",
                    "already have text" if full_text else "no PMCID")

    # ------------------------------------------------------------------
    # Step 3: PDF via pdf_url
    # ------------------------------------------------------------------
    if not full_text and stub.pdf_url:
        logger.info("[FETCH] Step 3: Trying PDF URL: %s ...", stub.pdf_url[:80])
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
        logger.info("[FETCH] Step 3: Skipped PDF URL (%s)",
                    "already have text" if full_text else "no pdf_url in stub")

    # ------------------------------------------------------------------
    # Step 4: EuropePMC PMCID discovery + PMC efetch (DOI-only stubs)
    # ------------------------------------------------------------------
    if not full_text and stub.doi:
        logger.info("[FETCH] Step 4: Trying EuropePMC PMCID discovery (DOI=%s) ...", stub.doi)
        try:
            pmcid = europepmc_pmcid_for_doi(stub.doi)
            if pmcid:
                logger.info("[FETCH]   EuropePMC found PMCID=%s — fetching PMC full text ...", pmcid)
                full_text = fetch_pmc_fulltext(pmcid)
                if full_text.strip():
                    coverage = "full_text"
                    source_used = "europepmc"
                    logger.info("[FETCH] ✓ EuropePMC/PMC SUCCESS — %d chars retrieved", len(full_text))
                else:
                    logger.info("[FETCH] ✗ EuropePMC: PMC returned empty text for PMCID=%s", pmcid)
            else:
                logger.info("[FETCH] ✗ EuropePMC: no PMCID found for DOI=%s", stub.doi)
        except Exception as exc:
            logger.info("[FETCH] ✗ EuropePMC failed: %s", exc)
    else:
        logger.info("[FETCH] Step 4: Skipped EuropePMC (%s)",
                    "already have text" if full_text else "no DOI")

    # ------------------------------------------------------------------
    # Step 5: bioRxiv / medRxiv
    # ------------------------------------------------------------------
    if not full_text and stub.doi:
        logger.info("[FETCH] Step 5: Trying bioRxiv/medRxiv (DOI=%s) ...", stub.doi)
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
        logger.info("[FETCH] Step 5: Skipped bioRxiv (%s)",
                    "already have text" if full_text else "no DOI")

    # ------------------------------------------------------------------
    # Step 6: Semantic Scholar OA PDF / arXiv mirror
    # ------------------------------------------------------------------
    if not full_text and stub.doi:
        logger.info("[FETCH] Step 6: Trying Semantic Scholar OA PDF (DOI=%s) ...", stub.doi)
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
        logger.info("[FETCH] Step 6: Skipped Semantic Scholar (%s)",
                    "already have text" if full_text else "no DOI")

    # ------------------------------------------------------------------
    # Step 7: Abstract-only fallback
    # ------------------------------------------------------------------
    if not full_text and stub.abstract:
        full_text = stub.abstract
        coverage = "abstract_only"
        source_used = "abstract_fallback"
        logger.info("[FETCH] Step 7: Fell back to ABSTRACT ONLY (%d chars) — "
                    "accuracy will be ~60%% for stats/reproducibility checks", len(full_text))

    if not full_text:
        logger.warning("[FETCH] ✗ NO TEXT retrieved — all sources exhausted. "
                       "Scoring will use metadata only (35%% accuracy)")

    logger.info("[FETCH] RESULT: coverage=%s | source=%s | text_length=%d chars",
                coverage, source_used, len(full_text))

    # ------------------------------------------------------------------
    # Section segmentation
    # When BioC already provided structured sections, use them directly.
    # For all other sources, run the heuristic line-scanner.
    # ------------------------------------------------------------------
    if not sections and full_text:
        sections = segment_sections(full_text)

    parsed = ParsedPaper(
        full_text=full_text,
        abstract=sections.get("abstract", stub.abstract),
        methods=sections.get("methods", ""),
        results=sections.get("results", ""),
        discussion=sections.get("discussion", ""),
        funding=sections.get("funding", ""),
        coi_statement=sections.get("coi", ""),
        references=_extract_reference_list(sections.get("references", "")),
        fetch_source=source_used,
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
