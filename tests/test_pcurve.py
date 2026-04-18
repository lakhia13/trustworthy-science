"""Tests for p-curve analysis."""

import pytest
from trustworthy_science.tools.pcurve import pcurve_analysis


def test_insufficient_pvalues():
    result = pcurve_analysis([0.03, 0.04], min_required=5)
    assert result.phack_suspected is False
    assert "Insufficient" in result.summary


def test_phacking_cluster_detected():
    # Pile-up just below 0.05 — classic p-hacking signature
    phacked = [0.041, 0.043, 0.044, 0.046, 0.049, 0.048, 0.047, 0.045, 0.042]
    result = pcurve_analysis(phacked, min_required=5, cluster_ratio_threshold=0.50)
    assert result.phack_suspected is True
    assert result.n_in_window == 9  # all are in (0.04, 0.05]


def test_right_skewed_clean_study():
    # Genuinely small p-values — healthy distribution
    clean = [0.0001, 0.001, 0.002, 0.005, 0.008, 0.01, 0.015, 0.02, 0.025, 0.03]
    result = pcurve_analysis(clean, min_required=5)
    assert result.phack_suspected is False


def test_window_ratio_calculation():
    pvalues = [0.041, 0.043, 0.001, 0.002, 0.03]
    result = pcurve_analysis(pvalues, min_required=5)
    assert result.n_pvalues == 5
    # 2 out of 5 are in (0.04, 0.05]: 0.041, 0.043
    assert result.n_in_window == 2
    assert abs(result.window_ratio - 0.4) < 0.01


def test_extract_pvalues_from_text():
    from trustworthy_science.tools.pvalue_extract import extract_pvalues
    text = "We found p < 0.05 for group A and p = 0.032 for group B. P-value = 0.001 for the interaction."
    pvalues = extract_pvalues(text)
    assert len(pvalues) >= 2
    assert any(abs(v - 0.032) < 0.001 for v in pvalues)
    assert any(abs(v - 0.001) < 0.001 for v in pvalues)


def test_extract_effect_sizes():
    from trustworthy_science.tools.pvalue_extract import extract_effect_sizes
    text = "Cohen's d = 0.45 (95% CI [0.12, 0.78]). OR = 2.3 for the primary endpoint."
    effects = extract_effect_sizes(text)
    types = [e["type"] for e in effects]
    assert "cohens_d" in types
    assert "odds_ratio" in types
