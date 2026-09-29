"""Isolated SecureAir SQLite schema and safe initialization helpers.

The SecureAir database has a fixed filename and application ID. Initialization
refuses a pre-existing unrelated SQLite database rather than altering the
legacy project's database. The schema stores enrollment feature JSON locally;
callers must obtain consent and protect the containing directory and backups.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Iterator

from backend.config import Settings

DATABASE_FILENAME = "secureair.sqlite3"
APPLICATION_ID = 0x53414952  # ASCII-ish marker: "SAIR"
SCHEMA_VERSION = 1

_SCHEMA_STATEMENTS = (
    """CREATE TABLE profiles (
        profile_id TEXT PRIMARY KEY NOT NULL,
        created_at TEXT NOT NULL,
        consent_at TEXT NOT NULL,
        feature_schema TEXT NOT NULL
    )""",
    """CREATE TABLE enrollment_samples (
        sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        sample_number INTEGER NOT NULL CHECK (sample_number BETWEEN 1 AND 20),
        features_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (profile_id, session_id, sample_number),
        FOREIGN KEY (profile_id) REFERENCES profiles(profile_id) ON DELETE CASCADE
    )""",
    """CREATE INDEX idx_enrollment_samples_profile_session
        ON enrollment_samples(profile_id, session_id)""",
    """CREATE TABLE security_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        occurred_at TEXT NOT NULL,
        event_type TEXT NOT NULL,
        outcome TEXT NOT NULL,
        profile_id TEXT,
        details_json TEXT NOT NULL,
        FOREIGN KEY (profile_id) REFERENCES profiles(profile_id) ON DELETE SET NULL
    )""",
    """CREATE INDEX idx_security_events_occurred_at
        ON security_events(occurred_at)""",
)

_EXPECTED_TABLES = {"profiles", "enrollment_samples", "security_events"}


class DatabaseError(ValueError):
    """Raised when a database path or existing database violates isolation."""


def database_path(settings: Settings) -> Path:
    """Return the dedicated SecureAir DB path inside configured local data."""
    return _validate_path(settings.data_dir / DATABASE_FILENAME)


def _validate_path(db_path: str | Path) -> Path:
    path = Path(db_path).expanduser()
    if path.name != DATABASE_FILENAME:
        raise DatabaseError(f"SecureAir database filename must be {DATABASE_FILENAME!r}.")
    if path.is_symlink():
        raise DatabaseError("SecureAir database path must not be a symbolic link.")
    return path


def connect_database(db_path: str | Path) -> sqlite3.Connection:
    """Open the named SecureAir database with foreign-key checks enabled.

    This helper does not initialize tables; call ``initialize_database`` first.
    It never deletes, truncates, or migrates a pre-existing database.
    """
    path = _validate_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise DatabaseError("SecureAir database path must not be a symbolic link.")
    connection = sqlite3.connect(path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _user_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def initialize_database(db_path: str | Path) -> Path:
    """Create schema v1, or verify a complete already-initialized SecureAir DB.

    Existing unmarked databases, including the legacy application database,
    are refused without changing their journal mode or contents. Schema DDL and
    markers are committed together under an exclusive transaction.
    """
    path = _validate_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise DatabaseError("SecureAir database path must not be a symbolic link.")

    connection = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    try:
        application_id = connection.execute("PRAGMA application_id").fetchone()[0]
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
        existing_tables = _user_tables(connection)

        if application_id not in (0, APPLICATION_ID):
            raise DatabaseError("Existing database belongs to a different application.")
        if user_version > SCHEMA_VERSION:
            raise DatabaseError("Database schema is newer than this SecureAir version.")
        if application_id == 0 and (user_version != 0 or existing_tables):
            raise DatabaseError("Unmarked existing database will not be modified.")
        if application_id == APPLICATION_ID:
            if user_version != SCHEMA_VERSION:
                raise DatabaseError("SecureAir database schema marker is invalid or unsupported.")
            if existing_tables != _EXPECTED_TABLES:
                raise DatabaseError("SecureAir database schema is incomplete or unexpected.")
            return path

        # Serialize initialization and re-check after acquiring the lock so a
        # competing initializer or replaced file cannot be overwritten.
        connection.execute("BEGIN EXCLUSIVE")
        application_id = connection.execute("PRAGMA application_id").fetchone()[0]
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
        existing_tables = _user_tables(connection)
        if application_id != 0 or user_version != 0 or existing_tables:
            raise DatabaseError("Database changed during initialization; refusing modification.")

        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()

        if os.name == "posix":
            os.chmod(path, 0o600)
        return path
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def database_connection(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Yield a SecureAir connection and commit on success or rollback on error."""
    connection = connect_database(db_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()
