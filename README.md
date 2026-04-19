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
                         paper_classifier          ← assigns paper_type
                                ↓
                           detective (statistical integrity + Shadow Data Verification)
                                ↓
      ┌────────┬──────────────┬────────────┬──────────────────────────┐
      ↓        ↓              ↓            ↓                          ↓
    coder  citation_network  methodology  librarian                 peer
 (repro +  (self-citations)  (LLM methods (venue/COI/author     (adversarial red-
  GitHub)                    critique)    consistency)           team + scite.ai)
      └────────┴──────────────┴────────────┴──────────────────────────┘
                                          ↓
                                       scoring
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
score = base(70) − Σ soft_penalties + Σ quality_bonuses(capped at 25) + methods_nudge(±15%)
if any hard_flag → score ≤ 25 → Untrusted
Trusted ≥ 70 | Caution ≥ 45 | Untrusted < 45
```

Hard flags immediately cap any score to ≤ 25 and force tier `Untrusted`:
`RETRACTED`, `P_HACKING_CLUSTER`, `PREDATORY_VENUE`, `OUTCOME_SWITCHING_CONFIRMED`, `OUTCOME_SWITCHING`, `DATA_FABRICATION_SIGNS`, `IMAGE_MANIPULATION`

All weights are in `config/scoring.yaml` — edit there to tune without touching code.

---

## Scoring System — Full Reference

### How the Score is Computed

```
final_score = base_score(70)
            − total_soft_penalties
            + min(total_quality_bonuses, 25)        ← capped (raised from 20)
            + methods_nudge                          ← see below

if any hard_flag raised:
    final_score = min(final_score, 25)
    tier = "Untrusted"
