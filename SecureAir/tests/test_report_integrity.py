"""Tests for report-byte hashing and tamper verification."""
import hashlib

import pytest

from backend.report_integrity import (
    ReportIntegrityError,
    report_sha256,
    verify_report_sha256,
)


def test_report_digest_is_sha256_of_exact_bytes():
    report = b"%PDF-1.4\nreport bytes\n"
    digest = report_sha256(report)
    assert digest == hashlib.sha256(report).hexdigest()
    assert len(digest) == 64
    assert verify_report_sha256(report, digest) is True


def test_modified_report_bytes_fail_verification():
    report = b"event_id,event_type\n1,auth_attempt\n"
    digest = report_sha256(report)
    assert verify_report_sha256(report + b"2,profile_delete\n", digest) is False
    assert verify_report_sha256(b"", digest) is False


@pytest.mark.parametrize("bad_digest", [
    "", "a" * 63, "A" * 64, "g" * 64, None, 42,
])
def test_rejects_malformed_digest(bad_digest):
    with pytest.raises(ReportIntegrityError, match="expected_digest"):
        verify_report_sha256(b"report", bad_digest)


@pytest.mark.parametrize("report", [None, "text", bytearray(b"bytes"), 123])
def test_rejects_non_bytes_report(report):
    with pytest.raises(ReportIntegrityError, match="report must be bytes"):
        report_sha256(report)
    with pytest.raises(ReportIntegrityError, match="report must be bytes"):
        verify_report_sha256(report, "0" * 64)


def test_empty_report_has_stable_valid_digest():
    digest = report_sha256(b"")
    assert verify_report_sha256(b"", digest) is True
