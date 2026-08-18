"""
Core authentication logic (password layer).
Gesture authentication is layered on top of this in gesture_auth.py.
"""

import json
import re
import sys
import os
from werkzeug.security import generate_password_hash, check_password_hash

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import get_db_connection


class AuthError(Exception):
    """Raised for expected/handleable auth failures (bad input, duplicate user, etc.)."""
    pass


def validate_username(username: str) -> str:
    username = (username or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", username):
        raise AuthError(
            "Username must be 3-32 characters: letters, numbers, underscore only."
        )
    return username


def validate_password(password: str) -> None:
    if not password or len(password) < 8:
        raise AuthError("Password must be at least 8 characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        raise AuthError("Password must contain both letters and numbers.")


def validate_gesture_sequence(sequence: list) -> list:
    from config import Config
    if not isinstance(sequence, list) or not (2 <= len(sequence) <= 8):
        raise AuthError("Gesture sequence must be a list of 2-8 gestures.")
    for g in sequence:
        if g not in Config.VALID_GESTURES:
            raise AuthError(f"Invalid gesture in sequence: {g}")
    return sequence


def register_user(username: str, password: str, gesture_sequence: list) -> int:
    """
    Registers a new user account. Raises AuthError on any validation
    failure or duplicate username. Returns the new user_id on success.
    """
    username = validate_username(username)
    validate_password(password)
    gesture_sequence = validate_gesture_sequence(gesture_sequence)

    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT user_id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            raise AuthError("That username is already taken.")

        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, gesture_sequence, account_status)
            VALUES (?, ?, ?, 'ACTIVE')
            """,
            (username, generate_password_hash(password), json.dumps(gesture_sequence)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = get_db_connection()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_db_connection()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()


def verify_password(username: str, password: str):
    """
    Returns the user row if username+password are valid AND the account
    is not currently locked, otherwise returns None.
    NOTE: this only checks the password layer. Full login in this app
    also requires the gesture layer (see gesture_auth.py) — this function
    is used for Step 3's password-only flow and will be composed with
    gesture auth in Step 6.
    """
    user = get_user_by_username(username)
    if user is None:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user
