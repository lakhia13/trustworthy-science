"""PubMed / MEDLINE API tools (NCBI E-utilities)."""

from __future__ import annotations

import logging
import os
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from trustworthy_science.cache.sqlite_cache import get_cache
from trustworthy_science.state import PaperStub

logger = logging.getLogger(__name__)

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_CACHE_NS = "pubmed"


def _api_key_param() -> dict[str, str]:
    key = os.environ.get("NCBI_API_KEY", "")
    return {"api_key": key} if key else {}


def _get(url: str, params: dict) -> dict:
    """HTTP GET with retry and caching."""
    cache = get_cache()
    cached = cache.get(_CACHE_NS, url, **params)
    if cached is not None:
        return cached
    for attempt in range(3):
        try:
            r = httpx.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json() if "json" in r.headers.get("content-type", "") else {"_text": r.text}
            cache.set(_CACHE_NS, data, url, **params)
            return data
        except Exception as exc:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return {}


def search_pubmed(query: str, max_results: int = 10) -> list[str]:
    """Return a list of PMIDs matching *query*."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        **_api_key_param(),
    }
    data = _get(f"{_BASE}/esearch.fcgi", params)
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_pubmed_metadata(pmids: list[str]) -> list[PaperStub]:
    """Fetch PaperStub objects for the given PMIDs."""
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
        **_api_key_param(),
    }
    cache = get_cache()
    cache_key = ("fetch", ",".join(sorted(pmids)))
    cached = cache.get(_CACHE_NS, *cache_key)
    if cached is not None:
        return [PaperStub(**s) for s in cached]

    r = httpx.get(f"{_BASE}/efetch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    stubs = _parse_pubmed_xml(r.text)
    cache.set(_CACHE_NS, [s.model_dump() for s in stubs], *cache_key)
    return stubs


def _parse_pubmed_xml(xml_text: str) -> list[PaperStub]:
    stubs: list[PaperStub] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse PubMed XML")
        return stubs

    for article in root.findall(".//PubmedArticle"):
        try:
            stub = _article_to_stub(article)
            stubs.append(stub)
        except Exception as exc:
            logger.debug("Skipping article: %s", exc)
    return stubs


def _article_to_stub(article: ET.Element) -> PaperStub:
    # Scope all queries to the correct sub-trees to avoid picking up IDs,
    # authors, or dates from the paper's reference list.
    mc = article.find("MedlineCitation")
    citation_article = mc.find("Article") if mc is not None else None

    # PMID — scoped to MedlineCitation only
    pmid = (mc.findtext("PMID") or "") if mc is not None else ""

    # Title
    title = (citation_article.findtext("ArticleTitle") or "") if citation_article is not None else ""

    # Journal + ISSN + Year — scoped to Article/Journal
    journal_el = citation_article.find("Journal") if citation_article is not None else None
    journal = (journal_el.findtext("Title") or "") if journal_el is not None else ""
    issn = (journal_el.findtext("ISSN") or None) if journal_el is not None else None
    pub_date = (journal_el.find("JournalIssue/PubDate") if journal_el is not None else None)
    year = None
    if pub_date is not None:
        year_text = pub_date.findtext("Year")
        if not year_text:
            # Fall back to first 4 digits of MedlineDate (e.g. "2021 Jan-Feb")
            medline = pub_date.findtext("MedlineDate") or ""
            year_text = medline[:4] if medline[:4].isdigit() else None
        if year_text:
            try:
                year = int(year_text)
            except ValueError:
                pass

    # Authors — iterate the AuthorList directly under Article, not .//Author
    # which would descend into reference author lists
    authors: list[str] = []
    author_list = citation_article.find("AuthorList") if citation_article is not None else None
    if author_list is not None:
        for author in author_list.findall("Author"):
            last = (author.findtext("LastName") or "").strip()
            fore = (author.findtext("ForeName") or "").strip()
            name = f"{fore} {last}".strip()
            if name:
                authors.append(name)

    # Abstract — scoped to Article/Abstract to avoid any embedded abstracts in references
    abstract_parts: list[str] = []
    abstract_el = citation_article.find("Abstract") if citation_article is not None else None
    if abstract_el is not None:
        for ab in abstract_el.findall("AbstractText"):
            if ab.text:
                abstract_parts.append(ab.text)
    abstract = " ".join(abstract_parts)

    # DOI and PMCID — scoped to PubmedData/ArticleIdList (the paper's own IDs only).
    # Using .//ArticleId descends into ReferenceList and picks up cited paper IDs.
    doi: str | None = None
    pmcid: str | None = None
    pubmed_data = article.find("PubmedData")
    if pubmed_data is not None:
        id_list = pubmed_data.find("ArticleIdList")
        if id_list is not None:
            for id_el in id_list.findall("ArticleId"):
                id_type = id_el.get("IdType")
                if id_type == "doi" and doi is None:
                    doi = id_el.text
                elif id_type == "pmc" and pmcid is None:
                    pmcid = id_el.text

    return PaperStub(
        doi=doi,
        pmid=pmid or None,
        pmcid=pmcid,
        title=title,
        authors=authors,
        venue=journal,
        issn=issn or None,
        year=year,
        abstract=abstract,
        source="pubmed",
    )


def fetch_pmc_fulltext(pmcid: str) -> str:
    """Fetch full-text XML from PubMed Central and return plain text."""
    cache = get_cache()
    cached = cache.get("pmc_fulltext", pmcid)
    if cached is not None:
        return cached

    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pmc", "id": pmcid, "retmode": "xml", **_api_key_param()}
    try:
        r = httpx.get(url, params=params, timeout=30)
        r.raise_for_status()
        text = _strip_xml_tags(r.text)
        cache.set("pmc_fulltext", text, pmcid)
        return text
    except Exception as exc:
        logger.warning("PMC fulltext fetch failed for %s: %s", pmcid, exc)
        return ""


def _strip_xml_tags(xml_text: str) -> str:
    """Very light XML→plaintext conversion."""
    try:
        root = ET.fromstring(xml_text)
        return " ".join(root.itertext())
    except Exception:
        return xml_text
