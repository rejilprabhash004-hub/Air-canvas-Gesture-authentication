# SecureAir

**Stage 12: privacy-conscious security event logger.** This remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection and validated 21-point landmarks; camera frames are transient and not stored.
- Geometric gesture classification and a release-aware ordered-sequence state machine.
- Consent-based local enrollment of 10–20 feature vectors and profile deletion. Profiles and feature data are sensitive, unencrypted local data; protect files and backups.
- Palm-normalized motion feature extraction and Random Forest/RBF SVM evaluation with session-disjoint splits. No real labeled dataset or performance claims are included.
- Unpredictable, user-bound, expiring, single-use challenges in process memory.
- Fail-closed decision policy and loopback FastAPI service. The service currently trusts caller-supplied gesture observations and match scores; it is not a production authentication boundary.
- An isolated SecureAir SQLite database with profile, enrollment sample, and event tables. Initialization refuses unrelated/unmarked databases and does not modify the legacy Flask database.
- `backend/security_events.py`: SQLite security-event writer with allowlisted event types, outcomes, reason codes, and components. It rejects free-form details and does not accept credentials, challenge IDs, video, landmarks, or gesture sequences.

## Event logging

Initialize the separate SecureAir DB and record minimized event metadata:

```python
from backend.config import load_settings
from backend.database import database_path, initialize_database
from backend.security_events import SecurityEventLogger

settings = load_settings()
db_path = initialize_database(database_path(settings))
logger = SecurityEventLogger(db_path)
logger.record(
    "auth_attempt",
    "denied",
    profile_id="local_user_1",  # pseudonymous local ID, not a name/email
    reason_code="challenge_failed",
    http_status=401,
    component="decision",
)
```

The logger stores UTC timestamps and allowlisted structured metadata only. Use a pseudonymous profile ID; do not log secrets, tokens, user-supplied text, raw frames/landmarks, gesture sequences, or model features. The logger is not a tamper-evident audit system; hash chaining is a later stage. Event and enrollment data remain local but are not encrypted. Apply OS-level protection to the data directory and backups.

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

The API defaults to `127.0.0.1:8000`; functional routes require a bearer token. Do not expose it to a network. Current challenge API observations and scores are caller supplied and forgeable; the webcam/detector and identity model are not integrated. Challenge state disappears on process restart.

## Checks

```powershell
python -m pytest
ruff check .
```

These checks have not been run in this environment. Camera preview is optional and requires user consent. Never commit secrets, profiles, or local databases. The original Flask project remains separate; its legacy test runner deletes its database, so run that only against a disposable clone.

See `docs/architecture.md`, `docs/development-plan.md`, and `docs/threat-model.md` for boundaries and limitations.
