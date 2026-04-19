"""FastAPI routes for the Deep Research pipeline."""
from __future__ import annotations

import logging
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from trustworthy_science.api import TruthFilter
from trustworthy_science.server.dependencies import get_truth_filter, resolve_truth_filter
from trustworthy_science.server.schemas import PaperResult, ScoringWeights

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class DeepResearchRequest(BaseModel):
    prompt: str = Field(..., description="Short description of the research task.")
    top_k: int = Field(default=20, ge=1, le=30, description="Max papers to fetch and score.")
    min_tier: str = Field(default="Caution", description="Minimum credibility tier to include.")
    collection_name: Optional[str] = Field(default=None, description="Optional ChromaDB collection name.")
    weights: Optional[ScoringWeights] = Field(default=None, description="Optional per-request scoring weight overrides.")


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Session ID from a DeepResearch result.")
    message: str = Field(..., description="User's follow-up question.")
    collection_name: str = Field(..., description="ChromaDB collection to query.")


class DeepResearchJobStatus(BaseModel):
    status: str                                        # pending | running | completed | failed
    message: Optional[str] = None
    collection_name: Optional[str] = None
    generated_queries: List[str] = []
    mesh_terms: List[str] = []
    query_metadata: List[dict] = []
    accepted_papers: List[PaperResult] = []
    scored_papers: List[PaperResult] = []
    literature_review: Optional[str] = None
    cited_papers: List[PaperResult] = []
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str


# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

_job_status: Dict[str, DeepResearchJobStatus] = {}


def _coerce_paper_list(raw: list) -> List[PaperResult]:
    """Safely coerce a list of raw dicts to PaperResult objects.

    Each individual item is wrapped in try/except so a malformed paper dict
    (e.g. an unexpected ``tier`` literal) degrades gracefully to an empty
    ``PaperResult`` with a logged warning rather than failing the entire job.
    """
    results: List[PaperResult] = []
    for item in raw:
        try:
            if isinstance(item, PaperResult):
                results.append(item)
            elif isinstance(item, dict):
                results.append(PaperResult.from_dict(item))
            else:
                logger.warning("Unexpected paper item type %s; skipping", type(item))
        except Exception as exc:
            logger.warning("Could not coerce paper to PaperResult: %s", exc)
            results.append(PaperResult())
    return results


def _run_deep_research(request: DeepResearchRequest, tf: TruthFilter, job_id: str) -> None:
    """Background task: run the full deep research pipeline and store results."""
    logger.info("[DEEP_RESEARCH_ROUTE] Starting job %s", job_id)
    _job_status[job_id] = DeepResearchJobStatus(status="running")

    try:
        result = tf.deep_research(
            prompt=request.prompt,
            top_k=request.top_k,
            min_tier=request.min_tier,
            collection_name=request.collection_name,
        )
        _job_status[job_id] = DeepResearchJobStatus(
            status="completed",
            collection_name=result.get("collection_name"),
            generated_queries=result.get("generated_queries", []),
            mesh_terms=result.get("mesh_terms", []),
            query_metadata=result.get("query_metadata", []),
            accepted_papers=_coerce_paper_list(result.get("accepted_papers", [])),
            scored_papers=_coerce_paper_list(result.get("scored_papers", [])),
            literature_review=result.get("literature_review"),
            cited_papers=_coerce_paper_list(result.get("cited_papers", [])),
            session_id=result.get("session_id"),
        )
        logger.info("[DEEP_RESEARCH_ROUTE] Job %s completed", job_id)
    except Exception as exc:
        logger.error("[DEEP_RESEARCH_ROUTE] Job %s failed: %s", job_id, exc)
        _job_status[job_id] = DeepResearchJobStatus(status="failed", message=str(exc))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "",
    summary="Start a Deep Research pipeline job",
    response_model=dict,
)
def start_deep_research(
    request: DeepResearchRequest,
    background_tasks: BackgroundTasks,
    tf: TruthFilter = Depends(get_truth_filter),
) -> dict:
    """Start a background deep research pipeline.

    The pipeline:
    1. LLM generates PubMed search queries from your prompt.
    2. Papers are retrieved and scored by all credibility agents.
    3. Papers meeting ``min_tier`` are ingested into a ChromaDB collection.
    4. A literature review with inline citations is generated.

    Poll ``GET /api/deep-research/status/{job_id}`` to retrieve results.
    """
    job_id = str(uuid.uuid4())
    active_tf = resolve_truth_filter(request.weights, tf)
    background_tasks.add_task(_run_deep_research, request, active_tf, job_id)
    return {"job_id": job_id}


@router.get(
    "/status/{job_id}",
    response_model=DeepResearchJobStatus,
    summary="Get status of a Deep Research job",
)
def get_deep_research_status(job_id: str) -> DeepResearchJobStatus:
    """Return the current status and results of a deep research job."""
    status = _job_status.get(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return status


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with the Deep Research collection",
)
def deep_research_chat(
    request: ChatRequest,
    tf: TruthFilter = Depends(get_truth_filter),
) -> ChatResponse:
    """Send a follow-up question and receive a citation-grounded answer.

    Use the ``session_id`` from the deep research result to maintain
    conversation continuity across multiple turns.
    """
    from trustworthy_science.agents.research_chat import chat

    try:
        answer = chat(
            session_id=request.session_id,
            user_message=request.message,
            collection_name=request.collection_name,
            config=tf._config,
        )
    except Exception as exc:
        logger.error("[CHAT_ROUTE] Chat failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return ChatResponse(session_id=request.session_id, answer=answer)
