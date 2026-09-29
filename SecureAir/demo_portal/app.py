"""Loopback-only FastAPI demo portal with server-side decision checks.

The portal is intentionally not integrated with camera or identity data. It
accepts an educational demonstration decision signal, and the visitor can
forge its values. Never use it to protect real resources.
"""
from __future__ import annotations

import ipaddress
import secrets
from typing import Annotated, Literal

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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


def create_demo_app() -> FastAPI:
    """Create a small demo site with server-side authorization on its resource."""
    app = FastAPI(title="SecureAir Controlled Demo Portal", version="0.1.0")
    app.state.demo_sessions = {}
    templates = Jinja2Templates(directory="SecureAir/demo_portal/templates")

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if not _loopback(request.client.host if request.client else None):
            return HTMLResponse("Local demo only", status_code=403)
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"request": request, "result": None},
        )

    @app.post("/demo/decision", response_class=HTMLResponse)
    async def submit_demo_decision(
        request: Request,
        sequence_status: Annotated[str, Form()],
        challenge_success: Annotated[str, Form()],
        behavioral_match_score: Annotated[str, Form()],
        threshold: Annotated[str, Form()] = "0.8",
    ):
        """Evaluate submitted demo fields, then keep authorization server-side."""
        try:
            payload = DemoDecisionInput.model_validate({
                "sequence_status": sequence_status,
                "challenge_success": challenge_success == "true",
                "behavioral_match_score": (
                    None if behavioral_match_score.strip() == "" else float(behavioral_match_score)
                ),
                "threshold": float(threshold),
            })
            decision = evaluate_authentication(
                sequence_status=payload.sequence_status,
                challenge_success=payload.challenge_success,
                behavioral_match_score=payload.behavioral_match_score,
                threshold=payload.threshold,
            )
        except (ValueError, TypeError):
            decision = {"decision": "DENY", "allowed": False, "reasons": ["invalid_demo_input"]}

        session_id = secrets.token_urlsafe(24)
        app.state.demo_sessions[session_id] = bool(decision.get("allowed"))
        response = templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"request": request, "result": decision},
        )
        response.set_cookie(
            "secureair_demo_session",
            session_id,
            httponly=True,
            samesite="strict",
            secure=False,  # HTTP is allowed only on loopback for this local demo.
            max_age=300,
        )
        return response

    @app.get("/protected", response_class=HTMLResponse)
    async def protected_resource(request: Request):
        """Authorize at the server; hiding a link or client-side flag is insufficient."""
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
