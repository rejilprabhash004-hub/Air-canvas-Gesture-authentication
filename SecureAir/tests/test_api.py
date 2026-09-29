"""API contract tests use FastAPI's in-process client; no camera is opened."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


SECRET = "test-only-secret-value-long-enough-123456"


def make_settings(*, host="127.0.0.1", challenge_seconds=60):
    return Settings(
        data_dir=Path("/tmp/secureair-test-data"),
        host=host,
        port=8000,
        secret_key=SECRET,
        lockout_max_attempts=3,
        lockout_seconds=300,
        challenge_seconds=challenge_seconds,
    )


def test_health_is_local_and_does_not_require_bearer():
    client = TestClient(create_app(make_settings()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "scope": "loopback"}


def test_challenge_requires_bearer_and_rejects_wrong_secret():
    client = TestClient(create_app(make_settings()))
    payload = {"profile_id": "alice"}
    assert client.post("/challenges", json=payload).status_code == 401
    assert client.post(
        "/challenges", json=payload, headers={"Authorization": "Bearer wrong"}
    ).status_code == 401


def test_issue_and_consume_returns_structured_allow_when_all_signals_pass():
    client = TestClient(create_app(make_settings()))
    headers = {"Authorization": f"Bearer {SECRET}"}
    issue = client.post("/challenges", json={"profile_id": "alice"}, headers=headers)
    assert issue.status_code == 200
    challenge = issue.json()
    assert challenge["profile_id"] == "alice"
    assert len(challenge["gestures"]) == 3

    response = client.post(
        f"/challenges/{challenge['challenge_id']}/consume",
        headers=headers,
        json={
            "profile_id": "alice",
            "observed_gestures": challenge["gestures"],
            "sequence_status": "SUCCESS",
            "behavioral_match_score": 0.9,
            "threshold": 0.8,
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "ALLOW"
    assert response.json()["behavioral_score_source"] == "caller_supplied"


def test_valid_wrong_sequence_fails_closed_and_consumes_challenge():
    client = TestClient(create_app(make_settings()))
    headers = {"Authorization": f"Bearer {SECRET}"}
    challenge = client.post(
        "/challenges", json={"profile_id": "alice"}, headers=headers
    ).json()
    wrong = ["FIST", "FIST", "FIST"]
    if wrong == challenge["gestures"]:
        wrong = ["OPEN_PALM", "OPEN_PALM", "OPEN_PALM"]
    payload = {
        "profile_id": "alice",
        "observed_gestures": wrong,
        "sequence_status": "SUCCESS",
        "behavioral_match_score": 1.0,
    }
    url = f"/challenges/{challenge['challenge_id']}/consume"
    response = client.post(url, json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert "challenge_failed" in response.json()["reasons"]
    assert client.post(url, json=payload, headers=headers).status_code == 409


def test_missing_score_denies_without_claiming_identity_confidence():
    client = TestClient(create_app(make_settings()))
    headers = {"Authorization": f"Bearer {SECRET}"}
    challenge = client.post(
        "/challenges", json={"profile_id": "alice"}, headers=headers
    ).json()
    response = client.post(
        f"/challenges/{challenge['challenge_id']}/consume",
        headers=headers,
        json={
            "profile_id": "alice",
            "observed_gestures": challenge["gestures"],
            "sequence_status": "SUCCESS",
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert "invalid_behavioral_match_score" in response.json()["reasons"]


def test_bad_bind_configuration_is_rejected_before_endpoint_processing():
    client = TestClient(create_app(make_settings(host="0.0.0.0")))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "non_loopback_bind_rejected"


def test_request_validation_rejects_invalid_payload():
    client = TestClient(create_app(make_settings()))
    headers = {"Authorization": f"Bearer {SECRET}"}
    response = client.post("/challenges", headers=headers, json={"profile_id": "../alice"})
    assert response.status_code == 422
