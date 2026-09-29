"""Transparent, fail-closed policy over independently computed auth signals.

This policy combines sequence and challenge outcomes with a caller-supplied
behavioral match score. It does not compute that score, verify detector
provenance, or establish identity; it is not a complete authentication system.
"""
from __future__ import annotations

import math
from typing import Any

_VALID_SEQUENCE_STATUSES = frozenset({"SUCCESS", "FAILED", "TIMEOUT", "IN_PROGRESS"})


def evaluate_authentication(
    *,
    sequence_status: str,
    challenge_success: bool,
    behavioral_match_score: float | None,
    threshold: float = 0.8,
) -> dict[str, Any]:
    """Return a JSON-friendly allow/deny decision with explicit reasons.

    The behavioral score must be supplied by the caller and must be a finite
    number in [0, 1]. A score equal to the threshold passes. Invalid signal or
    threshold values fail closed; no model score is inferred here.
    """
    reasons: list[str] = []

    threshold_valid = (
        isinstance(threshold, (int, float))
        and not isinstance(threshold, bool)
        and math.isfinite(threshold)
        and 0.0 <= threshold <= 1.0
    )
    if not threshold_valid:
        reasons.append("invalid_threshold")

    if not isinstance(sequence_status, str) or sequence_status not in _VALID_SEQUENCE_STATUSES:
        reasons.append("invalid_sequence_status")
    elif sequence_status != "SUCCESS":
        reasons.append(f"gesture_sequence_{sequence_status.lower()}")

    if not isinstance(challenge_success, bool):
        reasons.append("invalid_challenge_result")
    elif not challenge_success:
        reasons.append("challenge_failed")

    score_valid = (
        isinstance(behavioral_match_score, (int, float))
        and not isinstance(behavioral_match_score, bool)
        and math.isfinite(behavioral_match_score)
        and 0.0 <= behavioral_match_score <= 1.0
    )
    if not score_valid:
        reasons.append("invalid_behavioral_match_score")
    elif threshold_valid and behavioral_match_score < threshold:
        reasons.append("behavioral_match_below_threshold")

    allowed = not reasons
    return {
        "decision": "ALLOW" if allowed else "DENY",
        "allowed": allowed,
        "reasons": reasons if reasons else ["all_required_signals_passed"],
        "threshold": float(threshold) if threshold_valid else None,
        "behavioral_score_source": "caller_supplied",
    }
