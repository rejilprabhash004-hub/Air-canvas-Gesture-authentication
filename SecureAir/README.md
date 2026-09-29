# SecureAir

**Stage 22: report hash verification.** SecureAir remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are processed locally and not stored.
- Consent-based enrollment and gesture-classification evaluation. No labeled biometric dataset or validated identity-confidence model is included; no accuracy claim is made.
- User-bound, expiring, single-use challenges; fail-closed decisions; and a loopback FastAPI API. Gesture observations and behavioral scores remain caller-supplied and forgeable.
- Isolated SQLite schema, privacy-conscious event logger, and exact-host site preferences. Stored features are local and unencrypted.
- A minimal Manifest V3 extension and a loopback demo portal. The extension records only user-opened popup checks for enabled exact-host sites in local storage; it does not monitor in the background.
- `backend/activity_dashboard.py`: token-gated, read-only, paginated event queries against schema v3; event details and chain hashes are excluded.
- `backend/security_event_hashes.py` and `backend/security_event_chain.py`: canonical event hashes and a transactional backend event chain without an external trust anchor.
- `backend/event_reports.py`: local PDF, CSV, and JSON encoders for already-minimized dashboard records.
- `backend/report_integrity.py`: SHA-256 helpers to compute and verify digests for exact exported report bytes.

## Report exports and integrity verification

First obtain minimized rows through the read-only activity query, then encode them with `export_events(events, "csv" | "json" | "pdf")`. The exporter rejects details and chain hashes, applies CSV formula safeguards, paginates PDFs, and caps input at 10,000 rows.

For byte-level verification, compute `digest = report_sha256(report_bytes)` after export and retain that digest separately from the file. Later call `verify_report_sha256(report_bytes, digest)`: it returns `True` for matching bytes and `False` for modified bytes, while malformed digest strings and non-byte report input raise `ReportIntegrityError`. The digest is lowercase SHA-256 hex.

A hash only detects changes relative to a trusted digest. If an attacker can replace both the report and the saved digest, verification cannot establish authenticity. These helpers do not sign reports, store digests, or create an external trust anchor. Reports and digests may contain or relate to private records; keep them protected.

## Backend event integrity chain

New SecureAir databases use schema version 3. Structurally verified v1 or v2 databases migrate transactionally, with existing events linked in event-ID order. Invalid legacy event metadata stops and rolls back migration. Each backend event stores `previous_hash` and `event_hash`; the writer verifies history in the write transaction before appending and refuses to extend an invalid chain. The activity query supports v3 but excludes raw details and chain hashes. Profile deletion verifies and re-chains atomically to honor profile-reference nullification.

The chain can reveal inconsistent edits when verified; it cannot stop a database writer from changing records and recomputing the chain. There is no external chain anchor, signature, or remote checkpoint. Protect local database files and backups. Extension-local Stage 18 history is separate from Python SQLite.

## Extension-local event history

For an enabled exact-host site, opening the popup stores only timestamp, hostname, and fixed status label. It excludes URL paths, query strings, page content, and unconfigured or disabled sites. No background tab/navigation listeners, host permissions, network calls, or API credentials are used. Options lets you view and clear the latest 200 events. This unencrypted history is not sent to Python SQLite and is not general browsing history.

## Run the integrated local demo

From the `SecureAir` directory in PowerShell, install development dependencies, set a fresh random API secret, and run the API:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python -m backend.app
```

In another shell, set the same secret and run the portal:

```powershell
.\.venv\Scripts\Activate.ps1
$env:SECUREAIR_SECRET_KEY = "<same generated secret>"
python -m uvicorn demo_portal.app:app --host 127.0.0.1 --port 8765
```

Visit `http://127.0.0.1:8765/`. Portal requests and consumes challenges from the API server-to-server. The secret is not sent to the browser. Inputs remain forgeable; never use this demo to protect real data.

## Privacy and validation

The dedicated database is `settings.data_dir / "secureair.sqlite3"`; unmarked/foreign databases are refused and the legacy Flask database is untouched. Enrollment features, backend event metadata, chain hashes, and extension event history are local and unencrypted. Report files and hashes should be treated as private. The extension list and history are separate from Python SQLite.

```powershell
python -m pytest
ruff check .
```

Tests and lint have not been run in this environment. Never commit secrets, profiles, private reports, or report digests.
