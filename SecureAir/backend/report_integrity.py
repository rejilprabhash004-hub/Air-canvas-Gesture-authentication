"""SHA-256 integrity helpers for exported SecureAir report bytes.

A digest detects changes only when compared with a separately trusted value.
This module neither signs reports nor stores a trust anchor.
"""
from __future__ import annotations

import hashlib
import hmac
import re

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ReportIntegrityError(ValueError):
    """Raised when report bytes or an expected digest are invalid."""


def report_sha256(report: bytes) -> str:
    """Return the lowercase SHA-256 hex digest of the exact report bytes."""
    if not isinstance(report, bytes):
        raise ReportIntegrityError("report must be bytes.")
    return hashlib.sha256(report).hexdigest()


def verify_report_sha256(report: bytes, expected_digest: str) -> bool:
    """Verify report bytes against a lowercase SHA-256 digest.

    Digest syntax is validated before constant-time comparison. This proves
    byte equality relative to the supplied digest, not who created it or whether
    the digest itself was kept somewhere trustworthy.
    """
    if not isinstance(expected_digest, str) or not _DIGEST.fullmatch(expected_digest):
        raise ReportIntegrityError("expected_digest must be a lowercase SHA-256 hex digest.")
    actual_digest = report_sha256(report)
    return hmac.compare_digest(actual_digest, expected_digest)
