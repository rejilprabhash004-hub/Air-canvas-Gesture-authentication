"""
Dashboard aggregation queries.

Every query here is read-only and uses parameterized SQL (even where
a value is a constant today, to keep the pattern consistent and safe
against future changes). This module is the single place the
dashboard route pulls data from — templates never query the DB
directly.
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import get_db_connection


def get_summary_counts():
    """
    Returns the Module 4 summary-tile counts as a dict.
    """
    conn = get_db_connection()
    try:
        def count(sql, params=()):
            return conn.execute(sql, params).fetchone()["c"]

        return {
            "total_events": count("SELECT COUNT(*) AS c FROM security_events"),
            "critical_events": count("SELECT COUNT(*) AS c FROM security_events WHERE severity = ?", ("CRITICAL",)),
            "high_events": count("SELECT COUNT(*) AS c FROM security_events WHERE severity = ?", ("HIGH",)),
            "medium_events": count("SELECT COUNT(*) AS c FROM security_events WHERE severity = ?", ("MEDIUM",)),
            "low_events": count("SELECT COUNT(*) AS c FROM security_events WHERE severity = ?", ("LOW",)),
            "failed_logins": count("SELECT COUNT(*) AS c FROM authentication_logs WHERE result = ?", ("DENIED",)),
            "successful_logins": count("SELECT COUNT(*) AS c FROM authentication_logs WHERE result = ?", ("GRANTED",)),
            "suspicious_ips": count(
                "SELECT COUNT(DISTINCT source_ip) AS c FROM security_events WHERE event_type = ?",
                ("SUSPICIOUS_IP",),
            ),
            "port_scan_events": count(
                "SELECT COUNT(*) AS c FROM security_events WHERE event_type = ?", ("PORT_SCAN",)
            ),
            "malware_alerts": count(
                "SELECT COUNT(*) AS c FROM security_events WHERE event_type = ?", ("MALWARE_DETECTED",)
            ),
            "firewall_blocks": count(
                "SELECT COUNT(*) AS c FROM security_events WHERE event_type = ?", ("FIREWALL_BLOCK",)
            ),
        }
    finally:
        conn.close()


def get_severity_breakdown():
    """Returns [{"severity": "HIGH", "count": 4}, ...] for the severity chart."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT severity, COUNT(*) AS count FROM security_events GROUP BY severity"
        ).fetchall()
        return [{"severity": r["severity"], "count": r["count"]} for r in rows]
    finally:
        conn.close()


def get_event_timeline(days=7):
    """
    Returns [{"date": "2026-08-06", "count": 3}, ...] for the last N days
    (including days with zero events, so the chart's x-axis is continuous).
    """
    conn = get_db_connection()
    try:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        rows = conn.execute(
            """
            SELECT DATE(timestamp) AS day, COUNT(*) AS count
            FROM security_events
            WHERE DATE(timestamp) >= ?
            GROUP BY DATE(timestamp)
            """,
            (since,),
        ).fetchall()
        counts_by_day = {r["day"]: r["count"] for r in rows}

        timeline = []
        for i in range(days):
            day = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            timeline.append({"date": day, "count": counts_by_day.get(day, 0)})
        return timeline
    finally:
        conn.close()


def get_top_suspicious_ips(limit=5):
    """Returns [{"source_ip": "192.168.1.25", "count": 6}, ...] ranked by event volume."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT source_ip, COUNT(*) AS count
            FROM security_events
            GROUP BY source_ip
            ORDER BY count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [{"source_ip": r["source_ip"], "count": r["count"]} for r in rows]
    finally:
        conn.close()


def get_auth_stats():
    """Returns granted vs denied counts from authentication_logs for the auth-stats chart."""
    conn = get_db_connection()
    try:
        granted = conn.execute(
            "SELECT COUNT(*) AS c FROM authentication_logs WHERE result = ?", ("GRANTED",)
        ).fetchone()["c"]
        denied = conn.execute(
            "SELECT COUNT(*) AS c FROM authentication_logs WHERE result = ?", ("DENIED",)
        ).fetchone()["c"]
        return {"granted": granted, "denied": denied}
    finally:
        conn.close()


def get_recent_alerts(limit=10):
    """
    Returns the most recent security_events, highest severity first
    within recency, for the 'Recent security alerts' table.
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT event_id, event_type, severity, source_ip, status, timestamp
            FROM security_events
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_events(event_type=None, severity=None, limit=200):
    """
    Returns security_events filtered by optional event_type/severity,
    most recent first. Used by the /events page. Both filters use
    parameterized queries even though values come from a constrained
    dropdown, per the project's SQL-injection-prevention requirement.
    """
    conn = get_db_connection()
    try:
        query = "SELECT event_id, event_type, severity, source_ip, description, status, timestamp FROM security_events WHERE 1=1"
        params = []
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
