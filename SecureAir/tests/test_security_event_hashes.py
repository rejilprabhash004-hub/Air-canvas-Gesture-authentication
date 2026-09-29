"""Deterministic canonicalization and hash tests for security event rows."""
import hashlib
import json

import pytest

from backend.security_event_hashes import (
    SecurityEventHashError,
    canonical_event_bytes,
    hash_security_event,
)


@pytest.fixture
def event():
    return {
        "event_id": 7,
        "occurred_at": "2026-02-03T04:05:06+00:00",
        "event_type": "auth_attempt",
        "outcome": "denied",
        "profile_id": "user_1",
        "details_json": '{"http_status":401, "reason_code":"challenge_failed", "component":"decision"}',
    }


def test_hash_is_sha256_of_deterministic_canonical_json(event):
    canonical = canonical_event_bytes(event)
    assert canonical == canonical_event_bytes(event)
    assert hash_security_event(event) == hashlib.sha256(canonical).hexdigest()
    assert canonical.decode("utf-8") == (
        '{"details":{"component":"decision","http_status":401,'
        '"reason_code":"challenge_failed"},"event_id":7,"event_type":"auth_attempt",'
        '"occurred_at":"2026-02-03T04:05:06+00:00","outcome":"denied","profile_id":"user_1"}'
    )


def test_details_object_order_and_whitespace_do_not_change_hash(event):
    equivalent = dict(event)
    equivalent["details_json"] = json.dumps(
        {"component": "decision", "reason_code": "challenge_failed", "http_status": 401},
        indent=2,
    )
    assert hash_security_event(equivalent) == hash_security_event(event)


@pytest.mark.parametrize(("field", "value"), [
    ("event_id", 8),
    ("occurred_at", "2026-02-03T04:05:07+00:00"),
    ("event_type", "profile_enroll"),
    ("outcome", "failure"),
    ("profile_id", "user_2"),
    ("details_json", '{"http_status":403}'),
])
def test_change_to_any_covered_record_field_changes_hash(event, field, value):
    modified = dict(event)
    modified[field] = value
    assert hash_security_event(modified) != hash_security_event(event)


def test_rejects_missing_extra_and_invalid_event_data(event):
    with pytest.raises(SecurityEventHashError):
        canonical_event_bytes({key: value for key, value in event.items() if key != "profile_id"})
    with pytest.raises(SecurityEventHashError):
        canonical_event_bytes({**event, "unexpected": "value"})
    with pytest.raises(SecurityEventHashError):
        canonical_event_bytes({**event, "details_json": '{"token":"secret"}'})
    with pytest.raises(SecurityEventHashError):
        canonical_event_bytes({**event, "details_json": '{"http_status":true}'})
    with pytest.raises(SecurityEventHashError):
        canonical_event_bytes({**event, "details_json": '{"value":NaN}'})


def test_hashing_does_not_persist_or_mutate_input(event):
    original = dict(event)
    hash_security_event(event)
    assert event == original
