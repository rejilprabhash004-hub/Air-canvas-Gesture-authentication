"""Challenge lifecycle tests use synthetic gesture labels and a fake clock."""
from datetime import datetime, timezone

import pytest

from backend.challenges import (
    ChallengeAlreadyUsedError,
    ChallengeError,
    ChallengeExpiredError,
    ChallengeManager,
    ChallengeNotFoundError,
    ChallengeUserMismatchError,
)


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeUtcNow:
    def __init__(self):
        self.value = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


def manager(clock=None, lifetime=10, length=3):
    clock = clock or FakeClock()
    return ChallengeManager(
        lifetime_seconds=lifetime,
        sequence_length=length,
        clock=clock,
        utc_now=FakeUtcNow(),
    )


def test_issued_challenge_is_bound_and_correct_sequence_consumes_once():
    challenges = manager()
    challenge = challenges.issue("user_1")
    assert len(challenge.challenge_id) >= 32
    assert challenge.profile_id == "user_1"
    assert len(challenge.gestures) == 3
    assert challenge.created_at.endswith("+00:00")
    assert challenge.expires_at.endswith("+00:00")

    assert challenges.consume(challenge.challenge_id, "user_1", challenge.gestures) is True
    with pytest.raises(ChallengeAlreadyUsedError):
        challenges.consume(challenge.challenge_id, "user_1", challenge.gestures)


def test_wrong_sequence_is_consumed_and_cannot_be_retried():
    challenges = manager(length=2)
    challenge = challenges.issue("alice")
    wrong = ("NOT_A_GESTURE",)
    # Unsupported labels are rejected before any consumption attempt.
    with pytest.raises(ChallengeError, match="unsupported"):
        challenges.consume(challenge.challenge_id, "alice", wrong)
    valid_but_wrong = ("FIST", "FIST")
    if valid_but_wrong == challenge.gestures:
        valid_but_wrong = ("OPEN_PALM", "OPEN_PALM")
    assert challenges.consume(challenge.challenge_id, "alice", valid_but_wrong) is False
    with pytest.raises(ChallengeAlreadyUsedError):
        challenges.consume(challenge.challenge_id, "alice", challenge.gestures)


def test_profile_mismatch_does_not_consume_live_challenge():
    challenges = manager()
    challenge = challenges.issue("alice")
    with pytest.raises(ChallengeUserMismatchError):
        challenges.consume(challenge.challenge_id, "bob", challenge.gestures)
    assert challenges.consume(challenge.challenge_id, "alice", challenge.gestures) is True


def test_expiry_uses_monotonic_clock_and_purges_record():
    clock = FakeClock()
    challenges = manager(clock=clock, lifetime=5)
    challenge = challenges.issue("alice")
    clock.advance(5)
    with pytest.raises(ChallengeExpiredError):
        challenges.consume(challenge.challenge_id, "alice", challenge.gestures)
    with pytest.raises(ChallengeNotFoundError):
        challenges.consume(challenge.challenge_id, "alice", challenge.gestures)
    assert challenges.purge_expired() == 0


def test_purge_expired_removes_all_expired_entries():
    clock = FakeClock()
    challenges = manager(clock=clock, lifetime=5)
    challenges.issue("alice")
    challenges.issue("bob")
    clock.advance(5)
    assert challenges.purge_expired() == 2


@pytest.mark.parametrize("profile_id", ["", "../alice", "a" * 65, "has space"])
def test_rejects_unsafe_profile_ids(profile_id):
    with pytest.raises(ChallengeError, match="profile_id"):
        manager().issue(profile_id)


@pytest.mark.parametrize("kwargs", [
    {"lifetime_seconds": 4},
    {"lifetime_seconds": 301},
    {"lifetime_seconds": float("nan")},
    {"sequence_length": 0},
    {"sequence_length": 9},
])
def test_rejects_invalid_challenge_configuration(kwargs):
    with pytest.raises(ChallengeError):
        ChallengeManager(**kwargs)


def test_unknown_challenge_id_is_rejected():
    with pytest.raises(ChallengeNotFoundError):
        manager().consume("unknown", "alice", ("FIST",))
