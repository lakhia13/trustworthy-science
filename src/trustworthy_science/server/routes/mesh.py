"""FastAPI routes for MeSH (Medical Subject Headings) lookup.

Exposes the same ``mesh_lookup`` and ``batch_mesh_lookup`` functions used
internally by the Deep Research librarian agent so REST clients can validate
medical keywords and build Boolean PubMed queries without running the full
pipeline.
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class MeshLookupResult(BaseModel):
    """Result of a single MeSH descriptor lookup."""
    keyword: str
    result: str = Field(
        description=(
            "Either 'VALID MeSH descriptor: <name>' when the term is found, "
            "'NOT FOUND in MeSH. ...' when it is not, or an error message."
        )
    )
    valid: bool = Field(description="True when the lookup returned a valid MeSH descriptor.")
    descriptor: str | None = Field(
        default=None,
        description="The canonical MeSH descriptor name when valid is True, else None.",
    )


class BatchMeshRequest(BaseModel):
    """Batch MeSH lookup request."""
    keywords: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of medical concept strings to validate (max 20).",
    )
    max_terms: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Maximum number of NCBI calls to make. Extra keywords are ignored.",
    )


class BatchMeshResponse(BaseModel):
    """Batch MeSH lookup response."""
    results: List[MeshLookupResult]
    count: int
    validated_count: int = Field(description="Number of keywords that resolved to a valid MeSH descriptor.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_result(keyword: str, raw: str) -> MeshLookupResult:
    """Convert a raw mesh_lookup string into a structured MeshLookupResult."""
    valid = raw.startswith("VALID MeSH descriptor:")
    descriptor: str | None = None
    if valid:
        # "VALID MeSH descriptor: Depressive Disorder, Treatment-Resistant"
        descriptor = raw[len("VALID MeSH descriptor:"):].strip()
    return MeshLookupResult(keyword=keyword, result=raw, valid=valid, descriptor=descriptor)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/lookup",
    response_model=MeshLookupResult,
    summary="Look up a single keyword in the MeSH database",
)
def mesh_lookup_single(
    keyword: str = Query(..., min_length=1, description="Medical concept or clinical term to validate."),
) -> MeshLookupResult:
    """Validate a single keyword against the NCBI MeSH database.

    Returns the canonical MeSH descriptor name when found, or a suggestion
    message when the term is not in the database. Results are cached so
    repeated lookups for the same keyword are free.

    **Example:**
    ```
    GET /api/mesh/lookup?keyword=randomized+controlled+trial
    ```
    ```json
    {
      "keyword": "randomized controlled trial",
      "result": "VALID MeSH descriptor: Randomized Controlled Trials as Topic",
      "valid": true,
      "descriptor": "Randomized Controlled Trials as Topic"
    }
    ```
    """
    try:
        from trustworthy_science.tools.mesh import mesh_lookup
        # mesh_lookup is a LangChain @tool; call its underlying function directly
        raw: str = mesh_lookup.invoke({"keyword": keyword})  # type: ignore[attr-defined]
    except Exception as exc:
        logger.error("[MESH_ROUTE] lookup failed for '%s': %s", keyword, exc)
        raise HTTPException(status_code=500, detail=f"MeSH lookup failed: {exc}")

    return _parse_result(keyword, raw)


@router.post(
    "/batch-lookup",
    response_model=BatchMeshResponse,
    summary="Validate multiple keywords against the MeSH database",
)
def mesh_batch_lookup(request: BatchMeshRequest) -> BatchMeshResponse:
    """Validate a list of medical keywords against the NCBI MeSH database.

    Runs up to ``max_terms`` lookups (default 6, matching the Deep Research
    librarian agent limit). Additional keywords beyond ``max_terms`` are
    silently ignored. Results are cached individually.

    **Example request:**
    ```json
    {
      "keywords": ["depression", "SSRIs", "randomized controlled trial"],
      "max_terms": 6
    }
    ```
    """
    try:
        from trustworthy_science.tools.mesh import batch_mesh_lookup
        raw_results: dict[str, str] = batch_mesh_lookup(
            request.keywords,
            max_terms=request.max_terms,
        )
    except Exception as exc:
        logger.error("[MESH_ROUTE] batch lookup failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Batch MeSH lookup failed: {exc}")

    items = [_parse_result(kw, result) for kw, result in raw_results.items()]
    return BatchMeshResponse(
        results=items,
        count=len(items),
        validated_count=sum(1 for r in items if r.valid),
    )
