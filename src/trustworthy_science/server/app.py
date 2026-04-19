"""FastAPI application factory and uvicorn entry-point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from trustworthy_science.server.dependencies import init_truth_filter
from trustworthy_science.server.routes.search import router as search_router
from trustworthy_science.server.routes.score import router as score_router
from trustworthy_science.server.routes.explain import router as explain_router
from trustworthy_science.server.routes.filter import router as filter_router
from trustworthy_science.server.routes.admin import router as admin_router
from trustworthy_science.server.routes.deep_research import router as deep_research_router

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # project root
_DEFAULT_CONFIG = str(_REPO_ROOT / "config" / "scoring.yaml")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: build the TruthFilter singleton. Shutdown: nothing to clean up."""
    logger.info("[SERVER] Initialising TruthFilter from %s", _DEFAULT_CONFIG)
    init_truth_filter(_DEFAULT_CONFIG)
    logger.info("[SERVER] TruthFilter ready.")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trustworthy Science API",
        version="0.1.0",
        description=(
            "AI-powered credibility filter for scientific literature. "
            "Scores papers by DOI or PMID and returns trust tier, flags, "
            "and per-dimension analysis."
        ),
        lifespan=lifespan,
    )

    # Global JSON error handler — ensures all 500s return JSON, not HTML
    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    app.include_router(search_router,        prefix="/api/search",        tags=["search"])
    app.include_router(score_router,         prefix="/score",             tags=["scoring"])
    app.include_router(explain_router,       prefix="/explain",           tags=["scoring"])
    app.include_router(filter_router,        prefix="/filter",            tags=["filtering"])
    app.include_router(admin_router,         prefix="/admin",             tags=["admin"])
    app.include_router(deep_research_router, prefix="/api/deep-research", tags=["deep-research"])

    return app


app = create_app()


def start() -> None:
    """Entry-point called by `uv run trustworthy-science-server`.

    Runs a single uvicorn worker. The LangGraph graph and TruthFilter singleton
    are process-local — use workers=1 for an MVP/dev deployment.
    For horizontal scale-out, run behind a process manager (e.g. gunicorn with
    uvicorn workers); each worker will build its own TruthFilter on startup.
    """
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(
        "trustworthy_science.server.app:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        workers=1,
    )
