"""Retriever agent — searches PubMed, bioRxiv, and Crossref for papers."""

from __future__ import annotations

import logging
from typing import Any

from trustworthy_science.state import GraphInput, PaperStub
from trustworthy_science.tools.pubmed import fetch_pubmed_metadata, search_pubmed
from trustworthy_science.tools.biorxiv import search_biorxiv, fetch_biorxiv_by_doi
from trustworthy_science.tools.crossref import doi_to_stub, search_crossref

logger = logging.getLogger(__name__)


def retrieve_papers(input_data: GraphInput) -> list[PaperStub]:
    """Retrieve paper stubs from multiple sources based on query or DOI list.

    If ``input_data.dois`` is non-empty, each DOI is resolved directly via
    Crossref and bioRxiv. Otherwise a multi-source search is executed.
    """
    stubs: list[PaperStub] = []

    if input_data.dois:
        stubs = _resolve_dois(input_data.dois)
    elif input_data.query:
        stubs = _search_query(input_data.query, input_data.top_k)
    else:
        logger.warning("Retriever: no query or DOIs provided")

    # Deduplicate by DOI
    seen: set[str] = set()
    unique: list[PaperStub] = []
    for stub in stubs:
        key = stub.doi or stub.pmid or stub.title
        if key and key not in seen:
            seen.add(key)
            unique.append(stub)

    return unique[: input_data.top_k]


def _resolve_dois(dois: list[str]) -> list[PaperStub]:
    stubs = []
    for doi in dois:
        stub = None
        # Try Crossref first (most complete structural metadata)
        try:
            stub = doi_to_stub(doi)
        except Exception as exc:
            logger.debug("Crossref failed for %s: %s", doi, exc)
        # Fallback: bioRxiv
        if stub is None:
            try:
                stub = fetch_biorxiv_by_doi(doi)
            except Exception as exc:
                logger.debug("bioRxiv failed for %s: %s", doi, exc)
        if stub is None:
            stub = PaperStub(doi=doi, source="unknown")
            logger.warning("Could not resolve DOI: %s", doi)
        # Enrich with PubMed when Crossref stub is missing abstract or PMID/PMCID.
        # Crossref often lacks abstracts for paywalled journals; PubMed carries them.
        if stub and (not stub.abstract or not stub.pmid):
            try:
                pmids = search_pubmed(doi, max_results=1)
                if pmids:
                    pubmed_stubs = fetch_pubmed_metadata(pmids)
                    if pubmed_stubs:
                        pm = pubmed_stubs[0]
                        if not stub.abstract and pm.abstract:
                            stub = stub.model_copy(update={"abstract": pm.abstract})
                        if not stub.pmid and pm.pmid:
                            stub = stub.model_copy(update={"pmid": pm.pmid})
                        if not stub.pmcid and pm.pmcid:
                            stub = stub.model_copy(update={"pmcid": pm.pmcid})
            except Exception as exc:
                logger.debug("PubMed enrichment failed for %s: %s", doi, exc)
        stubs.append(stub)
    return stubs


def _search_query(query: str, top_k: int) -> list[PaperStub]:
    stubs: list[PaperStub] = []

    # PubMed
    try:
        pmids = search_pubmed(query, max_results=top_k)
        stubs += fetch_pubmed_metadata(pmids)
    except Exception as exc:
        logger.warning("PubMed search failed: %s", exc)

    # bioRxiv (via EuropePMC)
    try:
        stubs += search_biorxiv(query, max_results=max(top_k - len(stubs), 3))
    except Exception as exc:
        logger.warning("bioRxiv search failed: %s", exc)

    # Crossref as final fill
    if len(stubs) < top_k:
        try:
            stubs += search_crossref(query, max_results=top_k - len(stubs))
        except Exception as exc:
            logger.warning("Crossref search failed: %s", exc)

    return stubs
