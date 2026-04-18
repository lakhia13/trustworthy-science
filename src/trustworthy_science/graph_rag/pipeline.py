"""
Graph RAG pipeline: score papers → add trusted ones → query with LLM.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from trustworthy_science.llm import get_llm
from trustworthy_science.graph_rag.session import QueryRecord, ReviewSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reasoning-strip helper
# ---------------------------------------------------------------------------

def _strip_reasoning(text: str) -> str:
    """
    Remove chain-of-thought/reasoning content from K2-Think-v2 output.

    Handles 3 patterns:
      1. <think>...</think> or <thinking>...</thinking> blocks
      2. Orphan </think> (reasoning without opening tag) — take everything after
      3. Reasoning paragraphs that start with known meta-phrases followed by
         a blank line + the real answer
    """
    # Pattern 1 & 2 — XML-style tags
    cleaned = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", text, flags=re.DOTALL)
    if re.search(r"</think(?:ing)?>", cleaned):
        parts = re.split(r"</think(?:ing)?>", cleaned, maxsplit=1)
        cleaned = parts[-1]

    # Pattern 3 — reasoning paragraphs (heuristic)
    # If text starts with a known reasoning opener and contains a blank line,
    # everything before the LAST blank-line boundary is likely reasoning.
    reasoning_openers = (
        "we need to", "let me ", "let's ", "i need to", "the user",
        "the question is", "first, ", "okay, ", "alright,",
        "so we have", "looking at", "thus final", "we must",
    )
    first_line = cleaned.lstrip().split("\n")[0].lower()
    if any(first_line.startswith(op) for op in reasoning_openers):
        # Split on double newline — take the last non-empty paragraph
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
        if len(paragraphs) > 1:
            cleaned = paragraphs[-1]

    return cleaned.strip()


# ---------------------------------------------------------------------------
# LLM system prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a rigorous biomedical research assistant.

OUTPUT FORMAT — STRICT:
- Output ONLY the final answer. Do NOT show reasoning, thinking steps, or "let me consider" text.
- Start your response immediately with the answer content.
- Cite every factual claim with the paper DOI in square brackets: [10.xxxx/xxxxx]
- End with exactly one line: "Confidence: HIGH/MEDIUM/LOW — <one-sentence reason>"
- Length: 3–6 sentences total (be concise)

CONTENT RULES:
- Answer ONLY from the provided papers — never use external knowledge
- If the papers lack enough data to answer, say so clearly and cite which papers were checked
- Use precise scientific language (no "basically", "simply", "in essence")
"""


# ---------------------------------------------------------------------------
# Add papers to a session
# ---------------------------------------------------------------------------

async def add_papers_to_session(
    session: ReviewSession,
    dois: list[str] | None = None,
    query: str | None = None,
    top_k: int = 10,
) -> dict[str, Any]:
    """
    Score papers via TruthFilter, add Trusted/Caution to the session graph.

    Returns a summary of what was added and excluded.
    """
    # Import here to avoid circular imports
    from trustworthy_science.service import get_truth_filter

    if not dois and not query:
        raise ValueError("Either 'dois' or 'query' must be provided")

    start = time.time()
    tf = get_truth_filter()

    logger.info(f"[Session {session.session_id}] Scoring papers: dois={dois}, query={query}")

    reports = tf.score_papers(dois=dois or [], query=query, top_k=top_k)

    added = []
    excluded = []

    for report in reports:
        tier = report.get("tier", "Untrusted")
        doi = report.get("doi", "unknown")
        title = report.get("title", "")
        score = report.get("score") or report.get("composite_score") or 0

        entry = {
            "doi": doi,
            "title": title,
            "score": score,
            "tier": tier,
        }

        if session.graph.add_paper(report):
            added.append(entry)
        else:
            entry["reason"] = "Untrusted — excluded from knowledge graph"
            excluded.append(entry)

    # Update session tallies
    session.total_scored += len(reports)
    session.total_added += len(added)
    session.total_excluded += len(excluded)

    took = time.time() - start
    logger.info(
        f"[Session {session.session_id}] Added {len(added)}, excluded {len(excluded)} "
        f"in {took:.2f}s. Graph size: {session.graph.size}"
    )

    return {
        "added": added,
        "excluded": excluded,
        "graph_size": session.graph.size,
        "graph_stats": session.graph.stats(),
        "took_seconds": took,
    }


# ---------------------------------------------------------------------------
# Query the session graph
# ---------------------------------------------------------------------------

async def query_session(
    session: ReviewSession,
    question: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    Find relevant trusted papers via graph traversal, then answer with LLM.
    """
    if session.graph.size == 0:
        return {
            "answer": "No papers in the knowledge graph yet. Please add papers first.",
            "papers_used": [],
            "graph_size": 0,
            "took_seconds": 0.0,
        }

    start = time.time()

    # Step 1: Graph traversal to find relevant papers
    relevant_papers = session.graph.query(question, top_k=top_k)

    if not relevant_papers:
        return {
            "answer": "Could not find relevant papers in the knowledge graph for this question.",
            "papers_used": [],
            "graph_size": session.graph.size,
            "took_seconds": time.time() - start,
        }

    # Step 2: Format context for LLM
    context_parts = []
    for i, paper in enumerate(relevant_papers, 1):
        doi = paper.get("doi", "unknown")
        title = paper.get("title", "Untitled")
        year = paper.get("year", "")
        venue = paper.get("venue", "")
        abstract = paper.get("abstract", "")
        score = paper.get("score") or paper.get("composite_score") or 0
        tier = paper.get("tier", "Caution")
        soft_flags = paper.get("soft_flags", [])

        flags_note = ""
        if soft_flags:
            flags_str = ", ".join(soft_flags[:3]) if isinstance(soft_flags[0], str) else ", ".join(f.get("code", "") for f in soft_flags[:3])
            flags_note = f"\n  ⚠ Flags: {flags_str}"

        context_parts.append(
            f"[{i}] DOI: {doi}\n"
            f"  Title: {title} ({year}, {venue})\n"
            f"  Trust Score: {score}/100 ({tier}){flags_note}\n"
            f"  Abstract: {abstract[:600]}{'...' if len(abstract) > 600 else ''}"
        )

    context = "\n\n".join(context_parts)

    user_message = (
        f"Research Question: {question}\n\n"
        f"Available Papers ({len(relevant_papers)}):\n\n{context}\n\n"
        f"Please answer the research question based strictly on the papers above."
    )

    # Step 3: Call LLM
    logger.info(f"[Session {session.session_id}] Querying LLM with {len(relevant_papers)} papers")

    try:
        llm = get_llm()
        response = await llm.ainvoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ])
        raw = response.content
        answer = _strip_reasoning(raw)
    except Exception as e:
        logger.error(f"LLM error: {e}")
        answer = f"LLM unavailable: {str(e)}. Papers retrieved: {[p.get('doi') for p in relevant_papers]}"

    took = time.time() - start

    # Step 4: Record in session history
    session.query_history.append(QueryRecord(
        question=question,
        answer=answer,
        papers_used=[p.get("doi", "") for p in relevant_papers],
        took_seconds=took,
    ))

    papers_used_summary = [
        {
            "doi": p.get("doi", ""),
            "title": p.get("title", ""),
            "score": p.get("score") or p.get("composite_score") or 0,
            "tier": p.get("tier", "Caution"),
        }
        for p in relevant_papers
    ]

    logger.info(f"[Session {session.session_id}] Query answered in {took:.2f}s")

    return {
        "answer": answer,
        "papers_used": papers_used_summary,
        "graph_size": session.graph.size,
        "took_seconds": took,
    }
