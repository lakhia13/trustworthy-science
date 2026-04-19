# Trustworthy Science Backend Architecture

Complete technical overview of the backend implementation for the Trustworthy Science credibility assessment system.

---

## Table of Contents

1. [Entry Points](#entry-points--app-structure)
2. [API Routes](#api-routes)
3. [Agent Pipeline](#core-agents--flow)
4. [State Management](#state-management)
5. [Scoring System](#scoring-system)
6. [External Integrations](#external-integrations)
7. [LLM Integration](#llm-integration)
8. [Caching](#caching--optimization)
9. [Error Handling](#error-handling)
10. [Data Flows](#data-flow-diagrams)
11. [File Locations](#key-file-locations--roles)
12. [Configuration](#configuration)
13. [System Connectivity](#connectivity-summary)

---

## Entry Points & App Structure

### Main Application Factory

**File:** `src/trustworthy_science/server/app.py`

```python
def create_app() -> FastAPI:
    """FastAPI factory that initializes the app with all routes and middleware."""
    # Lifespan handler calls init_truth_filter() on startup
    # Global exception handler returns JSON for all errors
    # Includes 6 routers: score, filter, explain, admin, search, deep_research
    return app

app = create_app()  # Module-level singleton

def start() -> None:
    """Entry-point for `trustworthy-science-server` command."""
    uvicorn.run("trustworthy_science.server.app:app", host="0.0.0.0", port=8001, workers=1)
```

**Key Points:**
- Lifespan handler initializes `TruthFilter` singleton from `config/scoring.yaml`
- Global exception handler catches all exceptions → JSON 500 response with error detail
- Single-worker design (graph state is process-local; use load balancer for scaling)

### Public API Interface

**File:** `src/trustworthy_science/api.py`

```python
class TruthFilter:
    """High-level API for scoring and filtering scientific papers."""
    
    @classmethod
    def from_config(cls, config_path: str = "config/scoring.yaml") -> TruthFilter:
        """Load configuration and initialize graphs."""
        
    async def score_papers(
        self,
        dois: list[str] | None = None,
        pmids: list[str] | None = None,
        query: str | None = None,
        top_k: int = 10,
    ) -> list[PaperResult]:
        """Score papers synchronously (blocking)."""
        
    async def filter_for_rag(
        self,
        query: str,
        top_k: int = 10,
        min_tier: str = "Caution",
    ) -> list[PaperResult]:
        """Retrieve and filter papers for RAG pipelines."""
        
    async def score_single(doi: str) -> TrustReport:
        """Score one paper by DOI."""
        
    async def deep_research(
        self,
        prompt: str,
        top_k: int = 10,
        min_tier: str = "Caution",
    ) -> DeepResearchResult:
        """Full research pipeline: query generation → retrieval → scoring → RAG ingest."""
        
    def reload_config(self, config_path: str) -> None:
        """Hot-reload configuration and rebuild graphs (thread-safe)."""
```

### Dependency Injection

**File:** `src/trustworthy_science/server/dependencies.py`

```python
_truth_filter: TruthFilter | None = None
_reload_lock: threading.RLock = threading.RLock()

def init_truth_filter(config_path: str) -> None:
    """Called on app startup to initialize singleton."""
    global _truth_filter
    _truth_filter = TruthFilter.from_config(config_path)

async def get_truth_filter() -> TruthFilter:
    """FastAPI dependency for route handlers."""
    if _truth_filter is None:
        raise RuntimeError("TruthFilter not initialized")
    return _truth_filter

def reload_truth_filter(config_path: str) -> None:
    """Thread-safe hot reload (used by /admin/reload-config)."""
    with _reload_lock:
        init_truth_filter(config_path)
```

---

## API Routes

### Route Summary

| Endpoint | Method | File | Purpose | Request | Response |
|----------|--------|------|---------|---------|----------|
| `/score` | POST | routes/score.py | Score papers (DOI/PMID/query) | SearchRequest | ScoreResponse |
| `/filter` | POST | routes/filter.py | Filter papers for RAG | FilterRequest | FilterResponse |
| `/explain` | POST | routes/explain.py | Detailed report | ExplainRequest | TrustReport |
| `/admin/reload-config` | POST | routes/admin.py | Hot reload config | ReloadConfigRequest | {status} |
| `/admin/health` | GET | routes/admin.py | Health check | — | {status, ok} |
| `/api/search` | POST/GET | routes/search.py | Async search job | SearchRequest | JobResponse |
| `/api/deep-research` | POST/GET | routes/deep_research.py | Research pipeline + chat | DeepResearchRequest | Job tracking |

### Request/Response Schemas

**SearchRequest:**
```python
class SearchRequest(BaseModel):
    dois: list[str] = []           # DOIs to score
    pmids: list[str] = []          # PubMed IDs
    query: str | None = None       # Natural language query
    top_k: int = 10                # 1-50, max results to return
```

**FilterRequest:**
```python
class FilterRequest(BaseModel):
    query: str                     # Natural language query
    top_k: int = 10                # 1-50
    min_tier: str = "Caution"      # "Trusted", "Caution", "Untrusted"
```

**ExplainRequest:**
```python
class ExplainRequest(BaseModel):
    doi: str | None = None         # Exactly one must be provided
    pmid: str | None = None        # (XOR validation in route)
```

**ScoreResponse:**
```python
class ScoreResponse(BaseModel):
    papers: list[PaperResult]
    count: int
    query: str | None              # Original search query
    retrieved_from: list[str]      # ["PubMed", "bioRxiv", "Crossref"]
```

**PaperResult:**
```python
class PaperResult(BaseModel):
    title: str
    doi: str | None
    pmid: str | None
    year: int | None
    venue: str                     # Journal/conference name
    authors: list[str]
    
    # Credibility assessment
    score: int                     # 0-100
    tier: Literal["Trusted", "Caution", "Untrusted"]
    coverage: Literal["full_text", "abstract_only", "metadata_only"]
    fetch_source: str              # Which API provided full text
    
    # Detailed breakdown
    summary: str                   # Executive summary
    hard_flags: list[Flag]         # Disqualifying issues
    soft_flags: list[Flag]         # Credibility concerns
    quality_signals: list[Flag]    # Positive indicators
    per_dimension: list[DimensionScore]  # {dimension, score, reason}
    
    # Structured report
    structured_report: StructuredReport | None
```

---

## Core Agents & Flow

### Per-Paper Sub-Graph Architecture

The LangGraph per-paper graph executes agents sequentially and in parallel:

```
┌─────────────────────────────────────────────────────┐
│                    START                             │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │   fetch_parse        │ ◄─── Retrieve full text from 7 sources
          │                      │      (BioC, PMC, PDF, bioRxiv, Semantic Scholar, Abstract)
          └────────┬─────────────┘
                   │
                   ▼
          ┌──────────────────────┐
          │  retraction_watch    │ ◄─── Check if paper is retracted
          └────────┬─────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
    [RETRACTED]          [NOT RETRACTED]
         │                   │
         │                   ▼
         │         ┌─────────────────────┐
         │         │ paper_classifier    │ ◄─── Classify into 8 paper types
         │         └──────────┬──────────┘
         │                    │
         │                    ▼
         │         ┌─────────────────────┐
         │         │ stats_integrity     │ ◄─── P-curve, Benford's, effect sizes
         │         └──────────┬──────────┘
         │                    │
         │         ┌──────────┴──────────┐
         │         │  [PARALLEL SPLIT]   │
         │         │                     │
         │    ┌────▼────┐  ┌────────────────┐  ┌─────────────────┐
         │    │  repro  │  │ citation_net   │  │  methodology    │
         │    │ (regex) │  │ (OpenAlex API) │  │  (LLM prompt)   │
         │    └────┬────┘  └────────┬───────┘  └────────┬────────┘
         │         │                │                    │
         │         └────────┬───────┴──────────┬─────────┘
         │                  │                  │
         │                  ▼                  │
         │         ┌──────────────────┐       │
         │         │ publication_meta │       │ ◄─── DOAJ check, Beall's heuristics
         │         └────────┬─────────┘       │
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │     scoring          │ ◄─── Deterministic formula + LLM report
                 └──────────┬───────────┘
                            │
                            ▼
                    ┌────────────────┐
                    │  TrustReport   │
                    │  (final result)│
                    └────────────────┘
```

### Agent Details

| Agent | File | Input | Output | Logic |
|-------|------|-------|--------|-------|
| **fetch_parse** | `agents/fetch_parse.py` | PaperStub (doi/pmid) | ParsedPaper + coverage | 7-step cascade: BioC→PMC→PDF→bioRxiv→Semantic Scholar→Abstract. Segments into title, abstract, methods, results, discussion, references. |
| **retraction_watch** | `agents/retraction_watch.py` | stub | retracted: bool | HTTP call to retraction-watch.org API |
| **paper_classifier** | `agents/paper_classifier.py` | title+abstract | paper_type: str | Regex patterns for 8 types: empirical_quantitative, clinical_trial, systematic_review_meta, review_narrative, theoretical, computational_methods, case_report, opinion_commentary |
| **stats_integrity** | `agents/stats_integrity.py` | parsed text | SubScore + Flags | P-curve analysis (p-hacking detection), Benford's Law (fabrication), effect size extraction, underpowered sample detection. Type-aware (skipped for non-empirical). |
| **reproducibility** | `agents/reproducibility.py` | text + paper_type | SubScore + Flags/Signals | Regex search for data repos, code URLs, pre-registration IDs. Type-aware (e.g., code optional for theory, preregistration required for clinical trials). |
| **citation_network** | `agents/citation_network.py` | DOI | SubScore + Flags | OpenAlex API query: self-citation ratio, institutional diversity of citing papers. Soft flag if self-citations > threshold. |
| **methodology** | `agents/methodology.py` | methods section | SubScore (via LLM) | K2-Think-v2 JSON critique: sample_size_justified, controls, blinding, prespecified stats, outcome definition clarity, reproducibility detail, 0-1 score. |
| **publication_metadata** | `agents/publication_metadata.py` | venue, ISSN, DOI | SubScore + Flags | DOAJ journal check (legitimate), Beall's List heuristics (predatory), Crossref review speed, impact factor check. |
| **scoring** | `agents/scoring.py` | all SubScores + Flags | TrustReport | Deterministic formula: base - penalties + bonuses + methods_nudge. If hard flags exist, cap at 25. LLM generates narrative report. |

### Agent Implementation Pattern

All agents follow this interface:

```python
async def agent_name(state: PaperState) -> dict:
    """
    Async function that reads from state and updates it.
    
    LangGraph automatically merges dict return values into state.
    For list fields with reducer=operator.add, dicts append to the list.
    """
    # Read input
    stub = state.stub
    parsed = state.parsed
    paper_type = state.paper_type
    
    # Compute (call APIs, LLM, statistical functions)
    result = ...
    
    # Return updates as dict
    return {
        "sub_scores": {
            "agent_name": SubScore(
                score=float(0-1),
                confidence=float(0-1),
                flags=[Flag(...)],
                reason="..."
            )
        },
        "soft_flags": [Flag(...)],     # appended via operator.add
        "quality_signals": [Flag(...)], # appended via operator.add
    }
```

---

## State Management

### PaperState: Complete Data Model

**File:** `src/trustworthy_science/state.py`

```python
class PaperStub(BaseModel):
    """Minimal paper identity."""
    doi: str | None
    pmid: str | None
    title: str
    authors: list[str]
    year: int | None
    venue: str
    abstract: str | None

class ParsedPaper(BaseModel):
    """Full text segmentation."""
    full_text: str
    abstract: str | None
    methods: str | None
    results: str | None
    discussion: str | None
    references: list[str]
    keywords: list[str]

class Flag(BaseModel):
    """Indicator (hard, soft, quality)."""
    code: str                   # e.g., "P_HACKING_CLUSTER", "OPEN_DATA"
    message: str
    source_agent: str          # which agent emitted this
    evidence: list[EvidenceQuote]  # {text: str, section: str}
    severity: Literal["hard", "soft", "quality"]

class SubScore(BaseModel):
    """Per-agent credibility component."""
    score: float (0-1)
    confidence: float (0-1)
    flags: list[Flag]
    notes: str
    reason: str                # used in per_dimension output

class DimensionScore(BaseModel):
    """Score breakdown by dimension."""
    dimension: str             # "statistical_integrity", "reproducibility", etc.
    score: float (0-100)
    reason: str

class StructuredReport(BaseModel):
    """LLM-generated structured assessment."""
    overall_verdict: str
    score_breakdown: str
    key_concerns: list[str]
    positive_signals: list[str]
    recommendation: str

class TrustReport(BaseModel):
    """Final credibility verdict."""
    composite_score: int (0-100)
    tier: Literal["Trusted", "Caution", "Untrusted"]
    summary: str               # executive summary
    hard_flags: list[Flag]
    soft_flags: list[Flag]
    quality_signals: list[Flag]
    per_dimension: list[DimensionScore]
    coverage: Literal["full_text", "abstract_only", "metadata_only"]
    structured_report: StructuredReport | None

class PaperState(BaseModel):
    """Complete paper credibility assessment state (flows through graph)."""
    
    # Input
    stub: PaperStub
    
    # Intermediate
    parsed: ParsedPaper | None = None
    coverage: Literal["full_text", "abstract_only", "metadata_only"] | None = None
    paper_type: str | None = None                      # 8 classifier outputs
    retracted: bool = False
    
    # Accumulated from agents (reducer=operator.add appends to lists)
    sub_scores: dict[str, SubScore] = {}               # {agent_name: SubScore}
    hard_flags: list[Flag] = []                        # via operator.add
    soft_flags: list[Flag] = []                        # via operator.add
    quality_signals: list[Flag] = []                   # via operator.add
    
    # Final
    final: TrustReport | None = None
    
    # Error tracking
    error: str | None = None
```

### State Flow Through Graph

```
PaperState (initial) {stub, parsed=None, hard_flags=[], ...}
     ↓ fetch_parse
     {stub, parsed=ParsedPaper(...), coverage="full_text", ...}
     ↓ retraction_watch
     {retracted=True/False, ...}
     ↓ paper_classifier
     {paper_type="clinical_trial", ...}
     ↓ [PARALLEL: stats_integrity, reproducibility, citation_network, methodology, publication_metadata]
     {sub_scores={stat:SubScore, repro:SubScore, ...}, hard_flags=[...], soft_flags=[...], quality_signals=[...]}
     ↓ scoring
     {final=TrustReport(...), composite_score=72, tier="Trusted", ...}
     ↓
PaperState (final)
```

**Key Mechanism:** LangGraph `Annotated` types with `reducer=operator.add` on list fields automatically append dict values:

```python
hard_flags: Annotated[list[Flag], operator.add] = []

# When agents return {"hard_flags": [Flag(...)]}, LangGraph appends (not replaces)
# allowing multiple agents to emit flags in parallel
```

---

## Scoring System

### Scoring Formula

**File:** `src/trustworthy_science/scoring/rules.py`

```
score = base_score 
        - sum(soft_flag_penalties)
        + min(sum(quality_bonuses), bonus_cap)
        + methods_nudge_bonus
        
score = clamp(score, 0, 100)

if hard_flags exist:
    score = min(score, hard_flag_cap)
    tier = "Untrusted"
elif score >= trusted_threshold:
    tier = "Trusted"
elif score >= caution_threshold:
    tier = "Caution"
else:
    tier = "Untrusted"
```

### Default Scoring Parameters

From `scoring/rules.py` + `config/scoring.yaml`:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `base_score` | 70 | Starting score |
| `bonus_cap` | 20 | Max total quality bonuses |
| `methods_nudge_weight` | 0.15 | Weight of methodology agent on bonus |
| `trusted_threshold` | 70 | Score ≥ 70 → Trusted |
| `caution_threshold` | 45 | Score ≥ 45 → Caution |
| `hard_flag_cap` | 25 | Score capped at 25 if hard flags exist |

### Soft Flag Penalties (Configurable)

Examples from config:

| Flag Code | Penalty | Triggered When |
|-----------|---------|----------------|
| `NO_DATA_DEPOSIT` | -8 | No data repository found |
| `NO_CODE_AVAILABILITY` | -5 | No code URL found |
| `HIGH_SELF_CITATION` | -7 | Self-citation ratio > threshold |
| `MISSING_EFFECT_SIZES` | -6 | No effect sizes reported |
| `SMALL_SAMPLE_UNDERPOWERED` | -6 | Sample size < threshold for given effect |
| `METHODS_INCOMPLETE` | -8 | Methods section incomplete (LLM critique) |
| `OUTCOME_SWITCHING` | -10 | Detected via text analysis |
| `PREDATORY_VENUE` | -15 | Beall's List or heuristic match |

### Quality Signal Bonuses (Configurable)

| Signal Code | Bonus | Triggered When |
|-------------|-------|----------------|
| `PREREGISTERED` | +6 | Pre-registration ID found |
| `OPEN_DATA` | +6 | Data repository URL found |
| `OPEN_CODE` | +4 | Code repository URL found |
| `INDEPENDENTLY_REPLICATED` | +10 | Citation pattern indicates replication |
| `DIVERSE_CITATIONS` | +4 | High institutional diversity in citations |
| `HIGH_IMPACT_VENUE` | +3 | DOAJ approved or high impact factor |

### Hard Flags (Instant Disqualification)

If **any** hard flag exists, score is capped at 25:

| Hard Flag | Source | Condition |
|-----------|--------|-----------|
| `RETRACTED` | retraction_watch agent | Paper appears in Retraction Watch DB |
| `P_HACKING_CLUSTER` | stats_integrity agent | P-curve analysis shows significant clustering in p < 0.05 |
| `PREDATORY_VENUE` | publication_metadata agent | Journal matches Beall's List heuristics |
| `OUTCOME_SWITCHING_CONFIRMED` | agents (LLM + text) | Text analysis + LLM confirm outcome switching |
| `IMAGE_MANIPULATION` | agents (future) | Reserved for image forensics |

### Paper Type Applicability Matrix

From `config/scoring.yaml`:

```yaml
paper_type_applicability:
  empirical_quantitative:
    data: true          # penalize if no data
    code: true          # penalize if no code
    preregistration: true
  clinical_trial:
    data: true
    code: false         # code not expected
    preregistration: true
  systematic_review_meta:
    data: true
    code: false
    preregistration: false  # meta-analyses don't need preregistration
  review_narrative:
    data: false         # no penalty for narrative reviews
    code: false
    preregistration: false
  theoretical:
    data: false         # no penalty for theory papers
    code: false
    preregistration: false
  computational_methods:
    data: false         # methods papers don't need raw data
    code: true          # but should have code
    preregistration: false
  case_report:
    data: false
    code: false
    preregistration: false
  opinion_commentary:
    data: false
    code: false
    preregistration: false
```

**Effect:** Agents skip checks for non-applicable types. No penalty, no bonus — just skipped.

Example: A theoretical model paper won't lose points for missing data or code.

---

## External Integrations

### PubMed Integration

**File:** `src/trustworthy_science/tools/pubmed.py`

```python
async def search_pubmed(query: str, max_results: int = 10) -> list[str]:
    """Search PubMed, return list of PMIDs."""
    # NCBI E-utilities API (Entrez)
    # Uses optional NCBI_API_KEY for higher rate limit (10 req/sec vs 3)
    
async def fetch_pubmed_metadata(pmids: list[str]) -> list[PaperStub]:
    """Fetch metadata (title, authors, year, abstract) from PubMed XML."""
    # Parses <MedlineCitation> XML structure
    
async def fetch_bioc_fulltext(pmid: str) -> tuple[str, dict[str, str]]:
    """Fetch full text from BioC (NCBI's annotated XML format)."""
    # Returns (full_text, sections_dict={abstract, methods, results, discussion})
    
async def fetch_pmc_fulltext(pmcid: str) -> str:
    """Fetch full text from PubMed Central (open-access articles)."""
    # Uses NCBI Open Archives API
```

**Caching:** All calls cached for 7 days in SQLite (`~/.cache/trustworthy_science/api_cache.db`)

### bioRxiv/medRxiv Integration

**File:** `src/trustworthy_science/tools/biorxiv.py`

```python
async def search_biorxiv(query: str, max_results: int = 10) -> list[PaperStub]:
    """Search bioRxiv/medRxiv via EuropePMC API (free, no auth)."""
    
async def fetch_biorxiv_fulltext(doi: str) -> str:
    """Fetch full text PDF as text via EuropePMC."""
    
async def fetch_biorxiv_by_doi(doi: str) -> PaperStub:
    """Get metadata from bioRxiv by DOI."""
```

### Crossref Integration

**File:** `src/trustworthy_science/tools/crossref.py`

```python
async def doi_to_stub(doi: str) -> PaperStub:
    """Convert DOI to paper metadata (title, authors, venue, year)."""
    # Crossref REST API (free, polite usage)
    
async def search_crossref(query: str, max_results: int = 10) -> list[PaperStub]:
    """Full-text search via Crossref."""
    
async def get_work(doi: str) -> dict:
    """Full Crossref metadata for DOI (references, citations, etc.)."""
    
async def get_submission_acceptance_days(doi: str) -> int:
    """Estimate days between submission and acceptance."""
```

### OpenAlex Integration

**File:** `src/trustworthy_science/tools/openalex.py`

```python
async def citation_diversity_score(doi: str) -> tuple[float, int, float]:
    """Query OpenAlex for citation network diversity.
    
    Returns: (diversity_ratio, n_citations, self_citation_ratio)
    """
    # OpenAlex REST API (free)
    # diversity_ratio = institutional_diversity / max_possible
    # self_citation_ratio = papers from same authors / total
```

### Retraction Watch

**File:** `src/trustworthy_science/tools/retraction_watch.py`

```python
async def is_retracted(doi: str) -> bool:
    """Check if paper is retracted."""
    # Simple HTTP HEAD check for known retracted DOIs
```

### Statistical Analysis Tools (No External APIs)

**P-Curve Analysis** (`tools/pcurve.py`):
```python
def analyze_pcurve(pvalues: list[float]) -> dict:
    """Detect p-hacking via p-curve distribution analysis.
    
    Returns: {is_phacked, clustering_ratio, evidence_strength}
    """
```

**Benford's Law** (`tools/benfords_law.py`):
```python
def benford_test(numbers: list[float]) -> dict:
    """Detect fabricated/manipulated data via Benford's Law."""
```

**P-Value & Effect Size Extraction** (`tools/pvalue_extract.py`):
```python
def extract_pvalues(text: str) -> list[float]:
    """Regex extraction of p-values from methods/results."""
    
def extract_effect_sizes(text: str) -> list[float]:
    """Regex extraction of effect sizes (Cohen's d, OR, RR, etc.)."""
    
def extract_sample_sizes(text: str) -> list[int]:
    """Regex extraction of N (sample sizes)."""
```

### Vector Store (RAG)

**File:** `src/trustworthy_science/tools/chroma_store.py`

```python
async def ingest_papers(
    papers: list[dict],      # {title, abstract, full_text, doi, ...}
    collection_name: str,
    config: dict,            # {embedding_model, chunk_size, ...}
) -> ChromaVectorStore:
    """Ingest papers into Chroma (uses sentence-transformers embedding)."""
    # Chunks text, embeds, stores in local SQLite or persistent backend
    
async def query_collection(
    query: str,
    collection_name: str,
    top_k: int = 10,
) -> list[dict]:
    """Retrieve most similar documents."""
```

---

## LLM Integration

### LLM Client Setup

**File:** `src/trustworthy_science/llm.py`

```python
def get_llm_client(config: dict) -> ChatOpenAI:
    """Factory function for K2-Think-v2 LLM client.
    
    Config:
    {
        "base_url": "https://api.k2think.ai/v1",
        "model": "MBZUAI-IFM/K2-Think-v2",
        "api_key": os.getenv("K2_API_KEY"),
        "temperature": 0.3,
        "max_tokens": 2000,
    }
    """
    return ChatOpenAI(
        model="MBZUAI-IFM/K2-Think-v2",
        base_url="https://api.k2think.ai/v1",
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
```

### Where LLM is Used

#### 1. Methodology Agent

**File:** `src/trustworthy_science/agents/methodology.py`

```python
async def methodology_agent(state: PaperState) -> dict:
    """LLM critique of methodology section."""
    
    prompt = f"""
    Review the following methodology section and provide a JSON critique.
    
    Criteria:
    - Sample size justified?
    - Controls/comparison groups described?
    - Blinding (if applicable)?
    - Pre-specified statistics?
    - Clear outcome definitions?
    
    {state.parsed.methods}
    
    Respond with JSON only:
    {{
        "sample_size_justified": bool,
        "controls_described": bool,
        "blinding_described": bool,
        "stats_prespecified": bool,
        "outcome_clearly_defined": bool,
        "reproducibility_detail_sufficient": bool,
        "overall_score": float (0-1),
        "weaknesses": [str],
        "strengths": [str],
    }}
    """
    
    response = llm_client.invoke(prompt)
    json_result = json.loads(strip_think_tokens(response.content))
    
    return {
        "sub_scores": {
            "methodology": SubScore(
                score=json_result["overall_score"],
                confidence=0.8,
                reason=f"LLM critique: {json_result['weaknesses']}"
            )
        }
    }
```

#### 2. Structured Report Generation

**File:** `src/trustworthy_science/agents/scoring.py`

```python
async def generate_structured_report(
    state: PaperState,
    llm_client: ChatOpenAI,
) -> StructuredReport:
    """Generate narrative report using LLM."""
    
    prompt = f"""
    Synthesize the following credibility assessment into a structured report.
    
    Paper: {state.stub.title}
    Composite Score: {state.final.composite_score}
    Tier: {state.final.tier}
    
    Hard Flags: {[f.code for f in state.hard_flags]}
    Soft Flags: {[f.code for f in state.soft_flags]}
    Quality Signals: {[f.code for f in state.quality_signals]}
    
    Per-dimension scores: {state.final.per_dimension}
    
    Generate a structured report with:
    1. OVERALL VERDICT (1 sentence)
    2. SCORE BREAKDOWN (explain the score)
    3. KEY CONCERNS (list top 3)
    4. POSITIVE SIGNALS (list strengths)
    5. RECOMMENDATION (for researchers/RAG)
    
    Keep output concise and evidence-based.
    """
    
    response = llm_client.invoke(prompt)
    # Parse response into StructuredReport
    return StructuredReport(...)
```

### Think Token Handling

K2-Think-v2 returns extended thinking in XML tags:

```python
def strip_think_tokens(response: str) -> str:
    """Remove <think>, <thinking>, <reasoning> blocks, keep final answer."""
    # Handles:
    # - <think>...</think>
    # - <thinking>...</thinking>
    # - <reasoning>...</reasoning>
    # - ```thinking ... ``` fenced blocks
    # Returns just the answer text
```

---

## Caching & Optimization

### SQLite Request Cache

**File:** `src/trustworthy_science/cache/sqlite_cache.py`

```python
class RequestCache:
    def __init__(self, db_path: str = "~/.cache/trustworthy_science/api_cache.db", ttl_days: int = 7):
        """SQLite cache for API responses."""
        # Creates tables per namespace: pubmed, biorxiv, crossref, pub_meta
        
    def get(self, namespace: str, *args, **kwargs) -> Any | None:
        """Retrieve cached result if fresh (< ttl_days old)."""
        # Key = SHA-256(namespace, *args, **kwargs)
        
    def set(self, namespace: str, result: Any, *args, **kwargs) -> None:
        """Cache result with timestamp."""
        
    def clear(self, namespace: str | None = None) -> None:
        """Clear cache (namespace or all)."""
```

### Cache Usage Pattern

All external API tools follow this pattern:

```python
async def fetch_pubmed_metadata(pmids: list[str]) -> list[PaperStub]:
    cache = get_cache()
    
    # Try cache first
    cached = cache.get("pubmed", tuple(pmids))
    if cached is not None:
        return cached
    
    # API call
    results = await _fetch_from_ncbi(pmids)
    
    # Cache result
    cache.set("pubmed", results, tuple(pmids))
    return results
```

### Deduplication

In multi-paper scoring, papers are deduplicated by {doi, pmid, title}:

```python
def _deduplicate_papers(papers: list[PaperStub]) -> list[PaperStub]:
    """Remove duplicates by (doi, pmid, title)."""
    seen = set()
    unique = []
    for paper in papers:
        key = (paper.doi, paper.pmid, paper.title.lower()[:50])
        if key not in seen:
            seen.add(key)
            unique.append(paper)
    return unique
```

### Parallelization

- **Per-paper agents:** Agents like `reproducibility`, `citation_network`, `methodology`, `publication_metadata` run in parallel within the per-paper graph (LangGraph concurrent execution)
- **Multi-paper batch:** Each paper is scored via the per-paper graph (no cross-paper parallelization, but could be added)
- **API calls:** httpx client uses connection pooling for concurrent requests

---

## Error Handling

### Application-Level Error Handler

**File:** `src/trustworthy_science/server/app.py`

```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch all unhandled exceptions, return JSON."""
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc, exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )
```

### Graph-Level Error Handling

Each agent wraps critical logic in try-except:

```python
async def fetch_parse(state: PaperState) -> dict:
    try:
        # Try BioC XML
        full_text = await fetch_bioc_fulltext(state.stub.pmid)
    except Exception as e:
        logger.warning(f"BioC fetch failed: {e}, trying next source...")
        try:
            # Try PMC PDF
            full_text = await fetch_pmc_fulltext(pmcid)
        except Exception as e2:
            logger.warning(f"PMC fetch failed: {e2}, trying next...")
            # Continue cascade...
    
    # Log final error state
    if full_text is None:
        logger.error(f"Could not fetch full text for {state.stub.doi}")
        return {"error": "Fetch failed for all 7 sources", "coverage": "metadata_only"}
```

### Error Recovery Strategy

| Scenario | Recovery |
|----------|----------|
| API timeout | Retry 3 times with exponential backoff (2^n seconds) |
| 5xx error | Retry 3 times with backoff |
| 4xx error (not found) | Fail fast, use fallback |
| LLM unavailable | Use neutral sub_score (0.5, low confidence) |
| Missing full text | Downgrade coverage to abstract_only, continue scoring |
| LangGraph node error | Log warning, continue to next node (no fail-fast) |

### Logging

Each agent logs at INFO level for progress, WARNING for retries, ERROR for failures:

```python
logger.info(f"[{agent_name}] Processing {state.stub.doi}")
logger.warning(f"[{agent_name}] Retry 1/3: {error}")
logger.error(f"[{agent_name}] Failed after 3 retries")
```

---

## Data Flow Diagrams

### Flow 1: Score Papers (Standard)

```
POST /score
├─ Request: {dois[], pmids[], query, top_k}
│
└─→ TruthFilter.score_papers()
    │
    ├─→ MultiPaperGraph (LangGraph)
    │   │
    │   ├─→ retrieve_papers()
    │   │   ├─ Resolve DOIs → PubMed/bioRxiv/Crossref
    │   │   ├─ Search query → PubMed/bioRxiv/Crossref
    │   │   └─ Deduplicate → [PaperStub]
    │   │
    │   ├─→ score_papers_node(stubs)
    │   │   │
    │   │   └─ For each stub:
    │   │       │
    │   │       └─→ PerPaperGraph.invoke(PaperState)
    │   │           │
    │   │           ├─ fetch_parse → ParsedPaper
    │   │           ├─ retraction_watch → bool
    │   │           ├─ paper_classifier → paper_type
    │   │           ├─ [PARALLEL]
    │   │           │  ├─ stats_integrity
    │   │           │  ├─ reproducibility
    │   │           │  ├─ citation_network
    │   │           │  ├─ methodology (LLM)
    │   │           │  └─ publication_metadata
    │   │           └─ scoring → TrustReport
    │   │
    │   └─→ filter_node()
    │       ├─ Apply min_tier filter
    │       └─ Sort by score (desc)
    │
    └─ Response: ScoreResponse{papers[], count}
```

### Flow 2: Deep Research Pipeline

```
POST /api/deep-research
├─ Request: {prompt, top_k, min_tier}
│
└─→ BackgroundTask: _run_deep_research()
    │
    ├─→ DeepResearchGraph (LangGraph)
    │   │
    │   ├─→ query_generator_node(prompt)
    │   │   └─ LLM generates 3-5 search queries + MeSH terms
    │   │
    │   ├─→ parallel_pubmed_fetch_node(queries)
    │   │   ├─ search_pubmed(query) for each query
    │   │   ├─ fetch_pubmed_metadata(pmids)
    │   │   └─ Deduplicate → [PaperStub]
    │   │
    │   ├─→ score_all_node(stubs)
    │   │   └─ PerPaperGraph.invoke() for each
    │   │
    │   └─→ rag_ingest_node(scored_papers)
    │       └─ chroma.ingest_papers(filtered, collection_name)
    │
    └─→ generate_literature_review(prompt, collection_name)
        ├─ Retrieve top-k from Chroma
        └─ LLM synthesis → review document

    Response: DeepResearchResult{
        accepted_papers[],
        scored_papers[],
        generated_queries[],
        literature_review,
        session_id,
    }
```

### Flow 3: Filter for RAG

```
POST /filter
├─ Request: {query, top_k, min_tier}
│
└─→ TruthFilter.filter_for_rag()
    │
    └─→ [Reuses MultiPaperGraph]
        └─ After scoring, filter: tier >= min_tier AND include=True
        
Response: FilterResponse{papers[], count, query, min_tier}
[Only papers with include=True returned]
```

---

## Key File Locations & Roles

| Path | Purpose | Key Functions |
|------|---------|---|
| `server/app.py` | FastAPI factory | `create_app()`, `start()`, lifespan, exception handler |
| `server/dependencies.py` | Singleton management | `init_truth_filter()`, `get_truth_filter()`, reload |
| `server/routes/score.py` | Score endpoint | POST /score |
| `server/routes/filter.py` | Filter endpoint | POST /filter |
| `server/routes/explain.py` | Explain endpoint | POST /explain |
| `server/routes/admin.py` | Admin endpoints | POST /reload-config, GET /health |
| `server/routes/search.py` | Async search | POST /api/search (job queue) |
| `server/routes/deep_research.py` | Research pipeline | POST /api/deep-research |
| `server/schemas.py` | Pydantic models | SearchRequest, ScoreResponse, etc. |
| `api.py` | Public API | `TruthFilter` class |
| `state.py` | State models | `PaperState`, `TrustReport`, `Flag`, etc. |
| `graph.py` | LangGraph builders | `_make_paper_graph()`, `_make_multi_paper_graph()`, `_make_deep_research_graph()` |
| `llm.py` | LLM client | `get_llm_client()`, `strip_think_tokens()` |
| `scoring/rules.py` | Deterministic scoring | `calculate_score()`, `apply_penalties()`, etc. |
| `agents/fetch_parse.py` | Full text retrieval | 7-source cascade |
| `agents/retraction_watch.py` | Retraction check | API call |
| `agents/paper_classifier.py` | Paper type classification | 8 regex-based types |
| `agents/stats_integrity.py` | P-curve, Benford's, effect sizes | Statistical analysis |
| `agents/reproducibility.py` | Data/code/preregistration | Regex search |
| `agents/citation_network.py` | Citation diversity | OpenAlex API |
| `agents/methodology.py` | Methods critique | LLM prompt |
| `agents/publication_metadata.py` | Venue credibility | DOAJ, Beall's, impact |
| `agents/scoring.py` | Final score + report | Deterministic formula + LLM |
| `tools/pubmed.py` | PubMed API | Search, fetch metadata, full text |
| `tools/biorxiv.py` | bioRxiv API | Search, fetch metadata, full text |
| `tools/crossref.py` | Crossref API | DOI lookup, search |
| `tools/openalex.py` | OpenAlex API | Citation diversity |
| `tools/retraction_watch.py` | Retraction check | HTTP query |
| `tools/pcurve.py` | P-curve analysis | P-hacking detection |
| `tools/benfords_law.py` | Benford's Law test | Data fabrication detection |
| `tools/pvalue_extract.py` | Regex extraction | P-values, effect sizes, N |
| `tools/chroma_store.py` | Vector store | Ingestion, retrieval |
| `tools/pdf_parse.py` | PDF text extraction | Full text to sections |
| `cache/sqlite_cache.py` | Request cache | Memoization with TTL |
| `config/scoring.yaml` | Configuration | All weights, thresholds, rules |

---

## Configuration

### Config File Structure

**File:** `config/scoring.yaml`

```yaml
# LLM Setup
llm:
  base_url: "https://api.k2think.ai/v1"
  model: "MBZUAI-IFM/K2-Think-v2"
  temperature: 0.3
  max_tokens: 2000

# Scoring Parameters
scoring:
  base: 70                    # Starting score
  quality_bonus_cap: 20       # Max total bonuses
  methods_nudge_weight: 0.15  # LLM methodology weight

# Tier Thresholds
tiers:
  trusted_min: 70
  caution_min: 45
  hard_flag_cap: 25

# Soft Flag Penalties (code -> penalty)
soft_flags:
  NO_DATA_DEPOSIT: 8
  NO_CODE_AVAILABILITY: 5
  HIGH_SELF_CITATION: 7
  MISSING_EFFECT_SIZES: 6
  SMALL_SAMPLE_UNDERPOWERED: 6
  METHODS_INCOMPLETE: 8
  # ... 12 total

# Quality Signal Bonuses
quality_signals:
  PREREGISTERED: 6
  OPEN_DATA: 6
  OPEN_CODE: 4
  INDEPENDENTLY_REPLICATED: 10
  DIVERSE_CITATIONS: 4
  HIGH_IMPACT_VENUE: 3
  # ... 7 total

# P-Curve Configuration
pcurve:
  min_pvalues_required: 3      # need at least 3 p-values to analyze
  cluster_ratio_threshold: 0.7 # if 70%+ p-values < 0.05, flag as p-hacking
  phack_window_lo: 0.04        # p-hacking detection window
  phack_window_hi: 0.05

# Citation Network Settings
citation_network:
  self_citation_ratio_threshold: 0.4  # 40% or more = soft flag
  diversity_threshold: 0.6

# Reproducibility Patterns (Regex)
reproducibility:
  data_repo_patterns:
    - "figshare.com"
    - "zenodo.org"
    - "osf.io"
    - "github.com"  # for data
  code_patterns:
    - "github.com"
    - "gitlab.com"
    - "bitbucket.org"
    - "pypi.org"
  preregistration_patterns:
    - "NCT\\d+"      # ClinicalTrials.gov
    - "osf.io/.*"    # Open Science Framework

# Paper Type Applicability
paper_type_applicability:
  empirical_quantitative: {data: true, code: true, preregistration: true}
  clinical_trial: {data: true, code: false, preregistration: true}
  systematic_review_meta: {data: true, code: false, preregistration: false}
  review_narrative: {data: false, code: false, preregistration: false}
  theoretical: {data: false, code: false, preregistration: false}
  computational_methods: {data: false, code: true, preregistration: false}
  case_report: {data: false, code: false, preregistration: false}
  opinion_commentary: {data: false, code: false, preregistration: false}

# RAG Configuration
rag:
  max_papers_per_session: 100
  embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
  chunk_size: 512
```

### Hot Reload

```bash
POST /admin/reload-config
Content-Type: application/json

{
    "config_path": "config/scoring.yaml"
}
```

Response:
```json
{
    "status": "success",
    "message": "Config reloaded, TruthFilter rebuilt"
}
```

The reload is thread-safe (uses RLock) — in-flight requests hold the old graph reference.

---

## Connectivity Summary

### Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Request                                │
│              POST /score, /filter, /deep-research               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
         ┌──────────────────────┐
         │   FastAPI Server     │
         │   (uvicorn)          │
         │   ▲                  │
         │   │ global exception │
         │   │ handler (→ JSON) │
         │   │                  │
         │   ├─ /score ─────┐   │
         │   ├─ /filter ────┤   │
         │   ├─ /explain ───┤   │
         │   ├─ /api/search ├──→├─ get_truth_filter()
         │   ├─ /api/deep-research (dependency injection)
         │   └─ /admin ────┘   │
         └──────────────────────┘
                     │
                     ▼
         ┌──────────────────────┐
         │  TruthFilter Singleton│  (initialized on startup)
         │  (api.py)            │  (reloadable via /admin/reload-config)
         └────────┬─────────────┘
                  │
      ┌───────────┼───────────┐
      │           │           │
      ▼           ▼           ▼
  MultiPaper   DeepResearch  Scoring
  Graph        Graph         Rules
  (LangGraph)  (LangGraph)   (rules.py)
      │           │           │
      │           │           └─→ config/scoring.yaml
      │           │               (weights, thresholds)
      │           │
      ▼           ▼
  PerPaperGraph (for each paper)
  ├─ fetch_parse ──────────────────────────→ 7 retrieval sources
  │                                          ├─ BioC (PubMed)
  │                                          ├─ PMC PDF
  │                                          ├─ bioRxiv PDF
  │                                          ├─ Semantic Scholar
  │                                          ├─ Crossref API
  │                                          └─ Abstract
  │
  ├─ [PARALLEL AGENTS]
  │  ├─ stats_integrity ─────────────→ pcurve.py, benfords_law.py, pvalue_extract.py
  │  ├─ reproducibility ──────────────→ config regex patterns
  │  ├─ citation_network ─────────────→ OpenAlex API
  │  ├─ methodology ────────────────→ K2-Think-v2 LLM via llm.py
  │  ├─ publication_metadata ────────→ DOAJ, Beall's List, Crossref API
  │  ├─ paper_classifier ────────────→ config paper type regex
  │  └─ retraction_watch ────────────→ Retraction Watch API
  │
  └─ scoring ──────────────────────→ scoring/rules.py (deterministic)
     │
     └─→ LLM narrative report ──────→ K2-Think-v2 LLM via llm.py

External APIs:
├─ NCBI E-utilities (PubMed, PMC)
├─ EuropePMC (bioRxiv, PMCID lookup)
├─ Crossref REST API (DOI metadata)
├─ OpenAlex API (citations)
├─ DOAJ API (journal legitimacy)
├─ K2 API (K2-Think-v2 LLM)
└─ Retraction Watch (retracted papers)

Caching:
└─ SQLite (~/.cache/trustworthy_science/api_cache.db)
   ├─ pubmed namespace (7-day TTL)
   ├─ biorxiv namespace
   ├─ crossref namespace
   └─ pub_meta namespace (DOAJ checks)

Vector Store (RAG):
└─ Chroma
   ├─ Embedding: sentence-transformers
   └─ Storage: local SQLite or persistent backend

Response → PaperResult
├─ title, doi, pmid, year, venue, authors
├─ score (0-100), tier
├─ hard_flags[], soft_flags[], quality_signals[]
├─ per_dimension: [{dimension, score, reason}]
└─ structured_report (LLM narrative)
```

---

## Summary

The Trustworthy Science backend is a **modular, configuration-driven, multi-agent credibility assessment pipeline** built on LangGraph. It coordinates 8 specialized agents to analyze papers across 5+ dimensions (statistical integrity, reproducibility, citation diversity, methodology, publication venue) and synthesizes results into a deterministic Trust Score (0-100) and tier classification.

**Key Design Principles:**
- **Modular:** Each agent is independent, composable, and replaceable
- **Configuration-driven:** All scoring logic lives in `scoring.yaml`, not code
- **Error-resilient:** Graceful fallbacks at every stage (API failures, missing data)
- **Extensible:** New agents, scoring signals, and data sources are easy to add
- **Cached:** All external API calls are memoized (7-day TTL)
- **Scalable:** Graph-based design allows horizontal scaling with process managers

The system integrates with 8+ external APIs (PubMed, bioRxiv, Crossref, OpenAlex, DOAJ, K2 LLM, Retraction Watch) while maintaining strict error handling and fast iteration through caching.
