"""Scoring rules — deterministic tier/score calculation from flags."""

from __future__ import annotations

import logging

from trustworthy_science.state import Flag

logger = logging.getLogger(__name__)

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
    # Previously missing — added by ASAS Phase 0 bug-fix
    "BENFORDS_LAW_ANOMALY": 6,
    "REPLICATION_FAILED": 8,
    # New ASAS flags
    "INTERNAL_INCONSISTENCY": 8,
    "CLAIM_OVERREACH": 7,
    "DATA_LINK_BROKEN": 10,
    "INDUSTRY_COI_UNSTATED": 6,
}

_DEFAULT_QUALITY_BONUSES: dict[str, int] = {
    "PREREGISTERED": 6,
    "OPEN_DATA": 6,
    "OPEN_CODE": 4,
    "INDEPENDENTLY_REPLICATED": 10,
    "DIVERSE_CITATIONS": 4,
    "COI_DISCLOSED": 2,
    "HIGH_IMPACT_VENUE": 3,
    # New ASAS quality signals
    "OPEN_DATA_PERMANENT": 8,
    "OPEN_DATA_GENERIC": 4,
    "OPEN_CODE_FUNCTIONAL": 6,
    "SUPPORTING_CITATIONS": 5,
    "DEEP_LIMITATIONS": 3,
}

_HARD_FLAG_CODES = frozenset([
    "RETRACTED",
    "P_HACKING_CLUSTER",
    "PREDATORY_VENUE",
    "OUTCOME_SWITCHING_CONFIRMED",
    "OUTCOME_SWITCHING",        # alias without _CONFIRMED suffix
    "DATA_FABRICATION_SIGNS",   # composite: BENFORDS_LAW_ANOMALY + INTERNAL_INCONSISTENCY
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

    base = int(cfg.get('base_score', cfg.get('base', 70)))
    bonus_cap = int(cfg.get("quality_bonus_cap", 20))
    methods_weight = float(cfg.get("methods_nudge_weight", 0.15))
    trusted_min = int(tiers_cfg.get("trusted_min", 70))
    caution_min = int(tiers_cfg.get("caution_min", 45))
    hard_cap = int(tiers_cfg.get("hard_flag_cap", 25))

    soft_penalties = (config or {}).get("soft_flags", {})
    quality_bonuses = (config or {}).get("quality_signals", {})

    logger.info("[SCORE] ── Score Breakdown ──────────────────────────")
    logger.info("[SCORE] Base score:          %d", base)

    # Compute soft penalty total
    total_penalty = 0
    for flag in soft_flags:
        cfg_entry = soft_penalties.get(flag.code, {})
        penalty = cfg_entry.get("penalty", _DEFAULT_SOFT_PENALTIES.get(flag.code, 5))
        total_penalty += penalty
        logger.info("[SCORE]   Soft flag %-35s  -%d pts", flag.code, penalty)

    if not soft_flags:
        logger.info("[SCORE]   No soft flags")

    # Compute quality bonus total (capped)
    total_bonus = 0
    for flag in quality_signals:
        cfg_entry = quality_bonuses.get(flag.code, {})
        bonus = cfg_entry.get("bonus", _DEFAULT_QUALITY_BONUSES.get(flag.code, 3))
        total_bonus += bonus
        logger.info("[SCORE]   Quality signal %-31s  +%d pts", flag.code, bonus)
    total_bonus_raw = total_bonus
    total_bonus = min(total_bonus, bonus_cap)
    if total_bonus_raw > bonus_cap:
        logger.info("[SCORE]   Quality bonus capped at %d (raw was %d)", bonus_cap, total_bonus_raw)

    if not quality_signals:
        logger.info("[SCORE]   No quality signals")

    # Methods nudge: only when a real methods score is available
    methods_nudge = methods_weight * (methods_score * 100 - 70) if methods_score is not None else 0.0
    if methods_score is not None:
        logger.info("[SCORE]   Methods nudge (LLM score=%.2f):  %+.1f pts", methods_score, methods_nudge)
    else:
        logger.info("[SCORE]   Methods nudge: skipped (no LLM methods score)")

    score = base - total_penalty + total_bonus + methods_nudge
    score = int(max(0, min(100, round(score))))

    logger.info("[SCORE] ─────────────────────────────────────────────")
    logger.info("[SCORE] Formula: %d - %d (penalties) + %d (bonuses) + %.1f (methods) = %d",
                base, total_penalty, total_bonus, methods_nudge, score)

    # Apply hard flag cap
    if hard_flags:
        logger.info("[SCORE] ⚠ HARD FLAGS detected: %s → capping score at %d",
                    [f.code for f in hard_flags], hard_cap)
        score = min(score, hard_cap)
        tier = "Untrusted"
    elif score >= trusted_min:
        tier = "Trusted"
    elif score >= caution_min:
        tier = "Caution"
    else:
        tier = "Untrusted"

    logger.info("[SCORE] FINAL SCORE: %d/100 | TIER: %s", score, tier)
    logger.info("[SCORE] ─────────────────────────────────────────────")

    return score, tier
