# SecureAir

**Stage 15: controlled local demo portal.** SecureAir remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are processed locally and not stored.
- Consent-based local enrollment and gesture-classification evaluation. No real labeled biometric dataset or validated identity-confidence model is included; no accuracy claim is made.
- User-bound expiring challenges, a transparent fail-closed decision policy, and a loopback FastAPI prototype. API gesture observations and scores remain caller-supplied and forgeable.
- Isolated SQLite schema, allowlisted privacy-conscious event logging, and exact-host protected-site settings. Local feature data is not encrypted, and events are not yet hash-chained.
- A minimal Manifest V3 extension that displays a local site-status preference after an explicit toolbar click; it does not authenticate or block browsing.
- `demo_portal/`: loopback-only example site that evaluates submitted demo signals and enforces its demonstration resource decision on the server.

## Run the controlled demo portal

From the `SecureAir` directory, install development requirements, then run:

```powershell
python -m uvicorn demo_portal.app:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. Submit the example sequence/challenge/score fields; when the policy returns `ALLOW`, the server issues a short-lived HttpOnly, SameSite cookie tied to a server-side demo session. The `/protected` route checks that server-side session rather than trusting a client-side display flag. `/logout` revokes that session. The app rejects non-loopback clients.

**This is only a control-flow demonstration.** The page lets the visitor submit every signal, including a behavioral score, so those values can be forged. The session is in-memory and is lost on process restart; it is not a user account or a secure login. Never use this portal or its cookie to protect real data. It is not integrated with the camera, identity model, dynamic challenge service, browser extension, or API token. Keep it bound to loopback.

## Browser extension: local status only

For Chrome/Chromium, enable developer mode in the extension manager and load the unpacked `extension/` folder. Add DNS hostnames through its options page. The popup checks the active tab only after you click the extension action and shows an exact-host match from extension-local storage. Permissions are limited to `activeTab` and `storage`; there are no host permissions, content scripts, web-request hooks, or remote calls. Extension settings do not sync with Python SQLite. The extension neither monitors in the background nor authenticates or blocks access. Never put the API bearer secret in the extension.

## SQLite and protected-site preferences

Use `settings.data_dir / "secureair.sqlite3"`. `initialize_database(database_path(settings))` creates schema v2 or transactionally migrates a verified SecureAir v1 database. Unmarked/foreign databases are refused; the legacy Flask database remains untouched. `ProtectedSiteStore` manages explicit normalized exact hostnames; a parent domain does not implicitly include subdomains. These are preferences, not browser enforcement.

Enrollment features and event metadata are local but not encrypted. Obtain consent and protect the data directory and backups. Event fields are allowlisted and avoid credentials, free text, raw camera data, and gesture sequences; events are not yet tamper-evident.

## Run the local API

From this `SecureAir` directory in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python -m backend.app
```

The API defaults to `127.0.0.1:8000`; functional routes require a bearer token. Do not expose it to a network. Challenges are process-local and disappear on restart. API signals are caller-supplied; camera provenance and an identity model are not integrated.

## Checks and privacy

```powershell
python -m pytest
ruff check .
```

These checks have not been run in this environment. Obtain consent before camera use. Never commit secrets, local profiles, or databases. The existing Flask project remains separate; its legacy test runner deletes its database, so run it only against a disposable clone.
