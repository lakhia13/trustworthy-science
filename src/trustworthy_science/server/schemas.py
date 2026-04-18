from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

class ScoreRequest(BaseModel):
    dois: list[str] = []
    pmids: list[str] = []
    query: str | None = None
    top_k: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def at_least_one_identifier(self) -> "ScoreRequest":
        if not self.dois and not self.pmids and not self.query:
            raise ValueError("Provide at least one of: dois, pmids, query")
        return self

class FilterRequest(BaseModel):
    query: str
    top_k: int = Field(default=20, ge=1, le=50)
    min_tier: Literal["Trusted", "Caution", "Untrusted"] = "Caution"

class ExplainRequest(BaseModel):
    doi: str | None = None
    pmid: str | None = None

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> "ExplainRequest":
        has_doi = bool(self.doi)
        has_pmid = bool(self.pmid)
        if not has_doi and not has_pmid:
            raise ValueError("Provide either doi or pmid")
        if has_doi and has_pmid:
            raise ValueError("Provide only one of doi or pmid, not both")
        return self

class PaperResult(BaseModel):
    title: str = ""
    doi: str | None = None
    pmid: str | None = None
    year: int | None = None
    venue: str = ""
    score: int = 0
    tier: Literal["Trusted", "Caution", "Untrusted"] = "Untrusted"
    coverage: str = "metadata_only"
    fetch_source: str = "unknown"
    summary: str = ""
    hard_flags: list[str] = []
    soft_flags: list[str] = []
    quality_signals: list[str] = []
    per_dimension: dict[str, float] = {}  # populated by /explain; empty for /score

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PaperResult":
        """Coerce a raw TruthFilter result dict into a PaperResult."""
        return cls(
            title=d.get("title", ""),
            doi=d.get("doi"),
            pmid=d.get("pmid"),
            year=d.get("year"),
            venue=d.get("venue", ""),
            score=d.get("score", 0),
            tier=d.get("tier", "Untrusted"),
            coverage=d.get("coverage", "metadata_only"),
            fetch_source=d.get("fetch_source", "unknown"),
            summary=d.get("summary", ""),
            hard_flags=d.get("hard_flags", []),
            soft_flags=d.get("soft_flags", []),
            quality_signals=d.get("quality_signals", []),
            per_dimension=d.get("per_dimension", {}),
        )

class ScoreResponse(BaseModel):
    papers: list[PaperResult]
    count: int

class FilterResponse(BaseModel):
    papers: list[PaperResult]
    count: int
    query: str
    min_tier: str

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str

class ReloadConfigRequest(BaseModel):
    config_path: str | None = None

class ReloadConfigResponse(BaseModel):
    reloaded: bool = True
    config_path: str
