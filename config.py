"""
Central configuration for the Air-Gesture Cybersecurity Dashboard.
All sensitive/tunable values are loaded from environment variables
(.env file) rather than hardcoded, per secure-development practice.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()  # loads .env if present


class Config:
    # --- Flask ---
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-key-CHANGE-ME")
    if SECRET_KEY == "dev-key-CHANGE-ME":
        # Not raising here so the app still boots for first-run setup,
        # but this should be treated as a hard requirement before any
        # real (even academic-demo) deployment.
        print("[WARNING] FLASK_SECRET_KEY not set — using an insecure default. "
              "Set it in your .env file before demoing.")

    # --- Database ---
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "database/cyberdash.db")

    # --- Brute-force / lockout policy ---
    LOCKOUT_MAX_ATTEMPTS = int(os.environ.get("LOCKOUT_MAX_ATTEMPTS", 3))
    LOCKOUT_DURATION_MINUTES = int(os.environ.get("LOCKOUT_DURATION_MINUTES", 5))

    # --- Session security ---
    SESSION_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT_MINUTES", 15))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # HTTPS-only cookie flag — disabled by default for local http://127.0.0.1
    # demo use. MUST be true for anything beyond localhost.
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # --- Debug mode --- never true outside local dev
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    # --- Gesture recognition ---
    # Confidence thresholds passed to MediaPipe Hands
    MP_DETECTION_CONFIDENCE = float(os.environ.get("MP_DETECTION_CONFIDENCE", 0.7))
    MP_TRACKING_CONFIDENCE = float(os.environ.get("MP_TRACKING_CONFIDENCE", 0.7))

    # Valid gesture vocabulary used across auth + navigation
    VALID_GESTURES = ["INDEX", "TWO_FINGERS", "OPEN_PALM", "THUMB_UP", "FIST"]
