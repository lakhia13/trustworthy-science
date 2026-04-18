"""Literature Review generator — RAG-grounded review from ChromaDB collection.

Given a user's research prompt and a ChromaDB collection populated with scored
papers, this agent:
1. Retrieves the most relevant chunks from ChromaDB.
2. Grounds the LLM prompt in the retrieved sources.
3. Returns a LiteratureReview with inline citations.

Public API
----------
- ``generate_literature_review(user_prompt, collection_name, config)``
  → LiteratureReview
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from trustworthy_science.llm import get_llm, strip_think_tokens
from trustworthy_science.tools.chroma_store import query_collection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

class LiteratureReview(BaseModel):
    """The output of the literature review generation agent."""
    narrative: str = ""
    cited_papers: list[dict[str, Any]] = Field(default_factory=list)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    collection_name: str = ""
    user_prompt: str = ""


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_REVIEW_PROMPT = """\
You are a scientific literature review assistant. Your task is to write a \
concise, well-structured literature review based on the research question and \
the provided source excerpts.

Research question: "{user_prompt}"

Available sources (cite them using the format [Author Year] or [Title, Year, DOI]):
{sources_block}

Instructions:
- Write a literature review of 3-5 paragraphs.
- Each paragraph should address a different aspect or theme.
- Cite sources inline using the format: (Title, Year) or (Author et al., Year).
- Only cite sources from the list above — do not introduce outside references.
- Highlight areas of consensus and any conflicting findings.
- End with a brief synthesis paragraph noting gaps or future directions.
- Use plain prose, no markdown headers, no bullet points.
"""


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def generate_literature_review(
    user_prompt: str,
    collection_name: str,
    config: dict | None = None,
    k: int = 8,
) -> LiteratureReview:
    """Generate a RAG-grounded literature review.

    Parameters
    ----------
    user_prompt:
        The original research question / task description.
    collection_name:
        ChromaDB collection to retrieve from.
    config:
        Optional config dict (passed to LLM and ChromaDB).
    k:
        Number of source chunks to retrieve.

    Returns
    -------
    LiteratureReview
    """
    logger.info("[LIT_REVIEW] Generating review for: %s", user_prompt[:80])

    # Retrieve relevant chunks
    chunks = query_collection(user_prompt, collection_name, config=config, k=k)

    if not chunks:
        logger.warning("[LIT_REVIEW] No chunks retrieved from '%s'", collection_name)
        return LiteratureReview(
            narrative="No relevant literature was found in the research database.",
            collection_name=collection_name,
            user_prompt=user_prompt,
        )

    # Build source block and cited_papers index
    sources_block, cited_papers = _build_sources_block(chunks)

    prompt = _REVIEW_PROMPT.format(
        user_prompt=user_prompt,
        sources_block=sources_block,
    )

    try:
        llm = get_llm(max_tokens=1200, config=config)
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        narrative = strip_think_tokens(response.content)
    except Exception as exc:
        logger.warning("[LIT_REVIEW] LLM call failed: %s", exc)
        narrative = _fallback_narrative(user_prompt, cited_papers)

    return LiteratureReview(
        narrative=narrative,
        cited_papers=cited_papers,
        collection_name=collection_name,
        user_prompt=user_prompt,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_sources_block(chunks: list[dict]) -> tuple[str, list[dict]]:
    """Build the numbered source listing and deduplicated cited_papers list."""
    seen_dois: set[str] = set()
    cited_papers: list[dict] = []
    lines: list[str] = []

    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title", "Unknown")
        year = chunk.get("year", "")
        doi = chunk.get("doi", "")
        score = chunk.get("score", 0)
        tier = chunk.get("tier", "")
        text = chunk.get("text", "")

        # Deduplicate by DOI (or title if no DOI)
        dedup_key = doi or title
        if dedup_key not in seen_dois:
            seen_dois.add(dedup_key)
            cited_papers.append({
                "title": title,
                "year": year,
                "doi": doi,
                "score": score,
                "tier": tier,
            })

        lines.append(
            f"[{i}] {title} ({year})"
            + (f" — DOI: {doi}" if doi else "")
            + f"\nTrust score: {score}/100 ({tier})"
            + f"\nExcerpt: {text[:400]}"
        )

    return "\n\n".join(lines), cited_papers


def _fallback_narrative(user_prompt: str, cited_papers: list[dict]) -> str:
    """Deterministic fallback when the LLM is unavailable."""
    if not cited_papers:
        return "No relevant literature was found."
    titles = "; ".join(
        f"{p['title']} ({p.get('year', '')})" for p in cited_papers[:5]
    )
    return (
        f"Based on the retrieved literature for '{user_prompt}', the following "
        f"papers were identified as relevant: {titles}. "
        "A full narrative review could not be generated at this time."
    )
