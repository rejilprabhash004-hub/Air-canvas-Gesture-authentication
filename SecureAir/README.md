# SecureAir

**Stage 25: final Windows setup and viva documentation.** SecureAir remains an educational research prototype, not an authentication system.

## Quick start

The full Windows setup, loopback demo, optional camera preview, troubleshooting, architecture notes, and viva Q&A are in [`docs/windows-setup-viva-guide.md`](docs/windows-setup-viva-guide.md).

From PowerShell in the `SecureAir` directory, with Python 3.11:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python -m pytest
ruff check .
```

Do not commit or expose the generated secret. To run the API and portal, use the same secret in both local server processes; full commands and camera/extension instructions are in the setup guide. Automated tests and lint have not been run as part of this documentation update.

## Scope and implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are processed locally and not stored by the diagnostic preview.
- Consent-based enrollment and gesture-classification evaluation. No labeled biometric dataset or validated identity-confidence model is included; no accuracy claim is made.
- User-bound, expiring, single-use challenges; fail-closed decisions; and a loopback FastAPI API. Gesture observations and behavioral scores remain caller-supplied and forgeable.
- Isolated SQLite schema, privacy-conscious event logger, and exact-host site preferences. Stored features and event metadata are local and unencrypted.
- A minimal Manifest V3 extension and a loopback demo portal. The extension records only user-opened popup checks for enabled exact-host sites in local storage; it does not monitor or block in the background.
- `backend/activity_dashboard.py`: token-gated, read-only, paginated schema-v3 queries. It verifies the complete event chain in the same SQLite read snapshot before returning minimized metadata.
- `backend/security_event_hashes.py`, `backend/security_event_chain.py`, `backend/event_reports.py`, and `backend/report_integrity.py`: canonical event hashes, transactional event chain, local minimized PDF/CSV/JSON reports, and exact-byte SHA-256 helpers.

## Security, privacy, and accessibility limits

Direct profile deletion is blocked by a SQLite trigger and routed through the chain-aware deletion helper. Dashboard queries reject invalid chain history. Report inputs are capped while iterating at 10,000 rows, with text values limited to 256 characters. These application-level controls do not withstand local administrator or database-file/schema tampering. The chain has no external trust anchor; report hashes do not establish authorship or digest trust.

The extension popup and options page include visible keyboard focus, forced-colors styles, and larger interactive targets, with static regression tests. These checks do not establish WCAG conformance. Manual keyboard, screen-reader, zoom/reflow, forced-colors, browser, camera, and dynamic security validation remain necessary.

API observations and behavioral scores are caller-supplied and forgeable. Challenges and demo portal sessions are process-local. Never use this prototype to protect real accounts or resources. Keep database files, reports, and report digests private; never commit secrets, profiles, or local data.
