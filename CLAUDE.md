# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode (use uv, not pip)
uv pip install -e .

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_scoring.py

# Run a single test by name
pytest tests/test_scoring.py::test_function_name

# CLI — score by DOI or query
trustworthy-science score --doi 10.1038/s41586-020-2748-1
trustworthy-science score --query "GLP-1 receptor agonists" --top-k 5
trustworthy-science filter --query "CRISPR" --top-k 20 --min-tier Caution
trustworthy-science explain --doi 10.1038/s41586-020-2748-1
trustworthy-science score --config config/scoring.yaml --doi 10.xxx/xxx

# Optional Streamlit UI
streamlit run src/trustworthy_science/ui/streamlit_app.py
```

**Required env vars:** `K2_API_KEY` (LLM; configured in `.env`). The LLM provider is `K2-Think-v2` at `https://api.k2think.ai/v1`.

## Architecture

A **LangGraph multi-agent pipeline** that assigns a Trust Score (0–100) and tier (`Trusted` / `Caution` / `Untrusted`) to scientific papers.

### Two-level graph structure (`graph.py`)

1. **Multi-paper graph** — takes a query or DOI list, retrieves papers (PubMed / bioRxiv / Crossref via `tools/`), deduplicates, then fans out to the per-paper graph.
2. **Per-paper sub-graph** — runs 9 agents sequentially/in parallel; produces a `TrustReport`.

### Per-paper agent pipeline

```
fetch_parse → retraction_check ─(retracted?)─→ scoring
                                ↓ (not retracted)
                         paper_classifier
                                ↓
           stats_integrity → [reproducibility ‖ citation_network ‖ methodology]
                                          ↓
                               publication_metadata → scoring
```

All agents read from and write back to `PaperState` (defined in `state.py`). LangGraph merges concurrent writes via reducer annotations on `PaperState` fields.

### Key files

| File | Role |
|------|------|
| `api.py` | `TruthFilter` — public Python API (`score_papers`, `filter_for_rag`, `score_single`) |
| `cli.py` | Click CLI wrapping `TruthFilter` |
| `graph.py` | LangGraph graph definitions for both levels |
| `state.py` | All Pydantic state models: `PaperStub`, `ParsedPaper`, `Flag`, `SubScore`, `TrustReport`, `PaperState`, `GraphInput/Output` |
| `llm.py` | LLM client factory (K2-Think-v2) |
| `scoring/rules.py` | Deterministic score engine: applies penalties, bonuses, hard-flag cap |
| `config/scoring.yaml` | **All scoring weights and thresholds** — edit here to tune behavior without touching code |

### Scoring formula (in `scoring/rules.py` + `config/scoring.yaml`)

```
score = base(70) − Σ soft_penalties + Σ quality_bonuses(capped at 20) + methods_nudge(0–15%)
if any hard_flag: score ≤ 25 → Untrusted
Trusted ≥ 70 | Caution ≥ 45 | Untrusted < 45
```

Hard flags: `RETRACTED`, `P_HACKING_CLUSTER`, `PREDATORY_VENUE`, `OUTCOME_SWITCHING_CONFIRMED`

### Paper type applicability

`paper_classifier.py` uses regex to classify paper type (empirical, clinical trial, systematic review, theoretical, etc.). The `paper_type_applicability` matrix in `config/scoring.yaml` controls which agents/checks are applied per type — e.g., p-curve analysis only runs on empirical papers.

### Extending the system

- **Add a new flag or signal**: add it to `config/scoring.yaml` under `soft_flags` or `quality_signals`, then emit it from an agent as a `Flag` object in `PaperState.flags`.
- **Add a new agent**: implement it as an async function `(state: PaperState) → dict`, register it as a node in `graph.py:_make_paper_graph`, and wire it into the graph edges.
- **Tune scoring weights**: edit `config/scoring.yaml` only — no code change needed.

### Testing notes

Tests in `tests/` are fully mocked (no live API calls). `pytest-asyncio` is used for async agent tests. Tests cover: scoring rules, p-curve algorithm, graph smoke tests per agent, and paper-type-aware scoring.
