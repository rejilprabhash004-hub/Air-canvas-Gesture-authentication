# SecureAir

**Stage 20: transactional hash chain for backend security events.** SecureAir remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are processed locally and not stored.
- Consent-based enrollment and gesture-classification evaluation. No labeled biometric dataset or validated identity-confidence model is included; no accuracy claim is made.
- User-bound, expiring, single-use challenges; fail-closed decisions; and a loopback FastAPI API. Gesture observations and behavioral scores remain caller-supplied and forgeable.
- Isolated SQLite schema, privacy-conscious event logger, and exact-host site preferences. Stored features are local and unencrypted.
- A minimal Manifest V3 extension and a loopback demo portal. The extension records only user-opened popup checks for enabled exact-host sites in local storage; it does not monitor in the background.
- `backend/activity_dashboard.py`: token-gated, read-only, paginated event queries against schema v3; event details and chain hashes are excluded.
- `backend/security_event_hashes.py`: canonical event encoding and SHA-256 digest helper.
- `backend/security_event_chain.py`: schema-v3 chain verification and profile deletion/re-chaining helpers. The event logger verifies prior history and appends new events and chain links atomically.

## Backend event integrity chain

New SecureAir databases use schema version 3. Structurally verified v1 or v2 databases migrate transactionally; v1 first gains the protected-sites table, and existing event rows are linked in event-ID order. Invalid legacy event metadata stops the migration and rolls back. Unmarked or unrelated databases continue to be refused.

Each backend security event stores `previous_hash` and `event_hash`. The first predecessor is 64 zeroes. The chain digest binds the Stage 19 canonical event hash to its predecessor with a versioned separator. Before every new event is appended, the writer verifies existing rows while holding the SQLite write transaction; it refuses to extend invalid history. The read-only activity query validates the v3 schema and continues to return only minimized event metadata. Profile deletion verifies then re-chains in one transaction to respect profile-reference nullification.

The chain can reveal inconsistent edits when verified; it does not stop an attacker with write access from changing events and recomputing the full chain. There is no external trust anchor, signature, or remote checkpoint. Protect local database files and backups. Extension-local Stage 18 history is separate and untouched by this schema migration.

## Extension-local event history

For an enabled exact-host site, opening the popup stores an event containing only a timestamp, hostname, and fixed status label. It excludes URL paths, query strings, page content, and unconfigured or disabled sites. There are no background tab/navigation listeners, host permissions, network calls, or API credentials. Options lets you view and clear the latest 200 events. This local unencrypted history is not sent to Python SQLite and is not general browsing history.

## Read-only Python activity queries

The backend query module is a library only; there is no HTTP dashboard endpoint. Initialize the dedicated SecureAir database and provide a private token of at least 32 characters. Do not commit or put the token in browser code.

```python
import os
from backend.activity_dashboard import ActivityDashboard
from backend.config import load_settings
from backend.database import database_path, initialize_database

settings = load_settings()
db_path = initialize_database(database_path(settings))
access_token = os.environ["SECUREAIR_DASHBOARD_TOKEN"]
dashboard = ActivityDashboard(db_path, access_token)
page = dashboard.list_events(access_token, event_type="auth_attempt", outcome="denied")
for event in page.items:
    print(event)
```

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

In a second shell, set the same secret and run the portal:

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

Tests and lint have not been run in this environment. Never commit secrets, profiles, or databases.
