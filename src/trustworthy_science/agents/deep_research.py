"""Deep Research MeSH Librarian agent.

Two-phase pipeline:
  Phase 1 — Concept Extraction: LLM extracts PICO elements and candidate medical
             concepts from the user's research prompt as a JSON list.
  Phase 2 — Query Construction: For each concept, the agent calls ``mesh_lookup``
             to retrieve the official MeSH descriptor, then constructs 3–5 diverse
             Boolean PubMed queries from the validated descriptors.

The agent is entirely domain-agnostic — it works for any biomedical research area.

Node function signature (LangGraph-compatible):
    query_generator_agent(state: DeepResearchState) -> dict
"""

from __future__ import annotations

import json
import logging
import re
import time

from trustworthy_science.llm import get_llm, strip_think_tokens

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase 1 prompt — concept extraction (PICO)
# ---------------------------------------------------------------------------

_PHASE1_PROMPT = """\
You are a biomedical research assistant specialising in clinical research design.

A researcher has described their task:
"{user_prompt}"

Extract the key medical/clinical concepts from this task. Focus on:
- Population (patient group, disease, condition)
- Intervention (drug, procedure, therapy, device)
- Comparison (standard of care, placebo, alternative)
- Outcome (endpoints, biomarkers, measures)

Output ONLY a JSON array of the top 4–6 most important medical concept strings. \
Include specific clinical terms, not generic words like "patients" or "study". \
Example: ["Randomized Controlled Trial", "Antibiotic Resistance", "Gram-negative bacteria", \
"Minimum Inhibitory Concentration"]

Output the JSON array only, nothing else."""

# ---------------------------------------------------------------------------
# Phase 2 prompt — Boolean query construction from validated MeSH terms
# ---------------------------------------------------------------------------

_PHASE2_PROMPT = """\
You are a Medical Librarian at a research university. You have validated the \
following MeSH (Medical Subject Headings) descriptors for a research task:

Research task: "{user_prompt}"

Validated MeSH descriptors:
{mesh_results}

Using these validated MeSH descriptors, construct 3–5 diverse Boolean PubMed \
search queries. Rules:
- Use [Mesh] tag for validated MeSH descriptors (e.g. "Randomized Controlled Trials as Topic"[Mesh])
- Use [Title/Abstract] for free-text terms not in MeSH
- Connect concepts with AND/OR operators
- Include at least one BROAD query (single or two MeSH terms) and one NARROW \
  query (3+ terms combined with AND)
- Make queries independent so they retrieve different paper sets
- If a term was NOT FOUND in MeSH, use it as a [Title/Abstract] search instead

Output ONLY a JSON array of query strings, nothing else. Example:
["(\\"Depressive Disorder, Treatment-Resistant\\"[Mesh]) AND (\\"Ketamine\\"[Mesh])", \
"(\\"Depression\\"[Mesh]) AND (novel drug[Title/Abstract])"]"""


def query_generator_agent(state, config: dict | None = None) -> dict:
    """Node: generate diverse MeSH-validated PubMed search queries.

    Parameters
    ----------
    state:
        DeepResearchState with ``user_prompt`` set.
    config:
        Optional scoring/LLM config dict.

    Returns
    -------
    dict with keys ``generated_queries`` (list[str]) and ``mesh_terms`` (list[str]).
    """
    user_prompt = getattr(state, "user_prompt", "") or ""
    logger.info("[LIBRARIAN] Starting two-phase MeSH query generation for: %s", user_prompt[:100])

    queries, mesh_terms = _run_librarian_agent(user_prompt, config)

    if not queries:
        logger.warning("[LIBRARIAN] Query generation failed; using raw prompt as fallback")
        queries = [user_prompt]
        mesh_terms = []

    logger.info("[LIBRARIAN] Generated %d queries using %d MeSH terms", len(queries), len(mesh_terms))
    return {"generated_queries": queries, "mesh_terms": mesh_terms}


def generate_queries(user_prompt: str, config: dict | None = None) -> list[str]:
    """Public helper: generate PubMed queries from a user prompt (no state required).

    Returns a list of 1–5 query strings. Falls back to [user_prompt] on any error.
    """
    queries, _ = _run_librarian_agent(user_prompt, config)
    return queries if queries else [user_prompt]


# ---------------------------------------------------------------------------
# Two-phase librarian implementation
# ---------------------------------------------------------------------------

