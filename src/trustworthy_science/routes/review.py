"""
Literature Review Session endpoints — Graph RAG pipeline.

Routes:
  POST /review/start               → create session
  POST /review/{id}/add            → score & add papers to graph
  GET  /review/{id}/graph          → get graph nodes + edges for visualization
  POST /review/{id}/query          → query graph, get LLM answer
  GET  /review/{id}/stats          → session stats
  DELETE /review/{id}              → delete session
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trustworthy_science.graph_rag.session import (
    create_session,
    delete_session,
    get_session,
    list_sessions,
)
from trustworthy_science.graph_rag.pipeline import add_papers_to_session, query_session

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StartSessionResponse(BaseModel):
    session_id: str
    message: str = "Literature review session created"


class AddPapersRequest(BaseModel):
    dois: list[str] = Field(default_factory=list)
    query: str | None = None
    top_k: int = Field(default=10, ge=1, le=50)


class PaperSummary(BaseModel):
    doi: str
    title: str
    score: int
    tier: str
    reason: str | None = None


class AddPapersResponse(BaseModel):
    added: list[PaperSummary]
    excluded: list[PaperSummary]
    graph_size: int
    graph_stats: dict
    took_seconds: float


class GraphNode(BaseModel):
    id: str
    title: str
    score: int
    tier: str
    year: int | None = None
    venue: str = ""
    hard_flags: list[str] = Field(default_factory=list)
    soft_flags: list[str] = Field(default_factory=list)
    quality_signals: list[str] = Field(default_factory=list)
    val: int = 4  # visual size hint


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str  # "CITES" | "SHARES_TOPIC"


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: dict


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class PaperUsed(BaseModel):
    doi: str
    title: str
    score: int
    tier: str


class QueryResponse(BaseModel):
    answer: str
    papers_used: list[PaperUsed]
    graph_size: int
    took_seconds: float


class SessionStats(BaseModel):
    session_id: str
    graph_stats: dict
    query_count: int
    total_scored: int
    total_added: int
    total_excluded: int
    created_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StartSessionResponse, summary="Start a new literature review session")
async def start_session():
    """Create a new isolated literature review session with an empty knowledge graph."""
    session = create_session()
    logger.info(f"Created session: {session.session_id}")
    return StartSessionResponse(session_id=session.session_id)


@router.post("/{session_id}/add", response_model=AddPapersResponse, summary="Score papers and add credible ones to graph")
async def add_papers(session_id: str, request: AddPapersRequest):
    """
    Score papers by DOI list or query, then add Trusted/Caution papers to the session graph.
    Untrusted papers are excluded — they will never reach the LLM.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    if not request.dois and not request.query:
        raise HTTPException(status_code=400, detail="Either 'dois' or 'query' must be provided")

    try:
        result = await add_papers_to_session(
            session=session,
            dois=request.dois,
            query=request.query,
            top_k=request.top_k,
        )
        return AddPapersResponse(
            added=[PaperSummary(**p) for p in result["added"]],
            excluded=[PaperSummary(**p) for p in result["excluded"]],
            graph_size=result["graph_size"],
            graph_stats=result["graph_stats"],
            took_seconds=result["took_seconds"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding papers to session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/{session_id}/graph", response_model=GraphResponse, summary="Get graph data for visualization")
async def get_graph(session_id: str):
    """
    Return the full knowledge graph as nodes and edges for frontend visualization.
    Nodes are color-coded by tier; edges show citation and topic relationships.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    vis_data = session.graph.to_vis_json()

    nodes = [GraphNode(**n) for n in vis_data["nodes"]]
    edges = [GraphEdge(**e) for e in vis_data["edges"]]

    return GraphResponse(nodes=nodes, edges=edges, stats=session.graph.stats())


@router.post("/{session_id}/query", response_model=QueryResponse, summary="Query the knowledge graph")
async def query_graph(session_id: str, request: QueryRequest):
    """
    Answer a research question using only the trusted papers in the knowledge graph.

    The graph is traversed from keyword-matched anchor papers to their trusted neighbors.
    The LLM is strictly instructed to cite by DOI and not hallucinate.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    try:
        result = await query_session(
            session=session,
            question=request.question,
            top_k=request.top_k,
        )
        return QueryResponse(
            answer=result["answer"],
            papers_used=[PaperUsed(**p) for p in result["papers_used"]],
            graph_size=result["graph_size"],
            took_seconds=result["took_seconds"],
        )
    except Exception as e:
        logger.error(f"Error querying session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/{session_id}/stats", response_model=SessionStats, summary="Get session statistics")
async def get_session_stats(session_id: str):
    """Return stats for a session: papers added, excluded, queries made, graph size."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return SessionStats(
        session_id=session.session_id,
        graph_stats=session.graph.stats(),
        query_count=len(session.query_history),
        total_scored=session.total_scored,
        total_added=session.total_added,
        total_excluded=session.total_excluded,
        created_at=session.created_at.isoformat(),
    )


@router.delete("/{session_id}", summary="Delete a session")
async def delete_review_session(session_id: str):
    """Delete a session and free its memory."""
    if delete_session(session_id):
        return {"message": f"Session '{session_id}' deleted"}
    raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
