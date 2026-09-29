"""Loopback demo portal that delegates challenge decisions to the local API.

The portal never receives API credentials from the browser. Form signals remain
visitor-supplied and forgeable, so this is only an educational integration demo.
"""
from __future__ import annotations

import html
import ipaddress
import json
import os
import secrets
import time
from http.client import HTTPRedirectHandler
from typing import Callable, Literal
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit
from urllib.request import Request, build_opener

from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

_SESSION_TTL_SECONDS = 300
_MAX_FORM_BYTES = 8192
_MAX_RESPONSE_BYTES = 65536


class DemoDecisionInput(BaseModel):
    sequence_status: Literal["SUCCESS", "FAILED", "TIMEOUT", "IN_PROGRESS"]
    behavioral_match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def _api_endpoint(path: str) -> str:
    base = os.environ.get("SECUREAIR_API_URL", "http://127.0.0.1:8000").strip()
    parsed = urlsplit(base)
    try:
        valid_port = parsed.port is None or 1 <= parsed.port <= 65535
    except ValueError:
        valid_port = False
    if (parsed.scheme != "http" or not _is_loopback(parsed.hostname)
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or not valid_port):
        raise RuntimeError("API URL must be an HTTP loopback origin without credentials or path.")
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    return f"{origin}/{path.lstrip('/')}"


class _RejectRedirects(HTTPRedirectHandler):
    """Do not forward the API bearer token to a redirect target."""

    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def _call_api(path: str, payload: dict) -> dict:
    """Make a bounded, authenticated server-to-server request to loopback API."""
    secret = os.environ.get("SECUREAIR_SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("Local API secret is not configured on the server.")
    request = Request(
        _api_endpoint(path),
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {secret}"},
        method="POST",
    )
    try:
        with build_opener(_RejectRedirects).open(request, timeout=3.0) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise RuntimeError("Local API response exceeded the allowed size.")
        result = json.loads(raw)
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Local API is unavailable or returned an invalid response.") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Local API returned an invalid response.")
    return result


def _read_form(body: bytes) -> dict[str, str]:
    if len(body) > _MAX_FORM_BYTES:
        raise ValueError("Form submission is too large.")
    values = parse_qs(body.decode("utf-8"), strict_parsing=True, max_num_fields=16)
    result: dict[str, str] = {}
    for key, entries in values.items():
        if len(entries) != 1:
            raise ValueError("Repeated form fields are not accepted.")
        result[key] = entries[0]
    return result


def _render_page(*, challenge: dict | None = None, result: dict | None = None,
                 message: str | None = None) -> str:
    challenge_form = ""
    if challenge:
        challenge_id = html.escape(challenge["challenge_id"], quote=True)
        profile_id = html.escape(challenge["profile_id"], quote=True)
        gestures = html.escape(", ".join(challenge["gestures"]))
        challenge_form = (
            '<form action="/demo/decision" method="post">'
            f'<input type="hidden" name="challenge_id" value="{challenge_id}">'
            f'<input type="hidden" name="profile_id" value="{profile_id}">'
            f'<p>Challenge gestures (enter in order): <strong>{gestures}</strong></p>'
            '<label for="observed">Observed gestures, comma-separated</label>'
            '<input id="observed" name="observed_gestures" autocomplete="off" required>'
            '<label for="sequence">Sequence status</label>'
            '<select id="sequence" name="sequence_status">'
            '<option value="SUCCESS">Success</option><option value="FAILED">Failed</option>'
            '<option value="TIMEOUT">Timeout</option><option value="IN_PROGRESS">In progress</option>'
            '</select><label for="score">Caller-supplied behavioral score (0–1)</label>'
            '<input id="score" name="behavioral_match_score" type="number" min="0" max="1" step="0.01">'
            '<label for="threshold">Decision threshold (0–1)</label>'
            '<input id="threshold" name="threshold" type="number" min="0" max="1" step="0.01" value="0.8">'
            '<button type="submit">Send response to local API</button></form>'
        )
    result_panel = ""
    if result:
        decision = html.escape(str(result.get("decision", "DENY")))
        reasons = html.escape(", ".join(result.get("reasons", [])))
        link = '<p><a href="/protected">Open protected demo resource</a></p>' if result.get("allowed") else ""
        result_panel = f'<section aria-live="polite"><h2>Server decision: {decision}</h2><p>{reasons}</p>{link}</section>'
    notice = f'<p role="status">{html.escape(message)}</p>' if message else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>SecureAir integrated local demo</title></head><body><main>'
        '<h1>SecureAir integrated local demo</h1>'
        '<p>Loopback demonstration only. Submitted responses and scores are forgeable; '
        'this is not authentication.</p>'
        f'{notice}{challenge_form}{result_panel}'
        '<form action="/logout" method="post"><button type="submit">Clear demo session</button></form>'
        '</main></body></html>'
    )


