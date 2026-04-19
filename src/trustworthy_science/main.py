"""FastAPI REST API for Trustworthy Science — exposes TruthFilter over HTTP."""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from trustworthy_science.service import get_truth_filter
from trustworthy_science.routes.papers import router as papers_router
from trustworthy_science.routes.review import router as review_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup
    logger.info("Trustworthy Science API starting up...")
    get_truth_filter()  # Initialize TruthFilter at startup
    yield
    # Shutdown
    logger.info("Trustworthy Science API shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Trustworthy Science API",
    description="REST API for assessing scientific paper credibility",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Local development
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:3000",
        # Production — DigitalOcean Droplet (replace with actual IP/domain)
        # "http://YOUR_DROPLET_IP",
        # "https://yourdomain.com",
        # "https://www.yourdomain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health & Status Routes
# ============================================================================


@app.get("/", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "Trustworthy Science API"}


@app.get("/health", tags=["health"])
async def health_status() -> dict[str, Any]:
    """Detailed health status."""
    return {
        "status": "ok",
        "service": "Trustworthy Science API",
        "version": "1.0.0",
    }


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle validation errors."""
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={
            "error": str(exc),
            "code": "validation_error",
        },
    )


@app.exception_handler(TimeoutError)
async def timeout_error_handler(request, exc):
    """Handle timeout errors."""
    logger.error(f"Timeout error: {exc}")
    return JSONResponse(
        status_code=504,
        content={
            "error": "Request timed out",
            "code": "timeout_error",
        },
    )


@app.exception_handler(Exception)
async def general_error_handler(request, exc):
    """Handle all other errors."""
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": "internal_error",
        },
    )


# ============================================================================
# Router Registration
# ============================================================================

app.include_router(papers_router, prefix="/api", tags=["papers"])
app.include_router(papers_router, tags=["papers"])

# Graph RAG — Literature Review Sessions
app.include_router(review_router, prefix="/review", tags=["review"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
