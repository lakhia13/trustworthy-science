"""Tests for the deterministic scoring engine."""

import pytest
from trustworthy_science.state import Flag
from trustworthy_science.scoring.rules import compute_composite_score


def _flag(tier, code):
    return Flag(tier=tier, code=code, message=f"Test: {code}", source_agent="test")


def test_no_flags_returns_base():
    score, tier = compute_composite_score([], [], [])
    assert score == 70
    assert tier == "Trusted"


def test_soft_flags_reduce_score():
    soft = [_flag("soft", "NO_DATA_DEPOSIT"), _flag("soft", "METHODS_INCOMPLETE")]
    score, tier = compute_composite_score([], soft, [])
    # 70 - 8 - 8 = 54
    assert score == 54
    assert tier == "Caution"


def test_quality_signals_increase_score():
    quality = [_flag("quality", "OPEN_DATA"), _flag("quality", "PREREGISTERED"), _flag("quality", "INDEPENDENTLY_REPLICATED")]
    score, tier = compute_composite_score([], [], quality)
    # 70 + min(6+6+10, 20) = 70 + 20 = 90
    assert score == 90
    assert tier == "Trusted"


def test_quality_bonus_is_capped():
    quality = [_flag("quality", code) for code in [
        "OPEN_DATA", "PREREGISTERED", "INDEPENDENTLY_REPLICATED",
        "OPEN_CODE", "DIVERSE_CITATIONS", "COI_DISCLOSED", "HIGH_IMPACT_VENUE"
    ]]
    score, tier = compute_composite_score([], [], quality)
    # Bonus should not exceed 20: 70 + 20 = 90
    assert score <= 90


def test_hard_flag_caps_score():
    hard = [_flag("hard", "RETRACTED")]
    score, tier = compute_composite_score(hard, [], [])
    assert score <= 25
    assert tier == "Untrusted"


def test_hard_flag_with_quality_still_capped():
    hard = [_flag("hard", "P_HACKING_CLUSTER")]
    quality = [_flag("quality", "OPEN_DATA"), _flag("quality", "PREREGISTERED")]
    score, tier = compute_composite_score(hard, [], quality)
    assert score <= 25
    assert tier == "Untrusted"


def test_heavy_soft_flags_make_untrusted():
    soft = [
        _flag("soft", "NO_DATA_DEPOSIT"),
        _flag("soft", "METHODS_INCOMPLETE"),
        _flag("soft", "HIGH_SELF_CITATION"),
        _flag("soft", "INDUSTRY_ONLY_FUNDING_NO_COI"),
    ]
    score, tier = compute_composite_score([], soft, [])
    # 70 - 8 - 8 - 7 - 7 = 40
    assert score == 40
    assert tier == "Untrusted"


def test_methods_nudge_applied():
    # Good methods score should nudge up
    score_good, _ = compute_composite_score([], [], [], methods_score=1.0)
    score_bad, _ = compute_composite_score([], [], [], methods_score=0.0)
    assert score_good > score_bad


def test_score_clamped_to_0_100():
    # Pile on many soft flags
    soft = [_flag("soft", "NO_DATA_DEPOSIT")] * 20
    score, tier = compute_composite_score([], soft, [])
    assert score >= 0
    assert score <= 100
