# SecureAir

**Stage 13: explicit protected-site settings.** This remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection and validated 21-point landmarks; camera frames are transient and not stored.
- Geometric gesture classification and a release-aware ordered-sequence state machine.
- Consent-based local enrollment of 10–20 feature vectors and profile deletion. Profiles and feature data are sensitive, unencrypted local data; protect files and backups.
- Palm-normalized motion feature extraction and Random Forest/RBF SVM evaluation with session-disjoint splits. No real labeled dataset or performance claims are included.
- Unpredictable, user-bound, expiring, single-use challenges in process memory.
- Fail-closed decision policy and loopback FastAPI service. The service currently trusts caller-supplied gesture observations and scores; it is not a production authentication boundary.
- Isolated SecureAir SQLite database and privacy-conscious allowlisted security event logger. Events are not yet hash-chained.
- `backend/protected_sites.py`: persistent explicit hostname settings with add/list/enable/disable/remove operations and exact-host matching. It performs no browser monitoring.

## Protected-site settings

Use only the dedicated SecureAir database. Add a domain explicitly, then query/update the exact hostname:

```python
from datetime import datetime, timezone
from backend.config import load_settings
from backend.database import database_path, initialize_database
from backend.protected_sites import ProtectedSiteStore

settings = load_settings()
db_path = initialize_database(database_path(settings))  # migrates verified SecureAir v1 to v2
sites = ProtectedSiteStore(db_path)
now = datetime.now(timezone.utc).isoformat()
sites.add("example.com", timestamp=now)
print(sites.list())
print(sites.is_enabled("example.com"))
sites.set_enabled("example.com", False, timestamp=datetime.now(timezone.utc).isoformat())
sites.remove("example.com")
```

Hostnames are normalized to lowercase ASCII IDNA and stored as exact fully-qualified DNS names; URLs, paths, ports, and IP literals are rejected. Adding `example.com` does **not** implicitly configure `shop.example.com`. This store is only user-managed settings: it does not monitor or block browsing, and no extension integration exists yet. The schema migration upgrades only a verified SecureAir v1 database transactionally; unmarked or foreign databases remain refused and the legacy Flask database is untouched.

## Database and privacy

The dedicated file is `settings.data_dir / "secureair.sqlite3"`. Stored enrollment feature JSON and event metadata are local but not encrypted. Obtain consent and protect the data directory/backups. Security event fields are allowlisted and avoid free text, secrets, raw camera data, and gesture sequences; events are not yet tamper-evident.

## Run local API

From this `SecureAir` directory in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python -m backend.app
```

The API defaults to `127.0.0.1:8000`; functional routes require a bearer token. Do not expose it to a network. Current challenge observations and scores are caller supplied and forgeable; the webcam/detector and identity model are not integrated. Challenge state disappears on process restart.

## Checks

```powershell
python -m pytest
ruff check .
```

These checks have not been run in this environment. Camera preview is optional and requires user consent. Never commit secrets, profiles, or local databases. The original Flask project remains separate; its legacy test runner deletes its database, so run that only against a disposable clone.

See `docs/architecture.md`, `docs/development-plan.md`, and `docs/threat-model.md` for boundaries and limitations.
