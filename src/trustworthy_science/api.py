"""TruthFilter — the public API for the Trustworthy Science library."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import yaml

from trustworthy_science.graph import build_graph
from trustworthy_science.state import GraphInput, PaperState, TrustReport

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
