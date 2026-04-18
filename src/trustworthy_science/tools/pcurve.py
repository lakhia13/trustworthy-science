"""P-curve analysis — detect p-hacking by examining distribution of p-values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import stats


@dataclass
class PCurveResult:
    """Result of a p-curve analysis."""
    n_pvalues: int
    n_in_window: int          # how many fall in (0.04, 0.05]
    window_ratio: float       # n_in_window / n_pvalues
    phack_suspected: bool     # True if cluster near 0.05
    right_skew_test_p: float  # p-value of the right-skew test (< 0.05 = evidential)
    flat_test_p: float        # p-value of the flat-null test
    summary: str


def pcurve_analysis(
    pvalues: Sequence[float],
    min_required: int = 5,
    window_lo: float = 0.04,
    window_hi: float = 0.05,
    cluster_ratio_threshold: float = 0.40,
) -> PCurveResult:
    """Perform a simplified p-curve analysis.

    Follows Simonsohn, Nelson & Simmons (2014) approach:
    - A *right-skewed* distribution (many small p-values) = genuine effect.
    - A *cluster just below 0.05* = signature of p-hacking.

    Parameters
    ----------
    pvalues:
        List of p-values extracted from the paper (all values in [0, 1]).
    min_required:
        Minimum number of p-values required to run the analysis.
    window_lo, window_hi:
        The suspicious cluster window, default (0.04, 0.05].
    cluster_ratio_threshold:
        If >= this fraction of p-values fall in the window, flag p-hacking.

    Returns
    -------
    PCurveResult
    """
    sig = [p for p in pvalues if 0 < p <= 0.05]
    n = len(sig)

    if n < min_required:
        return PCurveResult(
            n_pvalues=n,
            n_in_window=0,
            window_ratio=0.0,
            phack_suspected=False,
            right_skew_test_p=1.0,
            flat_test_p=1.0,
            summary=f"Insufficient p-values ({n} < {min_required}) for p-curve analysis.",
        )

    sig_arr = np.array(sig)

    # --- Cluster test: binomial test for pile-up near 0.05 ---
    n_window = int(np.sum((sig_arr > window_lo) & (sig_arr <= window_hi)))
    # Under uniform H0, expected fraction in window = (0.05 - 0.04) / 0.05 = 0.20
    expected_fraction = (window_hi - window_lo) / 0.05
    binom_result = stats.binomtest(n_window, n, expected_fraction, alternative="greater")
    cluster_ratio = n_window / n

    # --- Right-skew test: test whether distribution is uniform vs right-skewed ---
    # Convert to pp-values: under H0 (no effect), pp_i = uniform(0,1)
    # Under H1 (real effect), pp values should be right-skewed.
    # pp_i = F_p(p_i) where F_p is the distribution of p-values under the null.
    # Simple proxy: test that mean(sig_arr) < 0.025 (expected under uniform H0 = 0.025)
    # Use a one-sample t-test.
    tstat, ttest_p = stats.ttest_1samp(sig_arr, popmean=0.025, alternative="less")
    right_skew_test_p = float(ttest_p)

    # P-hacking decision
    phack_suspected = (
        cluster_ratio >= cluster_ratio_threshold
        or float(binom_result.pvalue) < 0.05
    )

    summary_parts = [
        f"Analysed {n} significant p-values (p ≤ 0.05).",
        f"{n_window}/{n} ({cluster_ratio:.0%}) fall in ({window_lo}, {window_hi}].",
    ]
    if phack_suspected:
        summary_parts.append(
            "P-HACKING SUSPECTED: Abnormal cluster of p-values just below 0.05."
        )
    else:
        if right_skew_test_p < 0.05:
            summary_parts.append("P-curve is right-skewed, consistent with a genuine effect.")
        else:
            summary_parts.append("P-curve does not show clear evidence of a genuine effect (flat/left-skewed).")

    return PCurveResult(
        n_pvalues=n,
        n_in_window=n_window,
        window_ratio=cluster_ratio,
        phack_suspected=phack_suspected,
        right_skew_test_p=right_skew_test_p,
        flat_test_p=float(binom_result.pvalue),
        summary=" ".join(summary_parts),
    )
