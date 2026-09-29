"""Transactional hash-chain helpers for SecureAir SQLite security events."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import hmac
import re
from typing import Any

from backend.database import database_connection
from backend.security_event_hashes import SecurityEventHashError, hash_security_event

GENESIS_HASH = "0" * 64
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class SecurityEventChainError(ValueError):
    """Raised for invalid chain inputs or unavailable chain storage."""


@dataclass(frozen=True)
class ChainVerificationResult:
    valid: bool
    event_count: int
    failed_event_id: int | None = None


def hash_chained_event(event: Mapping[str, Any], previous_hash: str) -> str:
    """Bind an event's Stage 19 canonical digest to its predecessor hash."""
    if not isinstance(previous_hash, str) or not _HASH_PATTERN.fullmatch(previous_hash):
        raise SecurityEventChainError("previous_hash must be a lowercase SHA-256 digest.")
    try:
        event_hash = hash_security_event(event)
    except SecurityEventHashError as exc:
        raise SecurityEventChainError("event cannot be included in the hash chain.") from exc
    payload = b"SecureAir:event-chain:v1\0" + bytes.fromhex(previous_hash) + bytes.fromhex(event_hash)
    return hashlib.sha256(payload).hexdigest()


def _rechain_all_events(connection) -> None:
    """Recompute all links inside the caller's active transaction."""
    previous_hash = GENESIS_HASH
    rows = connection.execute(
        """SELECT event_id, occurred_at, event_type, outcome, profile_id, details_json
           FROM security_events ORDER BY event_id ASC"""
    ).fetchall()
    for row in rows:
        event = {key: row[key] for key in (
            "event_id", "occurred_at", "event_type", "outcome", "profile_id", "details_json"
        )}
        try:
            event_hash = hash_chained_event(event, previous_hash)
        except SecurityEventChainError as exc:
            raise SecurityEventChainError("security event cannot be re-chained safely.") from exc
        connection.execute(
            "UPDATE security_events SET previous_hash = ?, event_hash = ? WHERE event_id = ?",
            (previous_hash, event_hash, row["event_id"]),
        )
        previous_hash = event_hash


def delete_profile_and_rechain(db_path: str, profile_id: str) -> bool:
    """Delete a profile, null its event references, then atomically re-chain.

    Profile deletion intentionally changes historical profile_id fields due to
    the database's ON DELETE SET NULL privacy behavior. Recomputing the affected
    chain in the same transaction preserves internal consistency. It does not
    provide an external tamper-evident anchor.
    """
    if not isinstance(profile_id, str) or not profile_id:
        raise SecurityEventChainError("profile_id must be a non-empty string.")
    try:
        with database_connection(db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "DELETE FROM profiles WHERE profile_id = ?", (profile_id,)
            )
            if cursor.rowcount:
                _rechain_all_events(connection)
            return cursor.rowcount > 0
    except SecurityEventChainError:
        raise
    except Exception as exc:
        raise SecurityEventChainError("profile deletion and chain update failed.") from exc


def verify_security_event_chain(db_path: str) -> ChainVerificationResult:
    """Verify every stored event and predecessor link in event_id order.

    Returns the first failing event ID rather than exposing event contents. An
    empty chain is valid. Database access failures raise SecurityEventChainError.
    """
    expected_previous = GENESIS_HASH
    count = 0
    try:
        with database_connection(db_path) as connection:
            rows = connection.execute(
                """SELECT event_id, occurred_at, event_type, outcome, profile_id,
                          details_json, previous_hash, event_hash
                   FROM security_events ORDER BY event_id ASC"""
            )
            for row in rows:
                count += 1
                event_id = row["event_id"]
                if not isinstance(row["previous_hash"], str) or not hmac.compare_digest(
                    row["previous_hash"], expected_previous
                ):
                    return ChainVerificationResult(False, count, event_id)
                event = {key: row[key] for key in (
                    "event_id", "occurred_at", "event_type", "outcome", "profile_id", "details_json"
                )}
                try:
                    expected_hash = hash_chained_event(event, expected_previous)
                except SecurityEventChainError:
                    return ChainVerificationResult(False, count, event_id)
                if not isinstance(row["event_hash"], str) or not hmac.compare_digest(
                    row["event_hash"], expected_hash
                ):
                    return ChainVerificationResult(False, count, event_id)
                expected_previous = expected_hash
    except Exception as exc:
        raise SecurityEventChainError("security event chain could not be read.") from exc
    return ChainVerificationResult(True, count)
