"""Pydantic schemas for FastAPI request/response bodies."""

from typing import Literal
from pydantic import BaseModel, Field


# ============================================================================
# Paper Response Models (reuse existing Pydantic models from state.py)
# ============================================================================

class EvidenceQuoteSchema(BaseModel):
    """A verbatim excerpt from the paper that supports a flag."""
    text: str
    section: str = ""


class FlagSchema(BaseModel):
    """A credibility flag (hard, soft, or quality signal)."""
    tier: Literal["hard", "soft", "quality"]
    code: str
    message: str
    source_agent: str
    evidence: list[EvidenceQuoteSchema] = Field(default_factory=list)


class TrustReportSchema(BaseModel):
    """Complete credibility report for a single paper."""
    composite_score: int | None = Field(default=None, ge=0, le=100, description="Overall trust score (0-100)")
    score: int | None = Field(default=None, ge=0, le=100, description="Overall trust score (alias for composite_score)")
    tier: Literal["Trusted", "Caution", "Untrusted"]
    summary: str = ""
    hard_flags: list[str] = Field(default_factory=list, description="Hard flag codes")
    soft_flags: list[str] = Field(default_factory=list, description="Soft flag codes")
    quality_signals: list[str] = Field(default_factory=list, description="Quality signal codes")
    per_dimension: dict[str, float] = Field(default_factory=dict)
    coverage: str = "metadata_only"

    class Config:
        json_schema_extra = {
            "example": {
                "composite_score": 78,
                "score": 78,
                "tier": "Trusted",
                "summary": "Open-access RCT with strong methodology",
                "hard_flags": [],
                "soft_flags": ["LOW_POWER"],
                "quality_signals": ["OPEN_ACCESS", "COI_DISCLOSED"],
                "per_dimension": {
                    "Reproducibility": 0.85,
                    "Stats Integrity": 0.90,
                    "Methodology": 0.80,
                },
                "coverage": "full_text",
            }
        }


class PaperWithDOISchema(BaseModel):
    """Trust report with paper metadata."""
    doi: str | None = None
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    abstract: str = ""
    composite_score: int | None = Field(default=None, ge=0, le=100)
    score: int | None = Field(default=None, ge=0, le=100)
    tier: Literal["Trusted", "Caution", "Untrusted"]
    summary: str = ""
    hard_flags: list[str] = Field(default_factory=list)
    soft_flags: list[str] = Field(default_factory=list)
    quality_signals: list[str] = Field(default_factory=list)
    per_dimension: dict[str, float] = Field(default_factory=dict)
    coverage: str = "metadata_only"


# ============================================================================
# Request Models
# ============================================================================

class ScoreRequest(BaseModel):
    """Request to score papers by DOI or query."""
    dois: list[str] | None = Field(default=None, description="List of DOIs to score")
    query: str | None = Field(default=None, description="Natural-language query")
    top_k: int = Field(default=10, ge=1, le=100, description="Max papers to return")

    class Config:
        json_schema_extra = {
            "example": {
                "dois": ["10.1371/journal.pmed.1001231"],
                "query": None,
                "top_k": 10,
            }
        }


class FilterRequest(BaseModel):
    """Request to filter papers for RAG input."""
    query: str = Field(..., description="Search query")
    top_k: int = Field(default=20, ge=1, le=100, description="Max papers to return")
    min_tier: Literal["Trusted", "Caution", "Untrusted"] = Field(
        default="Caution",
        description="Minimum trust tier to include",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "GLP-1 receptor agonists",
                "top_k": 20,
                "min_tier": "Caution",
            }
        }


class SinglePaperRequest(BaseModel):
    """Request to fetch a single paper's full report."""
    doi: str = Field(..., description="Paper DOI (URL-encoded)")

    class Config:
        json_schema_extra = {
            "example": {
                "doi": "10.1371/journal.pmed.1001231",
            }
        }


# ============================================================================
# Response Wrappers
# ============================================================================

class ScoreResponse(BaseModel):
    """Response from /score endpoint."""
    papers: list[PaperWithDOISchema] = Field(default_factory=list)
    took_seconds: float = Field(description="Execution time in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "papers": [
                    {
                        "doi": "10.1371/journal.pmed.1001231",
                        "title": "Example paper",
                        "composite_score": 78,
                        "tier": "Trusted",
                        "summary": "...",
                        "hard_flags": [],
                        "soft_flags": [],
                        "quality_signals": [],
                        "per_dimension": {},
                        "coverage": "full_text",
                    }
                ],
                "took_seconds": 2.3,
            }
        }


class FilterResponse(BaseModel):
    """Response from /filter endpoint."""
    papers: list[PaperWithDOISchema] = Field(default_factory=list)
    took_seconds: float = Field(description="Execution time in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "papers": [],
                "took_seconds": 3.1,
            }
        }


class PaperDetailResponse(BaseModel):
    """Response from /paper/{doi} endpoint."""
    paper: PaperWithDOISchema
    took_seconds: float = Field(description="Execution time in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "paper": {
                    "doi": "10.1371/journal.pmed.1001231",
                    "title": "Example paper",
                    "composite_score": 78,
                    "tier": "Trusted",
                    "summary": "...",
                    "hard_flags": [],
                    "soft_flags": [],
                    "quality_signals": [],
                    "per_dimension": {},
                    "coverage": "full_text",
                },
                "took_seconds": 1.5,
            }
        }


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    code: str
    details: dict | None = None
