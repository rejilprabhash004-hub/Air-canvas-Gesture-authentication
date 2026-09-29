"""Security event tests validate minimization, allowlists, and DB constraints."""
from datetime import datetime, timezone
import json
import sqlite3

import pytest

from backend.database import DATABASE_FILENAME, database_connection, initialize_database
from backend.security_events import SecurityEventError, SecurityEventLogger


class FixedClock:
    def __call__(self):
        return datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc)


def setup_logger(tmp_path):
    path = initialize_database(tmp_path / DATABASE_FILENAME)
    logger = SecurityEventLogger(path, clock=FixedClock())
    return path, logger


def add_profile(path, profile_id="user_1"):
    with database_connection(path) as connection:
        connection.execute(
            "INSERT INTO profiles VALUES (?, ?, ?, ?)",
            (profile_id, "created", "consent", "features-v1"),
        )


def test_writes_allowlisted_minimized_event_and_returns_row_id(tmp_path):
    path, logger = setup_logger(tmp_path)
    add_profile(path)
    event_id = logger.record(
        "auth_attempt", "denied", profile_id="user_1",
        reason_code="challenge_failed", http_status=401, component="decision",
    )
    with database_connection(path) as connection:
        row = connection.execute(
            "SELECT * FROM security_events WHERE event_id = ?", (event_id,)
        ).fetchone()
    assert row["occurred_at"] == "2026-02-03T04:05:06+00:00"
    assert row["event_type"] == "auth_attempt"
    assert row["outcome"] == "denied"
    assert row["profile_id"] == "user_1"
    assert json.loads(row["details_json"]) == {
        "component": "decision", "http_status": 401, "reason_code": "challenge_failed"
    }


def test_event_details_cannot_accept_or_persist_free_text_secrets(tmp_path):
    path, logger = setup_logger(tmp_path)
    add_profile(path)
    with pytest.raises(SecurityEventError, match="reason_code"):
        logger.record(
            "auth_attempt", "failure", profile_id="user_1",
            reason_code="Bearer super-secret-token",
        )
    with database_connection(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM security_events").fetchone()[0] == 0


@pytest.mark.parametrize("event_type", ["arbitrary", "password", "token", ["auth_attempt"]])
def test_rejects_unapproved_event_types(event_type, tmp_path):
    _, logger = setup_logger(tmp_path)
    with pytest.raises(SecurityEventError, match="event_type"):
        logger.record(event_type, "failure")


@pytest.mark.parametrize("outcome", ["ok", "denied because of user text", [], None])
def test_rejects_unapproved_outcomes(outcome, tmp_path):
    _, logger = setup_logger(tmp_path)
    with pytest.raises(SecurityEventError, match="outcome"):
        logger.record("auth_attempt", outcome)


@pytest.mark.parametrize("kwargs", [
    {"profile_id": "../alice"},
    {"profile_id": "alice@example.test"},
    {"reason_code": "raw user text"},
    {"component": "webpage-content"},
    {"http_status": 99},
    {"http_status": True},
])
def test_rejects_invalid_or_sensitive_event_fields(kwargs, tmp_path):
    _, logger = setup_logger(tmp_path)
    with pytest.raises(SecurityEventError):
        logger.record("auth_attempt", "failure", **kwargs)


def test_event_references_profile_with_set_null_on_profile_delete(tmp_path):
    path, logger = setup_logger(tmp_path)
    add_profile(path)
    event_id = logger.record("profile_enroll", "success", profile_id="user_1")
    with database_connection(path) as connection:
        connection.execute("DELETE FROM profiles WHERE profile_id = ?", ("user_1",))
        event = connection.execute(
            "SELECT profile_id FROM security_events WHERE event_id = ?", (event_id,)
        ).fetchone()
    assert event["profile_id"] is None


def test_database_failure_is_wrapped_without_leaking_sql_details(tmp_path):
    path, logger = setup_logger(tmp_path)
    path.unlink()
    with pytest.raises(SecurityEventError, match="could not be stored") as error:
        logger.record("auth_attempt", "failure", profile_id="user_1")
    assert "sqlite" not in str(error.value).lower()
