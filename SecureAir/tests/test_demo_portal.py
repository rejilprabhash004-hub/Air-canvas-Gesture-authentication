"""Portal tests stub only the server-side API caller; they never bypass its decision."""
from fastapi.testclient import TestClient

from demo_portal.app import create_demo_app


GESTURES = ["FIST", "OPEN_PALM", "THUMBS_UP"]


def fake_api(path, payload):
    if path == "/challenges":
        return {
            "challenge_id": "local-challenge-1",
            "profile_id": payload["profile_id"],
            "gestures": GESTURES,
            "created_at": "now",
            "expires_at": "later",
        }
    if path.endswith("/consume"):
        success = payload["observed_gestures"] == GESTURES
        allowed = (success and payload["sequence_status"] == "SUCCESS"
                   and payload["behavioral_match_score"] is not None
                   and payload["behavioral_match_score"] >= payload["threshold"])
        return {
            "decision": "ALLOW" if allowed else "DENY",
            "allowed": allowed,
            "reasons": ["all_required_signals_passed"] if allowed else ["challenge_failed"],
            "threshold": payload["threshold"],
            "behavioral_score_source": "caller_supplied",
        }
    raise AssertionError(f"Unexpected API path: {path}")


def client(peer="127.0.0.1"):
    return TestClient(create_demo_app(api_caller=fake_api), client=(peer, 45678))


def submit(test_client, *, observed=", ".join(GESTURES), sequence="SUCCESS",
           score="0.95", threshold="0.8", challenge_id="local-challenge-1"):
    return test_client.post("/demo/decision", data={
        "challenge_id": challenge_id,
        "profile_id": "demo_user",
        "observed_gestures": observed,
        "sequence_status": sequence,
        "behavioral_match_score": score,
        "threshold": threshold,
    })


def test_home_page_requests_and_displays_an_api_challenge():
    response = client().get("/")
    assert response.status_code == 200
    assert "local-challenge-1" in response.text
    assert ", ".join(GESTURES) in response.text
    assert "Send response to local API" in response.text


def test_protected_resource_denies_without_an_api_allow():
    assert client().get("/protected").status_code == 403


def test_api_allow_creates_server_side_portal_session():
    test_client = client()
    response = submit(test_client)
    assert response.status_code == 200
    assert "Server decision: ALLOW" in response.text
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    protected = test_client.get("/protected")
    assert protected.status_code == 200
    assert "Protected demo resource" in protected.text


def test_wrong_response_and_failed_signals_do_not_grant_protected_resource():
    for fields in (
        {"observed": "OPEN_PALM, FIST, THUMBS_UP"},
        {"sequence": "FAILED"},
        {"score": "0.1"},
        {"score": ""},
    ):
        test_client = client()
        submit(test_client, **fields)
        assert test_client.get("/protected").status_code == 403


def test_invalid_input_fails_closed():
    test_client = client()
    response = submit(test_client, sequence="FORGED", challenge_id="")
    assert "Server decision: DENY" in response.text
    assert test_client.get("/protected").status_code == 403


def test_logout_revokes_server_side_session():
    test_client = client()
    submit(test_client)
    assert test_client.get("/protected").status_code == 200
    test_client.post("/logout")
    assert test_client.get("/protected").status_code == 403


def test_api_failure_when_issuing_challenge_fails_closed():
    def unavailable(_path, _payload):
        raise RuntimeError("unavailable")
    response = TestClient(create_demo_app(api_caller=unavailable)).get("/")
    assert response.status_code == 503
    assert "access remains denied" in response.text


def test_rejects_non_loopback_clients():
    assert client("192.0.2.10").get("/").status_code == 403
