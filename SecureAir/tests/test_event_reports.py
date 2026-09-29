"""Privacy and format tests for minimized PDF/CSV/JSON event exports."""
import csv
import io
import json

import pytest

from backend.event_reports import (
    EventReportError,
    export_events,
    export_events_csv,
    export_events_json,
    export_events_pdf,
)


@pytest.fixture
def events():
    return [
        {
            "event_id": 1,
            "occurred_at": "2026-09-29T10:00:00+00:00",
            "event_type": "auth_attempt",
            "outcome": "denied",
            "profile_id": "profile_1",
        },
        {
            "event_id": 2,
            "occurred_at": "2026-09-29T10:02:00+00:00",
            "event_type": "challenge_issue",
            "outcome": "success",
            "profile_id": None,
        },
    ]


def test_json_export_is_valid_deterministic_and_minimized(events):
    output = export_events_json(events)
    parsed = json.loads(output)
    assert parsed == {"schema": "secureair-event-report-v1", "events": events}
    assert output == export_events_json(events)
    assert b"details_json" not in output
    assert b"event_hash" not in output and b"previous_hash" not in output


def test_csv_export_has_fixed_minimized_columns_and_round_trips(events):
    output = export_events_csv(events)
    parsed = list(csv.DictReader(io.StringIO(output.decode("utf-8"))))
    assert list(parsed[0]) == ["event_id", "occurred_at", "event_type", "outcome", "profile_id"]
    assert parsed[0]["event_type"] == "auth_attempt"
    assert parsed[1]["profile_id"] == ""
    assert b"details_json" not in output
    assert b"event_hash" not in output and b"previous_hash" not in output


def test_csv_protects_spreadsheet_formula_like_profile_values():
    malicious = [{
        "event_id": 3,
        "occurred_at": "2026-09-29T10:03:00+00:00",
        "event_type": "auth_attempt",
        "outcome": "failure",
        "profile_id": "=HYPERLINK(\"https://example.invalid\")",
    }]
    parsed = list(csv.DictReader(io.StringIO(export_events_csv(malicious).decode("utf-8"))))
    assert parsed[0]["profile_id"].startswith("'=")


def test_pdf_has_valid_header_xref_and_minimized_report_text(events):
    output = export_events_pdf(events)
    assert output.startswith(b"%PDF-1.4")
    assert b"startxref" in output and b"%%EOF" in output
    assert b"Security Event Report" in output
    assert b"auth_attempt" in output and b"challenge_issue" in output
    assert b"details_json" not in output
    assert b"event_hash" not in output and b"previous_hash" not in output


def test_empty_reports_and_format_dispatch(events):
    assert json.loads(export_events([], "json"))["events"] == []
    assert export_events([], "pdf").startswith(b"%PDF-")
    assert export_events([], "csv").startswith(b"event_id,")
    assert export_events(events, "JSON") == export_events_json(events)
    with pytest.raises(EventReportError, match="report_format"):
        export_events(events, "xml")


@pytest.mark.parametrize("bad", [
    {"event_id": 1},
    {"event_id": 1, "occurred_at": "now", "event_type": "auth_attempt", "outcome": "failure", "profile_id": None, "details_json": "{}"},
    {"event_id": True, "occurred_at": "now", "event_type": "auth_attempt", "outcome": "failure", "profile_id": None},
    {"event_id": 1, "occurred_at": "now", "event_type": "password", "outcome": "failure", "profile_id": None},
])
def test_refuses_invalid_or_private_report_fields(bad):
    with pytest.raises(EventReportError):
        export_events_json([bad])
    with pytest.raises(EventReportError):
        export_events_csv([bad])
    with pytest.raises(EventReportError):
        export_events_pdf([bad])


def test_rejects_report_over_size_limit():
    from backend.event_reports import _MAX_EVENTS
    with pytest.raises(EventReportError, match="limited"):
        export_events_json([None] * (_MAX_EVENTS + 1))
