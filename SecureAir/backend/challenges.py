"""User-bound, expiring, single-use gesture challenges held in process memory.

This is a small state primitive for later local-service integration. It does
not capture camera input, authenticate a person, persist state, or survive a
process restart. A caller must independently establish that observed gestures
came from its trusted local detector.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import secrets
import threading
import time
from typing import Callable, Iterable

from gesture.gesture_recognition import GESTURES

_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_MIN_LIFETIME_SECONDS = 5
_MAX_LIFETIME_SECONDS = 300
_MIN_SEQUENCE_LENGTH = 1
_MAX_SEQUENCE_LENGTH = 8


class ChallengeError(ValueError):
    """Base class for challenge validation and lifecycle errors."""


class ChallengeNotFoundError(ChallengeError):
    """Raised when a challenge identifier is unknown."""


class ChallengeExpiredError(ChallengeError):
    """Raised when a challenge has passed its expiry time."""


class ChallengeAlreadyUsedError(ChallengeError):
    """Raised when a challenge has already been consumed."""


class ChallengeUserMismatchError(ChallengeError):
    """Raised when a different profile attempts to consume a challenge."""


@dataclass(frozen=True)
class Challenge:
    """Public challenge details required by a later local presentation layer."""

    challenge_id: str
    profile_id: str
    gestures: tuple[str, ...]
    created_at: str
    expires_at: str


@dataclass
class _ChallengeRecord:
    challenge: Challenge
    monotonic_deadline: float
    used: bool = False


class ChallengeManager:
    """Thread-safe in-memory issue/consume manager for local single-process use."""

    def __init__(
        self,
        *,
        lifetime_seconds: float = 60.0,
        sequence_length: int = 3,
        clock: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if (isinstance(lifetime_seconds, bool)
                or not isinstance(lifetime_seconds, (int, float))
                or not _MIN_LIFETIME_SECONDS <= lifetime_seconds <= _MAX_LIFETIME_SECONDS):
            raise ChallengeError("lifetime_seconds must be between 5 and 300 seconds.")
        if (isinstance(sequence_length, bool) or not isinstance(sequence_length, int)
                or not _MIN_SEQUENCE_LENGTH <= sequence_length <= _MAX_SEQUENCE_LENGTH):
            raise ChallengeError("sequence_length must be between 1 and 8 gestures.")
        self._lifetime_seconds = float(lifetime_seconds)
        self._sequence_length = sequence_length
        self._clock = clock
        self._utc_now = utc_now
        self._records: dict[str, _ChallengeRecord] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _validate_profile_id(profile_id: str) -> None:
        if not isinstance(profile_id, str) or not _PROFILE_ID.fullmatch(profile_id):
            raise ChallengeError("profile_id must be 1–64 safe letters, numbers, underscores, or hyphens.")

    @staticmethod
    def _validate_sequence(gestures: Iterable[str]) -> tuple[str, ...]:
        try:
            sequence = tuple(gestures)
        except TypeError as exc:
            raise ChallengeError("gestures must be an iterable of supported gesture labels.") from exc
        if not _MIN_SEQUENCE_LENGTH <= len(sequence) <= _MAX_SEQUENCE_LENGTH:
            raise ChallengeError("gesture sequence must contain between 1 and 8 gestures.")
        if any(not isinstance(item, str) or item not in GESTURES for item in sequence):
            raise ChallengeError("gesture sequence contains an unsupported gesture label.")
        return sequence

    def issue(self, profile_id: str) -> Challenge:
        """Create an unpredictable sequence challenge bound to one profile."""
        self._validate_profile_id(profile_id)
        sequence = tuple(secrets.choice(GESTURES) for _ in range(self._sequence_length))
        created = self._utc_now()
        if created.tzinfo is None or created.utcoffset() is None:
            raise ChallengeError("utc_now must return a timezone-aware datetime.")
        created = created.astimezone(timezone.utc)
        expires = created + timedelta(seconds=self._lifetime_seconds)
        challenge = Challenge(
            challenge_id=secrets.token_urlsafe(32),
            profile_id=profile_id,
            gestures=sequence,
            created_at=created.isoformat(),
            expires_at=expires.isoformat(),
        )
        record = _ChallengeRecord(
            challenge=challenge,
            monotonic_deadline=self._clock() + self._lifetime_seconds,
        )
        with self._lock:
            while challenge.challenge_id in self._records:
                challenge = Challenge(
                    challenge_id=secrets.token_urlsafe(32),
                    profile_id=challenge.profile_id,
                    gestures=challenge.gestures,
                    created_at=challenge.created_at,
                    expires_at=challenge.expires_at,
                )
                record.challenge = challenge
            self._records[challenge.challenge_id] = record
        return challenge

    def consume(self, challenge_id: str, profile_id: str,
                observed_gestures: Iterable[str]) -> bool:
        """Atomically consume the challenge, returning whether sequence matched.

        The challenge is consumed even on a wrong sequence, preventing retries
        against a known challenge. Expired and user-mismatched attempts do not
        consume a live challenge. Camera/detector provenance is out of scope.
        """
        self._validate_profile_id(profile_id)
        if not isinstance(challenge_id, str) or not challenge_id:
            raise ChallengeNotFoundError("challenge_id is required.")
        observed = self._validate_sequence(observed_gestures)
        with self._lock:
            record = self._records.get(challenge_id)
            if record is None:
                raise ChallengeNotFoundError("challenge was not found.")
            if record.challenge.profile_id != profile_id:
                raise ChallengeUserMismatchError("challenge belongs to a different profile.")
            if self._clock() >= record.monotonic_deadline:
                del self._records[challenge_id]
                raise ChallengeExpiredError("challenge has expired.")
            if record.used:
                raise ChallengeAlreadyUsedError("challenge has already been consumed.")
            record.used = True
            return secrets.compare_digest("\0".join(observed), "\0".join(record.challenge.gestures))

    def purge_expired(self) -> int:
        """Remove expired records and return the number removed."""
        now = self._clock()
        with self._lock:
            expired = [
                challenge_id for challenge_id, record in self._records.items()
                if now >= record.monotonic_deadline
            ]
            for challenge_id in expired:
                del self._records[challenge_id]
        return len(expired)
