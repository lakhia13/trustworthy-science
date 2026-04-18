"""Fetch & Parse agent — retrieves full text and segments it into sections."""

from __future__ import annotations

import logging

from trustworthy_science.state import ParsedPaper, PaperState
from trustworthy_science.tools.pubmed import fetch_pmc_fulltext
from trustworthy_science.tools.pdf_parse import fetch_pdf_text, segment_sections

logger = logging.getLogger(__name__)


def fetch_and_parse(state: PaperState) -> dict:
    """Node: fetch full text for the paper and segment into sections.

    Updates ``state.parsed`` and ``state.coverage``.
    Returns a dict with the updated fields for LangGraph state merging.
    """
    stub = state.stub
    full_text = ""
    coverage = "metadata_only"

    # 1. Try PMC full text (best quality, free)
    if stub.pmcid:
        try:
            full_text = fetch_pmc_fulltext(stub.pmcid)
            if full_text.strip():
                coverage = "full_text"
                logger.debug("Got PMC full text for %s", stub.uid)
        except Exception as exc:
            logger.debug("PMC fetch failed: %s", exc)

    # 2. Try PDF via pdf_url
    if not full_text and stub.pdf_url:
        try:
            full_text = fetch_pdf_text(stub.pdf_url)
            if full_text.strip():
                coverage = "full_text"
                logger.debug("Got PDF full text for %s", stub.uid)
        except Exception as exc:
            logger.debug("PDF fetch failed: %s", exc)

    # 3. Fall back to abstract only
    if not full_text and stub.abstract:
        full_text = stub.abstract
        coverage = "abstract_only"

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
