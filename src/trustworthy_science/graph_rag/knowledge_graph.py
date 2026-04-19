"""
In-memory knowledge graph for trusted scientific literature.

Only Trusted and Caution papers are admitted as nodes.
Edges represent citation relationships (CITES) and topic similarity (SHARES_TOPIC).
"""

from __future__ import annotations

import re
from typing import Any

import networkx as nx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_keywords(text: str) -> set[str]:
    """Extract simple keywords from title + abstract text."""
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "this", "that", "these", "those", "it", "its", "we", "our", "their",
        "not", "no", "nor", "so", "yet", "both", "either", "neither",
        "as", "than", "such", "each", "more", "most", "also", "via",
        "using", "used", "based", "between", "among", "after", "before",
    }
    words = re.findall(r"[a-z]{4,}", text.lower())
    return {w for w in words if w not in stopwords}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tier_rank(tier: str) -> int:
    return {"Trusted": 2, "Caution": 1, "Untrusted": 0}.get(tier, 0)


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------

class LiteratureGraph:
    """
    Directed knowledge graph of trusted/caution papers.

    Nodes  — papers (doi as id)
    Edges  — CITES (directed) or SHARES_TOPIC (undirected stored as two directed)
    """

    TOPIC_SIMILARITY_THRESHOLD = 0.15  # Jaccard threshold for SHARES_TOPIC edge

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()
        # doi → raw report dict (includes title, abstract, flags, etc.)
        self.papers: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    # Ingestion                                                            #
    # ------------------------------------------------------------------ #

    def add_paper(self, report: dict[str, Any]) -> bool:
        """
        Add a paper to the graph.

        Returns True if added (Trusted/Caution), False if rejected (Untrusted).
        """
        tier = report.get("tier", "Untrusted")
        if tier == "Untrusted":
            return False

        doi = report.get("doi")
        if not doi:
            return False

        # Already in graph
        if doi in self.papers:
            return True

        self.papers[doi] = report

        # Build keyword set for topic-edge computation
        kw_text = f"{report.get('title', '')} {report.get('abstract', '')}"
        keywords = _extract_keywords(kw_text)

        # Add node with display attributes
        self.graph.add_node(
            doi,
            title=report.get("title", ""),
            authors=report.get("authors", []),
            year=report.get("year"),
            venue=report.get("venue", ""),
            score=report.get("score") or report.get("composite_score") or 0,
            tier=tier,
            hard_flags=report.get("hard_flags", []),
            soft_flags=report.get("soft_flags", []),
            quality_signals=report.get("quality_signals", []),
            keywords=keywords,
            abstract=report.get("abstract", ""),
            summary=report.get("summary", ""),
        )

        # Add citation edges and topic edges
        self._add_citation_edges(doi, report)
        self._add_topic_edges(doi, keywords)

        return True

    def _add_citation_edges(self, doi: str, report: dict[str, Any]) -> None:
        """Add CITES edges to other nodes already in the graph."""
        # The references list may contain raw strings — try to extract DOIs
        refs = report.get("references", [])
        for ref in refs:
            if isinstance(ref, str):
                # Extract DOI pattern from reference string
                doi_match = re.search(r"10\.\d{4,}/\S+", ref)
                if doi_match:
                    ref_doi = doi_match.group(0).rstrip(".,;)")
                    if ref_doi in self.papers and ref_doi != doi:
                        self.graph.add_edge(doi, ref_doi, type="CITES")

    def _add_topic_edges(self, new_doi: str, new_kws: set[str]) -> None:
        """Add SHARES_TOPIC edges to similar existing nodes."""
        for existing_doi, data in self.graph.nodes(data=True):
            if existing_doi == new_doi:
                continue
            existing_kws: set[str] = data.get("keywords", set())
            sim = _jaccard(new_kws, existing_kws)
            if sim >= self.TOPIC_SIMILARITY_THRESHOLD:
                # Store as bidirectional (two directed edges)
                if not self.graph.has_edge(new_doi, existing_doi):
                    self.graph.add_edge(new_doi, existing_doi, type="SHARES_TOPIC", weight=sim)
                if not self.graph.has_edge(existing_doi, new_doi):
                    self.graph.add_edge(existing_doi, new_doi, type="SHARES_TOPIC", weight=sim)

    # ------------------------------------------------------------------ #
    # Query / Retrieval                                                    #
    # ------------------------------------------------------------------ #

    def query(self, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Find the most relevant papers for a query via keyword + graph traversal.

        1. Rank all nodes by keyword overlap with query text.
        2. Expand top-3 anchors via 1-hop BFS.
        3. Re-rank combined set, return top_k.
        """
        if not self.papers:
            return []

        query_kws = _extract_keywords(text)

        # Score every node
        scored: list[tuple[float, str]] = []
        for doi, data in self.graph.nodes(data=True):
            node_kws: set[str] = data.get("keywords", set())
            relevance = _jaccard(query_kws, node_kws)
            trust_boost = data.get("score", 50) / 100.0
            combined = 0.7 * relevance + 0.3 * trust_boost
            scored.append((combined, doi))

        scored.sort(reverse=True)

        # Pick top-3 anchors
        anchors = [doi for _, doi in scored[:3]]

        # BFS expand 1-hop
        neighborhood: set[str] = set(anchors)
        for doi in anchors:
            neighborhood.update(self.graph.successors(doi))
            neighborhood.update(self.graph.predecessors(doi))

        # Re-rank neighbourhood
        neighbourhood_scored = [
            (score, doi) for score, doi in scored if doi in neighborhood
        ]
        neighbourhood_scored.sort(reverse=True)

        result_dois = [doi for _, doi in neighbourhood_scored[:top_k]]
        return [self.papers[doi] for doi in result_dois if doi in self.papers]

    # ------------------------------------------------------------------ #
    # Serialization for frontend visualization                             #
    # ------------------------------------------------------------------ #

    def to_vis_json(self) -> dict[str, Any]:
        """
        Serialize graph to JSON for D3/react-force-graph rendering.

        Returns:
            {
                "nodes": [{"id", "title", "score", "tier", "year", "venue", ...}],
                "edges": [{"source", "target", "type"}]
            }
        """
        nodes = []
        for doi, data in self.graph.nodes(data=True):
            nodes.append({
                "id": doi,
                "title": data.get("title", doi),
                "score": data.get("score", 0),
                "tier": data.get("tier", "Caution"),
                "year": data.get("year"),
                "venue": data.get("venue", ""),
                "hard_flags": data.get("hard_flags", []),
                "soft_flags": data.get("soft_flags", []),
                "quality_signals": data.get("quality_signals", []),
                "val": max(4, data.get("score", 50) // 15),  # node size for vis
            })

        edges = []
        for src, tgt, edata in self.graph.edges(data=True):
            edges.append({
                "source": src,
                "target": tgt,
                "type": edata.get("type", "CITES"),
            })

        return {"nodes": nodes, "edges": edges}

    # ------------------------------------------------------------------ #
    # Stats                                                                #
    # ------------------------------------------------------------------ #

    @property
    def size(self) -> int:
        return len(self.papers)

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    def stats(self) -> dict[str, Any]:
        tiers = {"Trusted": 0, "Caution": 0}
        for data in self.graph.nodes.values():
            t = data.get("tier", "Caution")
            tiers[t] = tiers.get(t, 0) + 1
        return {
            "total_papers": self.size,
            "trusted": tiers.get("Trusted", 0),
            "caution": tiers.get("Caution", 0),
            "total_edges": self.edge_count,
        }
