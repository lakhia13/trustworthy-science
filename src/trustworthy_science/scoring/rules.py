"""Scoring rules — deterministic tier/score calculation from flags."""

from __future__ import annotations

from trustworthy_science.state import Flag

_DEFAULT_SOFT_PENALTIES: dict[str, int] = {
    "NO_DATA_DEPOSIT": 8,
    "NO_CODE_AVAILABILITY": 5,
    "HIGH_SELF_CITATION": 7,
    "HIGH_SELF_CITATION_RATIO": 5,
    "LOW_CITATION_DIVERSITY": 5,
    "INDUSTRY_ONLY_FUNDING_NO_COI": 7,
    "MISSING_EFFECT_SIZES": 6,
    "SMALL_SAMPLE_UNDERPOWERED": 6,
    "METHODS_INCOMPLETE": 8,
    "FAST_PEER_REVIEW": 4,
    "NO_PREREGISTRATION": 3,
    "VENUE_NOT_IN_DOAJ": 3,
}

_DEFAULT_QUALITY_BONUSES: dict[str, int] = {
    "PREREGISTERED": 6,
    "OPEN_DATA": 6,
    "OPEN_CODE": 4,
    "INDEPENDENTLY_REPLICATED": 10,
    "DIVERSE_CITATIONS": 4,
    "COI_DISCLOSED": 2,
    "HIGH_IMPACT_VENUE": 3,
}

_HARD_FLAG_CODES = frozenset([
    "RETRACTED",
    "P_HACKING_CLUSTER",
    "PREDATORY_VENUE",
    "OUTCOME_SWITCHING_CONFIRMED",
    "IMAGE_MANIPULATION",
])


def compute_composite_score(
    hard_flags: list[Flag],
    soft_flags: list[Flag],
    quality_signals: list[Flag],
    methods_score: float | None = None,  # 0–1 from methodology agent; None = not available
    config: dict | None = None,
) -> tuple[int, str]:
    """Return (composite_score 0-100, tier string).

    Parameters
    ----------
    methods_score:
        Overall score from the methodology agent (0–1). Use None when not available
        (avoids penalising papers where no methods text was extracted).
    config:
        Parsed scoring YAML dict. Falls back to defaults if None.
    """
    cfg = (config or {}).get("scoring", {})
    tiers_cfg = (config or {}).get("tiers", {})

    base = int(cfg.get("base", 70))
    bonus_cap = int(cfg.get("quality_bonus_cap", 20))
    methods_weight = float(cfg.get("methods_nudge_weight", 0.15))
    trusted_min = int(tiers_cfg.get("trusted_min", 70))
    caution_min = int(tiers_cfg.get("caution_min", 45))
    hard_cap = int(tiers_cfg.get("hard_flag_cap", 25))

    soft_penalties = (config or {}).get("soft_flags", {})
    quality_bonuses = (config or {}).get("quality_signals", {})

    # Compute soft penalty total
    total_penalty = 0
    for flag in soft_flags:
        cfg_entry = soft_penalties.get(flag.code, {})
        penalty = cfg_entry.get("penalty", _DEFAULT_SOFT_PENALTIES.get(flag.code, 5))
        total_penalty += penalty

    # Compute quality bonus total (capped)
    total_bonus = 0
    for flag in quality_signals:
        cfg_entry = quality_bonuses.get(flag.code, {})
        bonus = cfg_entry.get("bonus", _DEFAULT_QUALITY_BONUSES.get(flag.code, 3))
        total_bonus += bonus
    total_bonus = min(total_bonus, bonus_cap)

    # Methods nudge: only when a real methods score is available
    methods_nudge = methods_weight * (methods_score * 100 - 70) if methods_score is not None else 0.0

    score = base - total_penalty + total_bonus + methods_nudge
    score = int(max(0, min(100, round(score))))

    # Apply hard flag cap
    if hard_flags:
        score = min(score, hard_cap)
        tier = "Untrusted"
    elif score >= trusted_min:
        tier = "Trusted"
    elif score >= caution_min:
        tier = "Caution"
    else:
        tier = "Untrusted"

    return score, tier
