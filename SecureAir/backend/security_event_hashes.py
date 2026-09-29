"""Canonical SHA-256 hashes for minimized SecureAir security-event records.

This module computes hashes only; it does not persist them or modify the database.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from typing import Any

_EVENT_FIELDS = frozenset({
    "event_id", "occurred_at", "event_type", "outcome", "profile_id", "details_json",
})
_EVENT_TYPES = frozenset({
    "auth_attempt", "challenge_issue", "challenge_consume", "profile_enroll",
    "profile_delete", "service_auth_failure",
})
_OUTCOMES = frozenset({"success", "failure", "denied", "error"})
_DETAIL_KEYS = frozenset({"reason_code", "http_status", "component"})


class SecurityEventHashError(ValueError):
    """Raised when a record is incomplete or cannot be canonically encoded."""


def _reject_non_finite(value: str) -> None:
    raise SecurityEventHashError(f"Non-finite JSON number {value!r} is not supported.")


def canonical_event_bytes(event: Mapping[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON bytes for one database event row.

    The record must contain exactly the event-table columns. ``details_json``
    is parsed as a JSON object and re-serialized with sorted keys, so whitespace
    and object-key order do not affect the digest. Invalid or unexpected fields
    are rejected rather than silently omitted.
    """
    if not isinstance(event, Mapping) or set(event) != _EVENT_FIELDS:
        raise SecurityEventHashError("event must contain exactly the security event columns.")

    event_id = event["event_id"]
    if isinstance(event_id, bool) or not isinstance(event_id, int) or event_id < 1:
        raise SecurityEventHashError("event_id must be a positive integer.")
    for field in ("occurred_at", "event_type", "outcome"):
        if not isinstance(event[field], str) or not event[field]:
            raise SecurityEventHashError(f"{field} must be a non-empty string.")
    if event["event_type"] not in _EVENT_TYPES:
        raise SecurityEventHashError("event_type is not allowlisted.")
    if event["outcome"] not in _OUTCOMES:
        raise SecurityEventHashError("outcome is not allowlisted.")
    profile_id = event["profile_id"]
    if profile_id is not None and not isinstance(profile_id, str):
        raise SecurityEventHashError("profile_id must be a string or null.")

    details_json = event["details_json"]
    if not isinstance(details_json, str):
        raise SecurityEventHashError("details_json must be a JSON string.")
    try:
        details = json.loads(details_json, parse_constant=_reject_non_finite)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SecurityEventHashError("details_json must contain a valid JSON object.") from exc
    if not isinstance(details, dict) or any(key not in _DETAIL_KEYS for key in details):
        raise SecurityEventHashError("details_json must be an object with allowlisted keys.")
    if "reason_code" in details and not isinstance(details["reason_code"], str):
        raise SecurityEventHashError("details_json reason_code must be a string.")
    if "component" in details and not isinstance(details["component"], str):
        raise SecurityEventHashError("details_json component must be a string.")
    if "http_status" in details and (
        isinstance(details["http_status"], bool)
        or not isinstance(details["http_status"], int)
        or not 100 <= details["http_status"] <= 599
    ):
        raise SecurityEventHashError("details_json http_status must be an HTTP status integer.")

    payload = {
        "details": details,
        "event_id": event_id,
        "event_type": event["event_type"],
        "occurred_at": event["occurred_at"],
        "outcome": event["outcome"],
        "profile_id": profile_id,
    }
    try:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SecurityEventHashError("event could not be canonically encoded.") from exc
    return canonical.encode("utf-8")


def hash_security_event(event: Mapping[str, Any]) -> str:
    """Return a lowercase hexadecimal SHA-256 digest of a canonical event row."""
    return hashlib.sha256(canonical_event_bytes(event)).hexdigest()
