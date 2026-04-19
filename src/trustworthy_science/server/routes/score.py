from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException
from trustworthy_science.server.schemas import PaperResult, ScoreRequest, ScoreResponse
from trustworthy_science.server.dependencies import get_truth_filter
from trustworthy_science.api import TruthFilter

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("", response_model=ScoreResponse, summary="Score papers by DOI, PMID, or query")
def score_papers(request: ScoreRequest, tf: TruthFilter = Depends(get_truth_filter)) -> ScoreResponse:
    """Score one or more papers and return trust scores with flags.

    Supply any combination of:
    - **dois**: list of DOI strings
    - **pmids**: list of PubMed IDs (enables BioC JSON full-text fetch)
    - **query**: natural-language research question (retrieves top_k papers)
    """
    results: list[PaperResult] = []
    seen: set[str] = set()  # deduplicate by doi or pmid

    # Score PMIDs first (highest quality path via BioC JSON)
    for pmid in request.pmids:
        try:
            raw = tf.score_single_by_pmid(pmid)
            if raw:
                key = raw.get("doi") or raw.get("pmid") or pmid
                if key not in seen:
                    seen.add(key)
                    results.append(PaperResult.from_dict(raw))
        except Exception as exc:
            logger.warning("PMID %s scoring failed: %s", pmid, exc)

    # Score DOIs / query via multi-paper graph
    if request.dois or request.query:
        try:
            raw_list = tf.score_papers(
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
