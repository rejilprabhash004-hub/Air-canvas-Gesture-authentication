"""
Database access layer for the Air-Gesture Cybersecurity Dashboard.

All queries elsewhere in the app should go through get_db_connection()
and use parameterized queries (never string-formatted SQL) to prevent
SQL injection.
"""

import sqlite3
import os
import sys

# Allow running this file directly (python database/database.py) as
# well as importing it as part of the package.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_db_connection():
    """
    Returns a sqlite3 connection with:
    - row_factory set to sqlite3.Row (dict-like access by column name)
    - foreign key enforcement turned on for this connection
    """
    db_path = Config.DATABASE_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(db_path) else None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """
    Creates all tables from schema.sql if they don't already exist.
    Safe to call every time the app starts (idempotent — uses
    CREATE TABLE IF NOT EXISTS).
    """
    conn = get_db_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"[database] Schema initialised at {Config.DATABASE_PATH}")


def seed_admin_user():
    """
    Creates a single default admin account for first-run demo purposes,
    ONLY if the users table is currently empty. Password and gesture
    sequence are placeholders the user MUST change before any real demo
    — this function prints the credentials once so they're not silently
    hidden in the database.
    """
    from werkzeug.security import generate_password_hash
    import json

    conn = get_db_connection()
    existing = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]

    if existing > 0:
        conn.close()
        print("[database] Users already exist — skipping seed.")
        return

    default_username = "admin"
    default_password = "ChangeMe123!"  # demo-only; user must change on first login
    default_gesture_sequence = ["INDEX", "TWO_FINGERS", "OPEN_PALM", "THUMB_UP"]

    conn.execute(
        """
        INSERT INTO users (username, password_hash, gesture_sequence, account_status)
        VALUES (?, ?, ?, ?)
        """,
        (
            default_username,
            generate_password_hash(default_password),
            json.dumps(default_gesture_sequence),
            "ACTIVE",
        ),
    )
    conn.commit()
    conn.close()

    print("[database] Seeded default admin account:")
    print(f"           username: {default_username}")
    print(f"           password: {default_password}  (CHANGE THIS before any real demo)")
    print(f"           gesture sequence: {' -> '.join(default_gesture_sequence)}")


if __name__ == "__main__":
    # Allows: python database/database.py   -> sets up DB + seed admin
    init_db()
    seed_admin_user()
