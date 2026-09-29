# SecureAir

**Stage 24: extension accessibility improvements.** SecureAir remains an educational research prototype, not an authentication system.

## Implemented components

- Local MediaPipe hand detection, normalized landmarks, five geometric gesture labels, and an ordered sequence state machine. Camera frames are processed locally and not stored.
- Consent-based enrollment and gesture-classification evaluation. No labeled biometric dataset or validated identity-confidence model is included; no accuracy claim is made.
- User-bound, expiring, single-use challenges; fail-closed decisions; and a loopback FastAPI API. Gesture observations and behavioral scores remain caller-supplied and forgeable.
- Isolated SQLite schema, privacy-conscious event logger, and exact-host site preferences. Stored features are local and unencrypted.
- A minimal Manifest V3 extension and a loopback demo portal. The extension records only user-opened popup checks for enabled exact-host sites in local storage; it does not monitor or block in the background.
- `backend/activity_dashboard.py`: token-gated, read-only, paginated schema-v3 queries. It verifies the complete event chain in the same SQLite read snapshot before returning minimized metadata.
- `backend/security_event_hashes.py`, `backend/security_event_chain.py`, `backend/event_reports.py`, and `backend/report_integrity.py`: event hash chain, privacy-minimized local PDF/CSV/JSON reports, and exact-byte SHA-256 helpers.

## Extension accessibility

The popup and options page use visible `:focus-visible` indicators, higher-contrast control borders and text, 44px minimum button/input heights, and forced-colors adjustments. Status text is exposed via existing live/status regions, and options inputs retain explicit labels. Static regression tests assert these properties.

These CSS and markup checks do not establish WCAG conformance. Manually test keyboard-only navigation, screen-reader announcements, zoom/reflow, forced-colors/high-contrast, and real browser rendering before claiming accessibility compliance. The extension remains a local status preference only; it does not authenticate users or block navigation.

## Security and privacy limits

Direct profile deletion is blocked by a SQLite trigger and routed through the chain-aware deletion helper. Dashboard queries reject invalid chain history; report inputs are capped during iteration at 10,000 rows and text values at 256 characters. These application-level controls do not withstand local administrator/database-file tampering. The chain has no external trust anchor, and reports remain private unencrypted local files.

API observations and behavioral scores are caller-supplied and forgeable. Never use this prototype to protect real accounts or resources. The extension has no host permissions, page-content access, background browsing collection, or remote calls.

## Local validation

From `SecureAir` in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m pytest
ruff check .
```

No local test, lint, manual assistive-technology, camera, or dynamic security results are claimed here. Keep database files, reports, and digests private; never commit secrets, profiles, or local data.
