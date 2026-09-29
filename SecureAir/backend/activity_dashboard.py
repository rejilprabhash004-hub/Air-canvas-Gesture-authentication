"""Read-only, bearer-protected queries for minimized SecureAir activity events.

The reader opens only the dedicated SecureAir database in SQLite read-only mode.
It returns allowlisted event columns and deliberately excludes details_json.
This module does not monitor browsing or collect new activity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
from pathlib import Path
import sqlite3
from typing import Any

from backend.database import APPLICATION_ID, DATABASE_FILENAME, SCHEMA_VERSION

_EVENT_TYPES = frozenset({
    "auth_attempt", "challenge_issue", "challenge_consume", "profile_enroll",
    "profile_delete", "service_auth_failure",
})
_OUTCOMES = frozenset({"success", "failure", "denied", "error"})
_MAX_LIMIT = 100
_MAX_OFFSET = 1_000_000


class ActivityDashboardError(ValueError):
    """Base error for invalid credentials, filters, or database state."""


class ActivityDashboardAuthorizationError(ActivityDashboardError):
    """Raised when the caller does not present the configured local token."""


@dataclass(frozen=True)
class ActivityPage:
    """One bounded page of minimized activity events."""

    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class ActivityDashboard:
    """Read-only query service for an initialized SecureAir schema-v2 database.

    The local access token must be supplied for each query and is compared in
    constant time. The database is opened with SQLite ``mode=ro`` and
    ``query_only``; malformed or foreign databases are rejected, never migrated.
    """

    def __init__(self, db_path: str | Path, access_token: str) -> None:
        self._path = Path(db_path).expanduser()
        if self._path.name != DATABASE_FILENAME or self._path.is_symlink():
            raise ActivityDashboardError("A regular SecureAir database path is required.")
        if not isinstance(access_token, str) or len(access_token) < 32:
            raise ActivityDashboardError("access_token must contain at least 32 characters.")
        self._access_token = access_token

    def _connect_read_only(self) -> sqlite3.Connection:
        if self._path.is_symlink() or not self._path.is_file():
            raise ActivityDashboardError("SecureAir database is unavailable.")
        uri = f"{self._path.resolve().as_uri()}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=2.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            app_id = connection.execute("PRAGMA application_id").fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            columns = tuple(row[1] for row in connection.execute('PRAGMA table_info("security_events")'))
            expected = ("event_id", "occurred_at", "event_type", "outcome", "profile_id", "details_json")
            if app_id != APPLICATION_ID or version != SCHEMA_VERSION or columns != expected:
                connection.close()
                raise ActivityDashboardError("Database is not a verified SecureAir schema-v2 database.")
            return connection
        except sqlite3.Error as exc:
            raise ActivityDashboardError("SecureAir activity data could not be read.") from exc

    @staticmethod
    def _normalize_timestamp(value: str | None, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ActivityDashboardError(f"{field} must be an ISO-8601 timestamp.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ActivityDashboardError(f"{field} must be an ISO-8601 timestamp.") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ActivityDashboardError(f"{field} must include a timezone.")
        return parsed.astimezone(timezone.utc).isoformat()

    def list_events(
        self,
        access_token: str,
        *,
        event_type: str | None = None,
        outcome: str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> ActivityPage:
        """Return paginated minimized events; filters are exact and parameterized."""
        if not isinstance(access_token, str) or not hmac.compare_digest(access_token, self._access_token):
            raise ActivityDashboardAuthorizationError("Dashboard access denied.")
        if event_type is not None and event_type not in _EVENT_TYPES:
            raise ActivityDashboardError("event_type is not allowlisted.")
        if outcome is not None and outcome not in _OUTCOMES:
            raise ActivityDashboardError("outcome is not allowlisted.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_LIMIT:
            raise ActivityDashboardError("limit must be an integer from 1 to 100.")
        if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= _MAX_OFFSET:
            raise ActivityDashboardError("offset is outside the supported range.")

        after_utc = self._normalize_timestamp(after, "after")
        before_utc = self._normalize_timestamp(before, "before")
        if after_utc and before_utc and after_utc > before_utc:
            raise ActivityDashboardError("after must not be later than before.")

        clauses: list[str] = []
        parameters: list[Any] = []
        for column, value in (("event_type", event_type), ("outcome", outcome)):
            if value is not None:
                clauses.append(f"{column} = ?")
                parameters.append(value)
        if after_utc:
            clauses.append("occurred_at >= ?")
            parameters.append(after_utc)
        if before_utc:
            clauses.append("occurred_at <= ?")
            parameters.append(before_utc)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""

        connection = self._connect_read_only()
        try:
            connection.execute("BEGIN")
            total = connection.execute(
                f"SELECT COUNT(*) FROM security_events{where}", parameters
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT event_id, occurred_at, event_type, outcome, profile_id "
                f"FROM security_events{where} ORDER BY occurred_at DESC, event_id DESC LIMIT ? OFFSET ?",
                [*parameters, limit, offset],
            ).fetchall()
            items = [dict(row) for row in rows]
            connection.commit()
            return ActivityPage(items=items, total=total, limit=limit, offset=offset)
        except sqlite3.Error as exc:
            raise ActivityDashboardError("SecureAir activity data could not be read.") from exc
        finally:
            connection.close()
