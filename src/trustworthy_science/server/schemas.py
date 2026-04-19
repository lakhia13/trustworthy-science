from __future__ import annotations
import copy
from typing import Any, Literal, List, Optional
from pydantic import BaseModel, Field, model_validator

class ScoringWeights(BaseModel):
    """Optional per-request scoring weight overrides.

    All fields are optional — ``None`` means "keep the value from the base YAML".
    The five fields mirror the sidebar sliders in the Streamlit UI exactly.
    """
    retraction_cap: Optional[float] = None
    no_data_deposit_penalty: Optional[float] = None
    replicated_bonus: Optional[float] = None
    open_data_bonus: Optional[float] = None
    methods_nudge_pct: Optional[float] = None

    def to_config_overlay(self, base_config: dict) -> dict:
        """Deep-copy *base_config* and overlay any non-None fields.

        Mirrors ``streamlit_app._build_config()`` exactly:
        all five weights live under the ``scoring`` sub-dict.
        """
        cfg = copy.deepcopy(base_config)
        scoring = cfg.setdefault("scoring", {})
        if self.retraction_cap is not None:
            scoring["retraction_cap"] = self.retraction_cap
        if self.no_data_deposit_penalty is not None:
            scoring["no_data_deposit_penalty"] = self.no_data_deposit_penalty
        if self.replicated_bonus is not None:
            scoring["replicated_bonus"] = self.replicated_bonus
        if self.open_data_bonus is not None:
            scoring["open_data_bonus"] = self.open_data_bonus
        if self.methods_nudge_pct is not None:
            scoring["methods_nudge_pct"] = self.methods_nudge_pct
        return cfg


class SearchRequest(BaseModel):
    dois: list[str] = []
    pmids: list[str] = []
    query: str | None = None
    top_k: int = Field(default=10, ge=1, le=50)
    weights: Optional[ScoringWeights] = None

    @model_validator(mode="after")
    def at_least_one_identifier(self) -> "SearchRequest":
        if not self.dois and not self.pmids and not self.query:
            raise ValueError("Provide at least one of: dois, pmids, query")
        return self

class FilterRequest(BaseModel):
    query: str
    top_k: int = Field(default=20, ge=1, le=50)
    min_tier: Literal["Trusted", "Caution", "Untrusted"] = "Caution"
    weights: Optional[ScoringWeights] = None

class ExplainRequest(BaseModel):
    doi: str | None = None
    pmid: str | None = None
    weights: Optional[ScoringWeights] = None

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> "ExplainRequest":
        has_doi = bool(self.doi)
        has_pmid = bool(self.pmid)
        if not has_doi and not has_pmid:
            raise ValueError("Provide either doi or pmid")
        if has_doi and has_pmid:
            raise ValueError("Provide only one of doi or pmid, not both")
        return self

class DimensionScore(BaseModel):
    dimension: str
    score: float
    reason: str


def _coerce_per_dimension(raw: Any) -> list[DimensionScore]:
    """Normalise per_dimension from either old dict or new list format.

    Old format (pre-structured-report): ``{"stats_integrity": 0.9, ...}``
    New format: ``[{"dimension": "stats_integrity", "score": 0.9, "reason": "..."}]``
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        # Legacy dict format — convert to list of DimensionScore
        return [
            DimensionScore(dimension=k, score=float(v), reason="")
            for k, v in raw.items()
            if isinstance(v, (int, float))
        ]
    if isinstance(raw, list):
        result = []
        for item in raw:
            if isinstance(item, dict):
                try:
                    result.append(DimensionScore(**item))
                except Exception:
                    pass
            elif isinstance(item, DimensionScore):
                result.append(item)
        return result
    return []

class StructuredReportEntry(BaseModel):
    """One row in the per-dimension breakdown of a structured report."""
    dimension: str
    score_pct: int
    rationale: str


class StructuredReportSchema(BaseModel):
    """Structured, section-wise credibility report."""
    overall_verdict: str = ""
    score_breakdown: list[StructuredReportEntry] = []
    key_concerns: list[str] = []
    positive_signals: list[str] = []
    recommendation: str = ""
    raw_score: int = 0
    tier: str = "Untrusted"


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
    per_dimension: list[DimensionScore] = []
    structured_report: Optional[StructuredReportSchema] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PaperResult":
        """Coerce a raw TruthFilter result dict into a PaperResult."""
        # Handle structured_report — may be a Pydantic model or a plain dict
        sr_raw = d.get("structured_report")
        sr = None
        if sr_raw is not None:
            if hasattr(sr_raw, "model_dump"):
                sr_raw = sr_raw.model_dump()
            if isinstance(sr_raw, dict):
                try:
                    sr = StructuredReportSchema(
                        overall_verdict=sr_raw.get("overall_verdict", ""),
                        score_breakdown=[
                            StructuredReportEntry(**e)
                            for e in sr_raw.get("score_breakdown", [])
                        ],
                        key_concerns=sr_raw.get("key_concerns", []),
                        positive_signals=sr_raw.get("positive_signals", []),
                        recommendation=sr_raw.get("recommendation", ""),
                        raw_score=sr_raw.get("raw_score", 0),
                        tier=sr_raw.get("tier", "Untrusted"),
                    )
                except Exception:
                    sr = None

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
            per_dimension=_coerce_per_dimension(d.get("per_dimension")),
            structured_report=sr,
        )

class JobResponse(BaseModel):
    job_id: str

class JobStatus(BaseModel):
    status: str
    message: Optional[str] = None
    total: int = 0
    completed: int = 0
    results: Optional[List[PaperResult]] = None

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
