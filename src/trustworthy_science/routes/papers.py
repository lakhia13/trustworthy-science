"""API endpoints for scoring and filtering papers."""

import logging
import time
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from trustworthy_science.service import get_truth_filter
from trustworthy_science.schemas import (
    FilterRequest,
    FilterResponse,
    PaperDetailResponse,
    PaperWithDOISchema,
    ScoreRequest,
    ScoreResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _convert_report_to_schema(report: dict, doi: str | None = None) -> PaperWithDOISchema:
    """Convert a TrustReport dict to PaperWithDOISchema."""
    # Handle both "score" and "composite_score" field names
    score = report.get("composite_score") or report.get("score") or 0

    # Flags are returned as lists of strings (codes)
    hard_flags = report.get("hard_flags", [])
    soft_flags = report.get("soft_flags", [])
    quality_signals = report.get("quality_signals", [])

    return PaperWithDOISchema(
        doi=doi or report.get("doi"),
        title=report.get("title", ""),
        authors=report.get("authors", []),
        year=report.get("year"),
        venue=report.get("venue", ""),
        abstract=report.get("abstract", ""),
        composite_score=int(score) if score else None,
        score=int(score) if score else None,
        tier=report.get("tier", "Untrusted"),
        summary=report.get("summary", ""),
        hard_flags=hard_flags if isinstance(hard_flags, list) else [],
        soft_flags=soft_flags if isinstance(soft_flags, list) else [],
        quality_signals=quality_signals if isinstance(quality_signals, list) else [],
        per_dimension=report.get("per_dimension", {}),
        coverage=report.get("coverage", "metadata_only"),
    )


# ============================================================================
# POST /score — Score papers by DOI or query
# ============================================================================


@router.post(
    "/score",
    response_model=ScoreResponse,
    summary="Score papers by DOI or query",
    description="Score one or more papers using DOI list or natural-language query",
)
async def score_papers(request: ScoreRequest) -> ScoreResponse:
    """
    Score papers by DOI list or natural-language query.

    Either `dois` or `query` must be provided (not both empty).

    **Example:**
    ```json
    {
      "dois": ["10.1371/journal.pmed.1001231"],
      "top_k": 10
    }
    ```
    """
    if not request.dois and not request.query:
        raise HTTPException(
            status_code=400,
            detail="Either 'dois' or 'query' must be provided",
        )

    try:
        start = time.time()
        tf = get_truth_filter()

        logger.info(
            f"Scoring papers: dois={request.dois}, query={request.query}, top_k={request.top_k}"
        )

        reports = tf.score_papers(
            dois=request.dois,
            query=request.query,
            top_k=request.top_k,
        )

        # Convert reports to schema objects
        papers = [
            _convert_report_to_schema(r, r.get("doi"))
            for r in reports
        ]

        took = time.time() - start
        logger.info(f"Scored {len(papers)} papers in {took:.2f}s")

        return ScoreResponse(papers=papers, took_seconds=took)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError as e:
        logger.error(f"Timeout: {e}")
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        logger.error(f"Error scoring papers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# ============================================================================
# POST /filter — Filter papers for RAG
# ============================================================================


@router.post(
    "/filter",
    response_model=FilterResponse,
    summary="Filter papers for RAG input",
    description="Retrieve and filter papers by query, returning only papers above min_tier",
)
async def filter_for_rag(request: FilterRequest) -> FilterResponse:
    """
    Retrieve and filter papers for use in RAG pipelines.

    Returns only papers with tier >= `min_tier`, sorted by score (descending).

    **Example:**
    ```json
    {
      "query": "GLP-1 receptor agonists",
      "top_k": 20,
      "min_tier": "Caution"
    }
    ```
    """
    try:
        start = time.time()
        tf = get_truth_filter()

        logger.info(
            f"Filtering papers: query={request.query}, top_k={request.top_k}, min_tier={request.min_tier}"
        )

        reports = tf.filter_for_rag(
            query=request.query,
            top_k=request.top_k,
            min_tier=request.min_tier,
        )

        # Convert reports to schema objects
        papers = [
            _convert_report_to_schema(r, r.get("doi"))
            for r in reports
        ]

        took = time.time() - start
        logger.info(f"Filtered {len(papers)} papers in {took:.2f}s")

        return FilterResponse(papers=papers, took_seconds=took)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError as e:
        logger.error(f"Timeout: {e}")
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        logger.error(f"Error filtering papers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# ============================================================================
# GET /paper/{doi} — Get single paper detail
# ============================================================================


@router.get(
    "/paper/{doi:path}",
    response_model=PaperDetailResponse,
    summary="Get detailed credibility report for a single paper",
    description="Fetch the complete credibility assessment for a paper by DOI",
)
async def get_paper_detail(doi: str) -> PaperDetailResponse:
    """
    Get detailed credibility report for a single paper.

    The DOI will be URL-decoded automatically.

    **Example:**
    ```
    GET /paper/10.1371%2Fjournal.pmed.1001231
    ```
    """
    try:
        # URL-decode the DOI
        decoded_doi = unquote(doi)

        start = time.time()
        tf = get_truth_filter()

        logger.info(f"Fetching paper: {decoded_doi}")

        report = tf.score_single(decoded_doi)

        # Convert to schema object
        paper = _convert_report_to_schema(report, decoded_doi)

        took = time.time() - start
        logger.info(f"Fetched paper in {took:.2f}s")

        return PaperDetailResponse(paper=paper, took_seconds=took)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError as e:
        logger.error(f"Timeout: {e}")
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        logger.error(f"Error fetching paper: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
