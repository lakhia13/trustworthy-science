"""ChromaDB vector store integration for Deep Research RAG pipeline.

Provides a persistent ChromaDB collection backed by local sentence-transformer
embeddings. All collections are stored under:
    ~/.local/share/trustworthy_science/chroma/

The base path can be overridden via ``config/scoring.yaml``:

    rag:
      chroma_path: /custom/path/to/chroma

Public API
----------
- ``get_or_create_collection(collection_name, config)``  → chromadb Collection
- ``ingest_papers(papers, collection_name, config)``      → number of chunks upserted
- ``query_collection(query, collection_name, config, k)`` → list of result dicts
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CHROMA_PATH = Path.home() / ".local" / "share" / "trustworthy_science" / "chroma"
_DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"
_CHUNK_SIZE = 1200   # characters per chunk
_CHUNK_OVERLAP = 150  # character overlap between chunks


# ---------------------------------------------------------------------------
# Path / client helpers
# ---------------------------------------------------------------------------

def _chroma_path(config: dict | None = None) -> str:
    cfg = (config or {}).get("rag", {})
    path = cfg.get("chroma_path", str(_DEFAULT_CHROMA_PATH))
    os.makedirs(path, exist_ok=True)
    return path


def _embed_model_name(config: dict | None = None) -> str:
    cfg = (config or {}).get("rag", {})
    return cfg.get("embed_model", _DEFAULT_EMBED_MODEL)


def _get_client(config: dict | None = None):
    """Return a persistent ChromaDB client."""
    import chromadb
    return chromadb.PersistentClient(path=_chroma_path(config))


def _get_embedding_function(config: dict | None = None):
    """Return a ChromaDB-compatible SentenceTransformer embedding function."""
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    model_name = _embed_model_name(config)
    return SentenceTransformerEmbeddingFunction(model_name=model_name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_or_create_collection(collection_name: str, config: dict | None = None):
    """Return (creating if necessary) a persistent ChromaDB collection.

    Parameters
    ----------
    collection_name:
        Unique identifier for this research session's collection.
    config:
        Optional parsed scoring.yaml; ``rag`` section controls path and model.

    Returns
    -------
    chromadb.Collection
    """
    client = _get_client(config)
    ef = _get_embedding_function(config)
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("[CHROMA] Collection '%s' ready (%d docs)", collection_name, collection.count())
    return collection


def ingest_papers(
    papers: list[dict],
    collection_name: str,
    config: dict | None = None,
) -> int:
    """Chunk and upsert paper text into a ChromaDB collection.

    Parameters
    ----------
    papers:
        List of scored paper dicts (from TruthFilter). Each should have at least
        ``title``, ``score``, ``tier``, and optionally ``doi``, ``pmid``, ``year``,
        ``venue``, and ``summary``.  Full text is not stored directly in the
        result dicts — the summary and abstract (if available) are used as the
        document content for semantic retrieval.
    collection_name:
        Target ChromaDB collection name.
    config:
        Optional config dict.

    Returns
    -------
    int
        Number of document chunks upserted.
    """
    collection = get_or_create_collection(collection_name, config)
    total = 0

    for paper in papers:
        # Build the text to embed — prefer full abstract/summary content
        text_parts = []
        title = paper.get("title") or ""
        if title:
            text_parts.append(f"Title: {title}")
        summary = paper.get("summary") or ""
        if summary:
            text_parts.append(summary)
        abstract = paper.get("abstract") or ""
        if abstract and abstract != summary:
            text_parts.append(abstract)

        if not text_parts:
            logger.debug("[CHROMA] Skipping paper with no text: %s", paper.get("doi"))
            continue

        full_text = "\n\n".join(text_parts)
        chunks = _chunk_text(full_text, _CHUNK_SIZE, _CHUNK_OVERLAP)

        metadata = {
            "doi": paper.get("doi") or "",
            "pmid": paper.get("pmid") or "",
            "title": title,
            "score": paper.get("score", 0),
            "tier": paper.get("tier", "Untrusted"),
            "year": str(paper.get("year") or ""),
            "venue": paper.get("venue") or "",
        }

        uid_base = paper.get("doi") or paper.get("pmid") or hashlib.sha256(title.encode()).hexdigest()[:16]

        ids = [f"{uid_base}__chunk_{i}" for i in range(len(chunks))]
        metas = [{**metadata, "chunk_index": i} for i in range(len(chunks))]

        try:
            collection.upsert(documents=chunks, metadatas=metas, ids=ids)
            total += len(chunks)
            logger.debug("[CHROMA] Upserted %d chunks for '%s'", len(chunks), title[:60])
        except Exception as exc:
            logger.warning("[CHROMA] Failed to upsert '%s': %s", title[:60], exc)

    logger.info("[CHROMA] Ingested %d total chunks into '%s'", total, collection_name)
    return total


def query_collection(
    query: str,
    collection_name: str,
    config: dict | None = None,
    k: int = 6,
) -> list[dict[str, Any]]:
    """Retrieve the top-k most relevant chunks for a query.

    Parameters
    ----------
    query:
        Natural-language question or topic.
    collection_name:
        ChromaDB collection to search.
    config:
        Optional config dict.
    k:
        Number of results to return.

    Returns
    -------
    list of dicts, each with keys: ``text``, ``doi``, ``pmid``, ``title``,
    ``score``, ``tier``, ``year``, ``venue``, ``distance``.
    """
    try:
        collection = get_or_create_collection(collection_name, config)
        collection_count = collection.count()
        if collection_count == 0:
            logger.info("[CHROMA] Collection '%s' is empty; returning no results (this is normal for new collections)", collection_name)
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(k, collection_count),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.error("[CHROMA] Query failed for collection '%s': %s", collection_name, exc)
        return []

    output: list[dict] = []
    docs = (results.get("documents") or [[]])[0]
    metas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    for doc, meta, dist in zip(docs, metas, distances):
        output.append({
            "text": doc,
            "doi": meta.get("doi", ""),
            "pmid": meta.get("pmid", ""),
            "title": meta.get("title", ""),
            "score": meta.get("score", 0),
            "tier": meta.get("tier", ""),
            "year": meta.get("year", ""),
            "venue": meta.get("venue", ""),
            "distance": round(dist, 4),
        })

    return output


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping character-level chunks."""
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks
