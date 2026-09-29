"""Persistent, explicit user-managed protected-site settings."""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
import sqlite3
from pathlib import Path

from backend.database import database_connection

_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


class ProtectedSiteError(ValueError):
    """Raised when a protected-site operation or domain is invalid."""


@dataclass(frozen=True)
class ProtectedSite:
    domain: str
    enabled: bool
    created_at: str
    updated_at: str


def normalize_domain(domain: str) -> str:
    """Normalize a DNS hostname; reject URLs, ports, paths, and IP literals."""
    if not isinstance(domain, str):
        raise ProtectedSiteError("domain must be a hostname string.")
    value = domain.strip().rstrip(".").lower()
    if not value or len(value) > 253 or "://" in value or any(c in value for c in "/?#@"):
        raise ProtectedSiteError("Provide a hostname only, without scheme, path, or credentials.")
    try:
        ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        pass
    else:
        raise ProtectedSiteError("IP addresses are not supported; configure a DNS hostname.")
    try:
        ascii_domain = value.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ProtectedSiteError("domain is not a valid IDNA hostname.") from exc
    if len(ascii_domain) > 253:
        raise ProtectedSiteError("domain must be at most 253 characters.")
    labels = ascii_domain.split(".")
    if len(labels) < 2 or any(not _LABEL.fullmatch(label) for label in labels):
        raise ProtectedSiteError("domain must be a valid fully-qualified hostname.")
    if not labels[-1].isalpha() or len(labels[-1]) < 2:
        raise ProtectedSiteError("domain must end with a valid alphabetic top-level domain.")
    return ascii_domain


def _ensure_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS protected_sites (
            domain TEXT PRIMARY KEY NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )


class ProtectedSiteStore:
    """CRUD for explicit hostname settings in an initialized SecureAir DB."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = db_path

    def add(self, domain: str, *, timestamp: str) -> ProtectedSite:
        hostname = normalize_domain(domain)
        if not isinstance(timestamp, str) or not timestamp.strip():
            raise ProtectedSiteError("timestamp must be a non-empty UTC timestamp.")
        with database_connection(self._db_path) as connection:
            _ensure_table(connection)
            try:
                connection.execute(
                    "INSERT INTO protected_sites (domain, enabled, created_at, updated_at) "
                    "VALUES (?, 1, ?, ?)",
                    (hostname, timestamp, timestamp),
                )
            except sqlite3.IntegrityError as exc:
                raise ProtectedSiteError("domain is already configured.") from exc
        return ProtectedSite(hostname, True, timestamp, timestamp)

    def list(self, *, enabled_only: bool = False) -> list[ProtectedSite]:
        if not isinstance(enabled_only, bool):
            raise ProtectedSiteError("enabled_only must be a boolean.")
        with database_connection(self._db_path) as connection:
            _ensure_table(connection)
            query = "SELECT domain, enabled, created_at, updated_at FROM protected_sites"
            if enabled_only:
                query += " WHERE enabled = 1"
            query += " ORDER BY domain"
            rows = connection.execute(query).fetchall()
        return [ProtectedSite(row[0], bool(row[1]), row[2], row[3]) for row in rows]

    def set_enabled(self, domain: str, enabled: bool, *, timestamp: str) -> ProtectedSite:
        hostname = normalize_domain(domain)
        if not isinstance(enabled, bool):
            raise ProtectedSiteError("enabled must be a boolean.")
        if not isinstance(timestamp, str) or not timestamp.strip():
            raise ProtectedSiteError("timestamp must be a non-empty UTC timestamp.")
        with database_connection(self._db_path) as connection:
            _ensure_table(connection)
            cursor = connection.execute(
                "UPDATE protected_sites SET enabled = ?, updated_at = ? WHERE domain = ?",
                (int(enabled), timestamp, hostname),
            )
            if cursor.rowcount == 0:
                raise ProtectedSiteError("domain is not configured.")
            row = connection.execute(
                "SELECT domain, enabled, created_at, updated_at FROM protected_sites WHERE domain = ?",
                (hostname,),
            ).fetchone()
        return ProtectedSite(row[0], bool(row[1]), row[2], row[3])

    def remove(self, domain: str) -> bool:
        hostname = normalize_domain(domain)
        with database_connection(self._db_path) as connection:
            _ensure_table(connection)
            cursor = connection.execute("DELETE FROM protected_sites WHERE domain = ?", (hostname,))
            return cursor.rowcount > 0

    def is_enabled(self, domain: str) -> bool:
        """Return true only for a configured, enabled exact hostname."""
        hostname = normalize_domain(domain)
        with database_connection(self._db_path) as connection:
            _ensure_table(connection)
            row = connection.execute(
                "SELECT enabled FROM protected_sites WHERE domain = ?", (hostname,)
            ).fetchone()
        return bool(row[0]) if row is not None else False
