"""
Air-Gesture Cybersecurity Dashboard — main Flask application.

Step 3 scope: registration + password-based login/logout, with audit
logging on every attempt. Gesture authentication is layered on in
Step 6; brute-force lockout in Step 7; full dashboard in Step 8+.
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, jsonify
from functools import wraps
import time

from config import Config
from database.database import init_db, seed_admin_user
from authentication.auth import (
    register_user,
    verify_password,
    get_user_by_id,
    AuthError,
)
from authentication.gesture_auth import gesture_auth_manager
from security.brute_force import check_lockout, record_login_result
from authentication.auth import get_user_by_username
from dashboard.dashboard import (
    get_summary_counts,
    get_severity_breakdown,
    get_event_timeline,
    get_top_suspicious_ips,
    get_auth_stats,
    get_recent_alerts,
    get_events,
)
from security.security_events import generate_bulk_events, EVENT_TEMPLATES
from security.audit_logger import (
    log_action,
    get_audit_logs,
    export_audit_logs_csv,
    get_distinct_actions,
    get_distinct_usernames,
)
from dashboard.gesture_nav import nav_manager
from utils.csrf import get_or_create_csrf_token, validate_csrf_token
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.config.from_object(Config)
app.jinja_env.globals["csrf_token"] = lambda: get_or_create_csrf_token(session)

# Endpoints exempt from CSRF checks (none currently — every state-changing
# route requires a valid token). Kept as an explicit set for clarity/audit.
CSRF_EXEMPT_ENDPOINTS = set()


@app.before_request
def enforce_csrf():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.endpoint in CSRF_EXEMPT_ENDPOINTS:
        return
    token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
    if not validate_csrf_token(session, token):
        log_action(
            user_id=session.get("user_id"),
            action="CSRF_REJECTED",
            result="BLOCKED",
            ip_address=get_client_ip(),
            details=f"Invalid/missing CSRF token on {request.path}",
        )
        return jsonify({"error": "Invalid or missing CSRF token"}), 400


@app.before_request
def enforce_session_timeout():
    if "user_id" not in session:
        return
    last_activity_str = session.get("last_activity")
    now = datetime.now()
    if last_activity_str:
        last_activity = datetime.fromisoformat(last_activity_str)
        if now - last_activity > timedelta(minutes=Config.SESSION_TIMEOUT_MINUTES):
            user_id = session.get("user_id")
            session.clear()
            log_action(user_id, "SESSION_TIMEOUT", "SUCCESS", get_client_ip(),
                       details="Session expired due to inactivity")
            flash("Your session expired due to inactivity. Please log in again.", "warning")
            return redirect(url_for("login"))
    session["last_activity"] = now.isoformat()


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(500)
def server_error(e):
    # Secure error handling: never leak stack traces or internals to the
    # client, even with DEBUG off. Real error is only in server console.
    print(f"[ERROR] Unhandled exception: {e}")
    return render_template("error.html", code=500, message="Something went wrong."), 500


def get_client_ip():
    # Trusts X-Forwarded-For only if you later put this behind a proxy;
    # for local demo use, request.remote_addr is correct and sufficient.
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", valid_gestures=Config.VALID_GESTURES)

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    # Gesture sequence submitted as repeated form fields: gesture_1, gesture_2, ...
    gesture_sequence = [
        g for g in request.form.getlist("gesture_sequence") if g
    ]

    try:
        user_id = register_user(username, password, gesture_sequence)
        log_action(
            user_id=user_id,
            action="ACCOUNT_REGISTERED",
            result="SUCCESS",
            ip_address=get_client_ip(),
            details=f"New account created: {username}",
        )
        flash("Account created successfully. You can now log in.", "success")
        return redirect(url_for("login"))
    except AuthError as e:
        flash(str(e), "danger")
        return render_template("register.html", valid_gestures=Config.VALID_GESTURES)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    ip = get_client_ip()

    # Check lockout BEFORE attempting password verification — a locked
    # account must not leak whether the password would have been correct.
    existing_user = get_user_by_username(username)
    if existing_user is not None:
        locked, seconds_remaining = check_lockout(existing_user)
        if locked:
            minutes_remaining = max(1, seconds_remaining // 60)
            log_action(
                user_id=existing_user["user_id"],
                action="LOGIN_ATTEMPT",
                result="BLOCKED",
                ip_address=ip,
                details=f"Attempt while account locked ({seconds_remaining}s remaining)",
            )
            flash(
                f"Multiple authentication failures detected. Account temporarily "
                f"locked. Try again in about {minutes_remaining} minute(s).",
                "danger",
            )
            return render_template("login.html")

    user = verify_password(username, password)

    if user is None:
        log_action(
            user_id=None,
            action="LOGIN_ATTEMPT",
            result="DENIED",
            ip_address=ip,
            details=f"Invalid credentials for username '{username}'",
        )
        if existing_user is not None:
            # Account exists but password was wrong — this counts
            # toward brute-force lockout. (Unknown usernames are logged
            # above but don't increment any account's counter.)
            result = record_login_result(existing_user, detected_sequence=None, ip_address=ip, success=False)
            if result["locked"]:
                flash(
                    "Multiple authentication failures detected. Account temporarily locked.",
                    "danger",
                )
                return render_template("login.html")
            flash(
                f"Invalid username or password. {result['attempts_remaining']} attempt(s) remaining before lockout.",
                "danger",
            )
        else:
            flash("Invalid username or password.", "danger")
        return render_template("login.html")

    # Password layer passed. Do NOT log the user in yet — gesture
    # verification is a second required factor. Stash the pending
    # user id in session and hand off to /gesture-auth.
    # NOTE: brute-force lockout on repeated password failures is added
    # in Step 7 — this route will be revisited then.
    session["pending_user_id"] = user["user_id"]
    log_action(
        user_id=user["user_id"],
        action="PASSWORD_VERIFIED",
        result="SUCCESS",
        ip_address=ip,
        details="Password layer passed; awaiting gesture verification",
    )
    return redirect(url_for("gesture_auth_page"))


@app.route("/gesture-auth")
def gesture_auth_page():
    if "pending_user_id" not in session:
        flash("Please enter your username and password first.", "warning")
        return redirect(url_for("login"))

    user = get_user_by_id(session["pending_user_id"])
    if user is None:
        session.pop("pending_user_id", None)
        flash("Session expired. Please log in again.", "warning")
        return redirect(url_for("login"))

    expected_sequence = json.loads(user["gesture_sequence"])
    gesture_auth_manager.start(expected_sequence)

    return render_template(
        "gesture_auth.html",
        username=user["username"],
        expected_length=len(expected_sequence),
    )


@app.route("/video_feed")
def video_feed():
    def generate():
        while True:
            frame = gesture_auth_manager.get_latest_jpeg()
            if frame is not None:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/gesture-status")
def gesture_status():
    if "pending_user_id" not in session:
        return jsonify({"status": "NO_SESSION"}), 400

    status_data = gesture_auth_manager.get_status()

    if status_data["status"] == "GRANTED":
        user = get_user_by_id(session["pending_user_id"])
        record_login_result(user, status_data["captured_sequence"], get_client_ip(), success=True)
        session.permanent = True
        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session.pop("pending_user_id", None)
        log_action(
            user_id=user["user_id"],
            action="GESTURE_AUTH_RESULT",
            result="GRANTED",
            ip_address=get_client_ip(),
            details=f"Gesture sequence matched: {status_data['captured_sequence']}",
        )
    elif status_data["status"] in ("DENIED", "TIMEOUT"):
        pending_id = session.get("pending_user_id")
        user = get_user_by_id(pending_id) if pending_id else None
        if user is not None:
            lockout_result = record_login_result(
                user, status_data["captured_sequence"], get_client_ip(), success=False
            )
            status_data["locked"] = lockout_result["locked"]
            if lockout_result["locked"]:
                # A gesture-stage lockout should end the pending session
                # entirely — no "Try Again" loophole around the lockout.
                session.pop("pending_user_id", None)
        log_action(
            user_id=pending_id,
            action="GESTURE_AUTH_RESULT",
            result=status_data["status"],
            ip_address=get_client_ip(),
            details=f"Captured sequence: {status_data['captured_sequence']}",
        )

    return jsonify(status_data)


@app.route("/gesture-auth/restart", methods=["POST"])
def gesture_auth_restart():
    if "pending_user_id" not in session:
        return jsonify({"error": "no pending session"}), 400
    user = get_user_by_id(session["pending_user_id"])

    locked, seconds_remaining = check_lockout(user)
    if locked:
        return jsonify({"error": "account locked", "seconds_remaining": seconds_remaining}), 403

    expected_sequence = json.loads(user["gesture_sequence"])
    gesture_auth_manager.start(expected_sequence)
    return jsonify({"restarted": True})


@app.route("/logout")
@login_required
def logout():
    user_id = session.get("user_id")
    log_action(
        user_id=user_id,
        action="LOGOUT",
        result="SUCCESS",
        ip_address=get_client_ip(),
        details="User logged out",
    )
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    summary = get_summary_counts()
    severity_breakdown = get_severity_breakdown()
    timeline = get_event_timeline(days=7)
    top_ips = get_top_suspicious_ips(limit=5)
    auth_stats = get_auth_stats()
    recent_alerts = get_recent_alerts(limit=10)

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        summary=summary,
        recent_alerts=recent_alerts,
        # Pre-serialized for the Chart.js <script> block — avoids doing
        # JSON parsing/escaping logic inside the template itself.
        severity_breakdown_json=json.dumps(severity_breakdown),
        timeline_json=json.dumps(timeline),
        top_ips_json=json.dumps(top_ips),
        auth_stats_json=json.dumps(auth_stats),
        active_page="dashboard",
    )


@app.route("/events")
@login_required
def events_page():
    event_type_filter = request.args.get("event_type") or None
    severity_filter = request.args.get("severity") or None

    events = get_events(event_type=event_type_filter, severity=severity_filter, limit=200)

    return render_template(
        "events.html",
        username=session.get("username"),
        events=events,
        event_types=list(EVENT_TEMPLATES.keys()),
        severities=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        selected_type=event_type_filter,
        selected_severity=severity_filter,
        active_page="events",
    )


@app.route("/events/generate", methods=["POST"])
@login_required
def events_generate():
    count = 15
    generate_bulk_events(count)
    log_action(
        user_id=session.get("user_id"),
        action="SECURITY_EVENT_CREATED",
        result="SUCCESS",
        ip_address=get_client_ip(),
        details=f"Administrator generated {count} simulated security events for demo purposes.",
    )
    flash(f"Generated {count} simulated security events.", "success")
    return redirect(url_for("events_page"))


def _forensic_filters_from_request():
    return {
        "action": request.args.get("action") or None,
        "severity": request.args.get("severity") or None,
        "date_from": request.args.get("date_from") or None,
        "date_to": request.args.get("date_to") or None,
        "username": request.args.get("username") or None,
        "search": request.args.get("search") or None,
    }


@app.route("/forensic-logs")
@login_required
def forensic_logs_page():
    filters = _forensic_filters_from_request()
    logs = get_audit_logs(**filters, limit=300)
    clean_filters = {k: v for k, v in filters.items() if v}

    return render_template(
        "forensic_logs.html",
        username=session.get("username"),
        logs=logs,
        actions=get_distinct_actions(),
        usernames=get_distinct_usernames(),
        severities=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        filters=filters,
        clean_filters=clean_filters,
        active_page="forensic_logs",
    )


@app.route("/forensic-logs/export")
@login_required
def forensic_logs_export():
    filters = _forensic_filters_from_request()
    csv_text = export_audit_logs_csv(**filters)

    log_action(
        user_id=session.get("user_id"),
        action="FORENSIC_LOG_EXPORTED",
        result="SUCCESS",
        ip_address=get_client_ip(),
        details=f"Forensic log CSV export requested with filters: {filters}",
    )

    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=forensic_logs_export.csv"},
    )


@app.route("/nav/start", methods=["POST"])
@login_required
def nav_start():
    nav_manager.start()
    log_action(session.get("user_id"), "GESTURE_NAV_ENABLED", "SUCCESS", get_client_ip())
    return jsonify({"running": True})


@app.route("/nav/stop", methods=["POST"])
@login_required
def nav_stop():
    nav_manager.stop()
    log_action(session.get("user_id"), "GESTURE_NAV_DISABLED", "SUCCESS", get_client_ip())
    return jsonify({"running": False})


@app.route("/nav/video_feed")
@login_required
def nav_video_feed():
    def generate():
        while nav_manager.is_running():
            frame = nav_manager.get_latest_jpeg()
            if frame is not None:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            time.sleep(0.03)
    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/nav-status")
@login_required
def nav_status():
    status = nav_manager.get_and_clear_status()
    if status["pending_action"]:
        log_action(
            session.get("user_id"), "GESTURE_NAV", "COMMAND",
            get_client_ip(), details=f"Gesture command: {status['pending_action']}",
        )
    return jsonify(status)


@app.route("/lock", methods=["POST"])
@login_required
def lock_dashboard():
    user_id = session.get("user_id")
    nav_manager.stop()
    log_action(user_id, "DASHBOARD_LOCKED", "SUCCESS", get_client_ip(), details="Locked via FIST gesture or manual lock")
    session.clear()
    return jsonify({"locked": True})


if __name__ == "__main__":
    init_db()
    seed_admin_user()
    app.run(debug=Config.DEBUG, host="127.0.0.1", port=5000)
