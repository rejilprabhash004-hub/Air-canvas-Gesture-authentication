"""
Brute-force protection.

Policy (configurable via .env — see config.py):
  - LOCKOUT_MAX_ATTEMPTS consecutive failures (default 3) locks the account
  - LOCKOUT_DURATION_MINUTES (default 5) determines how long the lock lasts
  - A failure is counted at EITHER stage of the two-factor login: wrong
    password, OR correct password but wrong/timed-out gesture sequence.
    This is a deliberate design choice for this project: since gesture
    auth is the second factor, a compromised or fumbled second factor
    is just as much a "failed login" as a wrong password, and both are
    worth logging/rate-limiting the same way.
  - Every attempt (success or failure) writes a row to authentication_logs
    with IP, timestamp, detected gesture sequence, and result — required
    for the forensic trail regardless of outcome.
"""

import json
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from database.database import get_db_connection
from security.audit_logger import log_action
from security.security_events import insert_security_event


def check_lockout(user_row):
    """
    Returns (is_locked: bool, seconds_remaining: int|None).
    If a previous lock has expired, this auto-unlocks the account in
    the database (account_status -> ACTIVE, failed_attempts -> 0) and
    returns (False, None) — lockouts are time-limited, not permanent.
    """
    if user_row["account_status"] != "LOCKED":
        return False, None

    locked_until_str = user_row["locked_until"]
    if not locked_until_str:
        return False, None

    locked_until = datetime.fromisoformat(locked_until_str)
    now = datetime.now()

    if now >= locked_until:
        # Lock has expired — auto-unlock.
        conn = get_db_connection()
        try:
            conn.execute(
                """
                UPDATE users SET account_status = 'ACTIVE', failed_attempts = 0, locked_until = NULL
                WHERE user_id = ?
                """,
                (user_row["user_id"],),
            )
            conn.commit()
        finally:
            conn.close()
        return False, None

    seconds_remaining = int((locked_until - now).total_seconds())
    return True, seconds_remaining


def _write_authentication_log(user_id, username_attempted, detected_sequence, result, ip_address):
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO authentication_logs (user_id, username_attempted, detected_sequence, result, ip_address)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username_attempted,
                json.dumps(detected_sequence) if detected_sequence is not None else None,
                result,
                ip_address,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def record_login_result(user_row, detected_sequence, ip_address, success: bool):
    """
    Call this exactly once per completed login attempt (password
    failure, gesture failure/timeout, or full success). Handles:
      - authentication_logs row
      - failed_attempts counter + lockout trigger
      - security_events row (FAILED_LOGIN or BRUTE_FORCE_SUSPECTED)
      - audit_logs entry for the lockout itself (not the attempt —
        app.py already logs PASSWORD_VERIFIED / GESTURE_AUTH_RESULT)

    Returns dict: {"locked": bool, "attempts_remaining": int|None}
    """
    user_id = user_row["user_id"]
    username = user_row["username"]

    _write_authentication_log(
        user_id=user_id,
        username_attempted=username,
        detected_sequence=detected_sequence,
        result="GRANTED" if success else "DENIED",
        ip_address=ip_address,
    )

    conn = get_db_connection()
    try:
        if success:
            conn.execute(
                """
                UPDATE users SET failed_attempts = 0, account_status = 'ACTIVE', locked_until = NULL
                WHERE user_id = ?
                """,
                (user_id,),
            )
            conn.commit()
            return {"locked": False, "attempts_remaining": None}

        # --- failure path ---
        new_count = user_row["failed_attempts"] + 1
        max_attempts = Config.LOCKOUT_MAX_ATTEMPTS

        if new_count >= max_attempts:
            locked_until = datetime.now() + timedelta(minutes=Config.LOCKOUT_DURATION_MINUTES)
            conn.execute(
                """
                UPDATE users SET failed_attempts = ?, account_status = 'LOCKED', locked_until = ?
                WHERE user_id = ?
                """,
                (new_count, locked_until.isoformat(), user_id),
            )
            conn.commit()

            insert_security_event(
                event_type="BRUTE_FORCE_SUSPECTED",
                severity="HIGH",
                source_ip=ip_address or "unknown",
                description=(
                    f"{new_count} consecutive failed login attempts for user "
                    f"'{username}'. Account locked for {Config.LOCKOUT_DURATION_MINUTES} minute(s)."
                ),
                status="BLOCKED",
            )
            log_action(
                user_id=user_id,
                action="ACCOUNT_LOCKED",
                result="LOCKED",
                ip_address=ip_address,
                details=f"Locked after {new_count} consecutive failed attempts.",
            )
            return {"locked": True, "attempts_remaining": 0}

        else:
            conn.execute(
                "UPDATE users SET failed_attempts = ? WHERE user_id = ?",
                (new_count, user_id),
            )
            conn.commit()

            insert_security_event(
                event_type="FAILED_LOGIN",
                severity="MEDIUM",
                source_ip=ip_address or "unknown",
                description=f"Failed login attempt {new_count}/{max_attempts} for user '{username}'.",
                status="INVESTIGATING",
            )
            return {"locked": False, "attempts_remaining": max_attempts - new_count}
    finally:
        conn.close()
