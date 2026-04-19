from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException
from trustworthy_science.server.schemas import ExplainRequest, PaperResult
from trustworthy_science.server.dependencies import get_truth_filter, resolve_truth_filter
from trustworthy_science.api import TruthFilter

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("", response_model=PaperResult, summary="Detailed credibility explanation for a single paper")
def explain_paper(request: ExplainRequest, tf: TruthFilter = Depends(get_truth_filter)) -> PaperResult:
    """Return a full per-dimension credibility breakdown for a single paper.

    Provide exactly one of:
    - **pmid**: PubMed ID (preferred; uses BioC JSON full-text, includes `per_dimension`)
    - **doi**: DOI string
    """
    active_tf = resolve_truth_filter(request.weights, tf)
    raw: dict | None = None
    try:
        if request.pmid:
            raw = active_tf.score_single_by_pmid(request.pmid)
        else:
            raw = active_tf.score_single(request.doi)  # type: ignore[arg-type]
    except Exception as exc:
        logger.error("explain failed for %s: %s", request.pmid or request.doi, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if raw is None:
        identifier = f"PMID {request.pmid}" if request.pmid else f"DOI {request.doi}"
        raise HTTPException(
            status_code=404,
            detail=f"Paper not found or could not be scored: {identifier}",
        )

    return PaperResult.from_dict(raw)
