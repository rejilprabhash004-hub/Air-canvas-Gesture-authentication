"""End-to-end in-process integration of portal and real local challenge API."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app as create_api_app
from backend.config import Settings
from demo_portal.app import create_demo_app

SECRET = "integration-test-secret-long-enough-123456789"


def test_portal_issues_consumes_and_rejects_replayed_api_challenge():
    api_client = TestClient(
        create_api_app(Settings(
            data_dir=Path("/tmp/secureair-integration"),
            host="127.0.0.1",
            port=8000,
            secret_key=SECRET,
            lockout_max_attempts=3,
            lockout_seconds=300,
            challenge_seconds=60,
        )),
        client=("127.0.0.1", 50001),
    )
    issued = []

    def server_side_api_call(path, payload):
        response = api_client.post(
            path,
            json=payload,
            headers={"Authorization": f"Bearer {SECRET}"},
        )
        assert response.status_code == 200, response.text
        value = response.json()
        if path == "/challenges":
            issued.append(value)
        return value

    portal = TestClient(
        create_demo_app(api_caller=server_side_api_call),
        client=("127.0.0.1", 50002),
    )
    home = portal.get("/")
    assert home.status_code == 200
    assert len(issued) == 1
    challenge = issued[0]
    assert challenge["profile_id"] == "demo_user"
    assert all(gesture in home.text for gesture in challenge["gestures"])

    form = {
        "challenge_id": challenge["challenge_id"],
        "profile_id": "demo_user",
        "observed_gestures": ", ".join(challenge["gestures"]),
        "sequence_status": "SUCCESS",
        "behavioral_match_score": "0.95",
        "threshold": "0.8",
    }
    decision = portal.post("/demo/decision", data=form)
    assert decision.status_code == 200
    assert "Server decision: ALLOW" in decision.text
    assert portal.get("/protected").status_code == 200

    replay = portal.post("/demo/decision", data=form)
    assert "Server decision: DENY" in replay.text
    assert portal.get("/protected").status_code == 403
