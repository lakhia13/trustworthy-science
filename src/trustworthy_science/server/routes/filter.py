from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException
from trustworthy_science.server.schemas import FilterRequest, FilterResponse, PaperResult
from trustworthy_science.server.dependencies import get_truth_filter
from trustworthy_science.api import TruthFilter

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("", response_model=FilterResponse, summary="Retrieve and filter papers for a research question")
def filter_papers(request: FilterRequest, tf: TruthFilter = Depends(get_truth_filter)) -> FilterResponse:
    """Retrieve papers for a research query and return only those meeting `min_tier`.

    Results are sorted trusted-first, then by score descending. Intended for
    pre-filtering a RAG context window.
    """
    try:
        raw_list = tf.filter_for_rag(
            query=request.query,
            top_k=request.top_k,
            min_tier=request.min_tier,
        )
    except Exception as exc:
        logger.error("filter_for_rag failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    papers = [PaperResult.from_dict(r) for r in raw_list]
    return FilterResponse(
        papers=papers,
        count=len(papers),
        query=request.query,
        min_tier=request.min_tier,
    )
