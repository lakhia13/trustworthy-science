"""Benford's Law anomaly detector for scientific data tables.

Real experimental data follows Benford's Law: the leading digit d occurs
with probability log10(1 + 1/d).  When researchers fabricate or round data,
the leading-digit distribution deviates significantly from this expected
curve.  The same technique was used to detect the Enron accounting fraud
and election irregularities — here we apply it to scientific papers.

Reference: Benford, F. (1938). The law of anomalous numbers.
           Proceedings of the American Philosophical Society, 78(4), 551-572.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Benford expected probabilities for digits 1-9
# ---------------------------------------------------------------------------

BENFORD_PROBS = np.array([math.log10(1 + 1 / d) for d in range(1, 10)])

# Pattern to extract numeric values from scientific text.
# Captures integers and decimals; excludes years (19xx, 20xx), DOIs, IDs.
_NUMBER_RE = re.compile(
    r"(?<![/\w])"             # not preceded by word char or slash (skip DOIs)
    r"(?<!\d{2})"             # not part of a 4-digit year-like sequence
    r"(\d+(?:\.\d+)?)"        # capture: integer or decimal
    r"(?!\d)"                 # not followed by more digits
)

# Exclude numbers that are clearly not data (page numbers, years, small IDs)
_YEAR_RE   = re.compile(r"\b(19|20)\d{2}\b")
_SMALL_INT = re.compile(r"^\d$")  # single-digit standalone — skip


@dataclass
class BenfordsResult:
    """Result of a Benford's Law chi-squared test."""
    n_numbers: int            # total numbers analysed
    digit_counts: list[int]   # counts for digits 1-9
    digit_freqs: list[float]  # observed frequencies for digits 1-9
    chi2_stat: float
    p_value: float
    anomaly_detected: bool    # True if significant deviation (p < threshold)
    threshold: float          # p-value threshold used
    summary: str
    histogram: str            # ASCII bar chart for verbose logging


def extract_numbers(text: str) -> list[float]:
    """Extract all plausible data values from scientific text.

    Filters out:
    - Years (1900–2099)
    - Single-digit standalone numbers (sample sizes, indices)
    - Numbers > 1,000,000 (likely not data values)
    - Pure integers 0-9 (trivial)
    """
    # Remove years first
    cleaned = _YEAR_RE.sub(" ", text)

    raw = _NUMBER_RE.findall(cleaned)
    result: list[float] = []
    for s in raw:
        try:
            v = float(s)
        except ValueError:
            continue
        # Skip zeros (no leading digit), very large numbers, single-digit ints
        if v <= 0 or v > 1_000_000:
            continue
        if v == int(v) and v < 10:
            continue
        result.append(v)
    return result


def leading_digit(x: float) -> int:
    """Return the leading (most significant) digit of a positive number."""
    if x <= 0:
        raise ValueError("x must be positive")
    # Normalise to [1, 10)
    while x >= 10:
        x /= 10
    while x < 1:
        x *= 10
    return int(x)


def benfords_law_test(
    text: str,
    min_numbers: int = 30,
    p_threshold: float = 0.05,
) -> BenfordsResult:
    """Run Benford's Law chi-squared test on numbers extracted from text.

    Parameters
    ----------
    text:
        Full text (results section preferred) of the paper.
    min_numbers:
        Minimum numbers required before the test is considered reliable.
    p_threshold:
        Chi-squared p-value below which we flag an anomaly.

    Returns
    -------
    BenfordsResult with anomaly_detected=False if n < min_numbers.
    """
    numbers = extract_numbers(text)
    n = len(numbers)

    logger.info("[BENFORD] Numbers extracted: %d (min required: %d)", n, min_numbers)

    # Not enough data — inconclusive
    if n < min_numbers:
        hist = _ascii_histogram([0] * 9, BENFORD_PROBS * 0)
        return BenfordsResult(
            n_numbers=n,
            digit_counts=[0] * 9,
            digit_freqs=[0.0] * 9,
            chi2_stat=0.0,
            p_value=1.0,
            anomaly_detected=False,
            threshold=p_threshold,
            summary=f"Insufficient data: {n} numbers extracted (need ≥{min_numbers}) — Benford test skipped.",
            histogram=hist,
        )

    # Count leading digits 1-9
    counts = [0] * 9
    for x in numbers:
        try:
            d = leading_digit(x)
            if 1 <= d <= 9:
                counts[d - 1] += 1
        except ValueError:
            pass

    freqs = [c / n for c in counts]

    # Chi-squared goodness-of-fit against Benford's expected distribution
    expected = BENFORD_PROBS * n
    # Avoid zero expected (shouldn't happen for Benford, but guard anyway)
    expected = np.maximum(expected, 1e-9)
    observed = np.array(counts, dtype=float)

    chi2_stat, p_value = stats.chisquare(observed, f_exp=expected)

    anomaly = bool(p_value < p_threshold)

    hist = _ascii_histogram(counts, BENFORD_PROBS * n)

    if anomaly:
        summary = (
            f"Benford's Law anomaly detected (χ²={chi2_stat:.2f}, p={p_value:.4f} < {p_threshold}). "
            f"Leading-digit distribution of {n} extracted numbers deviates significantly from "
            f"the expected natural pattern. This may indicate data fabrication or heavy rounding."
        )
    else:
        summary = (
            f"Benford's Law: no anomaly (χ²={chi2_stat:.2f}, p={p_value:.4f}). "
            f"Leading-digit distribution of {n} numbers is consistent with natural data."
        )

    logger.info("[BENFORD] %s", summary)
    logger.info("[BENFORD]\n%s", hist)

    return BenfordsResult(
        n_numbers=n,
        digit_counts=counts,
        digit_freqs=freqs,
        chi2_stat=chi2_stat,
        p_value=p_value,
        anomaly_detected=anomaly,
        threshold=p_threshold,
        summary=summary,
        histogram=hist,
    )


def _ascii_histogram(observed: list[int], expected: list[float]) -> str:
    """Build an ASCII bar chart comparing observed vs Benford expected."""
    lines = ["Digit  Observed  Expected  Bar"]
    lines.append("─" * 50)
    total_obs = max(sum(observed), 1)
    for i, (obs, exp) in enumerate(zip(observed, expected), start=1):
        obs_pct = obs / total_obs * 100 if total_obs > 0 else 0
        exp_pct = exp / total_obs * 100 if total_obs > 0 else BENFORD_PROBS[i - 1] * 100
        bar_obs = "█" * round(obs_pct / 2)
        bar_exp = "░" * round(exp_pct / 2)
        lines.append(f"  {i}    {obs:5d} ({obs_pct:4.1f}%)  ({exp_pct:4.1f}%)  {bar_obs}{bar_exp}")
    return "\n".join(lines)
