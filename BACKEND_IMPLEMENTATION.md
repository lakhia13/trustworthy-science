# Trustworthy Science — Backend Implementation Guide

**Last Updated:** April 19, 2026 | Based on current main branch code

This document describes the **actual implementation** of the Trustworthy Science backend: what code exists, how it works, what's called, and how everything connects.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [LangGraph Architecture](#langgraph-architecture)
3. [Agent Implementations](#agent-implementations)
4. [API Routes](#api-routes)
5. [Data Models](#data-models)
6. [Scoring Algorithm](#scoring-algorithm)
7. [External APIs](#external-apis)
8. [LLM Integration](#llm-integration)
9. [Configuration System](#configuration-system)
10. [Request/Response Flow](#requestresponse-flow)
11. [Error Handling](#error-handling)
12. [Caching & Performance](#caching--performance)

---

## System Overview

**Purpose:** Assign a Trust Score (0-100) and tier (`Trusted` / `Caution` / `Untrusted`) to scientific papers using multi-agent analysis.

**Tech Stack:**
- **Framework:** FastAPI (Python) + LangGraph
- **LLM:** K2-Think-v2 (OpenAI-compatible API)
- **External Data:** PubMed, bioRxiv, Crossref, OpenAlex, DOAJ, Retraction Watch
- **Vector Store:** ChromaDB (for RAG in deep research)
- **Cache:** SQLite (7-day TTL)

**Entry Point:** `src/trustworthy_science/server/app.py`

---

## LangGraph Architecture

The system has **THREE separate LangGraph graphs**:

### 1. Per-Paper Sub-Graph

**Location:** `graph.py`: `_make_paper_graph()`

This graph runs for each individual paper and produces a `TrustReport`.

```
START
  ↓
fetch_parse ──────────────────┐
  (7-step text retrieval)     │
  ↓                           │
retraction_watch              │
  (check if retracted)        │
  ↓                           │
  ├─ [if retracted=True] ────→├─ scoring → END
  │                           │
  └─ [if retracted=False]     │
     ↓                        │
  paper_classifier            │
  (regex classify into 8 types)
     ↓                        │
  stats_integrity             │
  (p-curve, effect sizes)     │
     ↓                        │
  [PARALLEL AGENTS]           │
  ├─ reproducibility ─────────┤
  ├─ citation_network ────────┤
  ├─ methodology (LLM) ───────┤
  └─ publication_metadata ────┤
     ↓                        │
  scoring ←─────────────────────
  (deterministic + optional LLM)
     ↓
  TrustReport (final)
     ↓
END
```

**Key Feature:** Conditional routing after retraction_watch
- If `retracted=True`: Skip all other agents, jump to scoring with hard flag
- If `retracted=False`: Continue through all agents

**State Object:** `PaperState` (flows through every node)
- Agents read from state, compute, return dict
- LangGraph merges returns into state (list fields use `operator.add` for appending)

---

### 2. Multi-Paper Graph

**Location:** `graph.py`: `_make_multi_graph()`

Coordinates scoring for a batch of papers (from query or DOI list).

```
START
  ↓
retrieve
  (fetch paper stubs from PubMed/bioRxiv/Crossref)
  → [PaperStub list]
  ↓
score_papers
  (run each stub through per-paper graph)
  → [PaperState with final TrustReport]
  ↓
filter
  (apply min_tier threshold, sort by score)
  → [PaperResult list]
  ↓
END
```

**Flow:**
1. `retrieve`: Query PubMed, bioRxiv, Crossref; deduplicate by {doi, pmid, title}
2. `score_papers`: For each stub, invoke per-paper graph
3. `filter`: Keep only papers with `tier >= min_tier`; sort by score descending

---

### 3. Deep Research Graph

**Location:** `graph.py`: `_make_deep_research_graph()`

Full research pipeline: generates queries, fetches papers, scores them, ingests into RAG.

```
START
  ↓
query_generator
  (LLM generates 3-5 PubMed queries + MeSH terms)
  → [queries[], mesh_terms[]]
  ↓
parallel_pubmed_fetch
  (search each query, fetch metadata, deduplicate)
  → [candidate_stubs[]]
  ↓
score_all
  (score each stub via per-paper graph)
  → [scored_papers[]]
  ↓
rag_ingest
  (filter by min_tier, chunk & embed, store in ChromaDB)
  → [rag collection created]
  ↓
generate_literature_review
  (LLM synthesizes review from RAG context)
  → [review text with citations]
  ↓
END
```

Returns: `DeepResearchResult`
- `accepted_papers[]` — papers meeting min_tier
- `scored_papers[]` — all scored papers
- `generated_queries[]` — queries that were run
- `literature_review` — LLM-generated narrative
- `session_id` — for later retrieval

---

## Agent Implementations

### Agent 1: fetch_parse

**File:** `agents/fetch_parse.py`

**Purpose:** Retrieve full text from paper

**7-Step Cascade:**
1. **BioC JSON** (via NCBI E-utils) → highly structured XML with sections
2. **PMC PDF** (PubMed Central) → efetch API
3. **PDF from DOI** → Crossref/DOI.org resolution
4. **EuropePMC API** → searches preprints
5. **bioRxiv PDF** → native bioRxiv/medRxiv
6. **Semantic Scholar** → their open-access API
7. **Abstract-only fallback** → uses stub abstract

**Returns:**
- `ParsedPaper` with sections: `{methods, results, discussion, abstract, references, funding, coi_statement}`
- `coverage` field: `"full_text"` | `"abstract_only"` | `"metadata_only"`
- `fetch_source` field: which step succeeded

**Key Code Logic:**
```python
# Try each source
for step in [bioc, pmc, pdf, europepmc, biorxiv, semantic_scholar]:
    try:
        full_text = await step.fetch(stub)
        if full_text and len(full_text) > 500:  # meaningful text
            break  # success, exit loop
    except Exception:
        continue  # try next

# Segment full_text into sections
sections = _segment_sections(full_text)  # regex-based splitting
```

---

### Agent 2: retraction_watch

**File:** `agents/retraction_watch.py`

**Purpose:** Check if paper is retracted or failed replication

**Checks:**
1. **Retraction Watch DB** — HTTP lookup (or cached JSON)
2. **Crossref Crossmark** — API check for retraction notices
3. **OSC 2015 Reproducibility** — Open Science Collaboration replication failures
4. **SSRP (Social Science Replication Project)** — failed replications

**Returns:**
- `retracted: bool` — True if found in any DB
- Flags: `REPLICATION_FAILED`, `INDEPENDENTLY_REPLICATED` (quality signal)

---

### Agent 3: paper_classifier

**File:** `agents/paper_classifier.py`

**Purpose:** Classify paper into one of 8 types (NO LLM, pure regex)

**Classification Rules** (all regex-based on title + abstract):
1. `clinical_trial` — "RCT", "randomized", "clinical trial", "phase I", etc.
2. `systematic_review_meta` — "systematic review", "meta-analysis", "PRISMA"
3. `case_report` — "case report", "case series", "n=1"
4. `opinion_commentary` — "editorial", "perspective", "commentary", "opinion"
5. `review_narrative` — "literature review", "scoping review", "narrative"
6. `theoretical` — "mathematical model", "computational", "simulation", "theoretical"
7. `computational_methods` — "software", "pipeline", "tool", "algorithm", "method"
8. `empirical_quantitative` — default fallback

**Why No LLM?**
- Fast (ms, not seconds)
- Deterministic (no token usage)
- Type-aware scoring still works (checks config matrix)

---

### Agent 4: stats_integrity

**File:** `agents/stats_integrity.py`

**Purpose:** Detect statistical issues (p-hacking, small samples, missing effect sizes)

**Techniques:**
1. **P-Curve Analysis** (`tools/pcurve.py`)
   - Extract all p-values from methods/results
   - Check distribution: if ≥40% cluster in (0.04, 0.05), flag `P_HACKING_CLUSTER`
   - (Method: Simonsohn et al. p-curve)

2. **Effect Size Extraction**
   - Regex for Cohen's d, Odds Ratio, Relative Risk
   - Flag `MISSING_EFFECT_SIZES` if none found

3. **Sample Size Check**
   - Extract N from methods
   - Given effect size + alpha/beta, compute minimum N_needed
   - Flag `SMALL_SAMPLE_UNDERPOWERED` if N < N_needed

4. **Benford's Law** (`tools/benfords_law.py`)
   - Test if reported statistics follow Benford's distribution
   - Extreme deviation flags `BENFORDS_LAW_ANOMALY` (fabrication signal)

**Returns:**
- `SubScore` with 0-1 score
- Soft flags: `[P_HACKING_CLUSTER, MISSING_EFFECT_SIZES, SMALL_SAMPLE_UNDERPOWERED, BENFORDS_LAW_ANOMALY]`

---

### Agent 5: reproducibility

**File:** `agents/reproducibility.py`

**Purpose:** Check for open data, code, preregistration

**Pattern Matching** (all configurable in `config/scoring.yaml`):
- **Data Repository Patterns:** GEO (NCBI), Zenodo, Figshare, Dryad, OSF, GitHub (data folder)
- **Code Repository Patterns:** GitHub, GitLab, CRAN, Bioconductor, PyPI, GitHub Gists
- **Preregistration Patterns:** ClinicalTrials.gov (NCT prefix), PROSPERO, OSF Registries, AsPredicted

**Type-Aware** (from `paper_type_applicability` in config):
- Empirical: checks all three (data, code, preregistration)
- Clinical trial: checks data & preregistration, skips code
- Reviews/theory: skips all (no penalty for absence)
- Case reports: skips all

**Returns:**
- Quality signals: `OPEN_DATA`, `OPEN_CODE`, `PREREGISTERED`
- Soft flags: `NO_DATA_DEPOSIT`, `NO_CODE_AVAILABILITY`, `NO_PREREGISTRATION`

---

### Agent 6: citation_network

**File:** `agents/citation_network.py`

**Purpose:** Analyze citation patterns (self-citations, diversity)

**OpenAlex API Query:**
- Fetch citing papers for the DOI
- Extract author names, institution affiliations
- Compute:
  - **Self-citation ratio** = papers from same authors / total citing papers
  - **Institutional diversity** = unique institutions citing / max possible

**Returns:**
- Quality signal: `DIVERSE_CITATIONS` (if diversity > threshold)
- Soft flag: `HIGH_SELF_CITATION_RATIO` (if self-citation > 30%)
- `SubScore` with diversity metrics

---

### Agent 7: methodology

**File:** `agents/methodology.py`

**Purpose:** LLM-powered critique of methodology section

**LLM Prompt** (structured JSON rubric):
```
You are a peer reviewer. Evaluate this methodology:

{methods_section}

Respond with JSON:
{
  "sample_size_justified": bool,
  "controls_described": bool,
  "blinding_described": bool,
  "statistics_prespecified": bool,
  "outcome_clearly_defined": bool,
  "reproducibility_detail_sufficient": bool,
  "overall_score": float(0-1),
  "weaknesses": [str],
  "strengths": [str]
}
```

**Model:** K2-Think-v2 (from config)
**Temperature:** 0 (deterministic)
**Max tokens:** 1500

**Returns:**
- `SubScore` with LLM's `overall_score`
- Soft flags based on weaknesses (e.g., if "controls not described" → flag)

---

### Agent 8: publication_metadata

**File:** `agents/publication_metadata.py`

**Purpose:** Check journal credibility, review speed

**Checks:**
1. **DOAJ Lookup** (via DOAJ API)
   - Is journal in Directory of Open Access Journals?
   - Quality signal: `HIGH_IMPACT_VENUE` (if in DOAJ)

2. **Beall's List Heuristics**
   - Keyword matching: "International Journal of...", "Scientific Journal of..."
   - Hard flag: `PREDATORY_VENUE` (predatory journal detected)

3. **Crossref Submission-Acceptance Days**
   - Calculate days from submitted to accepted
   - Flag: `FAST_PEER_REVIEW` (< 14 days = suspicious)

4. **Funding Declaration**
   - Check for funding statement + conflict-of-interest statement
   - Quality signal: `COI_DISCLOSED` (if both present)

**Returns:**
- Hard flag: `PREDATORY_VENUE`
- Soft flag: `FAST_PEER_REVIEW`, `VENUE_NOT_IN_DOAJ`
- Quality signal: `COI_DISCLOSED`
- `SubScore`

---

### Agent 9: scoring

**File:** `agents/scoring.py`

**Purpose:** Compute final Trust Score and generate structured report

**Deterministic Scoring:**
- Calls `compute_composite_score()` with all accumulated flags
- Applies config-driven penalties/bonuses
- Caps score at 25 if hard flags present
- Maps score to tier

**Optional LLM Report:**
- Calls K2-Think-v2 with structured report prompt
- Generates sections: OVERALL VERDICT, SCORE BREAKDOWN, KEY CONCERNS, POSITIVE SIGNALS, RECOMMENDATION
- Fallback to deterministic template if LLM fails

**Returns:**
- `TrustReport` with:
  - `composite_score: int [0-100]`
  - `tier: Literal["Trusted", "Caution", "Untrusted"]`
  - `structured_report: StructuredReport | None` (LLM-generated)
  - Lists of flags/signals
  - Per-dimension scores

---

## API Routes

### Route 1: POST `/score`

**Handler:** `routes/score.py`

**Request:**
```python
class SearchRequest(BaseModel):
    dois: list[str] = []           # DOIs to score
    pmids: list[str] = []          # PubMed IDs
    query: str | None = None       # Natural language query
    top_k: int = 10                # Max 50 results
    weights: ScoringWeights | None = None  # Optional config override
```

**Response:**
```python
class ScoreResponse(BaseModel):
    papers: list[PaperResult]
    count: int
    query: str | None
    retrieved_from: list[str]  # ["PubMed", "bioRxiv", "Crossref"]
```

**Flow:**
1. Validate SearchRequest
2. Call `TruthFilter.score_papers()`
3. Return ScoreResponse

---

### Route 2: POST `/filter`

**Handler:** `routes/filter.py`

**Request:**
```python
class FilterRequest(BaseModel):
    query: str                     # Search query
    top_k: int = 10
    min_tier: str = "Caution"      # "Trusted", "Caution", "Untrusted"
    weights: ScoringWeights | None = None
```

**Response:**
```python
class FilterResponse(BaseModel):
    papers: list[PaperResult]      # Only papers with tier >= min_tier
    count: int
    query: str
    min_tier: str
```

**Flow:**
1. Call `TruthFilter.filter_for_rag()`
2. Return only papers meeting tier threshold, sorted by score desc

---

### Route 3: POST `/explain`

**Handler:** `routes/explain.py`

**Request:**
```python
class ExplainRequest(BaseModel):
    doi: str | None = None
    pmid: str | None = None
    weights: ScoringWeights | None = None
```

**Response:**
```
TrustReport (directly returned as JSON)
```

**Flow:**
1. Validate exactly one of (doi, pmid) is provided
2. Score single paper
3. Return detailed TrustReport

---

### Route 4: POST `/api/search`

**Handler:** `routes/search.py`

**Async job submission** (non-blocking)

**Request:**
```python
class SearchRequest(BaseModel):
    # same as /score
```

**Response:**
```python
class JobResponse(BaseModel):
    job_id: str
    status: str  # "queued", "running", "completed", "failed"
    result: ScoreResponse | None
```

**Flow:**
1. Submit as background task
2. Return job_id immediately
3. Client polls `/admin/job/{job_id}` for status

---

### Route 5: POST `/api/deep-research`

**Handler:** `routes/deep_research.py`

**Async deep research pipeline**

**Request:**
```python
class DeepResearchRequest(BaseModel):
    prompt: str                    # Research question
    top_k: int = 10
    min_tier: str = "Caution"
    weights: ScoringWeights | None = None
```

**Response:**
```python
class DeepResearchResult(BaseModel):
    accepted_papers: list[PaperResult]   # Passing min_tier
    scored_papers: list[PaperResult]     # All papers
    generated_queries: list[str]
    literature_review: str                # LLM-synthesized review
    session_id: str
```

**Flow:**
1. Submit to background task
2. Return job_id
3. Poll for status/results
4. Final result includes RAG-based literature review

---

### Route 6: GET/POST `/admin/job/{job_id}`

**Handler:** `routes/admin.py`

**Poll job status**

**Response:**
```json
{
  "job_id": "abc123",
  "status": "completed",
  "result": {...}  // if completed
}
```

---

### Route 7: POST `/admin/config/reload`

**Handler:** `routes/admin.py`

**Hot reload configuration**

**Request:**
```json
{
  "config_path": "config/scoring.yaml"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Config reloaded, TruthFilter rebuilt"
}
```

**Behavior:**
- Thread-safe reload (uses RLock)
- In-flight requests unaffected (hold old graph reference)
- New requests use new config

---

## Data Models

### PaperState (Main State Object)

```python
class PaperState(BaseModel):
    # Input
    stub: PaperStub                              # DOI, PMID, title, authors, abstract
    
    # Processing
    parsed: ParsedPaper | None = None            # Full text + sections
    coverage: Literal["full_text", "abstract_only", "metadata_only"] | None = None
    paper_type: str | None = None                # 8 classifier outputs
    retracted: bool = False
    
    # Accumulated results from agents (reducer=operator.add appends)
    sub_scores: dict[str, SubScore] = {}         # {agent_name: SubScore}
    hard_flags: Annotated[list[Flag], operator.add] = []
    soft_flags: Annotated[list[Flag], operator.add] = []
    quality_signals: Annotated[list[Flag], operator.add] = []
    
    # Final verdict
    final: TrustReport | None = None
    
    # Error tracking
    error: str | None = None
```

**Key Feature:** `Annotated[list[Flag], operator.add]` means multiple agents can append flags; LangGraph merges them automatically.

### Flag

```python
class Flag(BaseModel):
    tier: Literal["hard", "soft", "quality"]
    code: str                       # e.g., "P_HACKING_CLUSTER", "OPEN_DATA"
    message: str                    # Human-readable message
    source_agent: str               # Which agent emitted this
    evidence: list[EvidenceQuote]   # Quoted supporting text
    severity: str | None            # Additional severity info
```

### SubScore

```python
class SubScore(BaseModel):
    score: float                    # 0-1
    confidence: float               # 0-1 (how certain is this agent?)
    flags: list[Flag]               # Flags emitted by this agent
    notes: str
    reason: str                     # Explanation of score
```

### TrustReport (Final Output)

```python
class TrustReport(BaseModel):
    composite_score: int            # 0-100
    tier: Literal["Trusted", "Caution", "Untrusted"]
    summary: str                    # Backward compat
    hard_flags: list[Flag]
    soft_flags: list[Flag]
    quality_signals: list[Flag]
    per_dimension: list[DimensionScore]  # {dimension, score, reason}
    coverage: Literal["full_text", "abstract_only", "metadata_only"]
    structured_report: StructuredReport | None  # LLM-generated
```

### PaperResult (API Response)

```python
class PaperResult(BaseModel):
    title: str
    doi: str | None
    pmid: str | None
    year: int | None
    venue: str
    authors: list[str]
    
    score: int                      # 0-100
    tier: str                       # "Trusted", "Caution", "Untrusted"
    coverage: str
    fetch_source: str               # Which source provided full text
    
    summary: str
    hard_flags: list[Flag]
    soft_flags: list[Flag]
    quality_signals: list[Flag]
    per_dimension: list[DimensionScore]
    structured_report: StructuredReport | None
```

---

## Scoring Algorithm

### Deterministic Scoring

**Location:** `scoring/rules.py`: `compute_composite_score()`

**Formula:**
```
BASE = 70 (from config)

Score = Base 
        - sum(soft_flag_penalties)
        + min(sum(quality_bonuses), quality_bonus_cap)
        + methods_nudge_bonus

Score = clamp(Score, 0, 100)

IF hard_flags exist:
    Score = min(Score, hard_flag_cap)        # Usually 25
    Tier = "Untrusted"
ELSE IF Score >= trusted_min:                # Usually 70
    Tier = "Trusted"
ELSE IF Score >= caution_min:                # Usually 45
    Tier = "Caution"
ELSE:
    Tier = "Untrusted"
```

### Soft Flag Penalties (Config-Driven)

Default penalties in `config/scoring.yaml`:

| Flag | Penalty | When |
|------|---------|------|
| `NO_DATA_DEPOSIT` | -3 | No data repo found (& type requires data) |
| `NO_CODE_AVAILABILITY` | -2 | No code repo (& type requires code) |
| `HIGH_SELF_CITATION_RATIO` | -4 | Self-citations > 30% |
| `MISSING_EFFECT_SIZES` | -4 | No effect sizes in methods/results |
| `SMALL_SAMPLE_UNDERPOWERED` | -5 | N < minimum required for effect size |
| `METHODS_INCOMPLETE` | -6 | LLM methodology score < 0.5 |
| `FAST_PEER_REVIEW` | -4 | Accepted in < 14 days |
| `P_HACKING_CLUSTER` | -8 | P-values cluster in 0.04-0.05 |
| `BENFORDS_LAW_ANOMALY` | -6 | Significant Benford's deviation |
| `REPLICATION_FAILED` | -8 | In OSC/SSRP failure list |
| `VENUE_NOT_IN_DOAJ` | -2 | Journal not in DOAJ |
| `NO_PREREGISTRATION` | -1 | Clinical trial without preregistration |
| `INDUSTRY_ONLY_FUNDING_NO_COI` | -5 | Industry funding but no COI statement |

### Quality Signal Bonuses (Config-Driven)

| Signal | Bonus | When |
|--------|-------|------|
| `PREREGISTERED` | +6 | Found preregistration ID |
| `OPEN_DATA` | +6 | Found data repository URL |
| `OPEN_CODE` | +4 | Found code repository URL |
| `INDEPENDENTLY_REPLICATED` | +10 | Found in successful replication study |
| `DIVERSE_CITATIONS` | +4 | Citing institutions > threshold |
| `COI_DISCLOSED` | +2 | Explicit COI statement present |
| `HIGH_IMPACT_VENUE` | +3 | Journal in DOAJ |

### Methods Nudge

```
methods_nudge = 0.15 * (LLM_methodology_score * 100 - 70)

Example:
  LLM score = 0.8 → methods_nudge = 0.15 * (80 - 70) = +1.5 pts
  LLM score = 0.5 → methods_nudge = 0.15 * (50 - 70) = -3 pts
```

### Hard Flags (Automatic Disqualification)

If **any** hard flag exists:
- Score is capped at 25
- Tier is forced to "Untrusted"

Hard flags:
- `RETRACTED` — In Retraction Watch/Crossref Crossmark
- `P_HACKING_CLUSTER` — P-curve shows severe clustering
- `PREDATORY_VENUE` — Journal matches Beall's List heuristics
- `OUTCOME_SWITCHING_CONFIRMED` — Text analysis detected outcome switching
- `IMAGE_MANIPULATION` — Reserved for future forensics

### Paper Type Applicability Matrix

From `config/scoring.yaml`:

```yaml
paper_type_applicability:
  empirical_quantitative: {data: true, code: true, preregistration: true}
  clinical_trial: {data: true, code: false, preregistration: true}
  systematic_review_meta: {data: true, code: false, preregistration: false}
  review_narrative: {data: false, code: false, preregistration: false}
  theoretical: {data: false, code: false, preregistration: false}
  computational_methods: {data: false, code: true, preregistration: false}
  case_report: {data: false, code: false, preregistration: false}
  opinion_commentary: {data: false, code: false, preregistration: false}
```

**Effect:** Agents skip checks for non-applicable types. No penalty, no bonus.

Example: A narrative review won't lose points for missing data.

---

## External APIs

### PubMed (NCBI E-utilities)

**File:** `tools/pubmed.py`

| Function | Purpose | Input | Output |
|----------|---------|-------|--------|
| `search_pubmed(query, max)` | Search PubMed | Natural language query | [pmids] |
| `fetch_pubmed_metadata(pmids)` | Get title, authors, abstract, venue | [pmids] | [PaperStub] |
| `fetch_bioc_fulltext(pmid)` | Get full text + sections from BioC JSON | pmid | (full_text, sections_dict) |
| `fetch_pmc_fulltext(pmcid)` | Get full text from PMC | pmcid | full_text |

**Auth:** Optional NCBI_API_KEY (increases rate limit to 10 req/sec vs 3)

**Cache:** SQLite namespace `pubmed`, 7-day TTL

---

### bioRxiv/medRxiv

**File:** `tools/biorxiv.py`

| Function | Purpose |
|----------|---------|
| `search_biorxiv(query, max)` | Search via EuropePMC API |
| `fetch_biorxiv_fulltext(doi)` | Fetch PDF text |
| `europepmc_pmcid_for_doi(doi)` | Resolve PMID from DOI |

**API:** EuropePMC (free, no auth)

**Cache:** SQLite namespace `biorxiv`, 7-day TTL

---

### Crossref

**File:** `tools/crossref.py`

| Function | Purpose |
|----------|---------|
| `doi_to_stub(doi)` | Get paper metadata from DOI |
| `search_crossref(query, max)` | Full-text search |
| `get_work(doi)` | Full metadata (includes references, citations) |
| `get_submission_acceptance_days(doi)` | Days from submission to acceptance |

**API:** Crossref REST API (free, polite user-agent required)

**Cache:** SQLite namespace `crossref`, 7-day TTL

---

### OpenAlex

**File:** `tools/openalex.py`

| Function | Purpose | Returns |
|----------|---------|---------|
| `citation_diversity_score(doi)` | Citation network analysis | (diversity_ratio, n_citations, self_citation_ratio) |

**API:** OpenAlex (free)

**Cache:** Computed on the fly (small computation)

---

### DOAJ (Directory of Open Access Journals)

**File:** `tools/doaj.py` (implied)

| Function | Purpose |
|----------|---------|
| `is_open_access(issn)` | Check if journal in DOAJ |

**API:** DOAJ REST API (free)

**Cache:** SQLite namespace `pub_meta`, 7-day TTL

---

### Retraction Watch + Replication DBs

**File:** `tools/retraction_watch.py` + `tools/replication_db.py`

| Function | Purpose |
|----------|---------|
| `is_retracted(doi)` | Check Retraction Watch DB |
| `check_replication(doi)` | Check OSC 2015 + SSRP replication failures |

**API:** Static JSON files or cached lookups

---

### K2-Think-v2 LLM

**File:** `llm.py`

**Endpoint:** `https://api.k2think.ai/v1`

**Model:** `MBZUAI-IFM/K2-Think-v2`

**Auth:** `K2_API_KEY` environment variable

**Used in:**
- Methodology critique (structured JSON rubric)
- Structured report generation
- Query generation (deep research)
- Literature review synthesis

**Temperature:** 0 (deterministic)

**Max tokens:** Configurable per call (usually 1500 for critique, 900 for report)

---

### ChromaDB (Vector Store)

**File:** `tools/chroma_store.py`

| Function | Purpose |
|----------|---------|
| `ingest_papers(papers[], collection_name, config)` | Embed & store papers |
| `query_collection(query, collection_name, top_k)` | Retrieve similar papers |

**Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2` (configurable)

**Storage:** Local SQLite or persistent backend (depends on config)

---

## LLM Integration

### Where LLM is Called

#### 1. Methodology Agent

**File:** `agents/methodology.py`

**Prompt:**
```
Review the following methodology section and provide a JSON critique.

Criteria:
- Sample size justified?
- Controls/comparison groups described?
- Blinding (if applicable)?
- Pre-specified statistics?
- Clear outcome definitions?

{methods_section_up_to_3000_chars}

Respond with JSON only:
{
  "sample_size_justified": bool,
  "controls_described": bool,
  "blinding_described": bool,
  "stats_prespecified": bool,
  "outcome_clearly_defined": bool,
  "reproducibility_detail_sufficient": bool,
  "overall_score": float(0-1),
  "weaknesses": [str],
  "strengths": [str]
}
```

**Model:** K2-Think-v2
**Temperature:** 0
**Max tokens:** 1500

**Response Handling:**
```python
response = llm_client.invoke(prompt)
cleaned = strip_think_tokens(response.content)  # Remove <think> blocks
json_result = json.loads(cleaned)
score = json_result["overall_score"]  # 0-1
```

#### 2. Scoring Agent (Structured Report)

**File:** `agents/scoring.py`

**Prompt:**
```
Synthesize the following credibility assessment into a structured report.

Paper: {title}
Composite Score: {score}
Tier: {tier}

Hard Flags: {hard_flags}
Soft Flags: {soft_flags}
Quality Signals: {quality_signals}

Per-dimension scores: {per_dimension}

Generate a structured report with:
1. OVERALL VERDICT (1 sentence)
2. SCORE BREAKDOWN (explain the score)
3. KEY CONCERNS (list top 3)
4. POSITIVE SIGNALS (list strengths)
5. RECOMMENDATION (for researchers/RAG)

Keep output concise and evidence-based.
```

**Model:** K2-Think-v2
**Temperature:** 0
**Max tokens:** 900

**Response Handling:**
```python
response = llm_client.invoke(prompt)
cleaned = strip_think_tokens(response.content)
# Parse sections (split by "OVERALL VERDICT", "SCORE BREAKDOWN", etc.)
# Return StructuredReport
```

**Fallback:** If LLM fails, returns deterministic StructuredReport template

#### 3. Deep Research Query Generator

**File:** `graph.py`: `query_generator_node()`

**Prompt:**
```
Given this research question, generate 3-5 targeted PubMed search queries and extract MeSH terms.

Research Question: {prompt}

Respond with:
{
  "queries": [str],
  "mesh_terms": [str]
}
```

**Model:** K2-Think-v2
**Response:** Parsed queries + MeSH terms for library search

#### 4. Literature Review Synthesizer

**File:** `literature_review.py`

**Prompt:**
```
Using the following papers as context, synthesize a comprehensive literature review.

Research Question: {prompt}

Papers:
{papers_from_rag_with_abstracts_and_key_findings}

Generate a narrative literature review with:
1. Background/context
2. Current state of research
3. Key findings across papers
4. Gaps and limitations
5. Future directions

Include inline citations [doi1, doi2, ...] to papers used.
```

**Model:** K2-Think-v2
**Response:** Narrative review text with citations

---

### Think Token Handling

K2-Think-v2 returns extended reasoning in XML-like blocks:

```python
def strip_think_tokens(response: str) -> str:
    """Remove thinking blocks, keep final answer."""
    # Removes:
    # <think>...</think>
    # <thinking>...</thinking>
    # <reasoning>...</reasoning>
    # ```thinking ... ``` (fenced blocks)
    # Returns just the answer text
    
    patterns = [
        r'<think>.*?</think>',
        r'<thinking>.*?</thinking>',
        r'<reasoning>.*?</reasoning>',
        r'```thinking.*?```',
    ]
    for pattern in patterns:
        response = re.sub(pattern, '', response, flags=re.DOTALL)
    return response.strip()
```

---

## Configuration System

### Config File Location

**File:** `config/scoring.yaml`

### Config Structure

```yaml
# LLM Configuration
llm:
  provider: k2                              # or "openai", "anthropic"
  base_url: https://api.k2think.ai/v1
  model: MBZUAI-IFM/K2-Think-v2
  temperature: 0
  max_tokens: 1024

# Scoring Parameters
scoring:
  base: 70                                  # Starting score
  quality_bonus_cap: 20                     # Max total bonuses
  methods_nudge_weight: 0.15                # LLM methodology multiplier

# Tier Thresholds
tiers:
  trusted_min: 70
  caution_min: 45
  hard_flag_cap: 25

# Soft Flag Penalties (all optional, defaults shown)
soft_flags:
  NO_DATA_DEPOSIT: 3
  NO_CODE_AVAILABILITY: 2
  HIGH_SELF_CITATION_RATIO: 4
  MISSING_EFFECT_SIZES: 4
  SMALL_SAMPLE_UNDERPOWERED: 5
  METHODS_INCOMPLETE: 6
  FAST_PEER_REVIEW: 4
  P_HACKING_CLUSTER: 8
  BENFORDS_LAW_ANOMALY: 6
  REPLICATION_FAILED: 8
  VENUE_NOT_IN_DOAJ: 2
  NO_PREREGISTRATION: 1
  INDUSTRY_ONLY_FUNDING_NO_COI: 5

# Quality Signal Bonuses
quality_signals:
  PREREGISTERED: 6
  OPEN_DATA: 6
  OPEN_CODE: 4
  INDEPENDENTLY_REPLICATED: 10
  DIVERSE_CITATIONS: 4
  COI_DISCLOSED: 2
  HIGH_IMPACT_VENUE: 3

# P-Curve Configuration
pcurve:
  phack_window_lo: 0.04                     # p-hacking detection window
  phack_window_hi: 0.05
  min_pvalues_required: 5
  cluster_ratio_threshold: 0.40             # if ≥40% cluster, flag

# Citation Network
citation_network:
  self_citation_ratio_threshold: 0.30
  diversity_threshold: 0.60

# Reproducibility Patterns
reproducibility:
  data_repo_patterns:
    - GEO\d+
    - zenodo\.org
    - figshare\.com
    - dryad\.org
    - osf\.io
    - github\.com
  code_patterns:
    - github\.com
    - gitlab\.com
    - bitbucket\.org
    - CRAN
    - Bioconductor
    - PyPI
  preregistration_patterns:
    - "NCT\\d+"                              # ClinicalTrials.gov
    - PROSPERO
    - "osf\\.io/"
    - AsPredicted

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
  embedding_model: sentence-transformers/all-MiniLM-L6-v2
  chunk_size: 512
  overlap: 50
```

### Runtime Config Overrides

Each API request can override config via `ScoringWeights`:

```python
class ScoringWeights(BaseModel):
    retraction_cap: int | None = None          # Override hard_flag_cap
    no_data_deposit_penalty: int | None = None  # Override soft flag penalty
    open_data_bonus: int | None = None          # Override quality bonus
    methods_nudge_pct: float | None = None      # Override methods_nudge_weight
    # ... per-flag overrides
```

**Example Request:**
```json
POST /score
{
  "dois": ["10.1038/nature12345"],
  "weights": {
    "retraction_cap": 30,
    "open_data_bonus": 10
  }
}
```

---

## Request/Response Flow

### Complete Example: POST /score

**1. User sends request:**
```json
POST /score
{
  "dois": ["10.1038/nature12345"],
  "top_k": 1,
  "weights": {"retraction_cap": 30}
}
```

**2. FastAPI route handler** (`routes/score.py`):
- Validates SearchRequest
- Calls `TruthFilter.score_papers(dois=["10.1038/..."], weights=...)`

**3. TruthFilter.score_papers()** (`api.py`):
- Creates GraphInput with input DOIs + weights
- Invokes `self.multi_graph.invoke(input)`
- Returns [PaperResult]

**4. Multi-Paper Graph** (`graph.py`):
```
START
  ↓ retrieve_node():
    - Crossref API: doi_to_stub("10.1038/nature12345")
      → {title, authors, venue, pmid, ...}
    → [PaperStub]
  
  ↓ score_papers_node(stubs):
    For each stub, invoke per-paper graph:
      
      Per-Paper Graph:
      ├─ fetch_parse: 7-step cascade → ParsedPaper
      ├─ retraction_watch: check DB → retracted=False
      ├─ paper_classifier: regex → "empirical_quantitative"
      ├─ [PARALLEL]
      │  ├─ stats_integrity: p-curve, effect sizes
      │  ├─ reproducibility: data/code patterns
      │  ├─ citation_network: OpenAlex diversity
      │  ├─ methodology: K2-Think-v2 LLM critique
      │  └─ publication_metadata: DOAJ, Beall's check
      └─ scoring: compute_composite_score + LLM report
      → PaperState with final TrustReport
  
  ↓ filter_node(papers):
    Apply min_tier (default "Caution"), sort by score
    → [PaperResult]

END
```

**5. Response generation**:
```python
ScoreResponse(
    papers=[
        PaperResult(
            title="...",
            doi="10.1038/nature12345",
            score=78,
            tier="Trusted",
            hard_flags=[],
            soft_flags=[Flag(code="MISSING_EFFECT_SIZES", ...)],
            quality_signals=[Flag(code="OPEN_DATA", ...)],
            structured_report=StructuredReport(...)
        )
    ],
    count=1,
    query=None,
    retrieved_from=["Crossref"]
)
```

**6. Return to client** (JSON)

---

## Error Handling

### Strategy: Graceful Degradation

| Component | Error | Recovery |
|-----------|-------|----------|
| **Fetch text** | All 7 sources fail | Return abstract-only + metadata_only coverage |
| **LLM call** | Timeout/API error | Log warning, skip LLM result, use deterministic |
| **External API** | 4xx/5xx error | Retry 3 times, then fallback |
| **JSON parse** | Malformed JSON from LLM | Log error, skip agent result |
| **Graph node** | Exception | Try/except wrapper, log warning, continue |
| **Cache failure** | SQLite error | Fall back to live API call |

### Example: fetch_parse Error Handling

```python
async def fetch_parse(state: PaperState) -> dict:
    full_text = None
    fetch_source = None
    
    sources = [
        ("BioC", fetch_bioc_fulltext),
        ("PMC", fetch_pmc_fulltext),
        ("DOI PDF", fetch_pdf_from_doi),
        ("EuropePMC", fetch_europepmc_fulltext),
        ("bioRxiv", fetch_biorxiv_fulltext),
        ("Semantic Scholar", fetch_semantic_scholar_fulltext),
    ]
    
    for name, fetch_fn in sources:
        try:
            logger.info(f"[FETCH] Trying {name}...")
            text = await fetch_fn(state.stub)
            if text and len(text) > 500:
                full_text = text
                fetch_source = name
                logger.info(f"[FETCH] ✓ Success via {name}")
                break
        except Exception as e:
            logger.warning(f"[FETCH] ✗ {name} failed: {e}, trying next...")
            continue
    
    # If all sources fail
    if not full_text:
        logger.warning(f"[FETCH] All sources failed for {state.stub.doi}, using abstract-only")
        full_text = state.stub.abstract or ""
        coverage = "abstract_only"
    else:
        coverage = "full_text"
    
    parsed = ParsedPaper(
        full_text=full_text,
        methods=extract_methods(full_text),
        results=extract_results(full_text),
        ...
    )
    
    return {
        "parsed": parsed,
        "coverage": coverage,
        "fetch_source": fetch_source or "abstract",
    }
```

---

## Caching & Performance

### SQLite Request Cache

**Location:** `~/.cache/trustworthy_science/api_cache.db`

**Namespaces:**
- `pubmed` — PubMed searches + fetches
- `biorxiv` — bioRxiv searches + fetches
- `crossref` — Crossref DOI lookups
- `pub_meta` — DOAJ journal checks

**TTL:** 7 days (configurable)

**Key:** SHA-256 hash of (namespace, function_args, function_kwargs)

### Cache Pattern

All external API tools follow:

```python
async def fetch_pubmed_metadata(pmids: list[str]) -> list[PaperStub]:
    cache = get_cache()
    
    # Check cache first
    cache_key = (tuple(pmids),)
    cached = cache.get("pubmed", cache_key)
    if cached is not None:
        logger.info(f"[CACHE HIT] pubmed {len(pmids)} papers")
        return cached
    
    # API call
    logger.info(f"[CACHE MISS] Fetching {len(pmids)} from PubMed")
    results = await fetch_from_ncbi(pmids)
    
    # Store in cache
    cache.set("pubmed", results, cache_key)
    return results
```

### Deduplication

Papers deduplicated by {doi, pmid, title}:

```python
def _deduplicate(papers: list[PaperStub]) -> list[PaperStub]:
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

- **Per-paper agents:** 5 agents run in parallel via LangGraph (reproducibility, citation_network, methodology, publication_metadata + others)
- **Per-query fetch:** Queries in deep_research run sequentially, but each fetch cascades through sources
- **HTTP client:** Uses httpx connection pooling for concurrent requests

---

## Summary

The Trustworthy Science backend is a **production-grade multi-agent credibility assessment system** built on LangGraph. It:

1. **Analyzes papers across 5+ dimensions** using 9 specialized agents
2. **Integrates with 8+ external APIs** while maintaining graceful fallbacks
3. **Uses LLM strategically** (methodology critique, narrative synthesis) without over-relying on it
4. **Provides deterministic, configurable scoring** (all weights in YAML)
5. **Scales efficiently** through caching (7-day SQLite TTL) and parallelization
6. **Degrades gracefully** (missing data, API failures, LLM timeouts)

**Key Metrics:**
- Per-paper scoring: ~30-60 seconds (depending on text retrieval)
- Cached papers: ~5-10 seconds (just scoring)
- Storage: SQLite cache + ChromaDB for RAG
- Cost: Minimal (mostly free APIs; K2 LLM calls on methodology + report)

---

## Quick Reference: File Locations

| File | Purpose |
|------|---------|
| `server/app.py` | FastAPI factory + lifespan |
| `api.py` | TruthFilter public API |
| `graph.py` | LangGraph definitions |
| `state.py` | Pydantic models (PaperState, TrustReport, etc.) |
| `llm.py` | K2-Think-v2 client factory |
| `scoring/rules.py` | Deterministic score calculation |
| `agents/*.py` | 9 agent implementations |
| `tools/*.py` | External API integrations |
| `server/routes/*.py` | 7 FastAPI route handlers |
| `config/scoring.yaml` | Configuration (all weights, thresholds, patterns) |
| `cache/sqlite_cache.py` | SQLite memoization |
| `tools/chroma_store.py` | ChromaDB integration |
