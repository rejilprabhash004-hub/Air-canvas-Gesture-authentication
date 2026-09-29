"""Security event tests validate minimized fields and transactional chain integrity."""
from datetime import datetime, timezone
import json
import sqlite3

import pytest

from backend.database import DATABASE_FILENAME, database_connection, initialize_database
from backend.security_event_chain import (
    GENESIS_HASH,
    SecurityEventChainError,
    delete_profile_and_rechain,
    verify_security_event_chain,
)
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


def test_writes_minimized_event_and_valid_chain_link(tmp_path):
    path, logger = setup_logger(tmp_path)
    add_profile(path)
    event_id = logger.record(
        "auth_attempt", "denied", profile_id="user_1",
        reason_code="challenge_failed", http_status=401, component="decision",
    )
    with database_connection(path) as connection:
        row = connection.execute("SELECT * FROM security_events WHERE event_id = ?", (event_id,)).fetchone()
    assert row["occurred_at"] == "2026-02-03T04:05:06+00:00"
    assert row["event_type"] == "auth_attempt"
    assert row["outcome"] == "denied"
    assert row["profile_id"] == "user_1"
    assert json.loads(row["details_json"]) == {
        "component": "decision", "http_status": 401, "reason_code": "challenge_failed"
    }
    assert row["previous_hash"] == GENESIS_HASH
    assert len(row["event_hash"]) == 64
    assert verify_security_event_chain(str(path)).valid


def test_multiple_events_extend_chain_in_event_id_order(tmp_path):
    path, logger = setup_logger(tmp_path)
    first = logger.record("auth_attempt", "failure")
    second = logger.record("challenge_issue", "success")
    assert (first, second) == (1, 2)
    assert verify_security_event_chain(str(path)).event_count == 2
    with database_connection(path) as connection:
        rows = connection.execute("SELECT previous_hash, event_hash FROM security_events ORDER BY event_id").fetchall()
    assert rows[0]["previous_hash"] == GENESIS_HASH
    assert rows[1]["previous_hash"] == rows[0]["event_hash"]


def test_rejects_invalid_event_without_partial_insert(tmp_path):
    path, logger = setup_logger(tmp_path)
    with pytest.raises(SecurityEventError, match="reason_code"):
        logger.record("auth_attempt", "failure", reason_code="Bearer secret")
    with database_connection(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM security_events").fetchone()[0] == 0


def test_detects_tampered_event_and_broken_chain_link(tmp_path):
    path, logger = setup_logger(tmp_path)
    first = logger.record("auth_attempt", "failure")
    second = logger.record("challenge_issue", "success")
    with database_connection(path) as connection:
        connection.execute("UPDATE security_events SET outcome = 'denied' WHERE event_id = ?", (first,))
    result = verify_security_event_chain(str(path))
    assert not result.valid
    assert result.failed_event_id == first

    path2, logger2 = setup_logger(tmp_path / "other")
    logger2.record("auth_attempt", "failure")
    second2 = logger2.record("challenge_issue", "success")
    with database_connection(path2) as connection:
        connection.execute("UPDATE security_events SET previous_hash = ? WHERE event_id = ?", ("f" * 64, second2))
    result = verify_security_event_chain(str(path2))
    assert not result.valid
    assert result.failed_event_id == second2


def test_profile_deletion_rechains_nullified_event_reference_atomically(tmp_path):
    path, logger = setup_logger(tmp_path)
    add_profile(path)
    event_id = logger.record("profile_enroll", "success", profile_id="user_1")
    assert verify_security_event_chain(str(path)).valid
    assert delete_profile_and_rechain(str(path), "user_1") is True
    with database_connection(path) as connection:
        row = connection.execute("SELECT profile_id FROM security_events WHERE event_id = ?", (event_id,)).fetchone()
        assert row["profile_id"] is None
    assert verify_security_event_chain(str(path)).valid
    assert delete_profile_and_rechain(str(path), "user_1") is False


def test_profile_deletion_rolls_back_if_history_cannot_be_rechained(tmp_path):
    path, logger = setup_logger(tmp_path)
    add_profile(path)
    logger.record("profile_enroll", "success", profile_id="user_1")
    with database_connection(path) as connection:
        connection.execute("UPDATE security_events SET details_json = '{\"secret\":true}'")
    with pytest.raises(SecurityEventChainError):
        delete_profile_and_rechain(str(path), "user_1")
    with database_connection(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM profiles WHERE profile_id='user_1'").fetchone()[0] == 1


def test_database_failure_is_wrapped_without_leaking_sql_details(tmp_path):
    path, logger = setup_logger(tmp_path)
    path.unlink()
    with pytest.raises(SecurityEventError, match="could not be stored") as error:
        logger.record("auth_attempt", "failure", profile_id="user_1")
    assert "sqlite" not in str(error.value).lower()
