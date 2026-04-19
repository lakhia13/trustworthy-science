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
    top_k: int = Field(default=20, ge=1, le=50, description="Max papers to fetch and score.")
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


def _run_deep_research(request: DeepResearchRequest, tf: TruthFilter, job_id: str) -> None:  # noqa: C901
    """Background task: run the full deep research pipeline and update status per-phase."""
    import hashlib
    from trustworthy_science.agents.deep_research import _run_librarian_agent
    from trustworthy_science.agents.literature_review import generate_literature_review
    from trustworthy_science.graph import _make_paper_graph
    from trustworthy_science.state import PaperState
    from trustworthy_science.tools.pubmed import fetch_pubmed_metadata, search_pubmed
    from trustworthy_science.tools.chroma_store import ingest_papers

    logger.info("[DEEP_RESEARCH_ROUTE] Starting job %s", job_id)
    cfg = tf._config or {}
    tier_order: Dict[str, int] = {"Trusted": 2, "Caution": 1, "Untrusted": 0}

    _job_status[job_id] = DeepResearchJobStatus(status="running")

    try:
        # ── Phase 1: generate MeSH-validated PubMed queries ──────────────────
        queries, mesh_terms = _run_librarian_agent(request.prompt, config=cfg)
        if not queries:
            queries = [request.prompt]
            mesh_terms = []

        collection = request.collection_name or (
            "research_" + hashlib.sha256(request.prompt.encode()).hexdigest()[:12]
        )

        _job_status[job_id] = DeepResearchJobStatus(
            status="running",
            generated_queries=queries,
            mesh_terms=mesh_terms,
            collection_name=collection,
        )
        logger.info("[DEEP_RESEARCH_ROUTE] [%s] Phase 1 done: %d queries", job_id, len(queries))

        # ── Phase 2: retrieve papers from PubMed ─────────────────────────────
        max_papers = min(request.top_k, 50)
        per_query = max(3, max_papers // max(len(queries), 1))
        stubs = []
        seen: set = set()
        query_metadata: List[dict] = []

        for query in queries:
            try:
                pmids = search_pubmed(query, max_results=per_query)
                new_stubs = fetch_pubmed_metadata(pmids)
                for stub in new_stubs:
                    key = stub.doi or stub.pmid or stub.title
                    if key and key not in seen:
                        seen.add(key)
                        stubs.append(stub)
                query_metadata.append({"query": query, "pmid_count": len(pmids)})
            except Exception as exc:
                logger.warning("[DEEP_RESEARCH_ROUTE] PubMed fetch failed: %s", exc)
                query_metadata.append({"query": query, "pmid_count": 0})

        stubs = stubs[:max_papers]

        _job_status[job_id] = DeepResearchJobStatus(
            status="running",
            generated_queries=queries,
            mesh_terms=mesh_terms,
            collection_name=collection,
            query_metadata=query_metadata,
        )
        logger.info("[DEEP_RESEARCH_ROUTE] [%s] Phase 2 done: %d stubs", job_id, len(stubs))

        # ── Phase 3: score every stub through the per-paper graph ────────────
        paper_graph = _make_paper_graph(cfg)
        scored: List[dict] = []

        for stub in stubs:
            paper_state = PaperState(stub=stub)
            try:
                final_state = paper_graph.invoke(paper_state)
                ps = PaperState(**final_state)
            except Exception as exc:
                logger.warning("[DEEP_RESEARCH_ROUTE] Scoring failed for %s: %s", stub.uid, exc)
                continue
            if ps.final:
                scored.append({
                    "title": ps.stub.title,
                    "doi": ps.stub.doi,
                    "pmid": ps.stub.pmid,
                    "year": ps.stub.year,
                    "venue": ps.stub.venue,
                    "score": ps.final.composite_score,
                    "tier": ps.final.tier,
                    "coverage": ps.final.coverage,
                    "summary": ps.final.summary,
                    "hard_flags": [f.code for f in ps.final.hard_flags],
                    "soft_flags": [f.code for f in ps.final.soft_flags],
                    "quality_signals": [f.code for f in ps.final.quality_signals],
                    "structured_report": ps.final.structured_report,
                })

        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        min_val = tier_order.get(request.min_tier, 1)
        accepted = [p for p in scored if tier_order.get(p.get("tier", "Untrusted"), 0) >= min_val]

        _job_status[job_id] = DeepResearchJobStatus(
            status="running",
            generated_queries=queries,
            mesh_terms=mesh_terms,
            collection_name=collection,
            query_metadata=query_metadata,
            scored_papers=_coerce_paper_list(scored),
            accepted_papers=_coerce_paper_list(accepted),
        )
        logger.info(
            "[DEEP_RESEARCH_ROUTE] [%s] Phase 3 done: %d scored, %d accepted",
            job_id, len(scored), len(accepted),
        )

        # ── Phase 4: ingest into ChromaDB + generate literature review ────────
        if accepted and collection:
            try:
                n = ingest_papers(accepted, collection, config=cfg)
                logger.info("[DEEP_RESEARCH_ROUTE] Ingested %d chunks into '%s'", n, collection)
            except Exception as exc:
                logger.error("[DEEP_RESEARCH_ROUTE] ChromaDB ingest failed: %s", exc)

        review = generate_literature_review(
            user_prompt=request.prompt,
            collection_name=collection,
            config=cfg,
        )

        _job_status[job_id] = DeepResearchJobStatus(
            status="completed",
            collection_name=collection,
            generated_queries=queries,
            mesh_terms=mesh_terms,
            query_metadata=query_metadata,
            scored_papers=_coerce_paper_list(scored),
            accepted_papers=_coerce_paper_list(accepted),
            literature_review=review.narrative,
            cited_papers=_coerce_paper_list(review.cited_papers),
            session_id=review.session_id,
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
