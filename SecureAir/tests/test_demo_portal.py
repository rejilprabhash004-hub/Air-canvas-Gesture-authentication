"""Server-side authorization tests for the local controlled demo portal."""
from fastapi.testclient import TestClient

from demo_portal.app import create_demo_app


def client():
    return TestClient(create_demo_app(), client=("127.0.0.1", 45678))


def post_decision(test_client, *, sequence="SUCCESS", challenge="true", score="0.95", threshold="0.8"):
    return test_client.post(
        "/demo/decision",
        data={
            "sequence_status": sequence,
            "challenge_success": challenge,
            "behavioral_match_score": score,
            "threshold": threshold,
        },
        follow_redirects=False,
    )


def test_protected_resource_denies_without_server_authorized_session():
    response = client().get("/protected")
    assert response.status_code == 403


def test_valid_demo_decision_grants_resource_server_side():
    test_client = client()
    response = post_decision(test_client)
    assert response.status_code == 200
    assert "Server decision: ALLOW" in response.text
    assert "secureair_demo_session" in response.headers["set-cookie"]

    protected = test_client.get("/protected")
    assert protected.status_code == 200
    assert "Protected demo resource" in protected.text


def test_failed_sequence_or_challenge_does_not_grant_resource():
    for payload in (
        {"sequence": "FAILED"},
        {"challenge": "false"},
        {"score": "0.1"},
    ):
        test_client = client()
        post_decision(test_client, **payload)
        assert test_client.get("/protected").status_code == 403


def test_invalid_fields_fail_closed_and_do_not_grant_resource():
    test_client = client()
    response = post_decision(test_client, sequence="FORGED", challenge="maybe", score="nan")
    assert response.status_code == 200
    assert "Server decision: DENY" in response.text
    assert test_client.get("/protected").status_code == 403


def test_session_cookie_is_http_only_and_logout_revokes_server_session():
    test_client = client()
    response = post_decision(test_client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert test_client.get("/protected").status_code == 200

    test_client.post("/logout")
    assert test_client.get("/protected").status_code == 403


def test_rejects_non_loopback_clients():
    nonlocal_client = TestClient(create_demo_app(), client=("192.0.2.10", 45678))
    assert nonlocal_client.get("/").status_code == 403
