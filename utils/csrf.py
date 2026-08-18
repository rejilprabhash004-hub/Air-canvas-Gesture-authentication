"""
Minimal CSRF protection. No Flask-WTF dependency — token stored in
session, checked on every state-changing (non-GET) request via
app.py's before_request hook.
"""

import secrets


def get_or_create_csrf_token(session):
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf_token(session, submitted_token):
    real_token = session.get("csrf_token")
    if not real_token or not submitted_token:
        return False
    return secrets.compare_digest(real_token, submitted_token)
