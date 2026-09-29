"""Read-only activity dashboard query tests; no browser activity is collected."""
import sqlite3

import pytest

from backend.activity_dashboard import (
    ActivityDashboard,
    ActivityDashboardAuthorizationError,
    ActivityDashboardError,
)
from backend.database import DATABASE_FILENAME, database_connection, initialize_database

TOKEN = "dashboard-test-token-at-least-32-characters"


def make_dashboard(tmp_path):
    db_path = initialize_database(tmp_path / DATABASE_FILENAME)
    with database_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO profiles VALUES (?, ?, ?, ?)",
            ("user_1", "created", "consented", "features-v1"),
        )
        connection.executemany(
            "INSERT INTO security_events "
            "(occurred_at,event_type,outcome,profile_id,details_json) VALUES (?,?,?,?,?)",
            [
                ("2026-04-02T12:00:00+00:00", "auth_attempt", "success", "user_1", '{"secret":"must-not-leak"}'),
                ("2026-04-03T12:00:00+00:00", "challenge_consume", "denied", "user_1", '{"token":"private"}'),
                ("2026-04-04T12:00:00+00:00", "auth_attempt", "failure", "user_1", '{}'),
            ],
        )
    return db_path, ActivityDashboard(db_path, TOKEN)


def test_lists_minimized_events_in_reverse_chronological_pages(tmp_path):
    _, dashboard = make_dashboard(tmp_path)
    page = dashboard.list_events(TOKEN, limit=2)
    assert page.total == 3
    assert page.limit == 2
    assert page.offset == 0
    assert [row["event_type"] for row in page.items] == ["auth_attempt", "challenge_consume"]
    assert all("details_json" not in row for row in page.items)
    assert all("secret" not in str(row) and "token" not in str(row) for row in page.items)

    next_page = dashboard.list_events(TOKEN, limit=2, offset=2)
    assert len(next_page.items) == 1
    assert next_page.items[0]["occurred_at"] == "2026-04-02T12:00:00+00:00"


def test_filters_exact_type_outcome_and_timezone_aware_range(tmp_path):
    _, dashboard = make_dashboard(tmp_path)
    page = dashboard.list_events(
        TOKEN,
        event_type="auth_attempt",
        outcome="success",
        after="2026-04-02T14:00:00+02:00",
        before="2026-04-03T00:00:00Z",
    )
    assert page.total == 1
    assert page.items[0]["event_type"] == "auth_attempt"


def test_bad_token_is_denied(tmp_path):
    _, dashboard = make_dashboard(tmp_path)
    with pytest.raises(ActivityDashboardAuthorizationError):
        dashboard.list_events("incorrect-token-value-long-enough-000")


@pytest.mark.parametrize("kwargs", [
    {"event_type": "password"},
    {"outcome": "visitor-supplied text"},
    {"limit": 0},
    {"limit": 101},
    {"offset": -1},
    {"after": "2026-04-02T12:00:00"},
    {"after": "2026-04-04T00:00:00Z", "before": "2026-04-03T00:00:00Z"},
])
def test_rejects_invalid_filters_and_ranges(tmp_path, kwargs):
    _, dashboard = make_dashboard(tmp_path)
    with pytest.raises(ActivityDashboardError):
        dashboard.list_events(TOKEN, **kwargs)


def test_refuses_write_and_returns_no_raw_details(tmp_path):
    db_path, dashboard = make_dashboard(tmp_path)
    page = dashboard.list_events(TOKEN)
    assert page.total == 3
    assert all("details_json" not in row for row in page.items)
    with pytest.raises(ActivityDashboardError):
        with dashboard._connect_read_only() as connection:
            connection.execute("DELETE FROM security_events")


def test_refuses_unmarked_database_and_does_not_modify_it(tmp_path):
    path = tmp_path / DATABASE_FILENAME
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
        connection.execute("INSERT INTO unrelated VALUES ('keep')")
    dashboard = ActivityDashboard(path, TOKEN)
    with pytest.raises(ActivityDashboardError):
        dashboard.list_events(TOKEN)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT value FROM unrelated").fetchone()[0] == "keep"


def test_rejects_short_token_and_wrong_database_filename(tmp_path):
    path = tmp_path / DATABASE_FILENAME
    initialize_database(path)
    with pytest.raises(ActivityDashboardError):
        ActivityDashboard(path, "short")
    with pytest.raises(ActivityDashboardError):
        ActivityDashboard(tmp_path / "other.sqlite3", TOKEN)