def _run_librarian_agent(user_prompt: str, config: dict | None) -> tuple[list[str], list[str]]:
    """Execute the two-phase MeSH librarian pipeline.

    Returns (queries, mesh_terms) — both lists may be empty on failure.
    """
    # Phase 1: extract PICO concepts
    concepts = _phase1_extract_concepts(user_prompt, config)
    if not concepts:
        logger.warning("[LIBRARIAN] Phase 1 concept extraction returned nothing")
        return [], []

    logger.info("[LIBRARIAN] Phase 1 extracted %d concepts: %s", len(concepts), concepts)

    # MeSH validation: look up each concept (cap at 6)
    from trustworthy_science.tools.mesh import batch_mesh_lookup
    mesh_results = batch_mesh_lookup(concepts, max_terms=6)

    # Collect only the validated descriptor names for display
    mesh_terms = []
    for kw, result in mesh_results.items():
        if result.startswith("VALID MeSH descriptor:"):
            descriptor = result.replace("VALID MeSH descriptor:", "").strip()
            mesh_terms.append(descriptor)

    logger.info("[LIBRARIAN] MeSH validation: %d/%d concepts validated",
                len(mesh_terms), len(concepts))

    # Phase 2: construct Boolean PubMed queries
    queries = _phase2_construct_queries(user_prompt, mesh_results, config)

    # Post-process: if fewer than 2 queries contain [Mesh], warn and supplement
    mesh_query_count = sum(1 for q in queries if "[mesh]" in q.lower())
    if mesh_query_count < 2 and concepts:
        logger.warning(
            "[LIBRARIAN] Only %d queries contain [Mesh] tags; "
            "appending fallback keyword queries", mesh_query_count
        )
        # Supplement with simple keyword queries from raw concepts
        for concept in concepts[:3]:
            kw_query = f'"{concept}"[Title/Abstract]'
            if kw_query not in queries:
                queries.append(kw_query)
                if len(queries) >= 5:
                    break

    return queries[:5], mesh_terms


def _phase1_extract_concepts(user_prompt: str, config: dict | None) -> list[str]:
    """Phase 1: call LLM to extract PICO concepts as a JSON list."""
    prompt = _PHASE1_PROMPT.format(user_prompt=user_prompt)
    try:
        llm = get_llm(max_tokens=400, config=config)
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = strip_think_tokens(response.content)
        return _parse_json_array(raw)
    except Exception as exc:
        logger.warning("[LIBRARIAN] Phase 1 LLM call failed: %s", exc)
        return []


def _phase2_construct_queries(
    user_prompt: str,
    mesh_results: dict[str, str],
    config: dict | None,
) -> list[str]:
    """Phase 2: call LLM to build Boolean PubMed queries from MeSH results."""
    # Format mesh results for the prompt
    mesh_lines = []
    for kw, result in mesh_results.items():
        mesh_lines.append(f"  - {kw}: {result}")
    mesh_results_text = "\n".join(mesh_lines) if mesh_lines else "  (no validated terms)"

    prompt = _PHASE2_PROMPT.format(
        user_prompt=user_prompt,
        mesh_results=mesh_results_text,
    )
    try:
        llm = get_llm(max_tokens=800, config=config)
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = strip_think_tokens(response.content)
        return _parse_json_array(raw)
    except Exception as exc:
        logger.warning("[LIBRARIAN] Phase 2 LLM call failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# JSON array parser (fixes the non-greedy regex bug)
# ---------------------------------------------------------------------------

def _parse_json_array(raw: str) -> list[str]:
    """Parse a JSON array of strings from the LLM response.

    Uses a greedy match to capture the full outermost [...] block, fixing the
    previous non-greedy bug that truncated multi-element arrays.
    """
    # Greedy match: finds the outermost [ ... ] block
    match = re.search(r"\[[\s\S]*\]", raw)
    if not match:
        logger.warning("[LIBRARIAN] Could not find JSON array in response: %s", raw[:200])
        return []
    try:
        items = json.loads(match.group())
        if isinstance(items, list):
            return [str(item).strip() for item in items if item and str(item).strip()]
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("[LIBRARIAN] JSON parse failed: %s | raw: %s", exc, raw[:200])
    return []


# Keep backward-compat alias used by some older call sites
_parse_queries = _parse_json_array
