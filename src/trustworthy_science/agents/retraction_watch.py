"""Retraction Watch agent — hard-flag retracted papers; check replication status."""

from __future__ import annotations

import logging

from trustworthy_science.state import EvidenceQuote, Flag, PaperState, SubScore
from trustworthy_science.tools.retraction_watch import is_retracted
from trustworthy_science.tools.replication_db import check_replication

logger = logging.getLogger(__name__)


def retraction_watch_agent(state: PaperState) -> dict:
    """Node: check if the paper has been retracted and look up replication status.

    If retracted, emits a hard flag and sets ``state.retracted = True``
    which triggers the short-circuit edge in LangGraph.

    Also checks replication databases (OSC 2015, SSRP) and emits:
    - REPLICATION_FAILED soft flag if an attempt failed
    - INDEPENDENTLY_REPLICATED quality signal if confirmed by another lab
    """
    doi = state.stub.doi
    retracted, record = is_retracted(doi or "")

    hard_flags: list[Flag] = []
    soft_flags: list[Flag] = []
    quality_signals: list[Flag] = []

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
        hard_flags.append(flag)
        sub = SubScore(score=0.0, confidence=0.99, flags=[flag], notes=msg)
        logger.info("RETRACTED: %s — %s", doi, msg)
        return {
            "hard_flags": hard_flags,
            "sub_scores": {"retraction_watch": sub},
            "retracted": True,
        }

    # --- Replication database lookup ---
    repl = check_replication(doi)
    logger.info("[RETRACTION] Replication check: doi=%s found=%s outcome=%s",
                doi, repl.found, repl.outcome)

    if repl.found and repl.outcome == "failed":
        f = Flag(
            tier="soft",
            code="REPLICATION_FAILED",
            message=repl.summary,
            source_agent="retraction_watch",
            evidence=[EvidenceQuote(
                text=f"Source: {repl.source}. {repl.summary}",
                section="metadata",
            )],
        )
        soft_flags.append(f)

    elif repl.found and repl.outcome == "replicated":
        q = Flag(
            tier="quality",
            code="INDEPENDENTLY_REPLICATED",
            message=repl.summary,
            source_agent="retraction_watch",
            evidence=[EvidenceQuote(
                text=f"Source: {repl.source}. {repl.summary}",
                section="metadata",
            )],
        )
        quality_signals.append(q)

    # Not retracted
    notes = "No retraction found in Crossref Crossmark or Retraction Watch."
    if repl.found:
        notes += f" Replication: {repl.summary}"
    sub = SubScore(score=1.0, confidence=0.85, notes=notes)

    return {
        "sub_scores": {"retraction_watch": sub},
        "soft_flags": soft_flags,
        "quality_signals": quality_signals,
        "retracted": False,
    }
