"""
Security event creation.

Full simulated event generator added in Step 9, on top of the same
insert_security_event() function real events (brute-force lockouts,
organic failed logins) already use — so simulated and real events are
indistinguishable in the database/dashboard, which is realistic for
a demo.
"""

import random
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import get_db_connection


def _generate_event_id(conn):
    row = conn.execute("SELECT COUNT(*) AS c FROM security_events").fetchone()
    next_num = row["c"] + 1
    # Simple retry loop guards against the (unlikely, single-process-demo)
    # case of a collision if events were ever deleted/reset out of band.
    while True:
        candidate = f"EVT{next_num:05d}"
        exists = conn.execute(
            "SELECT 1 FROM security_events WHERE event_id = ?", (candidate,)
        ).fetchone()
        if not exists:
            return candidate
        next_num += 1


def insert_security_event(event_type, severity, source_ip, description, status="INVESTIGATING"):
    """
    Inserts one row into security_events and returns the generated event_id.
    severity must be one of LOW/MEDIUM/HIGH/CRITICAL.
    """
    conn = get_db_connection()
    try:
        event_id = _generate_event_id(conn)
        conn.execute(
            """
            INSERT INTO security_events (event_id, event_type, severity, source_ip, description, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, event_type, severity, source_ip, description, status),
        )
        conn.commit()
        return event_id
    finally:
        conn.close()


# ============================================================
# SIMULATED EVENT GENERATOR
#
# SAFETY: source IPs are drawn ONLY from private (RFC 1918) and
# documentation/example (RFC 5737 / RFC 3927) ranges. No real-world
# hosts are contacted or referenced. This generator does not perform
# any network activity — it only writes synthetic rows to the local
# demo database for dashboard/visualization purposes.
# ============================================================

# event_type -> (severity, typical status choices)
EVENT_TEMPLATES = {
    "FAILED_LOGIN":         {"severity": "MEDIUM",   "statuses": ["BLOCKED", "INVESTIGATING"]},
    "SUCCESSFUL_LOGIN":     {"severity": "LOW",       "statuses": ["ALLOWED"]},
    "BRUTE_FORCE_SUSPECTED": {"severity": "HIGH",     "statuses": ["BLOCKED", "INVESTIGATING"]},
    "PORT_SCAN":            {"severity": "HIGH",      "statuses": ["BLOCKED", "INVESTIGATING"]},
    "SUSPICIOUS_IP":        {"severity": "MEDIUM",    "statuses": ["INVESTIGATING", "BLOCKED"]},
    "MALWARE_DETECTED":     {"severity": "CRITICAL",  "statuses": ["BLOCKED", "INVESTIGATING"]},
    "FIREWALL_BLOCK":       {"severity": "LOW",       "statuses": ["BLOCKED"]},
    "UNUSUAL_LOGIN":        {"severity": "MEDIUM",    "statuses": ["INVESTIGATING", "ALLOWED"]},
    "PRIVILEGE_CHANGE":     {"severity": "HIGH",      "statuses": ["INVESTIGATING", "ALLOWED"]},
}

# Private (RFC 1918) and documentation/example (RFC 5737) ranges only.
_PRIVATE_SUBNETS = ["192.168.1", "192.168.0", "10.0.0", "10.0.1", "172.16.0"]
_EXAMPLE_SUBNETS = ["203.0.113", "198.51.100", "192.0.2"]  # RFC 5737 — reserved for documentation


def _random_ip():
    subnet = random.choice(_PRIVATE_SUBNETS + _EXAMPLE_SUBNETS)
    return f"{subnet}.{random.randint(2, 254)}"


_DESCRIPTION_TEMPLATES = {
    "FAILED_LOGIN": "Failed login attempt detected from {ip}.",
    "SUCCESSFUL_LOGIN": "Successful login from {ip}.",
    "BRUTE_FORCE_SUSPECTED": "Repeated authentication failures from {ip} — brute-force pattern suspected.",
    "PORT_SCAN": "Sequential connection attempts across multiple ports detected from {ip} (simulated).",
    "SUSPICIOUS_IP": "Traffic from {ip} matched a suspicious-activity heuristic (simulated).",
    "MALWARE_DETECTED": "Signature match for known malware pattern associated with host {ip} (simulated).",
    "FIREWALL_BLOCK": "Firewall rule blocked inbound connection from {ip}.",
    "UNUSUAL_LOGIN": "Login from {ip} flagged as unusual (atypical time/location pattern, simulated).",
    "PRIVILEGE_CHANGE": "Account privilege level changed; originating request from {ip} (simulated).",
}


def generate_random_event():
    """
    Generates and inserts ONE synthetic security event using a random
    type/severity/IP combination from the safe templates above.
    Returns the generated event_id.
    """
    event_type = random.choice(list(EVENT_TEMPLATES.keys()))
    template = EVENT_TEMPLATES[event_type]
    ip = _random_ip()
    description = _DESCRIPTION_TEMPLATES[event_type].format(ip=ip)
    status = random.choice(template["statuses"])

    return insert_security_event(
        event_type=event_type,
        severity=template["severity"],
        source_ip=ip,
        description=description,
        status=status,
    )


def generate_bulk_events(count=20):
    """Generates `count` random simulated events. Returns list of event_ids."""
    return [generate_random_event() for _ in range(count)]
