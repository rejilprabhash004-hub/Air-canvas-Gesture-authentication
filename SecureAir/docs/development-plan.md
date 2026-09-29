# Staged development plan

Stages are built in isolation from the legacy Flask app. Automated checks should be run before release; a passing unit test is not proof of camera accuracy, identity assurance, or production security. The legacy test runner deletes its database; run it only against a disposable clone.

| Stage | Deliverable | Gate before release |
|---|---|---|
| 1 | Isolated scaffold, validated configuration, architecture/threat docs, tests | Scaffold tests/lint; legacy files unchanged |
| 2 | Local one-hand MediaPipe capture and landmarks | Synthetic tests; manual camera check; no frame persistence |
| 3 | Geometric classifier for five static gestures | Tests for known, ambiguous, absent, multiple hands |
| 4 | Gesture sequence state machine | Correct/wrong/repetition/timeout tests |
| 5 | Consent-based enrollment of 10–20 normalized samples; local deletion | Consent, sample validation, path safety, no-overwrite, deletion tests; disclose plaintext storage |
| 6 | Palm-normalized motion summaries | Timing/order, normalization, movement-rate, malformed and out-of-frame tests |
| 7 | Random Forest/SVM evaluator with session-disjoint holdout | Pipeline tests; real performance requires labeled multi-session data and measured results |
| 8 | User-bound expiring single-use challenges | Binding, unpredictability, expiry, wrong-response consumption, replay, invalid input, purge tests |
| 9 | Transparent combined decision policy | Fail-closed behavior, threshold boundaries, invalid signals, structured reasons; score source explicit |
| 10 | Loopback FastAPI service with bearer protection | API tests; reject non-loopback binds/clients; document trusted-input and model limitations |
| 11 | Separate SecureAir SQLite schema | Schema/foreign-key, migration-marker, rollback, and legacy-database non-modification tests |
| 12 | Authentication/security event logger | Privacy, redaction, failure-path tests |
| 13 | Explicit protected-site settings | Add/remove/enable/disable tests |
| 14 | Minimal Manifest V3 extension | Explicit domains only; no credential/page-content access |
| 15 | Controlled demo portal | Server-side authorization tests |
| 16 | End-to-end integration | Integration tests and manual demonstration |
| 17 | Local activity dashboard | Query/filter/privacy tests |
| 18 | Explicit-domain activity events | Confirm arbitrary browsing is not monitored |
| 19 | Canonical event hashes | Determinism and tamper tests |
| 20 | Transactional hash chain | Valid chain and altered-row detection |
| 21 | PDF/CSV/JSON reports | Content/privacy/export tests |
| 22 | Report hash verification | File hash and tamper tests |
| 23 | Security review | Threat-model checks and limitations |
| 24 | UI improvements | Accessibility and regression tests |
| 25 | Final docs and viva guide | Reproducible Windows install and demo |

## Current limitations

Stage 9 combines status signals only; it does not compute or calibrate identity. The gesture model classifies gesture labels and no real biometric dataset is tracked. Stage 10 receives caller-supplied, forgeable observations/scores; camera provenance is not integrated. Challenges are process-local. Stage 11 creates only a dedicated `secureair.sqlite3`; initialization refuses unmarked existing databases and the legacy database is not migrated or modified. Stored feature JSON is sensitive and not encrypted. Never represent the prototype as production authentication.
