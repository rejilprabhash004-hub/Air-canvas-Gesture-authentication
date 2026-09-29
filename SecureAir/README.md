# SecureAir

**Stage 23: security review remediation.** SecureAir remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are processed locally and not stored.
- Consent-based enrollment and gesture-classification evaluation. No labeled biometric dataset or validated identity-confidence model is included; no accuracy claim is made.
- User-bound, expiring, single-use challenges; fail-closed decisions; and a loopback FastAPI API. Gesture observations and behavioral scores remain caller-supplied and forgeable.
- Isolated SQLite schema, privacy-conscious event logger, and exact-host site preferences. Stored features are local and unencrypted.
- A minimal Manifest V3 extension and a loopback demo portal. The extension records only user-opened popup checks for enabled exact-host sites in local storage; it does not monitor or block in the background.
- `backend/activity_dashboard.py`: token-gated, read-only, paginated schema-v3 queries. It verifies the complete event chain in the same SQLite read snapshot before returning minimized event metadata; details and chain hashes are excluded.
- `backend/security_event_hashes.py` and `backend/security_event_chain.py`: canonical event hashing, transactional chain verification, and integrity-aware profile deletion.
- `backend/event_reports.py`: local PDF, CSV, and JSON encoders for already-minimized records, with incremental row-count bounding, 256-character text field limits, and CSV formula safeguards.
- `backend/report_integrity.py`: SHA-256 helpers for exact report bytes; these do not provide a signature or trustworthy anchor.

## Security review remediation

Direct profile deletion is blocked by a SQLite trigger; callers must use `delete_profile_and_rechain(...)`, which verifies the existing history and performs profile deletion, event-reference nullification, chain recalculation, and trigger restoration in one transaction. Schema initialization installs the guard for new, migrated, and existing v3 databases. Chain-aware deletion is an application-level consistency control, not protection against a local database administrator who can modify schema or file contents.

The activity query rejects invalid chain history before returning any records, so downstream report exporters only receive query results after successful verification when used via the documented flow. The query still excludes raw event details and hash columns.

Report exporters consume at most 10,001 iterator rows before refusing inputs over the 10,000-event cap. Text fields are limited to 256 characters to prevent unusually large fields from bypassing record-count bounds. These limits apply to the local encoding helper; callers should still obtain minimized rows from the dashboard and handle exports as private files.

The API's gesture samples and scores are caller-supplied and forgeable; the extension is an explicit local status display and is not an authentication or navigation-blocking boundary. The system must not be used to protect real accounts or resources.

## Report exports and integrity

Use the read-only `ActivityDashboard.list_events(...)` and pass `page.items` to `export_events(events, "csv" | "json" | "pdf")`. Export fields are exactly `event_id`, `occurred_at`, `event_type`, `outcome`, and `profile_id`; details and chain hashes are rejected. For byte verification, compute `report_sha256(report_bytes)` and separately retain the digest, then use `verify_report_sha256(report_bytes, digest)`. A hash detects changes only relative to a trusted digest. It does not establish authorship or protect against replacement of both report and digest.

## Backend chain limits

New databases use schema version 3. Verified v1/v2 SecureAir databases migrate transactionally; legacy event rows are linked by event ID. Event writes verify the full chain under a write lock and fail closed on invalid history. The chain has no external trust anchor, signature, or remote checkpoint; someone with database-file and schema control can rewrite rows and recompute the chain.

The extension-local Stage 18 history remains separate from Python SQLite. No network export endpoint is provided.

## Local demo and checks

From `SecureAir` in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m pytest
ruff check .
```

The API and portal remain loopback demonstrations, not production security controls. No local test, lint, camera, or dynamic penetration-test results are claimed here. Keep database files, reports, and report digests private; never commit secrets, profiles, or local data.
