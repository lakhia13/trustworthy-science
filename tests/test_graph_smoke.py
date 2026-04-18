"""Smoke tests for the LangGraph pipeline (no live API calls)."""

import pytest
from unittest.mock import patch, MagicMock

from trustworthy_science.state import PaperState, PaperStub, ParsedPaper, Flag


# ---------------------------------------------------------------------------
# Unit tests for individual agent functions (mocked dependencies)
# ---------------------------------------------------------------------------

def _make_state(doi="10.9999/test.001", with_text=True) -> PaperState:
    stub = PaperStub(
        doi=doi,
        title="A Study of Something Important",
        authors=["Alice Smith", "Bob Jones"],
        venue="Journal of Test Science",
        issn="1234-5678",
        year=2022,
        abstract="We performed tests. p < 0.05. No data was deposited publicly.",
    )
    parsed = None
    coverage = "abstract_only"
    if with_text:
        parsed = ParsedPaper(
            full_text="Methods: We used n = 5 mice. p = 0.048, p = 0.044, p = 0.046, p = 0.042. No data deposited.",
            abstract=stub.abstract,
            methods="We used n = 5 mice. Standard protocol applied.",
            results="p = 0.048, p = 0.044, p = 0.046, p = 0.042, p = 0.043. Effect observed.",
        )
        coverage = "full_text"
    return PaperState(stub=stub, parsed=parsed, coverage=coverage)


# --- retraction_watch agent ---

def test_retraction_watch_not_retracted():
    with patch("trustworthy_science.agents.retraction_watch.is_retracted", return_value=(False, None)):
        from trustworthy_science.agents.retraction_watch import retraction_watch_agent
        state = _make_state()
        result = retraction_watch_agent(state)
        assert result["retracted"] is False
        assert "retraction_watch" in result["sub_scores"]
        assert result["sub_scores"]["retraction_watch"].score == 1.0


def test_retraction_watch_retracted():
    record = {"source": "retraction_watch", "Reason": "Data fabrication"}
    with patch("trustworthy_science.agents.retraction_watch.is_retracted", return_value=(True, record)):
        from trustworthy_science.agents.retraction_watch import retraction_watch_agent
        state = _make_state()
        result = retraction_watch_agent(state)
        assert result["retracted"] is True
        assert len(result["hard_flags"]) == 1
        assert result["hard_flags"][0].code == "RETRACTED"


# --- stats_integrity agent ---

def test_stats_integrity_detects_phacking():
    from trustworthy_science.agents.stats_integrity import stats_integrity_agent
    state = _make_state()
    # State already has p-values 0.042-0.048 in results — should trigger p-hacking
    result = stats_integrity_agent(state)
    assert "stats_integrity" in result["sub_scores"]
    # With 5 p-values all in (0.04, 0.05], should flag p-hacking
    hard_codes = [f.code for f in result.get("hard_flags", [])]
    assert "P_HACKING_CLUSTER" in hard_codes


def test_stats_integrity_missing_effect_sizes():
    from trustworthy_science.agents.stats_integrity import stats_integrity_agent
    state = _make_state()
    result = stats_integrity_agent(state)
    soft_codes = [f.code for f in result.get("soft_flags", [])]
    assert "MISSING_EFFECT_SIZES" in soft_codes


# --- reproducibility agent ---

def test_reproducibility_flags_no_data():
    from trustworthy_science.agents.reproducibility import reproducibility_agent
    state = _make_state()
    result = reproducibility_agent(state)
    soft_codes = [f.code for f in result.get("soft_flags", [])]
    assert "NO_DATA_DEPOSIT" in soft_codes


def test_reproducibility_detects_open_data():
    from trustworthy_science.agents.reproducibility import reproducibility_agent
    state = _make_state()
    state.parsed.full_text += " Data available at zenodo.org/record/123456. Code on github.com/user/repo."
    result = reproducibility_agent(state)
    quality_codes = [f.code for f in result.get("quality_signals", [])]
    assert "OPEN_DATA" in quality_codes
    assert "OPEN_CODE" in quality_codes


# --- scoring agent ---

def test_scoring_agent_produces_report():
    from trustworthy_science.agents.scoring import scoring_agent
    state = _make_state()
    # Manually add flags
    state.hard_flags.append(Flag(tier="hard", code="RETRACTED", message="Test", source_agent="test"))
    result = scoring_agent(state)
    assert result["final"] is not None
    assert result["final"].tier == "Untrusted"
    assert result["final"].composite_score <= 25


def test_scoring_agent_trusted_paper():
    from trustworthy_science.agents.scoring import scoring_agent
    from trustworthy_science.state import SubScore
    state = _make_state()
    # Simulate a clean paper: quality signals, no flags
    state.quality_signals.extend([
        Flag(tier="quality", code="OPEN_DATA", message="Test", source_agent="test"),
        Flag(tier="quality", code="PREREGISTERED", message="Test", source_agent="test"),
    ])
    state.sub_scores["methodology"] = SubScore(score=0.85, confidence=0.9)
    result = scoring_agent(state)
    assert result["final"] is not None
    # Score should be above caution threshold
    assert result["final"].composite_score >= 45