def create_demo_app(api_caller: Callable[[str, dict], dict] | None = None) -> FastAPI:
    """Create the portal. ``api_caller`` is injectable for isolated integration tests."""
    app = FastAPI(title="SecureAir Controlled Demo Portal", version="0.2.0")
    app.state.demo_sessions = {}
    app.state.api_caller = api_caller or _call_api

    @app.middleware("http")
    async def local_only(request: FastAPIRequest, call_next):
        if not _is_loopback(request.client.host if request.client else None):
            return HTMLResponse("Local demo only", status_code=403)
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        try:
            challenge = app.state.api_caller("/challenges", {"profile_id": "demo_user"})
            if (not isinstance(challenge.get("challenge_id"), str)
                    or not isinstance(challenge.get("profile_id"), str)
                    or not isinstance(challenge.get("gestures"), list)
                    or not challenge["gestures"]
                    or not all(isinstance(item, str) for item in challenge["gestures"])):
                raise RuntimeError("Local API returned an invalid challenge.")
            return HTMLResponse(_render_page(challenge=challenge))
        except (RuntimeError, ValueError, TypeError, AttributeError):
            return HTMLResponse(
                _render_page(message="Challenge service unavailable; access remains denied."),
                status_code=503,
            )

    @app.post("/demo/decision", response_class=HTMLResponse)
    async def submit_demo_decision(request: FastAPIRequest):
        """Consume the API challenge; only its ALLOW response creates a portal session."""
        try:
            form = _read_form(await request.body())
            challenge_id = form["challenge_id"]
            profile_id = form["profile_id"]
            observed = [item.strip() for item in form["observed_gestures"].split(",")]
            if not challenge_id or len(challenge_id) > 128 or not profile_id or len(profile_id) > 64:
                raise ValueError("Invalid challenge or profile identifier.")
            score_text = form.get("behavioral_match_score", "").strip()
            payload = DemoDecisionInput.model_validate({
                "sequence_status": form["sequence_status"],
                "behavioral_match_score": None if not score_text else float(score_text),
                "threshold": float(form.get("threshold", "0.8")),
            })
            response = app.state.api_caller(
                f"/challenges/{quote(challenge_id, safe='')}/consume",
                {
                    "profile_id": profile_id,
                    "observed_gestures": observed,
                    "sequence_status": payload.sequence_status,
                    "behavioral_match_score": payload.behavioral_match_score,
                    "threshold": payload.threshold,
                },
            )
            if (response.get("decision") not in {"ALLOW", "DENY"}
                    or not isinstance(response.get("allowed"), bool)
                    or response["allowed"] != (response["decision"] == "ALLOW")):
                raise RuntimeError("Local API returned an invalid decision.")
            result = response
        except (KeyError, ValueError, TypeError, ValidationError):
            result = {"decision": "DENY", "allowed": False, "reasons": ["invalid_demo_input"]}
        except (RuntimeError, AttributeError):
            result = {"decision": "DENY", "allowed": False, "reasons": ["challenge_service_unavailable"]}

        session_id = secrets.token_urlsafe(24)
        app.state.demo_sessions[session_id] = (result["allowed"] is True, time.monotonic() + _SESSION_TTL_SECONDS)
        response = HTMLResponse(_render_page(result=result))
        response.set_cookie(
            "secureair_demo_session", session_id, httponly=True,
            samesite="strict", secure=False, max_age=_SESSION_TTL_SECONDS,
        )
        return response

    @app.get("/protected", response_class=HTMLResponse)
    async def protected_resource(request: FastAPIRequest):
        now = time.monotonic()
        app.state.demo_sessions = {
            key: record for key, record in app.state.demo_sessions.items() if record[1] > now
        }
        session_id = request.cookies.get("secureair_demo_session", "")
        record = app.state.demo_sessions.get(session_id)
        if not record or record[0] is not True:
            return HTMLResponse("<!doctype html><title>Denied</title><h1>Access denied</h1>", status_code=403)
        return HTMLResponse(
            "<!doctype html><title>Demo</title><h1>Protected demo resource</h1>"
            "<p>Educational only; API inputs are forgeable.</p>"
        )

    @app.post("/logout")
    async def logout(request: FastAPIRequest):
        app.state.demo_sessions.pop(request.cookies.get("secureair_demo_session", ""), None)
        response = HTMLResponse("<!doctype html><h1>Demo session cleared</h1>")
        response.delete_cookie("secureair_demo_session", httponly=True, samesite="strict")
        return response

    return app


app = create_demo_app()
