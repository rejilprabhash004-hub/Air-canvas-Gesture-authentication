# Staged development plan

Each stage should be reviewed and its automated checks run before the next. Keep the existing Flask app/database separate. Its current test runner deletes its database; only run that against a disposable clone.

| Stage | Deliverable | Gate before proceeding |
|---|---|---|
| 1 | Isolated scaffold, validated configuration, architecture/threat docs, tests | Scaffold tests/lint pass; legacy files unchanged |
| 2 | Local one-hand MediaPipe capture and landmarks | Synthetic tests; manual camera check; no frame persistence |
| 3 | Geometric classifier for five static gestures | Tests for known, ambiguous, absent, multiple hands |
| 4 | Gesture sequence state machine | Correct/wrong/repetition/timeout tests |
| 5 | Consent-based enrollment of 10–20 normalized samples; local deletion | Consent, sample validation, path safety, no-overwrite, deletion tests; disclose plaintext profile storage |
| 6 | Palm-normalized motion summaries from timestamped landmarks | Timing/order, normalization, movement-rate, malformed and out-of-frame tests |
| 7 | Random Forest/SVM evaluator with session-disjoint holdout and standard classification metrics | Pipeline behavior tests; real performance claims require labeled multi-session data and measured results |
| 8 | User-bound expiring single-use gesture challenges | Tests for profile binding, unpredictable IDs, expiry, wrong-response consumption, one-time use, invalid input, and purge behavior |
| 9 | Transparent combined decision policy | Tests for fail-closed behavior, threshold boundaries, invalid signals, and structured failure reasons; behavioral match score source must be explicitly supplied |
| 10 | Loopback FastAPI service with local bearer protection | API tests; refuse non-loopback binds/clients; document trusted-input and identity-model limitations |
| 11 | Secure SQLite schema | Foreign-key/schema tests; no legacy DB changes |
| 12 | Authentication/security event logger | Privacy and failure-path tests |
| 13 | Explicit protected-site settings | Add/remove/enable/disable tests |
| 14 | Minimal Manifest V3 extension | Configured domains only; no credential/page-content access |
| 15 | Controlled demo portal | Server-side authorization tests |
| 16 | End-to-end integration | Integration and manual demonstration |
| 17 | Local activity dashboard | Query/filter/privacy tests |
| 18 | Explicit-domain activity events | Confirm arbitrary browsing is not monitored |
| 19 | Canonical event hashes | Determinism and tamper tests |
| 20 | Transactional hash chain | Valid chain and altered-row detection |
| 21 | PDF/CSV/JSON reports | Content/privacy/export tests |
| 22 | Report hash verification | File hash and tamper tests |
| 23 | Security review | Threat-model checks and limitations |
| 24 | UI improvements | Accessibility and regression tests |
| 25 | Final docs and viva guide | Reproducible Windows install and demo |

The Stage 9 policy combines status signals only; it does not compute or calibrate user identity. The current classifier/evaluator predicts gesture classes, and the repository has no real labeled biometric dataset. Stage 10 API observations and scores are caller supplied and forgeable until a trusted local detector/model is integrated. Challenges remain process-local. A passing unit test is not proof of camera accuracy, identity assurance, or production security.
