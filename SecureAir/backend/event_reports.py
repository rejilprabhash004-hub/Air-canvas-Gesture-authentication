"""Privacy-minimized CSV, JSON, and PDF exports for SecureAir event queries.

Exports operate only on records already returned by the read-only dashboard;
they do not open the database or include event details or chain hashes.
"""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from typing import Any

_FIELDS = ("event_id", "occurred_at", "event_type", "outcome", "profile_id")
_EVENT_TYPES = frozenset({
    "auth_attempt", "challenge_issue", "challenge_consume", "profile_enroll",
    "profile_delete", "service_auth_failure",
})
_OUTCOMES = frozenset({"success", "failure", "denied", "error"})
_MAX_EVENTS = 10_000
_LINES_PER_PAGE = 48
_LINE_WIDTH = 88


class EventReportError(ValueError):
    """Raised for invalid, overlarge, or unsupported report input."""


def _validated_events(events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(events, (str, bytes, Mapping)):
        raise EventReportError("events must be an iterable of minimized event records.")
    try:
        rows = list(events)
    except TypeError as exc:
        raise EventReportError("events must be iterable.") from exc
    if len(rows) > _MAX_EVENTS:
        raise EventReportError(f"reports are limited to {_MAX_EVENTS} events.")
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != set(_FIELDS):
            raise EventReportError("each record must contain only minimized dashboard fields.")
        event_id = row["event_id"]
        if isinstance(event_id, bool) or not isinstance(event_id, int) or event_id < 1:
            raise EventReportError("event_id must be a positive integer.")
        for field in ("occurred_at", "event_type", "outcome"):
            if not isinstance(row[field], str) or not row[field]:
                raise EventReportError(f"{field} must be a non-empty string.")
        if row["event_type"] not in _EVENT_TYPES or row["outcome"] not in _OUTCOMES:
            raise EventReportError("event_type or outcome is not allowlisted.")
        profile_id = row["profile_id"]
        if profile_id is not None and not isinstance(profile_id, str):
            raise EventReportError("profile_id must be a string or null.")
        result.append({field: row[field] for field in _FIELDS})
    return result


def export_events_json(events: Iterable[Mapping[str, Any]]) -> bytes:
    """Encode minimized events as UTF-8 JSON; details and chain data are rejected."""
    rows = _validated_events(events)
    payload = {"schema": "secureair-event-report-v1", "events": rows}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _spreadsheet_safe(value: Any) -> str:
    text = "" if value is None else str(value)
    probe = text.lstrip(" \t\r\n")
    if probe.startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def export_events_csv(events: Iterable[Mapping[str, Any]]) -> bytes:
    """Encode minimized events as UTF-8 CSV with spreadsheet-formula safeguards."""
    rows = _validated_events(events)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=_FIELDS, lineterminator="\r\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _spreadsheet_safe(row[field]) for field in _FIELDS})
    return stream.getvalue().encode("utf-8")


def _pdf_text(value: str) -> str:
    """Return a safe, printable ASCII PDF literal string."""
    safe = "".join(character if 32 <= ord(character) <= 126 else "?" for character in value)
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_line(line: str, width: int = _LINE_WIDTH) -> list[str]:
    if len(line) <= width:
        return [line]
    parts: list[str] = []
    remaining = line
    while remaining:
        parts.append(remaining[:width])
        remaining = remaining[width:]
    return parts


def _pdf_document(pages: list[list[str]]) -> bytes:
    """Build a small standards-compliant PDF using only the Python standard library."""
    objects: list[bytes | None] = [None] * (3 + len(pages) * 2)
    page_refs = [f"{4 + index * 2} 0 R" for index in range(len(pages))]
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(pages)} >>".encode("ascii")
    objects[2] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"
    for index, lines in enumerate(pages):
        page_object = 4 + index * 2
        content_object = page_object + 1
        commands = ["BT", "/F1 9 Tf", "40 800 Td", "12 TL"]
        for line_index, line in enumerate(lines):
            if line_index:
                commands.append("T*")
            commands.append(f"({_pdf_text(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("ascii")
        objects[page_object - 1] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_object} 0 R >>"
        ).encode("ascii")
        objects[content_object - 1] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        )
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        if body is None:
            raise EventReportError("PDF report assembly failed.")
        offsets.append(len(output))
        output.extend(f"{object_number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def export_events_pdf(events: Iterable[Mapping[str, Any]]) -> bytes:
    """Render minimized events as a dependency-free, paginated PDF report."""
    rows = _validated_events(events)
    lines = [
        "SecureAir Security Event Report",
        "Minimized fields only; event details and chain hashes are excluded.",
        "",
        "ID  Timestamp                         Type                 Outcome  Profile",
        "-" * 88,
    ]
    for row in rows:
        profile = row["profile_id"] or "-"
        text = (
            f"{row['event_id']}  {row['occurred_at']}  {row['event_type']}  "
            f"{row['outcome']}  {profile}"
        )
        lines.extend(_wrap_line(text))
    if not rows:
        lines.append("No events matched the selected filters.")
    pages = [lines[start:start + _LINES_PER_PAGE] for start in range(0, len(lines), _LINES_PER_PAGE)]
    return _pdf_document(pages or [["SecureAir Security Event Report"]])


def export_events(events: Iterable[Mapping[str, Any]], report_format: str) -> bytes:
    """Export minimized dashboard rows as ``csv``, ``json``, or ``pdf`` bytes."""
    exporters = {"csv": export_events_csv, "json": export_events_json, "pdf": export_events_pdf}
    if not isinstance(report_format, str) or report_format.lower() not in exporters:
        raise EventReportError("report_format must be csv, json, or pdf.")
    return exporters[report_format.lower()](events)
