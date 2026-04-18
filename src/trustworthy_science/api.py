"""TruthFilter — the public API for the Trustworthy Science library."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import yaml

from trustworthy_science.graph import build_graph, _make_paper_graph
from trustworthy_science.state import GraphInput, PaperState, PaperStub, TrustReport

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "config" / "scoring.yaml"


class TruthFilter:
    """High-level interface for scoring and filtering scientific papers.

    Usage
    -----
    ::

        from trustworthy_science import TruthFilter

        tf = TruthFilter.from_config("config/scoring.yaml")

        # Score specific DOIs
        reports = tf.score_papers(dois=["10.1038/s41586-020-2748-1"])

        # Filter a research corpus
        results = tf.filter_for_rag(
            query="GLP-1 receptor agonists in NASH",
            top_k=20,
            min_tier="Caution",
        )
    """

    def __init__(self, config: dict | None = None) -> None:
        self._config = config or {}
        self._graph = build_graph(self._config)

    @classmethod
    def from_config(cls, config_path: str | Path = _DEFAULT_CONFIG) -> "TruthFilter":
        """Instantiate TruthFilter from a YAML config file."""
        path = Path(config_path)
        if not path.exists():
            logger.warning("Config not found at %s; using defaults.", path)
            return cls(config=None)
        with path.open() as f:
            cfg = yaml.safe_load(f)
        return cls(config=cfg)

    def reload_config(self, config_path: str | Path = _DEFAULT_CONFIG) -> None:
        """Reload YAML config and rebuild the graph (e.g. for live weight tuning)."""
        path = Path(config_path)
        with path.open() as f:
            self._config = yaml.safe_load(f)
        self._graph = build_graph(self._config)

    # ------------------------------------------------------------------
    # Core methods
    # ------------------------------------------------------------------

    def score_papers(
        self,
        dois: list[str] | None = None,
        query: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Score papers by DOI list or natural-language query.

        Returns a list of result dicts sorted by trust score (descending):
        ``{"title", "doi", "score", "tier", "summary", "hard_flags", "soft_flags", ...}``
        """
        inp = GraphInput(
            query=query,
            dois=dois or [],
            top_k=top_k,
            min_tier="Untrusted",   # return everything, let caller filter
        )
        state = {"input": inp, "stubs": [], "papers": [], "filtered": []}
        result = self._graph.invoke(state)
        return result.get("filtered", [])

    def filter_for_rag(
        self,
        query: str,
        top_k: int = 20,
        min_tier: Literal["Trusted", "Caution", "Untrusted"] = "Caution",
    ) -> list[dict[str, Any]]:
        """Retrieve and filter papers for use in a RAG pipeline.

        Returns only papers with tier >= ``min_tier``, each annotated with
        trust metadata. Trusted papers appear first.
        """
        inp = GraphInput(query=query, dois=[], top_k=top_k, min_tier=min_tier)
        state = {"input": inp, "stubs": [], "papers": [], "filtered": []}
        result = self._graph.invoke(state)
        return [r for r in result.get("filtered", []) if r.get("include", False)]

    def score_single(self, doi: str) -> dict[str, Any] | None:
        """Score a single paper by DOI and return the full result dict."""
        results = self.score_papers(dois=[doi], top_k=1)
        return results[0] if results else None

    def score_single_by_pmid(self, pmid: str) -> dict[str, Any] | None:
        """Score a single paper by PMID and return the full result dict.

        The PMID is used directly for the BioC JSON full-text fetch (Step 1 in
        the fetch cascade), which provides structured, pre-segmented sections and
        is the highest-quality source available.  The PubMed metadata fetch also
        populates DOI, PMCID, authors, journal, and abstract from the same call.
        """
        from trustworthy_science.tools.pubmed import fetch_pubmed_metadata

        stubs = fetch_pubmed_metadata([pmid])
        if not stubs:
            logger.warning("PMID %s not found in PubMed", pmid)
            return None

        stub = stubs[0]
        # Ensure pmid is set even if PubMed XML parsed it into a different field
        if not stub.pmid:
            stub = stub.model_copy(update={"pmid": pmid})

        paper_graph = _make_paper_graph(self._config)
        paper_state = PaperState(stub=stub)
        try:
            final_state = paper_graph.invoke(paper_state)
            ps = PaperState(**final_state)
        except Exception as exc:
            logger.error("Paper scoring failed for PMID %s: %s", pmid, exc)
            return None

        if ps.final is None:
            return None

        return {
            "title": ps.stub.title,
            "doi": ps.stub.doi,
            "pmid": ps.stub.pmid,
            "year": ps.stub.year,
            "venue": ps.stub.venue,
            "score": ps.final.composite_score,
            "tier": ps.final.tier,
            "include": True,
            "coverage": ps.final.coverage,
            "fetch_source": ps.parsed.fetch_source if ps.parsed else "unknown",
            "summary": ps.final.summary,
            "hard_flags": [f.code for f in ps.final.hard_flags],
            "soft_flags": [f.code for f in ps.final.soft_flags],
            "quality_signals": [f.code for f in ps.final.quality_signals],
            "per_dimension": ps.final.per_dimension,
        }
