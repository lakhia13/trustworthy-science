from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException
from trustworthy_science.server.schemas import HealthResponse, ReloadConfigRequest, ReloadConfigResponse
from trustworthy_science.server.dependencies import get_truth_filter, reload_truth_filter
from trustworthy_science.api import TruthFilter

logger = logging.getLogger(__name__)
router = APIRouter()

_VERSION = "0.1.0"

@router.get("/health", response_model=HealthResponse, summary="Health check", tags=["admin"])
def health() -> HealthResponse:
    """Returns {"status": "ok"} when the server is running."""
    return HealthResponse(status="ok", version=_VERSION)

@router.post("/reload-config", response_model=ReloadConfigResponse, summary="Hot-reload scoring config", tags=["admin"])
def reload_config(
    request: ReloadConfigRequest,
    tf: TruthFilter = Depends(get_truth_filter),
) -> ReloadConfigResponse:
    """Rebuild the LangGraph pipeline from a (possibly updated) scoring YAML.

    Pass an optional `config_path` to load a different YAML file.
    Omit it to reload from the default `config/scoring.yaml`.
    In-flight scoring requests are not affected; only new requests use the
    rebuilt graph.
    """
    from pathlib import Path
    from trustworthy_science.api import _DEFAULT_CONFIG as DEFAULT_CFG

    target = request.config_path or str(DEFAULT_CFG)
    try:
        reload_truth_filter(target)
    except Exception as exc:
        logger.error("Config reload failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Config reload failed: {exc}")

    return ReloadConfigResponse(reloaded=True, config_path=target)