elif final_score >= 70: tier = "Trusted"
elif final_score >= 45: tier = "Caution"
else:                   tier = "Untrusted"
```

The **methods nudge** applies only when a full methods section was available for LLM critique:

```
methods_nudge = 0.15 × (methodology_score × 100 − 70)
```

A methodology score of 0.70 → no nudge. A score of 0.90 → +3 pts. A score of 0.40 → −4.5 pts.

---

### Sub-agent Dimensions

The pipeline runs six concurrent sub-agents before the final scoring node. Each produces a `SubScore` (0.0–1.0) and any flags. The sub-scores are shown in the Score Breakdown table but do **not** directly feed into the composite formula — flags produced by the sub-agents do. The exception is `methodology`, whose single `overall_score` drives the methods nudge.

#### 1. Detective (`detective`)

Wraps the existing statistical integrity checks and adds two new LLM skills.

| Check | What it does | Output |
|---|---|---|
| **P-curve analysis** | Extracts all reported p-values; flags a p-hacking cluster if ≥ 40% fall in the (0.04, 0.05] window (requires ≥ 5 p-values) | Hard flag `P_HACKING_CLUSTER` (caps composite ≤ 25) |
| **Effect sizes** | Scans for Cohen's d, OR, HR, RR, CI, etc. | Soft flag `MISSING_EFFECT_SIZES` if p-values present but no effect sizes (−4 pts) |
| **Sample size** | Extracts all reported N values; flags the smallest | Soft flag `SMALL_SAMPLE_UNDERPOWERED` if min N < 20 (−5 pts) |
| **Benford's Law** | Chi-squared test on leading digits of all numbers (requires ≥ 30 data values) | Soft flag `BENFORDS_LAW_ANOMALY` if p < 0.05 (−6 pts) |
| **Shadow Data Verification** *(LLM)* | Cross-references N/p-values/effect sizes between Abstract and Results sections; requires a numeric discrepancy in the explanation | Soft flag `INTERNAL_INCONSISTENCY` (−8 pts) |
| **Industry COI Unstated** | Keyword search for industry funders without COI disclosure | Soft flag `INDUSTRY_COI_UNSTATED` (−6 pts) |

#### 2. Coder (`coder`)

Wraps the reproducibility agent and adds GitHub repo health checks.

| Check | What it does | Output |
|---|---|---|
| **Data availability** | Pattern matching for accession codes and repository URLs | Quality `OPEN_DATA_PERMANENT` (+8 pts) or `OPEN_DATA_GENERIC` (+4 pts); soft `NO_DATA_DEPOSIT` (−3 pts) |
| **Code availability** | GitHub/GitLab/Bitbucket URLs, `code available` statements | Quality `OPEN_CODE_FUNCTIONAL` (+6 pts) if repo health verified; `OPEN_CODE` (+4 pts) otherwise; soft `NO_CODE_AVAILABILITY` (−2 pts) |
| **Pre-registration** | ClinicalTrials.gov / NCT numbers, OSF, PROSPERO, AsPredicted | Quality `PREREGISTERED` (+6 pts) if found; soft `NO_PREREGISTRATION` (−1 pt) if not |
| **GitHub Repo Health** | Checks repo activity (last push < 24 months, not archived) | Upgrades `OPEN_CODE` → `OPEN_CODE_FUNCTIONAL` |
| **Environmental Viability** *(LLM)* | Checks README for installation instructions and dependency spec | Informs `OPEN_CODE_FUNCTIONAL` upgrade |
| **DATA_LINK_BROKEN** | HEAD request to data/code URLs; skips known-stable hosts (Zenodo, Dryad, OSF, etc.) | Soft flag `DATA_LINK_BROKEN` (−10 pts); cancels `OPEN_DATA_*` / `OPEN_CODE_*` signals |

#### 3. Librarian (`librarian`)

Wraps the publication metadata agent and adds author-topic-venue consistency checking.

| Check | What it does | Output |
|---|---|---|
| **Venue reputation (DOAJ)** | DOAJ API lookup for the journal ISSN | Quality `HIGH_IMPACT_VENUE` (+3 pts) if found; soft `VENUE_NOT_IN_DOAJ` (−2 pts) |
| **Predatory venue** | Beall's List pattern matching | Hard flag `PREDATORY_VENUE` (caps composite ≤ 25) |
| **Review speed** | Crossref submission/acceptance dates | Soft flag `FAST_PEER_REVIEW` (−4 pts) if < 14 days |
| **COI disclosure** | Presence of COI statement | Quality `COI_DISCLOSED` (+2 pts); soft `INDUSTRY_ONLY_FUNDING_NO_COI` (−5 pts) |
| **Author Consistency Audit** *(LLM)* | Checks if abstract topic matches the venue scope (paper mill indicator) | Score adjustment −0.20 on `librarian` sub-score |

#### 4. Peer (`peer`)

New agent providing adversarial review and citation context analysis.

| Check | What it does | Output |
|---|---|---|
| **Adversarial Red-Teaming** *(LLM)* | Hostile peer reviewer: identifies confounders and conclusion overreach | Soft flag `CLAIM_OVERREACH` (−7 pts) if overreach detected |
| **Deep Limitations** | Checks if paper has a self-critical limitations section (≥ 3 sentences with limitation keywords) | Quality `DEEP_LIMITATIONS` (+3 pts) |
| **Citation Context** *(scite.ai, optional)* | Fetches citation tallies (supporting / contrasting / mentioning) — requires `SCITE_API_KEY` | Quality `SUPPORTING_CITATIONS` (+5 pts) if ≥ 50% supporting; soft `CLAIM_OVERREACH` if contested |

#### 5. Citation Network (`citation_network`)

Queries the OpenAlex API for citation data. Requires a DOI.

| Check | Threshold | Output |
|---|---|---|
| **Self-citation ratio** | > 30% of citing papers share an author with the original | Soft flag `HIGH_SELF_CITATION` (−4 pts, −15 pts to sub-score) |
| **Institutional diversity** | Requires ≥ 5 citations; ≥ 50% of citing papers from different institutions | Quality `DIVERSE_CITATIONS` (+4 pts, +10 pts to sub-score) if diverse; soft `LOW_CITATION_DIVERSITY` if not |

Baseline sub-score is 0.70 (neutral). Confidence scales with citation count: ≥ 10 citations → 0.80; ≥ 3 → 0.50; < 3 → 0.25.

#### 6. Methodology (`methodology`)

LLM-based critique of the methods section using K2-Think-v2. Only runs when methods text is available from the full-text or abstract.

The LLM evaluates six binary criteria and returns a JSON rubric:

| Criterion | Penalty if false |
|---|---|
| `sample_size_justified` | Soft flag `METHODS_INCOMPLETE` (−6 pts) |
| `controls_described` | Soft flag `METHODS_INCOMPLETE` (−6 pts) |
| `reproducibility_detail_sufficient` | Soft flag `METHODS_INCOMPLETE` (−6 pts) |
| `statistics_prespecified` | Quality `PREREGISTERED` (+6 pts) if true |
| `blinding_described` | No automatic flag (factored into `overall_score`) |
| `outcome_clearly_defined` | No automatic flag (factored into `overall_score`) |

The `overall_score` (0.0–1.0) from the LLM response drives the **methods nudge** in the composite formula.

---

### Soft Penalties (config/scoring.yaml)

Each soft flag subtracts a fixed number of points from the composite score.

| Flag | Default Penalty | Raised by |
|---|---|---|
| `NO_DATA_DEPOSIT` | −3 pts | Coder agent |
| `NO_CODE_AVAILABILITY` | −2 pts | Coder agent |
| `NO_PREREGISTRATION` | −1 pt | Coder agent |
| `HIGH_SELF_CITATION` | −4 pts | Citation network agent |
| `HIGH_SELF_CITATION_RATIO` | −3 pts | Citation network agent |
| `INDUSTRY_ONLY_FUNDING_NO_COI` | −5 pts | Librarian agent |
| `MISSING_EFFECT_SIZES` | −4 pts | Detective agent |
| `SMALL_SAMPLE_UNDERPOWERED` | −5 pts | Detective agent |
| `METHODS_INCOMPLETE` | −6 pts | Methodology agent |
| `FAST_PEER_REVIEW` | −4 pts | Librarian agent |
| `BENFORDS_LAW_ANOMALY` | −6 pts | Detective agent |
| `REPLICATION_FAILED` | −8 pts | Librarian agent |
| `VENUE_NOT_IN_DOAJ` | −2 pts | Librarian agent |
| `INTERNAL_INCONSISTENCY` | −8 pts | Detective agent (Shadow Data Verification LLM) |
| `CLAIM_OVERREACH` | −7 pts | Peer agent (Adversarial Red-Teaming / scite.ai) |
| `DATA_LINK_BROKEN` | −10 pts | Coder agent (URL accessibility check) |
| `INDUSTRY_COI_UNSTATED` | −6 pts | Detective agent (keyword COI check) |

---

### Quality Bonuses (config/scoring.yaml)

Bonuses are summed and **capped at 25 pts total** (raised from 20).

| Signal | Default Bonus | Raised by |
|---|---|---|
| `OPEN_DATA` | +6 pts | Backward-compat alias for `OPEN_DATA_GENERIC` |
| `OPEN_DATA_PERMANENT` | +8 pts | Coder agent — DOI-backed repo (Zenodo, Dryad, Figshare, Harvard Dataverse) |
| `OPEN_DATA_GENERIC` | +4 pts | Coder agent — data available but not DOI-backed |
| `OPEN_CODE` | +4 pts | Backward-compat alias; used when repo health not verified |
| `OPEN_CODE_FUNCTIONAL` | +6 pts | Coder agent — repo health verified: not archived, recently maintained |
| `PREREGISTERED` | +6 pts | Coder / methodology agent |
| `INDEPENDENTLY_REPLICATED` | +10 pts | Librarian agent |
| `DIVERSE_CITATIONS` | +4 pts | Citation network agent |
| `HIGH_IMPACT_VENUE` | +3 pts | Librarian agent |
| `COI_DISCLOSED` | +2 pts | Librarian agent |
| `SUPPORTING_CITATIONS` | +5 pts | Peer agent (scite.ai — ≥ 50% supporting citations) |
| `DEEP_LIMITATIONS` | +3 pts | Peer agent — thorough self-critical limitations section (≥ 3 sentences) |

---

### Hard Flags

Any hard flag immediately caps `composite_score ≤ 25` and forces tier `Untrusted`, regardless of quality bonuses.

| Flag | Raised by | Trigger |
|---|---|---|
| `RETRACTED` | Retraction check agent | DOI or title found in retraction database |
| `P_HACKING_CLUSTER` | Detective agent | ≥ 40% of p-values in (0.04, 0.05] window |
| `PREDATORY_VENUE` | Librarian agent | Journal or publisher on known predatory list |
| `OUTCOME_SWITCHING_CONFIRMED` | Librarian agent | Registered outcomes differ from reported outcomes (backward compat alias) |
| `OUTCOME_SWITCHING` | Librarian agent | Registered outcomes differ from reported outcomes |
| `DATA_FABRICATION_SIGNS` | Scoring agent (composite) | Both `BENFORDS_LAW_ANOMALY` AND `INTERNAL_INCONSISTENCY` detected simultaneously |
| `IMAGE_MANIPULATION` | Post-MVP | — |

---

### Type-aware Applicability Matrix

Criteria are silently skipped (no flag, no penalty) for paper types where they are not meaningful.

| Paper Type | Data check | Code check | Pre-reg check |
|---|---|---|---|
| `empirical_quantitative` | ✓ | ✓ | ✓ |
| `clinical_trial` | ✓ | — | ✓ |
| `systematic_review_meta` | ✓ | — | — |
| `review_narrative` | — | — | — |
| `theoretical` | — | — | — |
| `computational_methods` | — | ✓ | — |
| `case_report` | — | — | — |
| `opinion_commentary` | — | — | — |

Statistical integrity checks (effect sizes, sample size, Benford's Law) are also skipped for all non-empirical types.

## Configuration

`config/scoring.yaml` controls everything:

- **`scoring`** — `base_score` (canonical) / `base` (alias), methods nudge weight, quality bonus cap
- **`soft_flags`** — penalty per flag code (includes new ASAS flags)
- **`quality_signals`** — bonus per signal code (includes new ASAS signals)
- **`tiers`** — score thresholds and hard-flag cap
- **`pcurve`** — p-hacking detection thresholds
- **`paper_type_applicability`** — per-type check matrix (now includes `stats` key)
- **`reproducibility`** — regex patterns for data/code/preregistration detection
- **`citation_network`** — self-citation and diversity thresholds

Optional API keys (set in `.env`):
- `GITHUB_TOKEN` — increases GitHub API rate limit (coder agent)
- `SCITE_API_KEY` — enables Citation Context skill in peer agent

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
