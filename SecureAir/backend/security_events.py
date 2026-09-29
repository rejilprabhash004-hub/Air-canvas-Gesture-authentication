"""Privacy-conscious allowlisted event writer for the SecureAir SQLite DB.

Never accept free-form event details. This logger intentionally excludes
credentials, challenge tokens, raw video/landmarks, and arbitrary request data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import sqlite3
from typing import Callable

from backend.database import database_connection

_EVENT_TYPES = frozenset({
    "auth_attempt",
    "challenge_issue",
    "challenge_consume",
    "profile_enroll",
    "profile_delete",
    "service_auth_failure",
})
_OUTCOMES = frozenset({"success", "failure", "denied", "error"})
_COMPONENTS = frozenset({"api", "camera", "challenge", "enrollment", "decision", "storage"})
_REASON_CODES = frozenset({
    "all_required_signals_passed",
    "behavioral_match_below_threshold",
    "challenge_failed",
    "challenge_expired",
    "challenge_already_used",
    "challenge_profile_mismatch",
    "gesture_sequence_failed",
    "gesture_sequence_timeout",
    "invalid_behavioral_match_score",
    "invalid_challenge_result",
    "invalid_sequence_status",
    "invalid_threshold",
    "invalid_user",
    "lockout_active",
    "rate_limited",
    "storage_error",
    "unknown",
})
_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class SecurityEventError(ValueError):
    """Raised when an event is unsafe, invalid, or cannot be stored."""


class SecurityEventLogger:
    """Write minimized, allowlisted security events to an initialized DB."""

    def __init__(
        self,
        db_path: str,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._db_path = db_path
        self._clock = clock

    def record(
        self,
        event_type: str,
        outcome: str,
        *,
        profile_id: str | None = None,
        reason_code: str | None = None,
        http_status: int | None = None,
        component: str | None = None,
    ) -> int:
        """Persist one event, returning its row ID; never accept free text.

        ``profile_id`` should be a local pseudonymous identifier, not a name or
        email. Callers must not place secrets, tokens, frame data, landmarks,
        gesture sequences, or user-submitted strings in event fields.
        """
        if event_type not in _EVENT_TYPES:
            raise SecurityEventError("event_type is not allowlisted.")
        if outcome not in _OUTCOMES:
            raise SecurityEventError("outcome is not allowlisted.")
        if profile_id is not None and (
            not isinstance(profile_id, str) or not _PROFILE_ID.fullmatch(profile_id)
        ):
            raise SecurityEventError("profile_id must be a safe pseudonymous identifier.")
        if reason_code is not None and reason_code not in _REASON_CODES:
            raise SecurityEventError("reason_code is not allowlisted.")
        if component is not None and component not in _COMPONENTS:
            raise SecurityEventError("component is not allowlisted.")
        if http_status is not None and (
            isinstance(http_status, bool) or not isinstance(http_status, int)
            or not 100 <= http_status <= 599
        ):
            raise SecurityEventError("http_status must be an integer from 100 to 599.")

        occurred_at = self._clock()
        if not isinstance(occurred_at, datetime) or occurred_at.tzinfo is None:
            raise SecurityEventError("clock must return a timezone-aware datetime.")
        occurred_at = occurred_at.astimezone(timezone.utc).isoformat()
        details = {
            key: value
            for key, value in (
                ("reason_code", reason_code),
                ("http_status", http_status),
                ("component", component),
            )
            if value is not None
        }
        details_json = json.dumps(details, sort_keys=True, separators=(",", ":"))

        try:
            with database_connection(self._db_path) as connection:
                cursor = connection.execute(
                    """INSERT INTO security_events
                       (occurred_at, event_type, outcome, profile_id, details_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    (occurred_at, event_type, outcome, profile_id, details_json),
                )
                return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise SecurityEventError("security event could not be stored.") from exc
