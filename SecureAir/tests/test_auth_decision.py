"""Synthetic tests for transparent fail-closed decision behavior."""
import math

import pytest

from backend.auth_decision import evaluate_authentication


def test_all_required_signals_pass_at_threshold():
    result = evaluate_authentication(
        sequence_status="SUCCESS",
        challenge_success=True,
        behavioral_match_score=0.8,
        threshold=0.8,
    )
    assert result["decision"] == "ALLOW"
    assert result["allowed"] is True
    assert result["reasons"] == ["all_required_signals_passed"]
    assert result["behavioral_score_source"] == "caller_supplied"


@pytest.mark.parametrize(("sequence_status", "expected_reason"), [
    ("FAILED", "gesture_sequence_failed"),
    ("TIMEOUT", "gesture_sequence_timeout"),
    ("IN_PROGRESS", "gesture_sequence_in_progress"),
])
def test_non_success_sequence_denies(sequence_status, expected_reason):
    result = evaluate_authentication(
        sequence_status=sequence_status,
        challenge_success=True,
        behavioral_match_score=1.0,
    )
    assert result["decision"] == "DENY"
    assert expected_reason in result["reasons"]


def test_challenge_failure_and_low_score_report_separate_reasons():
    result = evaluate_authentication(
        sequence_status="SUCCESS",
        challenge_success=False,
        behavioral_match_score=0.2,
        threshold=0.8,
    )
    assert result["allowed"] is False
    assert result["reasons"] == ["challenge_failed", "behavioral_match_below_threshold"]


@pytest.mark.parametrize("score", [None, -0.01, 1.01, float("nan"), float("inf"), True, "0.9"])
def test_invalid_score_fails_closed(score):
    result = evaluate_authentication(
        sequence_status="SUCCESS", challenge_success=True, behavioral_match_score=score,
    )
    assert result["decision"] == "DENY"
    assert "invalid_behavioral_match_score" in result["reasons"]


@pytest.mark.parametrize("threshold", [-0.1, 1.1, float("nan"), float("inf"), True, "0.8"])
def test_invalid_threshold_fails_closed(threshold):
    result = evaluate_authentication(
        sequence_status="SUCCESS", challenge_success=True,
        behavioral_match_score=1.0, threshold=threshold,
    )
    assert result["decision"] == "DENY"
    assert "invalid_threshold" in result["reasons"]


def test_invalid_sequence_and_challenge_types_fail_closed():
    result = evaluate_authentication(
        sequence_status="UNKNOWN", challenge_success=1, behavioral_match_score=0.9,
    )
    assert result["decision"] == "DENY"
    assert "invalid_sequence_status" in result["reasons"]
    assert "invalid_challenge_result" in result["reasons"]


def test_multiple_failures_are_reported_and_never_allow():
    result = evaluate_authentication(
        sequence_status="FAILED", challenge_success=False,
        behavioral_match_score=0.1, threshold=0.9,
    )
    assert result["decision"] == "DENY"
    assert len(result["reasons"]) == 3
    assert all(isinstance(reason, str) and reason for reason in result["reasons"])
