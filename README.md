# Trustworthy Science

Trustworthy Science is a tool designed to assess the credibility of scientific papers. It uses a multi-agent AI system to analyze papers against a configurable set of rules, providing a "Trust Score" and a detailed breakdown of its findings. This allows researchers to quickly filter out unreliable or retracted papers and focus on high-quality literature.

The system is built on LangGraph and uses a graph-based approach to run a series of analysis agents in parallel.

## Features

-   **Credibility Scoring**: Assigns a "Trust Score" (0-100) to each paper based on a configurable set of criteria.
-   **Tier-based Filtering**: Categorizes papers into Tiers: `Trusted`, `Caution`, and `Untrusted`.
-   **Detailed Explanations**: Provides a breakdown of the factors contributing to a paper's score, including:
    -   **Hard Flags**: Critical issues like retractions.
    -   **Soft Flags**: Concerns like statistical anomalies or conflicts of interest.
    -   **Quality Signals**: Positive indicators like adherence to best practices.
-   **Multiple Analysis Dimensions**:
    -   Retraction status checks
    -   Citation network analysis
    -   Methodology and reproducibility assessment
    -   Statistical integrity checks (e.g., p-curves)
    -   Publication metadata analysis
-   **Flexible Input**: Score papers by DOI or by a natural-language search query.
-   **RAG Integration**: Filter a corpus of papers to retrieve only those meeting a minimum credibility tier for use in Retrieval-Augmented Generation (RAG) pipelines.
-   **Command-Line and API Interface**: Use the tool as a CLI or import it as a Python library.

## Installation

This project uses `uv` for dependency management.

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/trustworthy-science.git
    cd trustworthy-science
    ```

2.  Install dependencies:
    ```bash
    uv pip install -e .
    ```
    *(The `-e` flag installs the project in editable mode.)*

3.  Set up your API keys (e.g., for OpenAI, Anthropic) as environment variables:
    ```bash
    export OPENAI_API_KEY="sk-..."
    export ANTHROPIC_API_KEY="..."
    ```

## Usage

The primary interface is the `trustworthy-science` CLI.

### `score`

Score one or more papers by their DOI.

```bash
trustworthy-science score --doi 10.1038/s41586-020-2748-1 --doi 10.1126/science.1127349
```

Or score the top results for a search query:

```bash
trustworthy-science score --query "GLP-1 receptor agonists in NASH" --top-k 5
```

### `filter`

Retrieve papers for a research question and only show those that meet a minimum credibility tier. This is ideal for feeding a RAG system.

```bash
trustworthy-science filter \
    --query "Impact of social media on adolescent mental health" \
    --top-k 20 \
    --min-tier Caution
```

### `explain`

Get a detailed credibility report for a single paper, including all flags and signals.

```bash
trustworthy-science explain --doi 10.1038/s41586-020-2748-1
```

## Configuration

The scoring behavior is controlled by `config/scoring.yaml`. This file allows you to:
-   Enable or disable specific analysis agents.
-   Define "hard flags", "soft flags", and "quality signals".
-   Assign weights to different flags to tune the final score.

You can specify a different config file with the `--config` option.

## API Usage

You can also use `TruthFilter` directly in your Python code.

```python
from trustworthy_science.api import TruthFilter

# Load from the default config/scoring.yaml
tf = TruthFilter.from_config()

# Score a list of DOIs
reports = tf.score_papers(dois=["10.1038/s41586-020-2748-1"])
print(reports)

# Filter papers for a RAG pipeline
filtered_papers = tf.filter_for_rag(
    query="CRISPR gene editing for cystic fibrosis",
    top_k=20,
    min_tier="Caution",
)
print(filtered_papers)
```
