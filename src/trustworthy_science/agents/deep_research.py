"""Deep Research query generator agent.

Given a short user prompt describing a research task, this agent uses the K2 LLM
to generate 3–5 diverse, MeSH-aware PubMed search queries covering different
angles of the research topic.

The agent is entirely domain-agnostic — it works for any research area.

Node function signature (LangGraph-compatible):
    query_generator_agent(state: DeepResearchState) -> dict
"""

from __future__ import annotations

import json
import logging
import re

from trustworthy_science.llm import get_llm, strip_think_tokens

logger = logging.getLogger(__name__)

_QUERY_GEN_PROMPT = """\
You are a biomedical literature search expert with deep knowledge of PubMed and MeSH terms.

A researcher has described their task:
"{user_prompt}"

Generate between 3 and 5 diverse PubMed search queries that together would retrieve \
the most relevant literature for this task. The queries should:
- Cover different aspects and sub-topics of the research question
- Use MeSH terms where appropriate (e.g. "GLP-1 receptor agonists[MeSH]")
- Vary in specificity — include at least one broad and one narrow query
- Be independent of one another so they retrieve different papers

Respond with ONLY a JSON array of strings, nothing else. Example format:
["query one", "query two", "query three"]
"""


def query_generator_agent(state, config: dict | None = None) -> dict:
    """Node: generate diverse PubMed search queries from the user's research prompt.

    Parameters
    ----------
    state:
        DeepResearchState with ``user_prompt`` set.
    config:
        Optional scoring/LLM config dict.

    Returns
    -------
    dict with key ``generated_queries`` (list[str]).
    """
    user_prompt = getattr(state, "user_prompt", "") or ""
    logger.info("[QUERY_GEN] Generating queries for prompt: %s", user_prompt[:100])

    queries = _call_llm(user_prompt, config)

    if not queries:
        # Deterministic fallback: use the prompt itself as a single query
        logger.warning("[QUERY_GEN] LLM query generation failed; using raw prompt as query")
        queries = [user_prompt]

    logger.info("[QUERY_GEN] Generated %d queries: %s", len(queries), queries)
    return {"generated_queries": queries}


def generate_queries(user_prompt: str, config: dict | None = None) -> list[str]:
    """Public helper: generate PubMed queries from a user prompt (no state required).

    Returns a list of 1–5 query strings. Falls back to [user_prompt] on any error.
    """
    queries = _call_llm(user_prompt, config)
    return queries if queries else [user_prompt]


def _call_llm(user_prompt: str, config: dict | None) -> list[str]:
    """Call the K2 LLM to generate search queries; return parsed list."""
    prompt = _QUERY_GEN_PROMPT.format(user_prompt=user_prompt)
    try:
        llm = get_llm(max_tokens=400, config=config)
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = strip_think_tokens(response.content)
        return _parse_queries(raw)
    except Exception as exc:
        logger.warning("[QUERY_GEN] LLM call failed: %s", exc)
        return []


def _parse_queries(raw: str) -> list[str]:
    """Parse a JSON array of strings from the LLM response.

    Tolerates extra text before/after the JSON array.
    """
    # Find JSON array in the response
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if not match:
        logger.warning("[QUERY_GEN] Could not find JSON array in response: %s", raw[:200])
        return []
    try:
        queries = json.loads(match.group())
        if isinstance(queries, list):
            # Keep only non-empty strings, limit to 5
            return [str(q).strip() for q in queries if q and str(q).strip()][:5]
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("[QUERY_GEN] JSON parse failed: %s | raw: %s", exc, raw[:200])
    return []
