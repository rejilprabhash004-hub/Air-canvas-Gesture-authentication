# Test Plan — Air-Gesture Cybersecurity Dashboard

Automated: `python tests/test_suite.py` (all 12 tests, run from project root
after `pip install -r requirements.txt`). Tests 1, 2, and 7 exercise the
pure gesture state-machine logic directly (`step()` / `nav_step()`) since
they don't require a physical camera to verify correctly; all others go
through the real Flask application via the test client. **Last run: 12/12
PASS.**

| # | Test | Method | Expected Result | Actual Result |
|---|------|--------|------------------|----------------|
| 1 | Correct gesture authentication | Feed the registered 4-gesture sequence into `GestureAuthState` via `step()`, dropping the hand between each gesture | Status becomes `GRANTED`; captured sequence matches registered sequence exactly | **PASS** — `GRANTED`, `[INDEX, TWO_FINGERS, OPEN_PALM, THUMB_UP]` |
| 2 | Incorrect gesture authentication | Feed a sequence that diverges from the registered one (`INDEX` then `FIST` instead of `TWO_FINGERS`) | Status becomes `DENIED` as soon as the mismatch occurs, without waiting for the full sequence length | **PASS** — `DENIED` after 2 gestures |
| 3 | Repeated failed authentication | 2 consecutive wrong-password POSTs to `/login` for an existing account | `failed_attempts` increments to 2; account remains `ACTIVE` (below the 3-attempt threshold) | **PASS** — `failed_attempts=2`, `status=ACTIVE` |
| 4 | Account lockout | A 3rd consecutive failure, then a 4th attempt using the *correct* password | Account status becomes `LOCKED`; the 4th attempt is blocked even with the right password | **PASS** — `LOCKED`, correct password still blocked |
| 5 | Session timeout | Set `last_activity` far in the past on an authenticated session, then request `/dashboard` | Session is cleared server-side; request redirects to `/login` | **PASS** — `302 → /login` |
| 6 | Dashboard access without authentication | Request `/dashboard` with a completely fresh (unauthenticated) client | Redirects to `/login`; dashboard content never renders | **PASS** — `302 → /login` |
| 7 | Gesture navigation | Hold `TWO_FINGERS` past the stability threshold (fires once), keep holding (must NOT re-fire), then drop and hold `FIST` | First hold fires exactly one `TWO_FINGERS` command; continuing to hold produces no further commands; `FIST` fires the lock command | **PASS** — trigger✓, no-spam✓, lock✓ |
| 8 | Security-event generation | POST `/events/generate` (15-event batch) via the real route | `security_events` row count increases by exactly 15 | **PASS** — +15 rows |
| 9 | Security-event filtering | Query `get_events()` unfiltered vs. `severity="CRITICAL"` | Filtered result is a subset of the unfiltered result; every row in the filtered set has the requested severity | **PASS** — 3 CRITICAL of 18 total, all correctly severity-matched |
| 10 | Audit-log generation | Inspect `audit_logs` row count after the above test activity | At least one row exists (in practice, every login/lockout/event-generation action logged one) | **PASS** — 7 rows |
| 11 | CSV export | GET `/forensic-logs/export` | `200` response, `text/csv` content type, valid CSV with the expected header row | **PASS** — valid CSV, correct header |
| 12 | Database integrity | `PRAGMA foreign_key_check` + verify all 5 required tables exist | Zero foreign-key violations; `users`, `authentication_logs`, `security_events`, `audit_logs`, `sessions` all present | **PASS** — 0 violations, all 5 tables present |

## Manual tests (require a physical webcam — not automatable here)

These were verified by design/inspection and via the standalone
`computer_vision/test_webcam.py` tool during Steps 4–6, but need to be
re-confirmed on your actual demo machine before your viva:

- **Live gesture detection accuracy** — run `python computer_vision/test_webcam.py`
  and confirm all 5 gestures (INDEX, TWO_FINGERS, OPEN_PALM, THUMB_UP, FIST)
  classify correctly and consistently for your hand/lighting/camera setup.
- **End-to-end login flow** — password → live gesture sequence → dashboard,
  including a deliberate wrong-gesture attempt and a lockout scenario.
- **Live gesture navigation** — enable "Gesture Nav" on the dashboard and
  confirm TWO_FINGERS/OPEN_PALM/INDEX/THUMB_UP/FIST all behave as expected
  in the browser, not just in the state-machine unit tests above.

If any of these behave differently on your machine than in this plan, the
two most likely causes (per the troubleshooting notes from Steps 4 and 6)
are lighting/distance affecting MediaPipe's confidence thresholds, or an
unpinned `mediapipe` version — both documented with fixes earlier in this
build log.
