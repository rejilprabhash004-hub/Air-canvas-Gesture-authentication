-- Air-Gesture Cybersecurity Dashboard — Database Schema
-- SQLite. Run once via database/database.py init_db().

PRAGMA foreign_keys = ON;

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username          TEXT UNIQUE NOT NULL,
    password_hash     TEXT NOT NULL,
    gesture_sequence  TEXT NOT NULL,           -- JSON array, e.g. ["INDEX","TWO_FINGERS","OPEN_PALM","THUMB_UP"]
    account_status    TEXT NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE | LOCKED
    failed_attempts   INTEGER NOT NULL DEFAULT 0,
    locked_until      TIMESTAMP,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- AUTHENTICATION LOGS
-- ============================================================
CREATE TABLE IF NOT EXISTS authentication_logs (
    log_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER,
    username_attempted  TEXT,
    detected_sequence   TEXT,                  -- JSON array
    result              TEXT NOT NULL,          -- GRANTED | DENIED
    ip_address          TEXT,
    timestamp           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_authlogs_user_time
    ON authentication_logs(user_id, timestamp);

-- ============================================================
-- SECURITY EVENTS (simulated)
-- ============================================================
CREATE TABLE IF NOT EXISTS security_events (
    event_id     TEXT PRIMARY KEY,              -- e.g. EVT00125
    event_type   TEXT NOT NULL,                 -- FAILED_LOGIN, PORT_SCAN, etc.
    severity     TEXT NOT NULL,                 -- LOW | MEDIUM | HIGH | CRITICAL
    source_ip    TEXT NOT NULL,
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'INVESTIGATING',  -- BLOCKED | ALLOWED | INVESTIGATING
    timestamp    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_severity_time
    ON security_events(severity, timestamp);

CREATE INDEX IF NOT EXISTS idx_events_type
    ON security_events(event_type);

-- ============================================================
-- AUDIT / FORENSIC LOGS  (append-only; no UPDATE/DELETE routes
-- are exposed anywhere in the application layer)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER,
    action       TEXT NOT NULL,                 -- LOGIN_ATTEMPT, GESTURE_NAV, LOCKOUT, ...
    event_ref    TEXT,                           -- optional link to security_events.event_id
    result       TEXT,
    ip_address   TEXT,
    details      TEXT,
    timestamp    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);

-- ============================================================
-- SESSIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,               -- UUID
    user_id      INTEGER NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at   TIMESTAMP NOT NULL,
    is_locked    INTEGER NOT NULL DEFAULT 0,      -- 0/1 boolean, set by FIST gesture
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
