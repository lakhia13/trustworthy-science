"""Retraction Watch agent — hard-flag retracted papers immediately."""

from __future__ import annotations

import logging

from trustworthy_science.state import EvidenceQuote, Flag, PaperState, SubScore
from trustworthy_science.tools.retraction_watch import is_retracted

logger = logging.getLogger(__name__)


def retraction_watch_agent(state: PaperState) -> dict:
    """Node: check if the paper has been retracted.

    If retracted, emits a hard flag and sets ``state.retracted = True``
    which triggers the short-circuit edge in LangGraph.
    """
    doi = state.stub.doi
    retracted, record = is_retracted(doi or "")

    if retracted:
        source = (record or {}).get("source", "retraction_watch")
        reason = (record or {}).get("Reason", "see Retraction Watch database")
        notice_doi = (record or {}).get("RetractionDOI", "")
        msg = f"Paper has been retracted. Reason: {reason}."
        if notice_doi:
            msg += f" Retraction notice DOI: {notice_doi}."

        flag = Flag(
            tier="hard",
            code="RETRACTED",
            message=msg,
            source_agent="retraction_watch",
            evidence=[EvidenceQuote(text=msg, section="metadata")],
        )
        sub = SubScore(score=0.0, confidence=0.99, flags=[flag], notes=msg)
        logger.info("RETRACTED: %s — %s", doi, msg)
        return {
            "hard_flags": [flag],
            "sub_scores": {"retraction_watch": sub},
            "retracted": True,
        }

    # Not retracted
    sub = SubScore(score=1.0, confidence=0.85, notes="No retraction found in Crossref Crossmark or Retraction Watch.")
    return {
        "sub_scores": {"retraction_watch": sub},
        "retracted": False,
    }
