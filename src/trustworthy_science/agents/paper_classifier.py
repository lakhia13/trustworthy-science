"""Paper Type Classifier — lightweight regex heuristic, no LLM required."""

from __future__ import annotations

import re

from trustworthy_science.state import PaperState, PaperType

# ---------------------------------------------------------------------------
# Classification rules — evaluated in priority order (first match wins).
# Each entry is (paper_type, list_of_regex_patterns).  A type is selected
# when ANY pattern matches the combined title + abstract text.
# ---------------------------------------------------------------------------

_RULES: list[tuple[PaperType, list[str]]] = [
    # Clinical trials must be caught before "review" since some RCT papers use
    # "systematic review of RCTs" in the abstract.
    ("clinical_trial", [
        r"\brandomized\s+controlled\s+trial\b",
        r"\brandomised\s+controlled\s+trial\b",
        r"\bRCT\b",
        r"NCT\d{8}",
        r"ClinicalTrials\.gov",
        r"ISRCTN\d+",
        r"\bphase\s+(?:I{1,3}|IV|1|2|3|4)\s+(?:clinical\s+)?trial\b",
    ]),
    # Systematic reviews / meta-analyses
    ("systematic_review_meta", [
        r"\bsystematic\s+review\b",
        r"\bmeta-analysis\b",
        r"\bmetaanalysis\b",
        r"\bPRISMA\b",
        r"\bCochrane\s+review\b",
        r"\bnetwork\s+meta-analysis\b",
    ]),
    # Case reports / case series
    ("case_report", [
        r"\bcase\s+report\b",
        r"\bcase\s+series\b",
        r"\bwe\s+report\s+(?:a|an|the)\s+case\b",
        r"\bwe\s+describe\s+(?:a|an)\s+case\b",
        r"\bcase\s+presentation\b",
    ]),
    # Opinion / commentary / perspective
    ("opinion_commentary", [
        r"\bcommentary\b",
        r"\bperspective\b",
        r"\bletter\s+to\s+the\s+editor\b",
        r"\beditorial\b",
        r"\bviewpoint\b",
        r"\bopinion\s+(?:piece|article)\b",
        r"\bwe\s+(?:argue|propose|suggest|contend)\s+that\b",
    ]),
    # Narrative reviews (must come AFTER systematic_review_meta so "systematic
    # review" doesn't also match here)
    ("review_narrative", [
        r"\bnarrative\s+review\b",
        r"\bscoping\s+review\b",
        r"\bliterature\s+review\b",
        r"\bwe\s+(?:review|survey|summarise|summarize)\b",
        r"\bthis\s+review\b",
        r"\boverall\s+review\b",
        r"\bcomprehensive\s+review\b",
        r"\bwe\s+surveyed\s+\d+\s+studi",
        r"\b(?:overview|survey)\s+of\s+(?:the\s+)?(?:current\s+)?(?:literature|field|research)\b",
        r"\breview\s+article\b",
    ]),
    # Theoretical / mathematical / formal
    ("theoretical", [
        r"\btheoretical\s+(?:framework|model|analysis|study)\b",
        r"\bmathematical\s+(?:model|framework|analysis)\b",
        r"\bwe\s+derive\b",
        r"\bwe\s+prove\b",
        r"\banalytical\s+(?:solution|model|framework)\b",
        r"\bdifferential\s+(?:equation|model)\b",
        r"\bformal\s+(?:analysis|proof|framework)\b",
        r"\bno\s+(?:experimental\s+)?data\s+(?:were|was)\s+collected\b",
        r"\bstochastic\s+model\b",
        r"\bgame.theoretic\b",
    ]),
    # Computational / software / methods papers
    ("computational_methods", [
        r"\bsoftware\s+tool\b",
        r"\bwe\s+present\s+(?:a\s+)?(?:novel\s+)?(?:tool|software|pipeline|package|algorithm|framework)\b",
        r"\bcomputational\s+pipeline\b",
        r"\bbioinformatics\s+(?:tool|pipeline|package)\b",
        r"\bwe\s+implemented\b",
        r"\bbenchmark(?:ing)?\b",
        r"\bopen.source\s+(?:tool|software|package)\b",
        r"\bsource\s+code\s+(?:is\s+)?available\b",
    ]),
]

_FALLBACK: PaperType = "empirical_quantitative"


def classify_paper_type(state: PaperState, config: dict | None = None) -> dict:
    """LangGraph node: classify paper type from title + abstract heuristics.

    Returns a state-update dict ``{"paper_type": <PaperType>}`` which
    LangGraph merges into the running ``PaperState``.
    """
    # Build text: title + abstract (both always available from PaperStub)
    title = state.stub.title or ""
    abstract = state.stub.abstract or ""
    # Also include abstract from ParsedPaper when available
    if state.parsed and state.parsed.abstract:
        abstract = state.parsed.abstract

    text = f"{title} {abstract}".lower()

    import logging as _logging
    _logger = _logging.getLogger(__name__)
    _logger.info("[CLASSIFY] Classifying paper: %s", (title[:60] + "...") if len(title) > 60 else title)

    for paper_type, patterns in _RULES:
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                _logger.info("[CLASSIFY] ✓ Matched type '%s' via pattern: %s", paper_type, pat)
                return {"paper_type": paper_type}

    _logger.info("[CLASSIFY] No pattern matched → using fallback type: %s", _FALLBACK)
    return {"paper_type": _FALLBACK}
