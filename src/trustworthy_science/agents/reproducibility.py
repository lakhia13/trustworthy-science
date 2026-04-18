"""Reproducibility Signals agent — detect data/code deposits and pre-registration."""

from __future__ import annotations

import logging
import re

from trustworthy_science.state import EvidenceQuote, Flag, PaperState, SubScore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Applicability matrix — which criteria are expected per paper type.
# Criteria that are not applicable are silently skipped (no flag, no penalty,
# no bonus expectation).  "empirical_quantitative" is the most conservative
# default and preserves the pre-existing behaviour for unknown types.
# ---------------------------------------------------------------------------
_DEFAULT_APPLICABILITY: dict[str, dict[str, bool]] = {
    "empirical_quantitative":   {"data": True,  "code": True,  "prereg": True},
    "clinical_trial":           {"data": True,  "code": False, "prereg": True},
    "systematic_review_meta":   {"data": True,  "code": True,  "prereg": False},
    "review_narrative":         {"data": False, "code": False, "prereg": False},
    "theoretical":              {"data": False, "code": False, "prereg": False},
    "computational_methods":    {"data": False, "code": True,  "prereg": False},
    "case_report":              {"data": False, "code": False, "prereg": False},
    "opinion_commentary":       {"data": False, "code": False, "prereg": False},
}

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
    """Node: check for data availability, code deposit, and pre-registration.

    Only criteria that apply to the detected paper type are checked.
    Criteria that are not applicable are silently skipped so that inherently
    non-reproducible paper types (reviews, theory, case reports, etc.) are not
    penalised for not having datasets or code they were never expected to have.
    """
    cfg = (config or {}).get("reproducibility", {})
    data_pats = cfg.get("data_repo_patterns", _DATA_PATTERNS)
    code_pats = cfg.get("code_patterns", _CODE_PATTERNS)
    prereg_pats = cfg.get("preregistration_patterns", _PREREG_PATTERNS)

    # Resolve applicability for this paper type
    applicability_cfg = (config or {}).get("paper_type_applicability", {})
    paper_type = state.paper_type or "empirical_quantitative"
    applies = applicability_cfg.get(
        paper_type,
        _DEFAULT_APPLICABILITY.get(paper_type, _DEFAULT_APPLICABILITY["empirical_quantitative"]),
    )

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

    data_hits: list[str] = []
    code_hits: list[str] = []
    prereg_hits: list[str] = []

    logger.info("[REPRO] Paper type: %s | Applicable checks — data:%s, code:%s, prereg:%s",
                paper_type, applies.get("data"), applies.get("code"), applies.get("prereg"))
    logger.info("[REPRO] Searching %d chars of text for reproducibility signals", len(text))

    # --- Data availability ---
    if applies.get("data"):
        data_hits = _search(text, data_pats)
        if data_hits:
            logger.info("[REPRO] ✓ DATA found — matched patterns: %s", list(set(data_hits[:5])))
            quality_signals.append(Flag(
                tier="quality",
                code="OPEN_DATA",
                message=f"Data appears to be publicly available: {', '.join(set(data_hits[:3]))}.",
                source_agent="reproducibility",
                evidence=[EvidenceQuote(text=data_hits[0], section="methods")],
            ))
        else:
            logger.info("[REPRO] ✗ DATA not found — issuing NO_DATA_DEPOSIT soft flag (-3 pts)")
            soft_flags.append(Flag(
                tier="soft",
                code="NO_DATA_DEPOSIT",
                message="No public data repository accession or data availability statement detected.",
                source_agent="reproducibility",
            ))
    else:
        logger.info("[REPRO] — DATA check skipped (not applicable for %s)", paper_type)

    # --- Code availability ---
    if applies.get("code"):
        code_hits = _search(text, code_pats)
        if code_hits:
            logger.info("[REPRO] ✓ CODE found — matched patterns: %s", list(set(code_hits[:5])))
            quality_signals.append(Flag(
                tier="quality",
                code="OPEN_CODE",
                message=f"Code or scripts appear to be available: {', '.join(set(code_hits[:2]))}.",
                source_agent="reproducibility",
                evidence=[EvidenceQuote(text=code_hits[0], section="methods")],
            ))
        else:
            logger.info("[REPRO] ✗ CODE not found — issuing NO_CODE_AVAILABILITY soft flag (-2 pts)")
            soft_flags.append(Flag(
                tier="soft",
                code="NO_CODE_AVAILABILITY",
                message="No code/software repository or availability statement detected.",
                source_agent="reproducibility",
            ))
    else:
        logger.info("[REPRO] — CODE check skipped (not applicable for %s)", paper_type)

    # --- Pre-registration ---
    if applies.get("prereg"):
        prereg_hits = _search(text, prereg_pats)
        if prereg_hits:
            logger.info("[REPRO] ✓ PREREG found — matched patterns: %s", list(set(prereg_hits[:3])))
            quality_signals.append(Flag(
                tier="quality",
                code="PREREGISTERED",
                message=f"Study appears to be pre-registered: {', '.join(set(prereg_hits[:2]))}.",
                source_agent="reproducibility",
                evidence=[EvidenceQuote(text=prereg_hits[0], section="methods")],
            ))
        else:
            logger.info("[REPRO] ✗ PREREG not found — issuing NO_PREREGISTRATION soft flag (-1 pt)")
            soft_flags.append(Flag(
                tier="soft",
                code="NO_PREREGISTRATION",
                message="No pre-registration identifier detected (ClinicalTrials.gov, OSF, PROSPERO, etc.).",
                source_agent="reproducibility",
            ))
    else:
        logger.info("[REPRO] — PREREG check skipped (not applicable for %s)", paper_type)

    # Compute sub-score relative to the number of applicable criteria.
    # When no criteria apply (pure review / theory / case report), the paper
    # has no reproducibility concerns → score = 1.0.
    applicable_count = sum(1 for v in applies.values() if v)
    if applicable_count == 0:
        score = 1.0
    else:
        # Scale bonus/penalty so a paper that meets all applicable criteria
        # scores ~1.0 and one that meets none scores ~0.46.
        bonus = len(quality_signals) * (0.30 / applicable_count)
        penalty = len(soft_flags) * (0.24 / applicable_count)
        score = max(0.0, min(1.0, 0.70 + bonus - penalty))

    confidence = 0.75 if state.coverage in ("full_text", "abstract_only") else 0.45

    all_flags = hard_flags + soft_flags + quality_signals
    logger.info("[REPRO] Sub-score: %.2f | Confidence: %.2f | "
                "Soft flags: %d | Quality signals: %d",
                score, confidence, len(soft_flags), len(quality_signals))

    sub = SubScore(
        score=score,
        confidence=confidence,
        flags=all_flags,
        notes=(
            f"paper_type={paper_type} | "
            f"Data: {bool(data_hits)}, Code: {bool(code_hits)}, Pre-reg: {bool(prereg_hits)} | "
            f"Applicable criteria: {applicable_count}"
        ),
    )

    return {
        "sub_scores": {"reproducibility": sub},
        "hard_flags": hard_flags,
        "soft_flags": soft_flags,
        "quality_signals": quality_signals,
    }
