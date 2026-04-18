"""Reproducibility Signals agent — detect data/code deposits and pre-registration."""

from __future__ import annotations

import logging
import re

from trustworthy_science.state import EvidenceQuote, Flag, PaperState, SubScore

logger = logging.getLogger(__name__)

# Default patterns (overridable via config)
_DATA_PATTERNS = [
    r"GEO\d+", r"GSE\d+", r"SRA\d+", r"PRJNA\d+",
    r"zenodo\.org", r"figshare\.com", r"datadryad\.org", r"dryad\.org",
    r"osf\.io", r"OSF\.io", r"Zenodo", r"Figshare",
    r"data\s+available", r"data\s+are\s+available", r"publicly\s+available",
    r"GigaDB", r"ArrayExpress", r"E-MTAB-\d+",
]
_CODE_PATTERNS = [
    r"github\.com/\S+", r"gitlab\.com/\S+", r"bitbucket\.org/\S+",
    r"code\s+available", r"scripts?\s+available", r"software\s+available",
    r"zenodo.*code", r"code.*zenodo",
    r"https?://\S+\.r$", r"CRAN", r"Bioconductor",
]
_PREREG_PATTERNS = [
    r"NCT\d{8}", r"ClinicalTrials\.gov", r"ISRCTN\d+",
    r"OSF.*preregistr", r"AsPredicted\.org", r"PROSPERO",
    r"pre-registr", r"preregistr", r"registered\s+report",
]


def _search(text: str, patterns: list[str]) -> list[str]:
    """Return list of matched snippets from text against pattern list."""
    matches = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            matches.append(m.group(0))
    return matches


def reproducibility_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: check for data availability, code deposit, and pre-registration."""
    cfg = (config or {}).get("reproducibility", {})
    data_pats = cfg.get("data_repo_patterns", _DATA_PATTERNS)
    code_pats = cfg.get("code_patterns", _CODE_PATTERNS)
    prereg_pats = cfg.get("preregistration_patterns", _PREREG_PATTERNS)

    # Gather text to search
    text_parts = []
    if state.parsed:
        for section in (
            state.parsed.full_text,
            state.parsed.abstract,
            state.parsed.methods,
            state.parsed.funding,
            state.parsed.coi_statement,
        ):
            if section:
                text_parts.append(section)
    text = " ".join(text_parts)

    hard_flags: list[Flag] = []
    soft_flags: list[Flag] = []
    quality_signals: list[Flag] = []

    # --- Data availability ---
    data_hits = _search(text, data_pats)
    if data_hits:
        q = Flag(
            tier="quality",
            code="OPEN_DATA",
            message=f"Data appears to be publicly available: {', '.join(set(data_hits[:3]))}.",
            source_agent="reproducibility",
            evidence=[EvidenceQuote(text=data_hits[0], section="methods")],
        )
        quality_signals.append(q)
    else:
        f = Flag(
            tier="soft",
            code="NO_DATA_DEPOSIT",
            message="No public data repository accession or data availability statement detected.",
            source_agent="reproducibility",
        )
        soft_flags.append(f)

    # --- Code availability ---
    code_hits = _search(text, code_pats)
    if code_hits:
        q = Flag(
            tier="quality",
            code="OPEN_CODE",
            message=f"Code or scripts appear to be available: {', '.join(set(code_hits[:2]))}.",
            source_agent="reproducibility",
            evidence=[EvidenceQuote(text=code_hits[0], section="methods")],
        )
        quality_signals.append(q)
    else:
        f = Flag(
            tier="soft",
            code="NO_CODE_AVAILABILITY",
            message="No code/software repository or availability statement detected.",
            source_agent="reproducibility",
        )
        soft_flags.append(f)

    # --- Pre-registration ---
    prereg_hits = _search(text, prereg_pats)
    if prereg_hits:
        q = Flag(
            tier="quality",
            code="PREREGISTERED",
            message=f"Study appears to be pre-registered: {', '.join(set(prereg_hits[:2]))}.",
            source_agent="reproducibility",
            evidence=[EvidenceQuote(text=prereg_hits[0], section="methods")],
        )
        quality_signals.append(q)
    else:
        f = Flag(
            tier="soft",
            code="NO_PREREGISTRATION",
            message="No pre-registration identifier detected (ClinicalTrials.gov, OSF, PROSPERO, etc.).",
            source_agent="reproducibility",
        )
        soft_flags.append(f)

    # Compute sub-score
    bonus = len(quality_signals) * 0.12
    penalty = len(soft_flags) * 0.08
    score = max(0.0, min(1.0, 0.70 + bonus - penalty))
    confidence = 0.75 if state.coverage in ("full_text", "abstract_only") else 0.45

    all_flags = hard_flags + soft_flags + quality_signals
    sub = SubScore(
        score=score,
        confidence=confidence,
        flags=all_flags,
        notes=f"Data available: {bool(data_hits)}, Code available: {bool(code_hits)}, Pre-registered: {bool(prereg_hits)}",
    )

    return {
        "sub_scores": {"reproducibility": sub},
        "hard_flags": hard_flags,
        "soft_flags": soft_flags,
        "quality_signals": quality_signals,
    }
