"""
Forensic/audit logging.

This is intentionally the FIRST piece of the security/ package we build,
because every module from here on (login, gesture auth, brute-force,
navigation) needs to write to the audit trail. The log-viewer UI
(search/filter/export) is added in Step 10 — this file just owns the
single write path so every caller stays consistent.

IMPORTANT: There is deliberately no update_log() or delete_log()
function anywhere in the application. Audit logs are append-only.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import get_db_connection


def log_action(user_id, action, result, ip_address, details="", event_ref=None):
    """
    Writes one row to audit_logs. Never raises on its own logging failure
    in a way that would block the calling security-relevant action from
    completing — but does print a warning so failures aren't silent.
    """
    try:
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO audit_logs (user_id, action, event_ref, result, ip_address, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, action, event_ref, result, ip_address, details),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[audit_logger] WARNING: failed to write audit log: {e}")


# ============================================================
# FORENSIC LOG VIEWER — query + export layer
#
# IMPORTANT: there is deliberately no update/delete function in this
# file. Audit logs are append-only; the UI built on top of these
# functions must never expose an edit or delete action.
# ============================================================

def get_distinct_actions():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT DISTINCT action FROM audit_logs ORDER BY action").fetchall()
        return [r["action"] for r in rows]
    finally:
        conn.close()


def get_distinct_usernames():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT u.username FROM audit_logs a
            JOIN users u ON a.user_id = u.user_id
            ORDER BY u.username
            """
        ).fetchall()
        return [r["username"] for r in rows]
    finally:
        conn.close()


def _build_filtered_query(action=None, severity=None, date_from=None, date_to=None,
                           username=None, search=None):
    """
    Shared WHERE-clause builder for both the on-screen viewer and CSV
    export, so the two never drift out of sync. Returns (sql, params)
    for the SELECT columns the caller wants appended after FROM/JOIN.
    """
    where = ["1=1"]
    params = []

    if action:
        where.append("a.action = ?")
        params.append(action)
    if severity:
        where.append("s.severity = ?")
        params.append(severity)
    if date_from:
        where.append("DATE(a.timestamp) >= ?")
        params.append(date_from)
    if date_to:
        where.append("DATE(a.timestamp) <= ?")
        params.append(date_to)
    if username:
        where.append("u.username = ?")
        params.append(username)
    if search:
        where.append("(a.details LIKE ? OR a.action LIKE ?)")
        like_term = f"%{search}%"
        params.extend([like_term, like_term])

    return " AND ".join(where), params


_BASE_FROM = """
    FROM audit_logs a
    LEFT JOIN users u ON a.user_id = u.user_id
    LEFT JOIN security_events s ON a.event_ref = s.event_id
"""


def get_audit_logs(action=None, severity=None, date_from=None, date_to=None,
                    username=None, search=None, limit=300):
    where_sql, params = _build_filtered_query(action, severity, date_from, date_to, username, search)
    conn = get_db_connection()
    try:
        query = f"""
            SELECT a.audit_id, a.timestamp, u.username, a.action, a.event_ref,
                   s.severity, a.result, a.ip_address, a.details
            {_BASE_FROM}
            WHERE {where_sql}
            ORDER BY a.timestamp DESC
            LIMIT ?
        """
        rows = conn.execute(query, params + [limit]).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def export_audit_logs_csv(action=None, severity=None, date_from=None, date_to=None,
                           username=None, search=None):
    """
    Returns CSV text for the SAME filtered result set get_audit_logs()
    would show (no row limit on export, since it's for offline record-
    keeping rather than on-screen browsing).
    """
    import csv
    import io

    where_sql, params = _build_filtered_query(action, severity, date_from, date_to, username, search)
    conn = get_db_connection()
    try:
        query = f"""
            SELECT a.audit_id, a.timestamp, u.username, a.action, a.event_ref,
                   s.severity, a.result, a.ip_address, a.details
            {_BASE_FROM}
            WHERE {where_sql}
            ORDER BY a.timestamp DESC
        """
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["audit_id", "timestamp", "username", "action", "event_ref",
                      "severity", "result", "ip_address", "details"])
    for r in rows:
        writer.writerow([r["audit_id"], r["timestamp"], r["username"] or "", r["action"],
                          r["event_ref"] or "", r["severity"] or "", r["result"] or "",
                          r["ip_address"] or "", r["details"] or ""])
    return output.getvalue()
