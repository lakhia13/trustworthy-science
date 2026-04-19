"""Shared Pydantic state models for the Trustworthy Science agent graph."""

from __future__ import annotations

from typing import Annotated, Any, Literal, List
from pydantic import BaseModel, Field
import operator

PaperType = Literal[
    "empirical_quantitative",
    "clinical_trial",
    "systematic_review_meta",
    "review_narrative",
    "theoretical",
    "computational_methods",
    "case_report",
    "opinion_commentary",
]


# ---------------------------------------------------------------------------
# Paper stubs & parsed content
# ---------------------------------------------------------------------------

class PaperStub(BaseModel):
    """Minimal metadata retrieved during search/lookup."""
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    venue: str = ""           # journal or preprint server name
    issn: str | None = None
    year: int | None = None
    abstract: str = ""
    pdf_url: str | None = None
    source: str = ""          # "pubmed" | "biorxiv" | "arxiv" | "openalex"

    @property
    def uid(self) -> str:
        """Best available unique identifier."""
        return self.doi or self.pmid or self.pmcid or self.title


class ParsedPaper(BaseModel):
    """Structured content extracted from full text or abstract."""
    full_text: str = ""
    abstract: str = ""
    methods: str = ""
    results: str = ""
    discussion: str = ""
    references: list[str] = Field(default_factory=list)
    figures_meta: list[str] = Field(default_factory=list)  # captions
    funding: str = ""
    coi_statement: str = ""
    submission_date: str | None = None
    acceptance_date: str | None = None
    # Tracks which fetcher successfully retrieved the text
    fetch_source: str = "unknown"  # e.g. "bioc", "pmc", "pdf_url", "biorxiv", etc.


# ---------------------------------------------------------------------------
# Flags & evidence
# ---------------------------------------------------------------------------

FlagTier = Literal["hard", "soft", "quality"]


class EvidenceQuote(BaseModel):
    """A verbatim excerpt from the paper that supports a flag."""
    text: str
    section: str = ""   # e.g. "methods", "results"


class Flag(BaseModel):
    tier: FlagTier
    code: str           # e.g. "P_HACKING_CLUSTER"
    message: str
    source_agent: str
    evidence: list[EvidenceQuote] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-agent sub-scores
# ---------------------------------------------------------------------------

class SubScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)         # 0 = terrible, 1 = excellent
    confidence: float = Field(ge=0.0, le=1.0)    # how sure is the agent
    flags: list[Flag] = Field(default_factory=list)
    notes: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# Final trust report
# ---------------------------------------------------------------------------
class DimensionScore(BaseModel):
    dimension: str
    score: float
    reason: str


class ScoreBreakdownEntry(BaseModel):
    """One row in the per-dimension breakdown table of a structured report."""
    dimension: str
    score_pct: int = Field(ge=0, le=100)
    rationale: str


class StructuredReport(BaseModel):
    """Structured, section-by-section scoring report produced by the scoring agent.

    This replaces the flat narrative summary for human-readable output.
    The ``summary`` field on TrustReport is kept as a flattened fallback for
    backward-compatible API consumers.
    """
    overall_verdict: str = ""
    score_breakdown: list[ScoreBreakdownEntry] = Field(default_factory=list)
    key_concerns: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    recommendation: str = ""
    raw_score: int = 0
    tier: str = "Untrusted"


class TrustReport(BaseModel):
    composite_score: int = Field(ge=0, le=100)
    tier: Literal["Trusted", "Caution", "Untrusted"]
    summary: str = ""
    hard_flags: list[Flag] = Field(default_factory=list)
    soft_flags: list[Flag] = Field(default_factory=list)
    quality_signals: list[Flag] = Field(default_factory=list)
    per_dimension: list[DimensionScore] = Field(default_factory=list)
    coverage: str = "metadata_only"
    structured_report: StructuredReport | None = None


# ---------------------------------------------------------------------------
# LangGraph node state
# ---------------------------------------------------------------------------

class PaperState(BaseModel):
    """The shared state object that flows through the LangGraph nodes."""

    # Set at graph entry
    stub: PaperStub = Field(default_factory=PaperStub)
    parsed: ParsedPaper | None = None
    coverage: Literal["full_text", "abstract_only", "metadata_only"] = "metadata_only"
    paper_type: PaperType | None = None

    # Accumulate results from parallel agent nodes
    sub_scores: Annotated[dict[str, SubScore], operator.or_] = Field(default_factory=dict)
    hard_flags: Annotated[list[Flag], operator.add] = Field(default_factory=list)
    soft_flags: Annotated[list[Flag], operator.add] = Field(default_factory=list)
    quality_signals: Annotated[list[Flag], operator.add] = Field(default_factory=list)

    # Set by scoring node
    final: TrustReport | None = None

    # Short-circuit flag: set by retraction_watch if paper is retracted
    retracted: bool = False

    # Extra context
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Top-level graph state (wraps multiple papers)
# ---------------------------------------------------------------------------

class GraphInput(BaseModel):
    query: str | None = None
    dois: list[str] = Field(default_factory=list)
    top_k: int = 10
    min_tier: Literal["Trusted", "Caution", "Untrusted"] = "Caution"


class GraphOutput(BaseModel):
    papers: list[PaperState] = Field(default_factory=list)
    filtered: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Deep Research state
# ---------------------------------------------------------------------------

class DeepResearchState(BaseModel):
    """State for the Deep Research LangGraph pipeline.

    Flows through: query_generator → parallel_pubmed_fetch → score_all → rag_ingest
    """
    # Set by user at entry
    user_prompt: str = ""
    top_k: int = 20
    min_tier: Literal["Trusted", "Caution", "Untrusted"] = "Caution"
    collection_name: str = ""       # ChromaDB collection; auto-generated if empty

    # Populated by query_generator node
    generated_queries: list[str] = Field(default_factory=list)

    # Populated by parallel_pubmed_fetch node
    candidate_stubs: Annotated[list[PaperStub], operator.add] = Field(default_factory=list)

    # Populated by score_all node
    scored_papers: list[dict[str, Any]] = Field(default_factory=list)

    # Populated by rag_ingest node (papers that passed min_tier)
    accepted_papers: list[dict[str, Any]] = Field(default_factory=list)

    # Error message if pipeline fails
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}