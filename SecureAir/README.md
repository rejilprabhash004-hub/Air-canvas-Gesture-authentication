# SecureAir

**Stage 21: privacy-minimized PDF, CSV, and JSON event reports.** SecureAir remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are processed locally and not stored.
- Consent-based enrollment and gesture-classification evaluation. No labeled biometric dataset or validated identity-confidence model is included; no accuracy claim is made.
- User-bound, expiring, single-use challenges; fail-closed decisions; and a loopback FastAPI API. Gesture observations and behavioral scores remain caller-supplied and forgeable.
- Isolated SQLite schema, privacy-conscious event logger, and exact-host site preferences. Stored features are local and unencrypted.
- A minimal Manifest V3 extension and a loopback demo portal. The extension records only user-opened popup checks for enabled exact-host sites in local storage; it does not monitor in the background.
- `backend/activity_dashboard.py`: token-gated, read-only, paginated event queries against schema v3; event details and chain hashes are excluded.
- `backend/security_event_hashes.py` and `backend/security_event_chain.py`: canonical hashes and a transactional backend event chain, without an external trust anchor.
- `backend/event_reports.py`: local PDF, CSV, and JSON encoders for already-minimized dashboard records. It does not access the database or add a network export endpoint.

## Event report exports

Call the read-only `ActivityDashboard.list_events(...)` first and pass its `page.items` to `export_events(events, "csv" | "json" | "pdf")`. The export module accepts exactly the minimized fields `event_id`, `occurred_at`, `event_type`, `outcome`, and `profile_id`; it rejects extra fields such as `details_json`, `previous_hash`, or `event_hash`. Event type and outcome are allowlisted and report size is capped at 10,000 rows. CSV values that could be interpreted as spreadsheet formulas are prefixed defensively. JSON has a versioned report marker. PDF generation uses the Python standard library, is paginated, and emits only the same minimized metadata.

These are local encoding helpers only; they do not write files, add endpoints, create a trusted signature, or alter the event chain. Reports may still contain timestamps and pseudonymous profile IDs; handle them as private records and store/export them only where appropriate. No third-party PDF dependency was added.

## Backend event integrity chain

New SecureAir databases use schema version 3. Structurally verified v1 or v2 databases migrate transactionally; v1 first gains the protected-sites table, and existing events are linked in event-ID order. Invalid legacy event metadata stops the migration and rolls it back.

Each backend security event stores `previous_hash` and `event_hash`. Before appending, the writer verifies existing rows while holding the SQLite write transaction, and refuses to extend invalid history. The activity query validates schema v3 and omits details and chain hashes. Profile deletion verifies then re-chains atomically to respect profile-reference nullification.

The chain can reveal inconsistent edits when verified; it cannot prevent an attacker with database write access from changing records and recomputing the chain. There is no external trust anchor, signature, or remote checkpoint. Protect local database files and backups. The extension-local history is separate from Python SQLite.

## Extension-local event history

For an enabled exact-host site, opening the popup stores only timestamp, hostname, and a fixed status label. It excludes URL paths, query strings, page content, and unconfigured or disabled sites. No background tab/navigation listeners, host permissions, network calls, or API credentials are used. Options lets you view and clear the latest 200 events. This unencrypted history is not sent to Python SQLite and is not general browsing history.

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

The dedicated database is `settings.data_dir / "secureair.sqlite3"`; unmarked/foreign databases are refused and the legacy Flask database is untouched. Enrollment features, backend event metadata, chain hashes, and extension event history are local and unencrypted. The extension list/history are separate from Python SQLite.

```powershell
python -m pytest
ruff check .
```

Tests and lint have not been run in this environment. Never commit secrets, profiles, or private reports.
