# SecureAir

**Stage 17: read-only local activity dashboard queries.** SecureAir remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are processed locally and not stored.
- Consent-based enrollment and gesture-classification evaluation. No labeled biometric dataset or validated identity-confidence model is included; no accuracy claim is made.
- User-bound, expiring, single-use challenges; fail-closed decisions; and a loopback FastAPI API. Gesture observations and behavioral scores remain caller-supplied and forgeable.
- Isolated SQLite schema, privacy-conscious event logger, and exact-host site preferences. Stored features are local and unencrypted; events are not yet hash-chained.
- A minimal Manifest V3 status extension and a loopback demo portal connected to the challenge API. The extension does not authenticate or block browsing, and the demo inputs are forgeable.
- `backend/activity_dashboard.py`: token-gated, read-only, paginated event queries. It reads only selected metadata fields; raw `details_json` is excluded. It does not collect or monitor browsing activity.

## Activity dashboard query example

The dashboard query module is a library layer only; no network dashboard endpoint is exposed. Initialize the dedicated SecureAir database and configure a private local token of at least 32 characters in your application configuration. Do not commit or place the token in browser code.

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

Optional `after` and `before` filters accept timezone-aware ISO-8601 timestamps. `event_type` and `outcome` are allowlisted exact matches; limit is 1–100. The SQLite connection uses read-only mode and query-only settings; only event ID, timestamp, event type, outcome, and pseudonymous profile ID are returned. Never expose this data beyond its intended local audience.

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

Visit `http://127.0.0.1:8765/`. Portal requests and consumes challenges from the API server-to-server. The secret is not sent to the browser. Inputs are still forgeable and this demonstration must never protect real data.

## Privacy and validation

The dedicated database is `settings.data_dir / "secureair.sqlite3"`; unmarked/foreign databases are refused and the legacy Flask database is untouched. Enrollment features and event metadata are local but unencrypted; protect the data directory and backups. The dashboard returns minimized event metadata and omits event details. The browser extension uses separate local storage and does not monitor browsing.

```powershell
python -m pytest
ruff check .
```

The tests and lint have not been run in this environment. Obtain consent before camera use. Never commit secrets, profiles, or databases.
