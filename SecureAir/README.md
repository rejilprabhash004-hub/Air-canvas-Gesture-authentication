# SecureAir

**Stage 11: isolated SQLite schema.** This remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detector and validated 21-point landmarks; camera frames are transient and are not stored.
- Geometric classifier for Open Palm, Fist, Thumbs Up, Victory, and Pointing, plus a release-aware gesture-sequence state machine.
- Consent-based local enrollment of 10–20 feature vectors and profile deletion. Profiles are sensitive, unencrypted files; protect data directories and backups.
- Palm-normalized temporal feature extraction and a Random Forest/RBF SVM evaluation pipeline using session-disjoint splits. No labeled real-world dataset is included and no performance claims are made.
- User-bound, expiring, single-use challenge manager. Challenge state is in-memory and disappears on restart.
- Fail-closed decision policy and loopback FastAPI endpoints. The API currently accepts caller-supplied gesture observations and match scores, not trusted camera/model results.
- `backend/database.py`: separate `secureair.sqlite3` schema under the configured SecureAir data directory, with profiles, enrollment samples, and security events.

## SQLite isolation and initialization

Initialize only at the dedicated path `settings.data_dir / "secureair.sqlite3"`:

```python
from backend.config import load_settings
from backend.database import database_path, initialize_database

settings = load_settings()
path = initialize_database(database_path(settings))
print(path)
```

Initialization marks the database with a SecureAir application ID and schema version. It refuses unmarked databases containing tables, databases marked for another application, unsupported versions, unexpected/incomplete schemas, symlink paths, and filenames other than `secureair.sqlite3`. Thus it will not modify the legacy Flask database. Connections made with `database_connection(path)` enable SQLite foreign keys and commit on success or roll back on exceptions. On POSIX systems the initialized database file is restricted to owner read/write permissions where supported.

Enrollment feature values are stored as JSON in the local database and are sensitive biometric-derived data. Obtain explicit consent and protect the data directory and its backups. This schema does not encrypt those values or claim secure deletion.

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

The API defaults to `127.0.0.1:8000`; functional routes require a bearer token. Do not expose it to a network. Current challenge API observations and scores can be forged by a caller; the webcam/detector and an identity model are not integrated.

## Checks

```powershell
python -m pytest
ruff check .
```

These checks have not been run in this environment. Camera preview is optional and requires user consent. Never commit secrets, profiles, or local databases. The original Flask project remains separate; its legacy test runner deletes its database, so run that only against a disposable clone.

See `docs/architecture.md`, `docs/development-plan.md`, and `docs/threat-model.md` for boundaries and limitations.
