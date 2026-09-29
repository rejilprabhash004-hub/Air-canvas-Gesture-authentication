# SecureAir

**Stage 16: local demo portal/API integration.** SecureAir remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are processed locally and not stored.
- Consent-based local enrollment and gesture-classification evaluation. No real labeled biometric dataset or validated identity-confidence model is included; no accuracy claim is made.
- User-bound, expiring, single-use challenges; a transparent fail-closed decision policy; and a loopback FastAPI API. Gesture observations and behavioral scores remain caller-supplied and forgeable.
- Isolated SQLite schema, allowlisted privacy-conscious event logging, and exact-host protected-site settings. Stored features are local and unencrypted; events are not yet hash-chained.
- A minimal Manifest V3 extension that displays a user-managed local site-status preference after a toolbar click. It does not authenticate or block browsing.
- `demo_portal/`: loopback-only demo that requests challenges from the local API and submits responses server-to-server. The API bearer secret is held in the portal server's environment, not extension or browser code.

## Run the local API and integrated demo

From the `SecureAir` directory in PowerShell, install dependencies and set a fresh random secret in that shell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python -m backend.app
```

In a second PowerShell window, activate the same virtual environment and run the portal with the same secret:

```powershell
.\.venv\Scripts\Activate.ps1
$env:SECUREAIR_SECRET_KEY = "<paste the generated secret from the first window>"
python -m uvicorn demo_portal.app:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. The portal requests a challenge from `http://127.0.0.1:8000`, displays the gesture sequence, and forwards the form response to the API. To use another loopback API origin, set `SECUREAIR_API_URL` on the portal server to an HTTP loopback origin only. The portal rejects non-loopback clients and the API URL validator rejects non-loopback origins. The bearer secret is never sent to the browser.

The API consumes each challenge once; replay or unavailable API results fail closed. A successful API decision creates a short-lived HttpOnly, SameSite cookie and server-side demo session. `/protected` checks that server-side authorization record; `/logout` revokes it. Session state is in-memory and expires after five minutes.

**This is only a control-flow integration demo.** The visitor can forge the sequence response and behavioral score; there is no camera provenance or validated identity score. Do not use it or its cookie to protect real data. Keep both services bound to loopback.

## Browser extension: local status only

For Chrome/Chromium, enable developer mode in the extension manager and load the unpacked `extension/` folder. Add DNS hostnames on its options page. The popup checks the active tab only after you click the extension action and displays an exact-host match from extension-local storage. Permissions are limited to `activeTab` and `storage`; it has no host permissions, content scripts, web-request hooks, or remote calls. The list does not sync with Python SQLite. The extension neither monitors in the background nor authenticates or blocks access. Never put the API bearer secret in the extension.

## SQLite and protected-site preferences

Use `settings.data_dir / "secureair.sqlite3"`. `initialize_database(database_path(settings))` creates schema v2 or transactionally migrates a verified SecureAir v1 database. Unmarked/foreign databases are refused; the legacy Flask database remains untouched. `ProtectedSiteStore` manages normalized exact hostnames; parent domains do not automatically include subdomains. These are preferences, not browser enforcement.

Enrollment features and event metadata are local but not encrypted. Obtain consent and protect the data directory and backups. Event fields are allowlisted and avoid credentials, free text, raw camera data, and gesture sequences; events are not yet tamper-evident.

## Checks

```powershell
python -m pytest
ruff check .
```

These checks have not been run in this environment. Obtain consent before camera use. Never commit secrets, local profiles, or databases. The existing Flask project remains separate; its legacy test runner deletes its database, so run it only against a disposable clone.
