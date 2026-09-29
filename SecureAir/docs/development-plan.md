# Staged development plan

SecureAir is developed separately from the legacy Flask application. Run automated checks before release; passing unit tests do not prove camera accuracy, identity assurance, or production security. The legacy test runner deletes its database; run it only against a disposable clone.

| Stage | Deliverable | Gate before release |
|---|---|---|
| 1 | Isolated scaffold, validated configuration, architecture/threat docs, tests | Scaffold tests/lint; legacy files unchanged |
| 2 | Local one-hand MediaPipe capture and landmarks | Synthetic tests; manual camera check; no frame persistence |
| 3 | Geometric classifier for five static gestures | Known, ambiguous, absent, multiple-hand tests |
| 4 | Gesture sequence state machine | Correct/wrong/repetition/timeout tests |
| 5 | Consent-based enrollment of 10–20 normalized samples; local deletion | Consent, validation, path safety, no-overwrite, deletion tests; disclose plaintext storage |
| 6 | Palm-normalized motion summaries | Timing/order, normalization, malformed and out-of-frame tests |
| 7 | Random Forest/SVM evaluator with session-disjoint holdout | Pipeline tests; performance claims need labeled multi-session data and measurements |
| 8 | User-bound expiring single-use challenges | Binding, unpredictability, expiry, replay, wrong-response consumption, invalid-input tests |
| 9 | Transparent combined decision policy | Fail-closed behavior, threshold boundary, invalid-signal, reason tests; score source explicit |
| 10 | Loopback FastAPI service with bearer protection | API tests; reject non-loopback binds/clients; document trusted-input/model limitations |
| 11 | Separate SecureAir SQLite schema | Schema, foreign-key, transaction, migration, legacy DB isolation tests |
| 12 | Privacy-conscious security event logger | Allowlist, redaction, database failure, privacy tests; no secrets/biometrics in logs |
| 13 | Explicit protected-site settings | Host normalization, exact matching, CRUD, v1-to-v2 migration, legacy DB isolation tests |
| 14 | Minimal Manifest V3 status extension | Explicit hosts only; least privilege; no background browsing, credentials, page-content access, or remote calls |
| 15 | Controlled local demo portal | Server-side authorization tests; loopback-only; disclose forgeable demo inputs and process-local session state |
| 16 | Portal-to-loopback API challenge/decision integration | Single-use challenge/replay, bearer secrecy, fail-closed errors, server-side authorization, end-to-end integration tests |
| 17 | Read-only local activity dashboard queries | Token validation, read-only DB access, minimized event fields, exact filters, pagination, privacy tests |
| 18 | Explicit-domain extension-local status-check events | Only user-opened popup checks for enabled exact hosts; local storage, bounded history, clear control, no background collection, page data, or network transfer |
| 19 | Canonical event hashes | Deterministic canonical JSON, SHA-256 test vectors, altered-field sensitivity, invalid-record rejection; no database writes |
| 20 | Transactional hash chain | Atomic append, v2-to-v3 backfill migration, chain verification, tamper detection, profile-deletion compatibility, rollback and privacy tests |
| 21 | PDF/CSV/JSON reports | Content/privacy/export tests |
| 22 | Report hash verification | File hash and tamper tests |
| 23 | Security review | Threat-model checks and limitations |
| 24 | UI improvements | Accessibility and regression tests |
| 25 | Final docs and viva guide | Reproducible Windows install and demo |

## Current limitations

The gesture model classifies gestures; there is no real labeled biometric dataset or validated user-identity confidence model. The API accepts caller-supplied, forgeable observations/scores; camera provenance is not integrated. Challenges are process-local. Backend security events are hash-chained in local SQLite after transactional schema-v3 migration, but the chain has no external trust anchor: someone who can rewrite the database can recompute it. SQLite feature and event data is not encrypted. Protected-site settings are exact-host preferences only. The Stage 14 extension stores a separate local list and shows status after an explicit toolbar click; it does not monitor, block, or authenticate. Stage 15 is a loopback-only control-flow demonstration with forgeable inputs and in-memory sessions. Stage 16 integrates portal and API over loopback using a server-held bearer secret, but visitor-submitted signals remain forgeable. Stage 17 adds a library-only, token-gated, read-only database query layer, not an HTTP dashboard. Stage 18 records only explicit popup checks of enabled exact-host sites, locally in extension storage; it does not collect general browsing history or sync with backend events. Stage 19 provides canonical event serialization and SHA-256. Stage 20 adds database persistence, transactional chain appends, migration, and verification; it does not anchor hashes externally. Keep all data local and the prototype educational until security review and remaining stages are complete.
