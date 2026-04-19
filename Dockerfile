# ─── Trustworthy Science — Backend Dockerfile ───────────────────────────────
# Builds the FastAPI + uvicorn backend.
# Frontend static files are served separately by nginx (see deployment docs).
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

WORKDIR /app

# System dependencies needed by lxml / chromadb / sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv

# Copy dependency manifests first (layer cache — only reinstall if these change)
COPY pyproject.toml uv.lock ./

# Install Python dependencies (no dev extras)
RUN uv pip install --system --no-dev .

# Copy application source and config
COPY src/ src/
COPY config/ config/

# Expose the API port
EXPOSE 8000

# Health check — curl the /health endpoint every 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run uvicorn (2 workers; tune up if you have more RAM)
CMD ["uvicorn", "trustworthy_science.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info"]
