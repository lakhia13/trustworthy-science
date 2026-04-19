# Trustworthy Science

An AI-powered credibility filter for scientific literature. It uses a LangGraph multi-agent pipeline to analyze papers and assign a **Trust Score (0–100)** and a tier (`Trusted` / `Caution` / `Untrusted`). Designed for researchers and RAG pipelines that need to ground themselves in reliable science.

## Features

- **Trust Score (0–100)** with tier classification (`Trusted` / `Caution` / `Untrusted`)
- **Paper Type Classification** — automatically detects paper type (RCT, systematic review, meta-analysis, case report, opinion, theoretical, computational, empirical) and applies type-appropriate checks
- **Type-aware Reproducibility Checks** — narrative reviews and theoretical papers are never penalized for missing data/code; clinical trials are checked for preregistration but not code availability
- **Statistical Integrity** — p-curve analysis to detect p-hacking; flags missing effect sizes and underpowered samples (skipped for non-empirical types)
- **Hard / Soft Flags and Quality Signals** — retraction detection, predatory venue check, self-citation ratio, open data/code detection, preregistration detection
- **Configurable Scoring** — all weights and thresholds live in `config/scoring.yaml`; no code change needed to tune behavior
- **Multiple Inputs** — score by DOI, or retrieve papers from PubMed / bioRxiv / Crossref via a natural-language query
- **RAG Integration** — `filter_for_rag()` returns only papers above a minimum credibility tier

## Installation

Requires Python 3.11+ and [`uv`](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/your-username/trustworthy-science.git
cd trustworthy-science
uv pip install -e .
```

Set your API key (K2-Think-v2 LLM):

```bash
# .env or shell export
export K2_API_KEY="your-key-here"
```

## CLI Usage

### Score papers

```bash
# By DOI
trustworthy-science score --doi 10.1038/s41586-020-2748-1

# Multiple DOIs
trustworthy-science score --doi 10.1038/s41586-020-2748-1 --doi 10.1126/science.1127349

# By search query
trustworthy-science score --query "GLP-1 receptor agonists in NASH" --top-k 5

# JSON output
trustworthy-science score --query "CRISPR off-target effects" --output json
```

### Filter for RAG

Retrieve papers and keep only those meeting a minimum credibility tier:

```bash
trustworthy-science filter \
    --query "Impact of social media on adolescent mental health" \
    --top-k 20 \
    --min-tier Caution
```

### Explain a single paper

```bash
trustworthy-science explain --doi 10.1038/s41586-020-2748-1
```

Shows the full credibility report: score, tier, narrative summary, all hard/soft flags, and quality signals.

### Global options

```bash
trustworthy-science --config config/scoring.yaml --log-level INFO score --doi 10.xxx/xxx
trustworthy-science -v score --doi 10.xxx/xxx   # verbose agent logs
```

## Python API

```python
from trustworthy_science.api import TruthFilter

tf = TruthFilter.from_config()          # uses config/scoring.yaml by default

# Score a list of DOIs
reports = tf.score_papers(dois=["10.1038/s41586-020-2748-1"])

# Score by query
reports = tf.score_papers(query="CRISPR gene editing", top_k=10)

# Filter for RAG — returns only papers at or above min_tier
filtered = tf.filter_for_rag(
    query="CRISPR gene editing for cystic fibrosis",
    top_k=20,
    min_tier="Caution",
)

# Single paper with full explanation
result = tf.score_single("10.1038/s41586-020-2748-1")
```

## Architecture

A two-level LangGraph graph defined in `graph.py`.

**Multi-paper graph** — fetches papers (PubMed / bioRxiv / Crossref), deduplicates, fans out to the per-paper graph.

**Per-paper pipeline:**

```
fetch_parse → retraction_check ──(retracted?)──→ scoring
                                ↓ (not retracted)
                         paper_classifier          ← NEW: assigns paper_type
                                ↓
           stats_integrity → [reproducibility ‖ citation_network ‖ methodology]
                                          ↓
                               publication_metadata → scoring
```

All state flows through `PaperState` (defined in `state.py`). LangGraph merges concurrent writes via reducer annotations.

### Paper Type Classification

`paper_classifier.py` identifies 8 paper types from title + abstract using regex rules:

| Type | Example |
|------|---------|
| `empirical_quantitative` | original research study (default) |
| `clinical_trial` | RCT, phase I–IV trial |
| `systematic_review_meta` | systematic review, meta-analysis, PRISMA |
| `review_narrative` | literature review, scoping review |
| `theoretical` | mathematical model, formal proof |
| `computational_methods` | software tool, pipeline, algorithm |
| `case_report` | case report, case series |
| `opinion_commentary` | editorial, perspective, commentary |

### Type-aware applicability matrix (`config/scoring.yaml`)

```yaml
paper_type_applicability:
  empirical_quantitative:   {data: true,  code: true,  prereg: true}
  clinical_trial:           {data: true,  code: false, prereg: true}
  systematic_review_meta:   {data: true,  code: false, prereg: false}
  review_narrative:         {data: false, code: false, prereg: false}
  theoretical:              {data: false, code: false, prereg: false}
  computational_methods:    {data: false, code: true,  prereg: false}
  case_report:              {data: false, code: false, prereg: false}
  opinion_commentary:       {data: false, code: false, prereg: false}
```

Criteria set to `false` are silently skipped — no penalty, no flag.

### Scoring formula

```
score = base(70) − Σ soft_penalties + Σ quality_bonuses(capped at 20) + methods_nudge(±15%)
if any hard_flag → score ≤ 25 → Untrusted
Trusted ≥ 70 | Caution ≥ 45 | Untrusted < 45
```

Hard flags: `RETRACTED`, `P_HACKING_CLUSTER`, `PREDATORY_VENUE`, `OUTCOME_SWITCHING_CONFIRMED`, `IMAGE_MANIPULATION`

All weights are in `config/scoring.yaml` — edit there to tune without touching code.

## Configuration

`config/scoring.yaml` controls everything:

- **`scoring`** — base score, methods nudge weight, quality bonus cap
- **`soft_flags`** — penalty per flag code
- **`quality_signals`** — bonus per signal code
- **`tiers`** — score thresholds and hard-flag cap
- **`pcurve`** — p-hacking detection thresholds
- **`paper_type_applicability`** — per-type check matrix
- **`reproducibility`** — regex patterns for data/code/preregistration detection
- **`citation_network`** — self-citation and diversity thresholds

## Running Tests

```bash
# All tests
pytest tests/

# Verbose output (shows each test name and result)
pytest tests/ -v

# Single file
pytest tests/test_paper_type_aware_scoring.py -v

# Single test by name
pytest tests/test_scoring.py::test_function_name -v
```

Tests are fully mocked (no live API calls). `pytest-asyncio` is used for async agent tests.

## Extending

**Add a new check**: emit a `Flag` object from an agent, add its penalty/bonus to `config/scoring.yaml`.

**Add a new agent**: implement `(state: PaperState) → dict`, register as a node in `graph.py`, wire into edges.

**Tune scoring**: edit `config/scoring.yaml` only.
