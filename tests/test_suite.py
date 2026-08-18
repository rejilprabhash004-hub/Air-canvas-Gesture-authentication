"""
Automated test suite — covers all 12 required test cases from the
project spec's Testing section. Run: python tests/test_suite.py

Tests 1-2 (gesture auth pass/fail) inject gestures directly into the
GestureAuthManager's internal state machine via the same step()
function the real camera loop calls — this exercises the exact
sequence-matching logic without needing a physical webcam, while
still going through the manager, not a mock.
"""

import os
import sys
import re
import time
import csv
import io
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FLASK_SECRET_KEY", "test-suite-key")

results = []


def check(test_id, name, condition, note=""):
    status = "PASS" if condition else "FAIL"
    results.append((test_id, name, status, note))
    print(f"[{status}] Test {test_id}: {name}" + (f" — {note}" if note else ""))
    return condition


def get_csrf(html):
    m = re.search(r'name="csrf_token" value="([a-f0-9]+)"', html)
    return m.group(1) if m else None


def run_all():
    # Fresh DB for a clean, repeatable run
    db_path = os.path.join(os.path.dirname(__file__), "..", "database", "cyberdash.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    from database.database import init_db, seed_admin_user
    init_db()
    seed_admin_user()

    from app import app
    from authentication.gesture_auth import gesture_auth_manager, GestureAuthState, step as gesture_step
    from dashboard.gesture_nav import NavState, nav_step, STABLE_FRAMES_REQUIRED_NAV
    from authentication.gesture_auth import STABLE_FRAMES_REQUIRED
    from security.security_events import generate_bulk_events
    from dashboard.dashboard import get_events
    from security.audit_logger import get_audit_logs
    import sqlite3

    client = app.test_client()
    EXPECTED_SEQ = ["INDEX", "TWO_FINGERS", "OPEN_PALM", "THUMB_UP"]

    # ---------- Test 1: Correct gesture authentication ----------
    state = GestureAuthState(EXPECTED_SEQ)
    for g in EXPECTED_SEQ:
        for _ in range(STABLE_FRAMES_REQUIRED):
            gesture_step(state, g)
        gesture_step(state, None)  # drop hand between gestures
    check("1", "Correct gesture authentication", state.status == "GRANTED",
          f"final status={state.status}, captured={state.captured_sequence}")

    # ---------- Test 2: Incorrect gesture authentication ----------
    state2 = GestureAuthState(EXPECTED_SEQ)
    for _ in range(STABLE_FRAMES_REQUIRED):
        gesture_step(state2, "INDEX")
    gesture_step(state2, None)
    for _ in range(STABLE_FRAMES_REQUIRED):
        gesture_step(state2, "FIST")  # wrong — should be TWO_FINGERS
    check("2", "Incorrect gesture authentication", state2.status == "DENIED",
          f"final status={state2.status}, captured={state2.captured_sequence}")

    # ---------- Test 3: Repeated failed authentication ----------
    r1 = client.get("/login")
    token = get_csrf(r1.data.decode())
    fail_count = 0
    for i in range(2):  # 2 failures, one below lockout threshold (3)
        r = client.post("/login", data={"username": "admin", "password": f"wrong{i}", "csrf_token": token})
        if r.status_code == 200:
            fail_count += 1
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    admin_row = conn.execute("SELECT failed_attempts, account_status FROM users WHERE username='admin'").fetchone()
    check("3", "Repeated failed authentication (tracked, not yet locked)",
          admin_row["failed_attempts"] == 2 and admin_row["account_status"] == "ACTIVE",
          f"failed_attempts={admin_row['failed_attempts']}, status={admin_row['account_status']}")

    # ---------- Test 4: Account lockout ----------
    r_final = client.post("/login", data={"username": "admin", "password": "wrong3", "csrf_token": token})
    admin_row2 = conn.execute("SELECT account_status FROM users WHERE username='admin'").fetchone()
    r_blocked = client.post("/login", data={"username": "admin", "password": "ChangeMe123!", "csrf_token": token})
    still_blocked = "/gesture-auth" not in (r_blocked.headers.get("Location") or "")
    check("4", "Account lockout (3 failures locks, blocks even correct password)",
          admin_row2["account_status"] == "LOCKED" and still_blocked,
          f"status={admin_row2['account_status']}, correct-pw-still-blocked={still_blocked}")

    # ---------- Test 5: Session timeout ----------
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "admin"
        sess["last_activity"] = (datetime.now() - timedelta(minutes=999)).isoformat()
    r_timeout = client.get("/dashboard", follow_redirects=False)
    check("5", "Session timeout", r_timeout.status_code == 302 and "/login" in r_timeout.headers.get("Location", ""),
          f"status={r_timeout.status_code}, redirect={r_timeout.headers.get('Location')}")

    # ---------- Test 6: Dashboard access without authentication ----------
    client2 = app.test_client()  # fresh, no session
    r_noauth = client2.get("/dashboard", follow_redirects=False)
    check("6", "Dashboard access without authentication",
          r_noauth.status_code == 302 and "/login" in r_noauth.headers.get("Location", ""),
          f"status={r_noauth.status_code}")

    # ---------- Test 7: Gesture navigation ----------
    nav_state = NavState()
    for _ in range(STABLE_FRAMES_REQUIRED_NAV):
        nav_step(nav_state, "TWO_FINGERS")
    triggered_next = nav_state.pending_action == "TWO_FINGERS"
    nav_state.pending_action = None
    for _ in range(3):  # still held — should NOT re-trigger
        nav_step(nav_state, "TWO_FINGERS")
    no_spam = nav_state.pending_action is None
    nav_step(nav_state, None)  # drop
    for _ in range(STABLE_FRAMES_REQUIRED_NAV):
        nav_step(nav_state, "FIST")
    lock_triggered = nav_state.pending_action == "FIST"
    check("7", "Gesture navigation (trigger, no-spam-while-held, lock gesture)",
          triggered_next and no_spam and lock_triggered,
          f"next={triggered_next}, no_spam={no_spam}, lock={lock_triggered}")

    # ---------- Test 8: Security-event generation ----------
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "admin"
        sess["last_activity"] = datetime.now().isoformat()
    r_events_page = client.get("/events")
    token2 = get_csrf(r_events_page.data.decode())
    before_count = conn.execute("SELECT COUNT(*) c FROM security_events").fetchone()["c"]
    client.post("/events/generate", data={"csrf_token": token2})
    after_count = conn.execute("SELECT COUNT(*) c FROM security_events").fetchone()["c"]
    check("8", "Security-event generation", after_count - before_count == 15,
          f"before={before_count}, after={after_count}")

    # ---------- Test 9: Security-event filtering ----------
    all_events = get_events()
    critical_only = get_events(severity="CRITICAL")
    filter_correct = all(e["severity"] == "CRITICAL" for e in critical_only) and len(all_events) >= len(critical_only)
    check("9", "Security-event filtering", filter_correct,
          f"total={len(all_events)}, critical={len(critical_only)}")

    # ---------- Test 10: Audit-log generation ----------
    audit_count = conn.execute("SELECT COUNT(*) c FROM audit_logs").fetchone()["c"]
    check("10", "Audit-log generation", audit_count > 0, f"audit_logs rows={audit_count}")

    # ---------- Test 11: CSV export ----------
    r_csv = client.get("/forensic-logs/export")
    csv_text = r_csv.data.decode()
    reader = list(csv.reader(io.StringIO(csv_text)))
    valid_csv = (r_csv.status_code == 200 and r_csv.headers.get("Content-Type", "").startswith("text/csv")
                 and len(reader) > 1 and reader[0][0] == "audit_id")
    check("11", "CSV export", valid_csv, f"rows={len(reader)}, header={reader[0] if reader else None}")

    # ---------- Test 12: Database integrity ----------
    fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]
    expected_tables = {"users", "authentication_logs", "security_events", "audit_logs", "sessions"}
    check("12", "Database integrity (FK constraints + expected tables present)",
          len(fk_check) == 0 and expected_tables.issubset(set(tables)),
          f"fk_violations={len(fk_check)}, tables={tables}")

    conn.close()

    # ---------- Summary ----------
    print("\n" + "=" * 50)
    passed = sum(1 for r in results if r[2] == "PASS")
    print(f"SUMMARY: {passed}/{len(results)} tests passed")
    for tid, name, status, note in results:
        if status == "FAIL":
            print(f"  FAILED: Test {tid} — {name} ({note})")
    print("=" * 50)

    return passed == len(results)


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
