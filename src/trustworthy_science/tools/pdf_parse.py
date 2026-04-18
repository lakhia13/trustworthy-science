"""PDF and plain-text parsing utilities."""

from __future__ import annotations

import io
import logging
import re

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
