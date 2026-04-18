"""P-value extraction from scientific text (regex + heuristics)."""

from __future__ import annotations

import re
from typing import Any

# Regex patterns that match p-values in scientific text
# Covers: p < 0.05, p = 0.032, P-value: 0.001, p<0.001, etc.
_PVAL_PATTERNS = [
    # Strict: p followed by comparison operator and decimal number
    r"[Pp][\s\-]*(?:value)?[\s]*[=<>≤≥]{1,2}[\s]*0?\.\d+",
    # e.g. "p < .05"
    r"[Pp][\s]*[=<>≤≥]{1,2}[\s]*\.\d+",
    # e.g. "P = 3.2×10⁻⁴", "P = 3.2e-4"
    r"[Pp][\s]*[=<>]{1,2}[\s]*\d+\.?\d*[eE×x\*]\d*[\s]*[\-−][\s]*\d+",
]

_NUM_RE = re.compile(r"(\d*\.\d+|\d+[eE][\-\+]?\d+|\d+\.\d+[eE][\-\+]?\d+)")


def extract_pvalues(text: str) -> list[float]:
    """Extract all reported p-values from scientific text as floats.

    Returns a sorted list of floats in [0, 1]. Values reported as exponents
    (e.g. 3.2e-4) are converted to float.
    """
    pvalues: list[float] = []
    for pattern in _PVAL_PATTERNS:
        for match in re.finditer(pattern, text):
            snippet = match.group(0)
            # Extract the numeric part
            nums = _NUM_RE.findall(snippet)
            for num_str in nums:
                try:
                    val = float(num_str)
                    if 0.0 <= val <= 1.0:
                        pvalues.append(val)
                except ValueError:
                    pass
    # Deduplicate (keep order, remove exact duplicates within small tolerance)
    seen: list[float] = []
    for v in sorted(set(round(p, 6) for p in pvalues)):
        seen.append(v)
    return seen


def extract_effect_sizes(text: str) -> list[dict[str, Any]]:
    """Extract Cohen's d, odds ratios, hazard ratios, and confidence intervals."""
    results: list[dict[str, Any]] = []

    # Cohen's d
    for m in re.finditer(r"Cohen['']?s?\s*d\s*[=≈]\s*(-?\d+\.?\d*)", text, re.IGNORECASE):
        results.append({"type": "cohens_d", "value": float(m.group(1)), "snippet": m.group(0)})

    # Odds ratio
    for m in re.finditer(r"(?:odds ratio|OR)\s*[=:≈]\s*(\d+\.?\d*)", text, re.IGNORECASE):
        results.append({"type": "odds_ratio", "value": float(m.group(1)), "snippet": m.group(0)})

    # Hazard ratio
    for m in re.finditer(r"(?:hazard ratio|HR)\s*[=:≈]\s*(\d+\.?\d*)", text, re.IGNORECASE):
        results.append({"type": "hazard_ratio", "value": float(m.group(1)), "snippet": m.group(0)})

    # Confidence intervals
    for m in re.finditer(r"(\d+)%\s*(?:CI|confidence interval)[:\s]+[\[\(]?(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)[\]\)]?", text, re.IGNORECASE):
        level, lo, hi = m.group(1), m.group(2), m.group(3)
        results.append({
            "type": "confidence_interval",
            "level": int(level),
            "lower": float(lo),
            "upper": float(hi),
            "snippet": m.group(0),
        })

    return results


def extract_sample_sizes(text: str) -> list[int]:
    """Heuristically extract sample sizes (n=...) from text."""
    sizes = []
    for m in re.finditer(r"[Nn]\s*[=≈]\s*(\d+)", text):
        sizes.append(int(m.group(1)))
    return sizes
