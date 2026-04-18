"""LangGraph wiring for the Trustworthy Science credibility pipeline."""

from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from trustworthy_science.state import PaperState, PaperStub, GraphInput, GraphOutput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-paper sub-graph
# ---------------------------------------------------------------------------

def _make_paper_graph(config: dict | None = None):
    """Build and compile the per-paper credibility evaluation sub-graph."""
    from trustworthy_science.agents.fetch_parse import fetch_and_parse
    from trustworthy_science.agents.retraction_watch import retraction_watch_agent
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

    # Routing: if paper is retracted, skip parallel agents and go straight to scoring
    def route_after_retraction(state: PaperState) -> Literal["stats_integrity", "scoring"]:
        if state.retracted:
            return "scoring"
        return "stats_integrity"

    builder = StateGraph(PaperState)

    builder.add_node("fetch_parse", fetch_node)
    builder.add_node("retraction_watch", retraction_node)
    builder.add_node("stats_integrity", stats_node)
    builder.add_node("reproducibility", repro_node)
    builder.add_node("citation_network", citation_node)
    builder.add_node("methodology", methods_node)
    builder.add_node("publication_metadata", venue_node)
    builder.add_node("scoring", score_node)

    builder.add_edge(START, "fetch_parse")
    builder.add_edge("fetch_parse", "retraction_watch")

    # After retraction check: either short-circuit or fan out to parallel agents
    builder.add_conditional_edges(
        "retraction_watch",
        route_after_retraction,
        {
            "scoring": "scoring",
            "stats_integrity": "stats_integrity",
        },
    )

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

            filtered.append({
                "title": ps.stub.title,
                "doi": ps.stub.doi,
                "year": ps.stub.year,
                "venue": ps.stub.venue,
                "score": score,
                "tier": tier,
                "include": include,
                "summary": ps.final.summary if ps.final else "",
                "hard_flags": [f.code for f in (ps.final.hard_flags if ps.final else [])],
                "soft_flags": [f.code for f in (ps.final.soft_flags if ps.final else [])],
                "quality_signals": [f.code for f in (ps.final.quality_signals if ps.final else [])],
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
