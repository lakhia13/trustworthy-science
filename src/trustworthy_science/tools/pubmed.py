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
    def text(path: str, default: str = "") -> str:
        el = article.find(path)
        return (el.text or "") if el is not None else default

    pmid = text(".//PMID")
    title = text(".//ArticleTitle")
    year_el = article.find(".//PubDate/Year")
    year = int(year_el.text) if year_el is not None and year_el.text else None
    journal = text(".//Journal/Title")
    issn = text(".//ISSN")

    # Authors
    authors = []
    for author in article.findall(".//Author"):
        last = text(".//LastName", "") if (ln := author.find("LastName")) is None else (ln.text or "")
        fore = text(".//ForeName", "") if (fn := author.find("ForeName")) is None else (fn.text or "")
        name = f"{fore} {last}".strip()
        if name:
            authors.append(name)

    # Abstract
    abstract_parts = []
    for ab in article.findall(".//AbstractText"):
        if ab.text:
            abstract_parts.append(ab.text)
    abstract = " ".join(abstract_parts)

    # DOI
    doi = None
    for id_el in article.findall(".//ArticleId"):
        if id_el.get("IdType") == "doi":
            doi = id_el.text
            break

    return PaperStub(
        doi=doi,
        pmid=pmid,
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
