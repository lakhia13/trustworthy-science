"""PDF, plain-text, and BioC JSON parsing utilities."""

from __future__ import annotations

import io
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Section header patterns (case-insensitive)
_SECTION_PATTERNS = {
    "abstract":   re.compile(r"\babstract\b", re.IGNORECASE),
    "methods":    re.compile(r"\b(methods?|materials?\s+and\s+methods?|methodology)\b", re.IGNORECASE),
    "results":    re.compile(r"\bresults?\b", re.IGNORECASE),
    "discussion": re.compile(r"\bdiscussion\b", re.IGNORECASE),
    "conclusion": re.compile(r"\bconclusions?\b", re.IGNORECASE),
    "references": re.compile(r"\breferences?\b", re.IGNORECASE),
    "funding":    re.compile(r"\b(funding|acknowledgements?|acknowledgments?|financial\s+disclosure)\b", re.IGNORECASE),
    "coi":        re.compile(r"\b(conflict[s]?\s+of\s+interest|competing\s+interests?|declarations?)\b", re.IGNORECASE),
}


def pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    """Convert PDF bytes to plain text using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception as exc:
        logger.warning("PDF text extraction failed: %s", exc)
        return ""


def fetch_pdf_text(url: str) -> str:
    """Download PDF from URL and return extracted text."""
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "pdf" in ct or url.endswith(".pdf"):
            return pdf_bytes_to_text(r.content)
        return r.text
    except Exception as exc:
        logger.warning("PDF fetch failed for %s: %s", url, exc)
        return ""


def segment_sections(text: str) -> dict[str, str]:
    """Split a paper's text into named sections.

    Returns a dict with keys like "methods", "results", "discussion", etc.
    Uses heuristic line-by-line scanning for section headers.
    """
    lines = text.split("\n")
    sections: dict[str, list[str]] = {"body": []}
    current = "body"

    for line in lines:
        stripped = line.strip()
        matched = False
        for name, pat in _SECTION_PATTERNS.items():
            # Treat short lines that match as section headers
            if len(stripped) < 80 and pat.search(stripped):
                current = name
                sections.setdefault(current, [])
                matched = True
                break
        if not matched:
            sections.setdefault(current, []).append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


# ---------------------------------------------------------------------------
# BioC JSON passage → sections converter
# ---------------------------------------------------------------------------

# Canonical mapping from BioC infons 'type' → our internal section keys.
# Keep in sync with the copy in tools/pubmed.py.
_BIOC_SECTION_MAP: dict[str, str] = {
    "title":            "title",
    "abstract":         "abstract",
    "intro":            "body",
    "introduction":     "body",
    "methods":          "methods",
    "materials":        "methods",
    "results":          "results",
    "discussion":       "discussion",
    "conclusion":       "discussion",
    "conclusions":      "discussion",
    "funding":          "funding",
    "acknowledgement":  "funding",
    "acknowledgements": "funding",
    "acknowledgment":   "funding",
    "acknowledgments":  "funding",
    "coi":              "coi",
    "conflict":         "coi",
    "ref":              "references",
    "references":       "references",
    "fig_caption":      "figures",
    "table":            "tables",
    "paragraph":        "body",
}


def parse_bioc_json(bioc_data: Any) -> tuple[str, dict[str, str]]:
    """Convert a raw BioC JSON response (already decoded) into text + sections.

    Accepts the top-level BioC value which may be a list of documents or a
    dict containing a ``"documents"`` key.

    Returns:
        full_text: Entire paper as a labelled string (``[SECTION]\\ntext``).
        sections:  Dict mapping section names to concatenated passage text.
    """
    full_parts: list[str] = []
    section_buckets: dict[str, list[str]] = {}

    documents = bioc_data if isinstance(bioc_data, list) else bioc_data.get("documents", [])
    for doc in documents:
        for passage in doc.get("passages", []):
            infons = passage.get("infons", {})
            raw_type = (
                infons.get("type") or infons.get("section_type") or "paragraph"
            ).lower()
            section_key = _BIOC_SECTION_MAP.get(raw_type, "body")
            text_content = passage.get("text", "").strip()
            if not text_content:
                continue
            full_parts.append(f"[{raw_type.upper()}]\n{text_content}")
            section_buckets.setdefault(section_key, []).append(text_content)

    full_text = "\n\n".join(full_parts)
    sections = {k: "\n\n".join(v) for k, v in section_buckets.items()}
    return full_text, sections
