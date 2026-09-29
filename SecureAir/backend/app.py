"""Loopback-only FastAPI wrapper for local SecureAir challenge decisions.

All functional endpoints require the configured SECUREAIR_SECRET_KEY as a
bearer token and a loopback client connection. This API is a prototype boundary,
not proof that submitted signals came from a camera or a calibrated identity
model. Run with ``python -m backend.app`` so the validated loopback bind applies.
"""
from __future__ import annotations

import hmac
import ipaddress
from typing import Annotated, Literal

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend.auth_decision import evaluate_authentication
from backend.challenges import (
    ChallengeAlreadyUsedError,
    ChallengeError,
    ChallengeExpiredError,
    ChallengeManager,
    ChallengeNotFoundError,
    ChallengeUserMismatchError,
)
from backend.config import ConfigurationError, Settings, load_settings

_LOOPBACK_NAMES = frozenset({"127.0.0.1", "localhost", "::1"})
_bearer = HTTPBearer(auto_error=False)


class IssueChallengeRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=64)


class ConsumeChallengeRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=64)
    observed_gestures: list[str] = Field(min_length=1, max_length=8)
    sequence_status: Literal["SUCCESS", "FAILED", "TIMEOUT", "IN_PROGRESS"]
    behavioral_match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class ChallengeResponse(BaseModel):
    challenge_id: str
    profile_id: str
    gestures: list[str]
    created_at: str
    expires_at: str


class DecisionResponse(BaseModel):
    decision: Literal["ALLOW", "DENY"]
    allowed: bool
    reasons: list[str]
    threshold: float | None
    behavioral_score_source: Literal["caller_supplied"]


def _is_loopback_host(host: str) -> bool:
    if host in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an app; ``settings=None`` loads validated environment settings per app."""
    application = FastAPI(
        title="SecureAir Local API",
        version="0.1.0",
        description=(
            "Local prototype API. It does not establish camera provenance or "
            "identity-model accuracy."
        ),
    )
    application.state.settings = settings
    application.state.challenge_manager = None

    @application.middleware("http")
    async def enforce_loopback_and_initialize(request: Request, call_next):
        current_settings = request.app.state.settings
        if current_settings is None:
            try:
                current_settings = load_settings()
            except ConfigurationError:
                return _json_error(status.HTTP_503_SERVICE_UNAVAILABLE, "service_not_configured")
            request.app.state.settings = current_settings
        if not _is_loopback_host(current_settings.host):
            return _json_error(status.HTTP_503_SERVICE_UNAVAILABLE, "non_loopback_bind_rejected")
        client_host = request.client.host if request.client else ""
        if not _is_loopback_host(client_host):
            return _json_error(status.HTTP_403_FORBIDDEN, "loopback_clients_only")
        if request.app.state.challenge_manager is None:
            request.app.state.challenge_manager = ChallengeManager(
                lifetime_seconds=current_settings.challenge_seconds,
            )
        return await call_next(request)

    async def require_local_bearer(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> None:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )
        expected = request.app.state.settings.secret_key
        if not hmac.compare_digest(credentials.credentials, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "scope": "loopback"}

    @application.post(
        "/challenges",
        response_model=ChallengeResponse,
        dependencies=[Depends(require_local_bearer)],
    )
    async def issue_challenge(body: IssueChallengeRequest, request: Request) -> ChallengeResponse:
        manager: ChallengeManager = request.app.state.challenge_manager
        manager.purge_expired()
        try:
            challenge = manager.issue(body.profile_id)
        except ChallengeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ChallengeResponse(
            challenge_id=challenge.challenge_id,
            profile_id=challenge.profile_id,
            gestures=list(challenge.gestures),
            created_at=challenge.created_at,
            expires_at=challenge.expires_at,
        )

    @application.post(
        "/challenges/{challenge_id}/consume",
        response_model=DecisionResponse,
        dependencies=[Depends(require_local_bearer)],
    )
    async def consume_challenge(
        challenge_id: str,
        body: ConsumeChallengeRequest,
        request: Request,
    ) -> DecisionResponse:
        manager: ChallengeManager = request.app.state.challenge_manager
        try:
            challenge_success = manager.consume(
                challenge_id,
                body.profile_id,
                body.observed_gestures,
            )
        except ChallengeNotFoundError as exc:
            raise HTTPException(status_code=404, detail="challenge_not_found") from exc
        except ChallengeExpiredError as exc:
            raise HTTPException(status_code=410, detail="challenge_expired") from exc
        except ChallengeAlreadyUsedError as exc:
            raise HTTPException(status_code=409, detail="challenge_already_used") from exc
        except ChallengeUserMismatchError as exc:
            raise HTTPException(status_code=403, detail="challenge_profile_mismatch") from exc
        except ChallengeError as exc:
            raise HTTPException(status_code=422, detail="invalid_challenge_input") from exc

        result = evaluate_authentication(
            sequence_status=body.sequence_status,
            challenge_success=challenge_success,
            behavioral_match_score=body.behavioral_match_score,
            threshold=body.threshold,
        )
        return DecisionResponse(**result)

    return application


def _json_error(code: int, detail: str) -> "JSONResponse":
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=code, content={"detail": detail})


if __name__ == "__main__":
    validated = load_settings()
    if not _is_loopback_host(validated.host):
        raise ConfigurationError("SecureAir service must bind to a loopback address.")
    uvicorn.run(create_app(validated), host=validated.host, port=validated.port)
