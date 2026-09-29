"""SQLite isolation and schema contract tests; legacy DB is never opened."""
import sqlite3

import pytest

from backend.config import Settings
from backend.database import (
    APPLICATION_ID,
    DATABASE_FILENAME,
    SCHEMA_VERSION,
    DatabaseError,
    database_connection,
    database_path,
    initialize_database,
)
from backend.security_event_chain import verify_security_event_chain
from backend.security_events import SecurityEventLogger


def db_path(tmp_path):
    return tmp_path / DATABASE_FILENAME


def test_database_path_uses_configured_data_directory(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "private-data",
        host="127.0.0.1",
        port=8000,
        secret_key="x" * 40,
        lockout_max_attempts=3,
        lockout_seconds=300,
        challenge_seconds=60,
    )
    assert database_path(settings) == tmp_path / "private-data" / DATABASE_FILENAME


def test_initialize_creates_v3_chain_schema_and_is_idempotent(tmp_path):
    path = db_path(tmp_path)
    assert initialize_database(path) == path
    assert initialize_database(path) == path

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 3
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"profiles", "enrollment_samples", "security_events", "protected_sites"} <= tables
        columns = {row[1] for row in connection.execute("PRAGMA table_info(security_events)")}
        assert {"previous_hash", "event_hash"} <= columns
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 0


def test_database_connection_enforces_foreign_keys_and_profile_delete_cascades(tmp_path):
    path = initialize_database(db_path(tmp_path))
    with database_connection(path) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        connection.execute(
            "INSERT INTO profiles VALUES (?, ?, ?, ?)",
            ("alice", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "v1"),
        )
        connection.execute(
            "INSERT INTO enrollment_samples "
            "(profile_id, session_id, sample_number, features_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("alice", "session-a", 1, "[0.1,0.2]", "2026-01-01T00:00:00+00:00"),
        )
    with database_connection(path) as connection:
        connection.execute("DELETE FROM profiles WHERE profile_id = ?", ("alice",))
        assert connection.execute("SELECT COUNT(*) FROM enrollment_samples").fetchone()[0] == 0


