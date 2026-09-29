"""Loopback-only FastAPI demo portal with server-side decision checks.

This educational portal is deliberately disconnected from camera and identity
signals. Submitted form values are forgeable and must never protect real data.
"""
from __future__ import annotations

import html
import ipaddress
import secrets
from typing import Literal
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.auth_decision import evaluate_authentication


class DemoDecisionInput(BaseModel):
    sequence_status: Literal["SUCCESS", "FAILED", "TIMEOUT", "IN_PROGRESS"]
    challenge_success: bool
    behavioral_match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)


def _loopback(client: str | None) -> bool:
    if not client:
        return False
    try:
        return ipaddress.ip_address(client).is_loopback
    except ValueError:
        return client.lower() == "localhost"


def _render_page(result: dict | None = None) -> str:
    decision_panel = ""
    if result is not None:
        decision = html.escape(str(result.get("decision", "DENY")))
        reasons = html.escape(", ".join(result.get("reasons", [])))
        link = '<p><a href="/protected">Open protected demo resource</a></p>' if result.get("allowed") else ""
        decision_panel = (
            f'<section aria-live="polite"><h2>Server decision: {decision}</h2>'
            f"<p>Reasons: {reasons}</p>{link}</section>"
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>SecureAir controlled demo</title></head><body><main>'
        '<h1>SecureAir controlled demo portal</h1>'
        '<p>This local educational demo checks access on the server. Submitted values are '
        'caller-supplied and forgeable; this is not real authentication.</p>'
        '<form action="/demo/decision" method="post">'
        '<label for="sequence">Gesture sequence status</label>'
        '<select id="sequence" name="sequence_status">'
        '<option value="SUCCESS">Success</option><option value="FAILED">Failed</option>'
        '<option value="TIMEOUT">Timeout</option><option value="IN_PROGRESS">In progress</option>'
        '</select><label for="challenge">Demo challenge result</label>'
        '<select id="challenge" name="challenge_success">'
        '<option value="true">Success</option><option value="false">Failure</option></select>'
        '<label for="score">Caller-supplied behavioral score (0–1)</label>'
        '<input id="score" name="behavioral_match_score" type="number" min="0" max="1" step="0.01">'
        '<label for="threshold">Decision threshold (0–1)</label>'
        '<input id="threshold" name="threshold" type="number" min="0" max="1" step="0.01" value="0.8" required>'
        '<button type="submit">Evaluate demo decision</button></form>'
        f"{decision_panel}"
        '<form action="/logout" method="post"><button type="submit">Clear demo session</button></form>'
        '</main></body></html>'
    )


def create_demo_app() -> FastAPI:
    """Create a small demo site with authorization enforced by the server."""
    app = FastAPI(title="SecureAir Controlled Demo Portal", version="0.1.0")
    app.state.demo_sessions = {}

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if not _loopback(request.client.host if request.client else None):
            return HTMLResponse("Local demo only", status_code=403)
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(_render_page())

    @app.post("/demo/decision", response_class=HTMLResponse)
    async def submit_demo_decision(request: Request):
        """Evaluate posted fields and grant only a server-recorded demo session."""
        try:
            form = parse_qs((await request.body()).decode("utf-8"), strict_parsing=True)
            def one(name: str, default: str | None = None) -> str:
                values = form.get(name, [])
                if len(values) != 1:
                    if default is not None and not values:
                        return default
                    raise ValueError("missing or repeated form value")
                return values[0]

            challenge = one("challenge_success")
            if challenge not in {"true", "false"}:
                raise ValueError("invalid challenge result")
            score_text = one("behavioral_match_score", "").strip()
            payload = DemoDecisionInput.model_validate({
                "sequence_status": one("sequence_status"),
                "challenge_success": challenge == "true",
                "behavioral_match_score": None if not score_text else float(score_text),
                "threshold": float(one("threshold", "0.8")),
            })
            decision = evaluate_authentication(
                sequence_status=payload.sequence_status,
                challenge_success=payload.challenge_success,
                behavioral_match_score=payload.behavioral_match_score,
                threshold=payload.threshold,
            )
        except (ValueError, TypeError, UnicodeDecodeError):
            decision = {"decision": "DENY", "allowed": False, "reasons": ["invalid_demo_input"]}

        session_id = secrets.token_urlsafe(24)
        app.state.demo_sessions[session_id] = bool(decision.get("allowed"))
        response = HTMLResponse(_render_page(decision))
        response.set_cookie(
            "secureair_demo_session", session_id, httponly=True,
            samesite="strict", secure=False, max_age=300,
        )
        return response

    @app.get("/protected", response_class=HTMLResponse)
    async def protected_resource(request: Request):
        """Authorize on the server; a hidden link/client flag is not sufficient."""
        session_id = request.cookies.get("secureair_demo_session", "")
        if not session_id or app.state.demo_sessions.get(session_id) is not True:
            return HTMLResponse(
                "<!doctype html><title>Denied</title><h1>Access denied</h1>",
                status_code=403,
            )
        return HTMLResponse(
            "<!doctype html><title>Demo</title><h1>Protected demo resource</h1>"
            "<p>For demonstration only; submitted signals are forgeable.</p>"
        )

    @app.post("/logout")
    async def logout(request: Request):
        session_id = request.cookies.get("secureair_demo_session", "")
        app.state.demo_sessions.pop(session_id, None)
        response = HTMLResponse("<!doctype html><h1>Demo session cleared</h1>")
        response.delete_cookie("secureair_demo_session", httponly=True, samesite="strict")
        return response

    return app


app = create_demo_app()
