# SecureAir

**Stage 14: minimal Manifest V3 explicit-site status extension.** SecureAir remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are transient and not saved.
- Consent-based local enrollment and gesture-classification model evaluation. There is no real labeled biometric dataset and no validated identity-confidence model; no biometric accuracy claim is made.
- User-bound expiring challenges, transparent fail-closed decision policy, and loopback FastAPI prototype. The API trusts caller-supplied gesture observations and scores; it is not a production login boundary.
- Isolated SQLite schema, allowlisted privacy-conscious event logger, and exact-host protected-site settings. Stored features and event metadata are local, not encrypted; events are not yet hash-chained.
- `extension/`: minimal Manifest V3 popup/options UI for a user-managed explicit-host status list.

## Browser extension: local status only

To try in Chrome/Chromium, open the browser's extension management page, enable developer mode, and load the unpacked `SecureAir/extension` folder. Add hostnames explicitly in the extension's options page. The toolbar popup checks the active tab only after you click the extension action, then displays an exact-host match from extension-local storage.

The extension requests only `activeTab` and `storage`; it has no host permissions, content scripts, web-request hooks, or remote network calls. Settings are stored in the browser extension's local storage and are not synchronized with the Python SQLite store. Parent hosts do not automatically cover subdomains. The UI is informational: it does not authenticate users, monitor browsing in the background, or block or protect access to sites. Do not put the API bearer secret in the extension. A secure extension-to-service authentication design is not implemented.

## Protected-site settings in the Python store

The backend separately stores explicit exact DNS hostnames in `settings.data_dir / "secureair.sqlite3"`. It normalizes domains to lowercase IDNA ASCII and rejects URLs, paths, ports, and IP literals. Initialization uses schema v2 and migrates only a verified SecureAir v1 database transactionally; unmarked or foreign databases are refused, and the legacy Flask database is untouched. Backend settings do not automatically sync with the extension.

## Local API

From this `SecureAir` directory in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python -m backend.app
```

The API defaults to `127.0.0.1:8000`; functional routes require a bearer token. Do not expose it to a network. Challenges are process-local and disappear on restart. API gesture observations and behavioral scores are caller-supplied and forgeable; camera/detector provenance and an identity model are not integrated.

## Checks and privacy

```powershell
python -m pytest
ruff check .
```

These checks have not been run in this environment. Obtain consent before any camera use. Never commit secrets, local profiles, or database files. SecureAir's enrollment feature values are sensitive and unencrypted; protect the data directory and backups. The original Flask project remains separate; its legacy test runner deletes its database, so run it only against a disposable clone.