def test_rejects_legacy_or_unmarked_existing_database_without_modifying_it(tmp_path):
    path = db_path(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE legacy_users (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO legacy_users VALUES (7)")
    before = path.read_bytes()
    with pytest.raises(DatabaseError, match="Unmarked existing database"):
        initialize_database(path)
    assert path.read_bytes() == before
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT id FROM legacy_users").fetchone()[0] == 7


def test_rejects_database_marked_for_another_application_without_modifying_it(tmp_path):
    path = db_path(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA application_id = 12345")
        connection.execute("CREATE TABLE foreign_app_data (value TEXT)")
    before = path.read_bytes()
    with pytest.raises(DatabaseError, match="different application"):
        initialize_database(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("filename", ["legacy.sqlite3", "cyberdash.db", "secureair.db"])
def test_refuses_non_secureair_filename(tmp_path, filename):
    with pytest.raises(DatabaseError, match="filename"):
        initialize_database(tmp_path / filename)


def test_refuses_newer_schema_version(tmp_path):
    path = db_path(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(DatabaseError, match="newer"):
        initialize_database(path)


def test_rejects_incomplete_secureair_schema(tmp_path):
    path = db_path(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.execute("CREATE TABLE profiles (profile_id TEXT PRIMARY KEY)")
    with pytest.raises(DatabaseError, match="incomplete"):
        initialize_database(path)


def test_connection_context_rolls_back_on_exception(tmp_path):
    path = initialize_database(db_path(tmp_path))
    with pytest.raises(RuntimeError):
        with database_connection(path) as connection:
            connection.execute(
                "INSERT INTO profiles VALUES (?, ?, ?, ?)", ("alice", "now", "now", "v1")
            )
            raise RuntimeError("abort transaction")
    with database_connection(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0


def _create_v1_database(path):
    """Build the original SecureAir v1 database fixture."""
    statements = (
        "CREATE TABLE profiles (profile_id TEXT PRIMARY KEY NOT NULL, created_at TEXT NOT NULL, consent_at TEXT NOT NULL, feature_schema TEXT NOT NULL)",
        "CREATE TABLE enrollment_samples (sample_id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id TEXT NOT NULL, session_id TEXT NOT NULL, sample_number INTEGER NOT NULL CHECK (sample_number BETWEEN 1 AND 20), features_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE (profile_id, session_id, sample_number), FOREIGN KEY (profile_id) REFERENCES profiles(profile_id) ON DELETE CASCADE)",
        "CREATE INDEX idx_enrollment_samples_profile_session ON enrollment_samples(profile_id, session_id)",
        "CREATE TABLE security_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, event_type TEXT NOT NULL, outcome TEXT NOT NULL, profile_id TEXT, details_json TEXT NOT NULL, FOREIGN KEY (profile_id) REFERENCES profiles(profile_id) ON DELETE SET NULL)",
        "CREATE INDEX idx_security_events_occurred_at ON security_events(occurred_at)",
    )
    with sqlite3.connect(path) as connection:
        for statement in statements:
            connection.execute(statement)
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute("PRAGMA user_version = 1")


def _downgrade_empty_v3_to_v2(path):
    """Create the v2 event-table shape for an isolated migration test."""
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE protected_sites")
        connection.execute("ALTER TABLE security_events RENAME TO events_v3")
        connection.execute(
            "CREATE TABLE security_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "occurred_at TEXT NOT NULL, event_type TEXT NOT NULL, outcome TEXT NOT NULL, "
            "profile_id TEXT, details_json TEXT NOT NULL, "
            "FOREIGN KEY (profile_id) REFERENCES profiles(profile_id) ON DELETE SET NULL)"
        )
        connection.execute("DROP TABLE events_v3")
        connection.execute("CREATE INDEX idx_security_events_occurred_at ON security_events(occurred_at)")
        connection.execute(
            "CREATE TABLE protected_sites (domain TEXT PRIMARY KEY NOT NULL, "
            "enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)), "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        connection.execute("PRAGMA user_version = 2")


def test_migrates_verified_v1_database_to_v3_and_preserves_rows(tmp_path):
    path = db_path(tmp_path)
    _create_v1_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO profiles VALUES (?, ?, ?, ?)", ("alice", "created", "consent", "v1"))
    assert initialize_database(path) == path
    with database_connection(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert connection.execute("SELECT profile_id FROM profiles").fetchone()[0] == "alice"
        assert connection.execute("SELECT COUNT(*) FROM protected_sites").fetchone()[0] == 0
    assert initialize_database(path) == path


def test_v2_migration_backfills_valid_chain_and_preserves_event_rows(tmp_path):
    path = initialize_database(db_path(tmp_path))
    _downgrade_empty_v3_to_v2(path)
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO profiles VALUES (?, ?, ?, ?)", ("user_1", "created", "consent", "v1"))
        connection.execute(
            "INSERT INTO security_events (event_id,occurred_at,event_type,outcome,profile_id,details_json) "
            "VALUES (1,?,?,?,?,?)",
            ("2026-02-03T04:05:06+00:00", "auth_attempt", "denied", "user_1", '{"reason_code":"challenge_failed"}'),
        )
    initialize_database(path)
    assert verify_security_event_chain(str(path)).valid
    with database_connection(path) as connection:
        row = connection.execute("SELECT event_id, previous_hash, event_hash FROM security_events").fetchone()
        assert row["event_id"] == 1
        assert row["previous_hash"] == "0" * 64
        assert len(row["event_hash"]) == 64


def test_v2_migration_rolls_back_when_existing_event_is_invalid(tmp_path):
    path = initialize_database(db_path(tmp_path))
    _downgrade_empty_v3_to_v2(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO security_events (event_id,occurred_at,event_type,outcome,profile_id,details_json) "
            "VALUES (1,?,?,?,?,?)",
            ("now", "auth_attempt", "failure", None, '{"token":"must-not-migrate"}'),
        )
    before = path.read_bytes()
    with pytest.raises(DatabaseError, match="cannot be safely migrated"):
        initialize_database(path)
    assert path.read_bytes() == before


def test_failed_or_unverified_v1_migration_rolls_back_without_changes(tmp_path):
    path = db_path(tmp_path)
    _create_v1_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE security_events")
        connection.execute("CREATE TABLE other_data (id INTEGER)")
        connection.execute("PRAGMA user_version = 1")
    before = path.read_bytes()
    with pytest.raises(DatabaseError, match="incomplete or unexpected"):
        initialize_database(path)
    assert path.read_bytes() == before
