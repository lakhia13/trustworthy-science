"""Research Chat agent — conversational Q&A backed by a ChromaDB collection.

Maintains per-session conversation history and grounds every LLM response in
retrieved chunks from the paper collection, so all answers carry citations.

Public API
----------
- ``chat(session_id, user_message, collection_name, config)`` → str
- ``clear_session(session_id)`` → None
- ``get_history(session_id)`` → list[dict]
"""

from __future__ import annotations

import logging
from typing import Any

from trustworthy_science.llm import get_llm, strip_think_tokens
from trustworthy_science.tools.chroma_store import query_collection

logger = logging.getLogger(__name__)

# In-memory session store: session_id → list of {"role": str, "content": str}
_sessions: dict[str, list[dict[str, str]]] = {}

_SYSTEM_PROMPT = """\
You are a scientific research assistant with access to a curated library of \
peer-reviewed papers that have been pre-screened for credibility. \
You answer questions by drawing exclusively on the provided source excerpts. \
Always cite your sources inline using the format (Title, Year) or (Author et al., Year). \
If the provided sources do not contain enough information to answer a question, \
say so explicitly rather than speculating.
"""

_CONTEXT_PROMPT = """\
Relevant source excerpts for this question:
{sources_block}

Conversation so far:
{history}

User: {user_message}

Assistant (cite sources inline):"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chat(
    session_id: str,
    user_message: str,
    collection_name: str,
    config: dict | None = None,
    k: int = 5,
) -> str:
    """Send a user message and receive a grounded, citation-backed response.

    Parameters
    ----------
    session_id:
        Unique identifier for this conversation session. Use the ``session_id``
        from a LiteratureReview to continue the same context.
    user_message:
        The user's question or follow-up.
    collection_name:
        ChromaDB collection to retrieve from.
    config:
        Optional config dict.
    k:
        Number of source chunks to retrieve per turn.

    Returns
    -------
    str
        The assistant's response with inline citations.
    """
    logger.info("[CHAT] session=%s | message=%s", session_id, user_message[:80])

    # Retrieve relevant chunks for this specific question
    chunks = query_collection(user_message, collection_name, config=config, k=k)
    sources_block = _format_sources(chunks)

    # Get or create session history
    history = _sessions.setdefault(session_id, [])
    history_text = _format_history(history)

    prompt = _CONTEXT_PROMPT.format(
        sources_block=sources_block or "No relevant sources found.",
        history=history_text or "(start of conversation)",
        user_message=user_message,
    )

    try:
        llm = get_llm(max_tokens=700, config=config)
        from langchain_core.messages import SystemMessage, HumanMessage
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        answer = strip_think_tokens(response.content)
    except Exception as exc:
        logger.warning("[CHAT] LLM call failed: %s", exc)
        answer = _fallback_answer(user_message, chunks)

    # Persist turn to history
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": answer})

    # Keep only last 10 turns (20 messages) to avoid context blowout
    if len(history) > 20:
        _sessions[session_id] = history[-20:]

    return answer


def clear_session(session_id: str) -> None:
    """Remove a session's conversation history from memory."""
    _sessions.pop(session_id, None)
    logger.info("[CHAT] Cleared session: %s", session_id)


def get_history(session_id: str) -> list[dict[str, str]]:
    """Return the full conversation history for a session."""
    return list(_sessions.get(session_id, []))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_sources(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return ""
    lines: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title", "Unknown")
        year = chunk.get("year", "")
        doi = chunk.get("doi", "")
        text = chunk.get("text", "")
        lines.append(
            f"[{i}] {title} ({year})"
            + (f" DOI: {doi}" if doi else "")
            + f"\n{text[:350]}"
        )
    return "\n\n".join(lines)


def _format_history(history: list[dict[str, str]]) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for turn in history[-6:]:  # last 3 exchanges
        role = turn.get("role", "").capitalize()
        content = turn.get("content", "")
        lines.append(f"{role}: {content[:300]}")
    return "\n".join(lines)


def _fallback_answer(user_message: str, chunks: list[dict[str, Any]]) -> str:
    """Deterministic fallback when the LLM is unavailable."""
    if not chunks:
        return (
            "I was unable to retrieve relevant sources for your question. "
            "Please try rephrasing or check that the research collection has been populated."
        )
    titles = "; ".join(
        f"{c.get('title', 'Unknown')} ({c.get('year', '')})" for c in chunks[:3]
    )
    return (
        f"Based on available sources for '{user_message}', the most relevant papers are: "
        f"{titles}. A full answer could not be generated at this time."
    )
