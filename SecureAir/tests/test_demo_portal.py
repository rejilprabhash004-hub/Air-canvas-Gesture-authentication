"""Server-side authorization tests for the local controlled demo portal."""
from fastapi.testclient import TestClient

from demo_portal.app import create_demo_app


def client(peer="127.0.0.1"):
    return TestClient(create_demo_app(), client=(peer, 45678))


def post_decision(test_client, *, sequence="SUCCESS", challenge="true", score="0.95", threshold="0.8"):
    return test_client.post(
        "/demo/decision",
        data={
            "sequence_status": sequence,
            "challenge_success": challenge,
            "behavioral_match_score": score,
            "threshold": threshold,
        },
    )


def test_protected_resource_denies_without_server_authorized_session():
    assert client().get("/protected").status_code == 403


def test_valid_demo_decision_grants_resource_server_side():
    test_client = client()
    response = post_decision(test_client)
    assert response.status_code == 200
    assert "Server decision: ALLOW" in response.text
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert test_client.get("/protected").status_code == 200
    assert "Protected demo resource" in test_client.get("/protected").text


def test_failed_sequence_challenge_or_score_does_not_grant_resource():
    cases = (
        {"sequence": "FAILED"},
        {"challenge": "false"},
        {"score": "0.1"},
    )
    for values in cases:
        test_client = client()
        post_decision(test_client, **values)
        assert test_client.get("/protected").status_code == 403


def test_invalid_fields_fail_closed_and_do_not_grant_resource():
    test_client = client()
    response = post_decision(test_client, sequence="FORGED", challenge="maybe", score="nan")
    assert response.status_code == 200
    assert "Server decision: DENY" in response.text
    assert test_client.get("/protected").status_code == 403


def test_logout_revokes_server_session():
    test_client = client()
    post_decision(test_client)
    assert test_client.get("/protected").status_code == 200
    test_client.post("/logout")
    assert test_client.get("/protected").status_code == 403


def test_rejects_non_loopback_clients():
    assert client("192.0.2.10").get("/").status_code == 403
