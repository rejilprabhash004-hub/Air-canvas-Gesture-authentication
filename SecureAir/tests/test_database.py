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


def test_initialize_creates_isolated_schema_and_is_idempotent(tmp_path):
    path = db_path(tmp_path)
    assert initialize_database(path) == path
    assert initialize_database(path) == path

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"profiles", "enrollment_samples", "security_events"} <= tables
        # SQLite connections default foreign keys off; app connections enable them.
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
                "INSERT INTO profiles VALUES (?, ?, ?, ?)",
                ("alice", "now", "now", "v1"),
            )
            raise RuntimeError("abort transaction")
    with database_connection(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0
