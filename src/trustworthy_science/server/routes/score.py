"""Synchronous /score endpoint — backward-compatible shortcut.

Accepts the same ``SearchRequest`` payload as ``POST /api/search`` but returns
a synchronous ``ScoreResponse`` instead of a background job. Suitable for
small batches (a few DOIs or PMIDs) where the caller wants an immediate result.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from trustworthy_science.api import TruthFilter
from trustworthy_science.server.dependencies import get_truth_filter, resolve_truth_filter
from trustworthy_science.server.schemas import PaperResult, ScoreResponse, SearchRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=ScoreResponse, summary="Score papers by DOI, PMID, or query (synchronous)")
def score_papers(
    request: SearchRequest,
    tf: TruthFilter = Depends(get_truth_filter),
) -> ScoreResponse:
    """Score one or more papers and return results immediately.

    Supply any combination of:
    - **dois**: list of DOI strings
    - **pmids**: list of PubMed IDs
    - **query**: natural-language research question (retrieves top_k papers)

    Returns the full list of scored papers in a single response.
    For large batches, prefer ``POST /api/search`` (async job).
    """
    active_tf = resolve_truth_filter(request.weights, tf)
    results: list[PaperResult] = []
    seen: set[str] = set()

    # Score each PMID individually (uses BioC full-text path)
    for pmid in request.pmids:
        try:
            raw = active_tf.score_single_by_pmid(pmid)
            if raw:
                key = raw.get("doi") or raw.get("pmid") or pmid
                if key not in seen:
                    seen.add(key)
                    results.append(PaperResult.from_dict(raw))
        except Exception as exc:
            logger.warning("PMID %s scoring failed: %s", pmid, exc)

    # Score DOIs / text query in a single graph invocation
    if request.dois or request.query:
        try:
            raw_list = active_tf.score_papers(
                dois=request.dois or None,
                query=request.query,
                top_k=request.top_k,
            )
            for raw in raw_list:
                key = raw.get("doi") or raw.get("pmid") or ""
                if key not in seen:
                    seen.add(key)
                    results.append(PaperResult.from_dict(raw))
        except Exception as exc:
            logger.error("score_papers failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    return ScoreResponse(papers=results, count=len(results))
