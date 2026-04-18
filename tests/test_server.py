"""Tests for the FastAPI server routes — all pipeline calls are mocked."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from trustworthy_science.server.app import create_app
from trustworthy_science.server.dependencies import get_truth_filter

# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

_MOCK_PAPER: dict = {
    "title": "Test Paper",
    "doi": "10.1038/nature12345",
    "pmid": "23193264",
    "year": 2013,
    "venue": "Nature",
    "score": 82,
    "tier": "Trusted",
    "coverage": "full_text",
    "fetch_source": "bioc",
    "summary": "A well-conducted study.",
    "hard_flags": [],
    "soft_flags": ["NO_DATA_DEPOSIT"],
    "quality_signals": ["OPEN_DATA"],
    "per_dimension": {"stats_integrity": 0.9, "methodology": 0.85},
}


# ---------------------------------------------------------------------------
# Fixture: override get_truth_filter via FastAPI dependency_overrides
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_tf():
    tf = MagicMock()
    tf.score_single_by_pmid.return_value = _MOCK_PAPER
    tf.score_papers.return_value = [_MOCK_PAPER]
    tf.filter_for_rag.return_value = [_MOCK_PAPER]
    tf.score_single.return_value = _MOCK_PAPER
    tf.reload_config.return_value = None
    return tf


@pytest.fixture()
def client(mock_tf):
    """TestClient with the real TruthFilter replaced via dependency_overrides.

    FastAPI's ``dependency_overrides`` is the recommended approach for
    replacing ``Depends(...)`` callables in tests without patching module
    internals. The override is scoped to this test via teardown.
    """
    # Suppress lifespan so init_truth_filter is never called
    with patch("trustworthy_science.server.dependencies.init_truth_filter"):
        app = create_app()

    # Replace the get_truth_filter dependency for the entire app
    app.dependency_overrides[get_truth_filter] = lambda: mock_tf

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, mock_tf

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 1: POST /score with pmids → 200
# ---------------------------------------------------------------------------

def test_score_by_pmid(client):
    c, tf = client
    response = c.post("/score", json={"pmids": ["23193264"]})
    assert response.status_code == 200
    data = response.json()
    assert "papers" in data
    assert len(data["papers"]) >= 1
    assert data["papers"][0]["score"] == 82
    tf.score_single_by_pmid.assert_called_once_with("23193264")


# ---------------------------------------------------------------------------
# Test 2: POST /score with dois → 200
# ---------------------------------------------------------------------------

def test_score_by_doi(client):
    c, tf = client
    response = c.post("/score", json={"dois": ["10.1038/nature12345"]})
    assert response.status_code == 200
    data = response.json()
    assert "papers" in data
    assert len(data["papers"]) >= 1
    tf.score_papers.assert_called_once()


# ---------------------------------------------------------------------------
# Test 3: POST /score with no identifiers → 422
# ---------------------------------------------------------------------------

def test_score_missing_identifiers(client):
    c, _ = client
    response = c.post("/score", json={"dois": [], "pmids": [], "query": None})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test 4: POST /explain with pmid → 200 with per_dimension populated
# ---------------------------------------------------------------------------

def test_explain_by_pmid(client):
    c, tf = client
    response = c.post("/explain", json={"pmid": "23193264"})
    assert response.status_code == 200
    data = response.json()
    assert data["pmid"] == "23193264"
    assert data["fetch_source"] == "bioc"
    assert "per_dimension" in data
    assert data["per_dimension"]["stats_integrity"] == pytest.approx(0.9)
    tf.score_single_by_pmid.assert_called_once_with("23193264")


# ---------------------------------------------------------------------------
# Test 5: POST /explain with both doi and pmid → 422
# ---------------------------------------------------------------------------

def test_explain_both_identifiers(client):
    c, _ = client
    response = c.post("/explain", json={"doi": "10.1038/nature12345", "pmid": "23193264"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test 6: POST /explain where mock returns None → 404
# ---------------------------------------------------------------------------

def test_explain_not_found(client):
    c, tf = client
    tf.score_single_by_pmid.return_value = None
    response = c.post("/explain", json={"pmid": "99999999"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 7: POST /filter with query → 200 with papers and count
# ---------------------------------------------------------------------------

def test_filter_papers(client):
    c, tf = client
    response = c.post("/filter", json={"query": "CRISPR cancer therapy"})
    assert response.status_code == 200
    data = response.json()
    assert "papers" in data
    assert "count" in data
    assert data["count"] == len(data["papers"])
    assert data["query"] == "CRISPR cancer therapy"
    assert data["min_tier"] == "Caution"  # default
    tf.filter_for_rag.assert_called_once_with(
        query="CRISPR cancer therapy", top_k=20, min_tier="Caution"
    )


# ---------------------------------------------------------------------------
# Test 8: GET /admin/health → 200 {"status": "ok", "version": "0.1.0"}
# ---------------------------------------------------------------------------

def test_health(client):
    c, _ = client
    response = c.get("/admin/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# Test 9: POST /admin/reload-config with {} → 200 with reloaded: true
# ---------------------------------------------------------------------------

def test_reload_config(client):
    c, _ = client
    with patch("trustworthy_science.server.routes.admin.reload_truth_filter"):
        response = c.post("/admin/reload-config", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["reloaded"] is True
    assert "config_path" in data
