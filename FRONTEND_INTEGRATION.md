# Frontend Integration Guide

This document explains how to run the backend (Python) and frontend (React) together.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│  Browser (http://localhost:5173)             │
│  React App (Vite + TypeScript + Tailwind)    │
└───────────────┬──────────────────────────────┘
                │ HTTP/REST API (Axios)
                ↓
┌──────────────────────────────────────────────┐
│  Backend (http://localhost:8000)             │
│  FastAPI + LangGraph (Python)                │
│  - POST /score                               │
│  - POST /filter                              │
│  - GET /paper/{doi}                          │
└──────────────────────────────────────────────┘
```

---

## Running Locally (Development)

### Terminal 1: Backend (Python)

```bash
# From repo root
source .venv/bin/activate
# or: .venv/bin/activate

# Start the backend API
python -m trustworthy_science.cli  # Or use FastAPI wrapper

# Expected output:
# Uvicorn running on http://127.0.0.1:8000
```

### Terminal 2: Frontend (React/Node)

```bash
cd frontend
pnpm install          # (first time only)
pnpm dev

# Expected output:
# VITE v6.3.5  ready in XXX ms
# ➜  Local:   http://localhost:5173
```

### Terminal 3: Optional — Run Python Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## API Endpoints

The frontend expects these endpoints on the backend:

### 1. Score Papers (by DOI or query)

**POST** `/score`

```json
{
  "dois": ["10.1038/s41586-020-2748-1"],
  "query": null,
  "top_k": 10
}
```

**Response:**
```json
{
  "papers": [
    {
      "doi": "10.1038/...",
      "title": "...",
      "score": 78,
      "tier": "Trusted",
      "summary": "...",
      "hard_flags": [],
      "soft_flags": [{...}],
      "quality_signals": [{...}],
      "coverage": "metadata_only"
    }
  ]
}
```

### 2. Filter for RAG

**POST** `/filter`

```json
{
  "query": "GLP-1 receptor agonists",
  "top_k": 20,
  "min_tier": "Caution"
}
```

**Response:** Same as /score, but only returns papers where `tier >= min_tier`

### 3. Get Single Paper

**GET** `/paper/{doi}`

**Response:** Single paper object from /score

---

## Frontend Configuration

In `frontend/.env.local`:

```
VITE_API_URL=http://localhost:8000
VITE_LOG_LEVEL=debug
```

The frontend's API client (`src/api/client.ts`) reads this:

```typescript
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function scorepapers(body) {
  const res = await fetch(`${API_BASE}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}
```

---

## CORS Setup

The backend must allow requests from `http://localhost:5173`.

**Backend (FastAPI):**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Building for Production

### Frontend Build

```bash
cd frontend
pnpm build

# Output in frontend/dist/
# Upload dist/ to your hosting (Vercel, Netlify, etc.)
```

### Backend Build

```bash
# Package as Docker or gunicorn/uvicorn
python -m pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker trustworthy_science.main:app
```

---

## Docker Compose (Optional)

Create `docker-compose.yml` at repo root:

```yaml
version: "3.8"
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - K2_API_KEY=${K2_API_KEY}
    volumes:
      - ./config:/app/config

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://backend:8000
    depends_on:
      - backend
```

**Run:**
```bash
docker-compose up
# http://localhost:5173 (frontend)
# http://localhost:8000 (backend)
```

---

## Troubleshooting

### "Failed to fetch from http://localhost:8000"
- ✅ Backend is running on port 8000?
- ✅ CORS headers are set?
- ✅ `.env.local` has correct API URL?

### "Module not found" (frontend)
```bash
cd frontend
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### "Connection refused" on backend
- ✅ Python venv activated?
- ✅ K2_API_KEY set in `.env`?
- ✅ Port 8000 not used by another process?

---

## Next Steps

1. ✅ Backend running: `source .venv/bin/activate && pytest tests/ -v`
2. ✅ Frontend deps: `cd frontend && pnpm install`
3. ✅ Start both servers (2 terminals)
4. ✅ Open http://localhost:5173 in browser
5. ✅ Test: Search by DOI in frontend
6. ✅ Verify API calls in browser DevTools (Network tab)

---

## File Structure

```
trustworthy-science/
├── src/                          # Backend Python code
│   ├── trustworthy_science/
│   │   ├── api.py               # Public API (TruthFilter class)
│   │   ├── cli.py               # CLI interface
│   │   └── ...
│   └── ...
├── frontend/                     # React/Vite app
│   ├── src/
│   │   ├── api/                 # API client
│   │   ├── components/          # UI components
│   │   ├── pages/               # Page containers
│   │   └── ...
│   ├── package.json
│   └── vite.config.ts
├── config/scoring.yaml           # Scoring configuration
├── tests/                        # Backend tests
├── .env                          # Backend env (K2_API_KEY, etc.)
├── README.md                     # This repo's README
└── FIGMA_DESIGN_BRIEF.md        # Frontend design spec
```

---

## Design & Frontend Plan

See [FIGMA_DESIGN_BRIEF.md](FIGMA_DESIGN_BRIEF.md) for:
- 5 screen designs (Landing, Search by DOI, Search by Query, Detail, RAG Comparison)
- Color palette (Trusted=green, Caution=amber, Untrusted=red)
- Typography & spacing
- Interactive flows

See [frontend/FRONTEND_README.md](frontend/FRONTEND_README.md) for:
- Component structure
- Type definitions
- Development workflow
- Deployment options
