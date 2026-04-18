"""
In-memory session store for Literature Review sessions.

Each session has its own isolated LiteratureGraph.
Sessions are keyed by UUID, stored in a module-level dict (demo-suitable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from trustworthy_science.graph_rag.knowledge_graph import LiteratureGraph


@dataclass
class QueryRecord:
    question: str
    answer: str
    papers_used: list[str]       # list of DOIs
    took_seconds: float
    asked_at: datetime = field(default_factory=datetime.now)


@dataclass
class ReviewSession:
    session_id: str
    graph: LiteratureGraph = field(default_factory=LiteratureGraph)
    query_history: list[QueryRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    # Running tallies
    total_scored: int = 0
    total_added: int = 0
    total_excluded: int = 0


# ---------------------------------------------------------------------------
# Module-level session registry
# ---------------------------------------------------------------------------

_sessions: dict[str, ReviewSession] = {}


def create_session() -> ReviewSession:
    """Create a new isolated literature review session."""
    session_id = str(uuid4())
    session = ReviewSession(session_id=session_id)
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> ReviewSession | None:
    """Retrieve an existing session by ID. Returns None if not found."""
    return _sessions.get(session_id)


def delete_session(session_id: str) -> bool:
    """Delete a session. Returns True if it existed."""
    if session_id in _sessions:
        del _sessions[session_id]
        return True
    return False


def list_sessions() -> list[dict]:
    """List all active sessions (for debugging)."""
    return [
        {
            "session_id": s.session_id,
            "created_at": s.created_at.isoformat(),
            "papers_in_graph": s.graph.size,
            "queries": len(s.query_history),
        }
        for s in _sessions.values()
    ]
