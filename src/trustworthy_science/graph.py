"""LangGraph wiring for the Trustworthy Science credibility pipeline."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from trustworthy_science.state import (
    DeepResearchState,
    PaperState,
    PaperStub,
    GraphInput,
    GraphOutput,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-paper sub-graph
# ---------------------------------------------------------------------------

def _make_paper_graph(config: dict | None = None):
    """Build and compile the per-paper credibility evaluation sub-graph."""
    from trustworthy_science.agents.fetch_parse import fetch_and_parse
    from trustworthy_science.agents.retraction_watch import retraction_watch_agent
    from trustworthy_science.agents.paper_classifier import classify_paper_type
    from trustworthy_science.agents.stats_integrity import stats_integrity_agent
    from trustworthy_science.agents.reproducibility import reproducibility_agent
    from trustworthy_science.agents.citation_network import citation_network_agent
    from trustworthy_science.agents.methodology import methodology_agent
    from trustworthy_science.agents.publication_metadata import publication_metadata_agent
    from trustworthy_science.agents.scoring import scoring_agent

    cfg = config or {}

    # Wrap agents to inject config
    def fetch_node(state: PaperState):
        return fetch_and_parse(state)

    def retraction_node(state: PaperState):
        return retraction_watch_agent(state)

    def classifier_node(state: PaperState):
        return classify_paper_type(state, config=cfg)

    def stats_node(state: PaperState):
        return stats_integrity_agent(state, config=cfg)

    def repro_node(state: PaperState):
        return reproducibility_agent(state, config=cfg)

    def citation_node(state: PaperState):
        return citation_network_agent(state, config=cfg)

    def methods_node(state: PaperState):
        return methodology_agent(state, config=cfg)

    def venue_node(state: PaperState):
        return publication_metadata_agent(state, config=cfg)

    def score_node(state: PaperState):
        return scoring_agent(state, config=cfg)

    # Routing: if paper is retracted, skip remaining nodes and go straight to scoring
    def route_after_retraction(state: PaperState) -> Literal["paper_classifier", "scoring"]:
        if state.retracted:
            return "scoring"
        return "paper_classifier"

    builder = StateGraph(PaperState)

    builder.add_node("fetch_parse", fetch_node)
    builder.add_node("retraction_watch", retraction_node)
    builder.add_node("paper_classifier", classifier_node)
    builder.add_node("stats_integrity", stats_node)
    builder.add_node("reproducibility", repro_node)
    builder.add_node("citation_network", citation_node)
    builder.add_node("methodology", methods_node)
    builder.add_node("publication_metadata", venue_node)
    builder.add_node("scoring", score_node)

    builder.add_edge(START, "fetch_parse")
    builder.add_edge("fetch_parse", "retraction_watch")

    # After retraction check: either short-circuit to scoring or classify then analyse
    builder.add_conditional_edges(
        "retraction_watch",
        route_after_retraction,
        {
            "scoring": "scoring",
            "paper_classifier": "paper_classifier",
        },
    )
    builder.add_edge("paper_classifier", "stats_integrity")

    # Parallel credibility agents all feed into scoring
    for parallel_node in ("reproducibility", "citation_network", "methodology", "publication_metadata"):
        builder.add_edge("stats_integrity", parallel_node)
        builder.add_edge(parallel_node, "scoring")

    builder.add_edge("scoring", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Top-level multi-paper graph
# ---------------------------------------------------------------------------

class MultiPaperState(GraphOutput):
    """State for the outer graph that processes multiple papers."""
    input: GraphInput = GraphInput()
    stubs: list[PaperStub] = []

    model_config = {"arbitrary_types_allowed": True}


def _make_multi_graph(config: dict | None = None):
    """Build and compile the outer graph that retrieves and scores N papers."""
    from trustworthy_science.agents.retriever import retrieve_papers

    paper_graph = _make_paper_graph(config)

    def retrieve_node(state: MultiPaperState) -> dict:
        stubs = retrieve_papers(state.input)
        return {"stubs": stubs}

    def score_papers_node(state: MultiPaperState) -> dict:
        """Score each stub through the paper sub-graph and collect results."""
        results: list[PaperState] = []
        for stub in state.stubs:
            paper_state = PaperState(stub=stub)
            try:
                final_state = paper_graph.invoke(paper_state)
                results.append(PaperState(**final_state))
            except Exception as exc:
                logger.warning("Paper scoring failed for %s: %s", stub.uid, exc)
                results.append(PaperState(stub=stub, error=str(exc)))
        return {"papers": results}

    def filter_node(state: MultiPaperState) -> dict:
        """Apply min_tier filter and produce the filtered list."""
        tier_order = {"Trusted": 2, "Caution": 1, "Untrusted": 0}
        min_tier_val = tier_order.get(state.input.min_tier, 1)

        filtered = []
        for ps in state.papers:
            if ps.final is None:
                include = False
                score = 0
                tier = "Untrusted"
            else:
                tier = ps.final.tier
                score = ps.final.composite_score
                include = tier_order.get(tier, 0) >= min_tier_val

            # Prefer parsed abstract (richer) over stub abstract
            abstract = ""
            if ps.parsed and ps.parsed.abstract:
                abstract = ps.parsed.abstract
            elif ps.stub.abstract:
                abstract = ps.stub.abstract

            filtered.append({
                "title": ps.stub.title,
                "doi": ps.stub.doi,
                "pmid": ps.stub.pmid,
                "year": ps.stub.year,
                "venue": ps.stub.venue,
                "authors": ps.stub.authors,
                "abstract": abstract,
                "score": score,
                "tier": tier,
                "include": include,
                "coverage": ps.final.coverage if ps.final else ps.coverage,
                "fetch_source": ps.parsed.fetch_source if ps.parsed else "unknown",
                "summary": ps.final.summary if ps.final else "",
                "hard_flags": [f.code for f in (ps.final.hard_flags if ps.final else [])],
                "soft_flags": [f.code for f in (ps.final.soft_flags if ps.final else [])],
                "quality_signals": [f.code for f in (ps.final.quality_signals if ps.final else [])],
                "per_dimension": ps.final.per_dimension if ps.final else [],
                "structured_report": ps.final.structured_report if ps.final else None,
            })

        # Sort: included first, then by score desc
        filtered.sort(key=lambda x: (x["include"], x["score"]), reverse=True)
        return {"filtered": filtered}

    builder = StateGraph(MultiPaperState)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("score_papers", score_papers_node)
    builder.add_node("filter", filter_node)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "score_papers")
    builder.add_edge("score_papers", "filter")
    builder.add_edge("filter", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Convenience builder
# ---------------------------------------------------------------------------

def build_graph(config: dict | None = None):
    """Return the compiled multi-paper LangGraph graph."""
    return _make_multi_graph(config)


# ---------------------------------------------------------------------------
# Deep Research graph
# ---------------------------------------------------------------------------

def _make_deep_research_graph(config: dict | None = None):
    """Build the deep research pipeline graph.

    Node sequence:
        START → query_generator → parallel_pubmed_fetch → score_all → rag_ingest → END

    The pipeline:
    1. ``query_generator``      — LLM generates 3-5 PubMed queries from user prompt
    2. ``parallel_pubmed_fetch``— fans out over queries, fetches PaperStubs
    3. ``score_all``            — scores every stub through the per-paper sub-graph
    4. ``rag_ingest``           — filters by min_tier, ingests into ChromaDB
    """
    from trustworthy_science.tools.pubmed import search_pubmed, fetch_pubmed_metadata
    from trustworthy_science.tools.chroma_store import ingest_papers

    paper_graph = _make_paper_graph(config)
    cfg = config or {}
    max_papers = cfg.get("rag", {}).get("max_papers_per_session", 30)

    def query_generator_node(state: DeepResearchState) -> dict:
        from trustworthy_science.agents.deep_research import _run_librarian_agent
        queries, mesh_terms = _run_librarian_agent(state.user_prompt, config=cfg)
        if not queries:
            queries = [state.user_prompt]
            mesh_terms = []
        # Auto-generate a collection name if not set
        collection = state.collection_name
        if not collection:
            slug = hashlib.sha256(state.user_prompt.encode()).hexdigest()[:12]
            collection = f"research_{slug}"
        return {
            "generated_queries": queries,
            "mesh_terms": mesh_terms,
            "collection_name": collection,
        }

    def parallel_pubmed_fetch_node(state: DeepResearchState) -> dict:
        """Fetch papers for every generated query and return deduplicated stubs."""
        stubs: list[PaperStub] = []
        seen: set[str] = set()
        # Use the user-requested top_k (capped by the config max) to control fetch size
        max_to_fetch = min(state.top_k, max_papers) if state.top_k else max_papers
        per_query = max(3, max_to_fetch // max(len(state.generated_queries), 1))

        query_metadata: list[dict] = []
        for query in state.generated_queries:
            try:
                pmids = search_pubmed(query, max_results=per_query)
                new_stubs = fetch_pubmed_metadata(pmids)
                count_before = len(stubs)
                for stub in new_stubs:
                    key = stub.doi or stub.pmid or stub.title
                    if key and key not in seen:
                        seen.add(key)
                        stubs.append(stub)
                query_metadata.append({"query": query, "pmid_count": len(pmids)})
            except Exception as exc:
                logger.warning("[DEEP_RESEARCH] PubMed fetch failed for '%s': %s", query, exc)
                query_metadata.append({"query": query, "pmid_count": 0})

        # Hard cap to prevent runaway
        stubs = stubs[:max_to_fetch]
        logger.info("[DEEP_RESEARCH] Fetched %d unique stubs from %d queries",
                    len(stubs), len(state.generated_queries))
        return {"candidate_stubs": stubs, "query_metadata": query_metadata}

    def score_all_node(state: DeepResearchState) -> dict:
        """Score every candidate stub through the per-paper graph."""
        tier_order = {"Trusted": 2, "Caution": 1, "Untrusted": 0}
        scored: list[dict] = []

        for stub in state.candidate_stubs:
            paper_state = PaperState(stub=stub)
            try:
                final_state = paper_graph.invoke(paper_state)
                ps = PaperState(**final_state)
            except Exception as exc:
                logger.warning("[DEEP_RESEARCH] Scoring failed for %s: %s", stub.uid, exc)
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

        scored.sort(key=lambda x: x["score"], reverse=True)
        logger.info("[DEEP_RESEARCH] Scored %d papers", len(scored))
        return {"scored_papers": scored}

    def rag_ingest_node(state: DeepResearchState) -> dict:
        """Filter papers by min_tier and ingest accepted ones into ChromaDB."""
        tier_order = {"Trusted": 2, "Caution": 1, "Untrusted": 0}
        min_val = tier_order.get(state.min_tier, 1)

        accepted = [
            p for p in state.scored_papers
            if tier_order.get(p.get("tier", "Untrusted"), 0) >= min_val
        ]
        logger.info(
            "[DEEP_RESEARCH] %d/%d papers accepted (min_tier=%s)",
            len(accepted), len(state.scored_papers), state.min_tier,
        )

        if accepted and state.collection_name:
            try:
                n = ingest_papers(accepted, state.collection_name, config=cfg)
                logger.info("[DEEP_RESEARCH] Ingested %d chunks into '%s'", n, state.collection_name)
            except Exception as exc:
                logger.error("[DEEP_RESEARCH] ChromaDB ingest failed: %s", exc)

        return {"accepted_papers": accepted}

    builder = StateGraph(DeepResearchState)
    builder.add_node("query_generator", query_generator_node)
    builder.add_node("parallel_pubmed_fetch", parallel_pubmed_fetch_node)
    builder.add_node("score_all", score_all_node)
    builder.add_node("rag_ingest", rag_ingest_node)

    builder.add_edge(START, "query_generator")
    builder.add_edge("query_generator", "parallel_pubmed_fetch")
    builder.add_edge("parallel_pubmed_fetch", "score_all")
    builder.add_edge("score_all", "rag_ingest")
    builder.add_edge("rag_ingest", END)

    return builder.compile()


def build_deep_research_graph(config: dict | None = None):
    """Return the compiled deep research LangGraph pipeline."""
    return _make_deep_research_graph(config)
