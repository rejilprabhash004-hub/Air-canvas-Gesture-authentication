# SecureAir

**Stage 18: explicit-domain, extension-local activity events.** SecureAir remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are processed locally and not stored.
- Consent-based enrollment and gesture-classification evaluation. No labeled biometric dataset or validated identity-confidence model is included; no accuracy claim is made.
- User-bound, expiring, single-use challenges; fail-closed decisions; and a loopback FastAPI API. Gesture observations and behavioral scores remain caller-supplied and forgeable.
- Isolated SQLite schema, privacy-conscious event logger, and exact-host site preferences. Stored features are local and unencrypted; backend events are not yet hash-chained.
- A minimal Manifest V3 status extension and loopback demo portal. The extension does not authenticate, block access, or monitor browsing in the background. Demo signals remain forgeable.
- `backend/activity_dashboard.py`: token-gated, read-only, paginated event queries; raw event details are excluded. This is a library module, not an HTTP dashboard.
- Extension-local event history for an explicit toolbar-popup check of an exact hostname the user has configured and enabled.

## Extension-local event history

When the extension popup is opened for an enabled exact-host site, the extension stores a local event containing only a timestamp, hostname, and fixed status label. It does not record URL paths, query strings, page content, or visits to unconfigured/disabled sites. No background tab or navigation listeners, host permissions, network calls, or API credentials are used. The options page displays the recent events and lets you clear them. The list is capped at 200 events, remains in extension-local storage, is not encrypted, and is not sent to the Python dashboard.

This records an explicit popup status check, **not a general visit history**. Adding or enabling a site means popup checks for that site will be recorded. Remove or disable the site to stop recording checks; use **Clear event history** to erase saved events.

## Read-only Python activity queries

The backend query module remains separate from extension-local events; there is no network dashboard endpoint. Initialize the dedicated SecureAir database and supply a private token of at least 32 characters from application configuration. Do not commit or put the token in browser code.

```python
import os
from backend.activity_dashboard import ActivityDashboard
from backend.config import load_settings
from backend.database import database_path, initialize_database

settings = load_settings()
db_path = initialize_database(database_path(settings))
access_token = os.environ["SECUREAIR_DASHBOARD_TOKEN"]
dashboard = ActivityDashboard(db_path, access_token)
page = dashboard.list_events(
    access_token,
    event_type="auth_attempt",
    outcome="denied",
    limit=25,
    offset=0,
)
for event in page.items:
    print(event)
print(f"{page.total} matching events")
```

Optional `after` and `before` filters accept timezone-aware ISO-8601 timestamps. Event type and outcome use allowlisted exact matches; page size is 1–100. Queries open SQLite read-only and return only event ID, timestamp, type, outcome, and pseudonymous profile ID, never `details_json`.

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

Visit `http://127.0.0.1:8765/`. Portal requests and consumes challenges from the API server-to-server. The secret is not sent to the browser. Inputs are still forgeable, so this demo must never protect real data.

## Privacy and validation

The dedicated database is `settings.data_dir / "secureair.sqlite3"`; unmarked/foreign databases are refused and the legacy Flask database is untouched. Enrollment features, backend event metadata, and extension event history are local and unencrypted; protect the data directory and browser profile. The extension's site list and event history are separate from Python SQLite.

```powershell
python -m pytest
ruff check .
```

Tests and lint have not been run in this environment. Obtain consent before camera use. Never commit secrets, profiles, or databases.
