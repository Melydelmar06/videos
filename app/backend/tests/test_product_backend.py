import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from astroengine.db import connect_and_migrate  # noqa: E402

import auth  # noqa: E402
import checkin_service  # noqa: E402
import profile as profile_service  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    connection = connect_and_migrate(str(tmp_path / "test.db"))
    yield connection
    connection.close()


def test_request_link_creates_user_and_dev_token(conn):
    result = auth.request_magic_link(conn, "Person@Example.com ")
    assert result["dev_mode"] is True
    assert result["dev_magic_token"]
    row = conn.execute("SELECT email FROM users").fetchone()
    assert row["email"] == "person@example.com"  # trimmed + lowercased


def test_request_link_reuses_existing_user(conn):
    auth.request_magic_link(conn, "a@example.com")
    auth.request_magic_link(conn, "a@example.com")
    count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    assert count == 1


def test_consume_link_issues_session_and_marks_token_used(conn):
    result = auth.request_magic_link(conn, "a@example.com")
    session = auth.consume_magic_link(conn, result["dev_magic_token"])
    assert session["session_token"]
    used_at = conn.execute("SELECT used_at FROM magic_link_tokens").fetchone()["used_at"]
    assert used_at is not None


def test_consume_link_twice_fails():
    from fastapi import HTTPException
    connection = connect_and_migrate(":memory:")
    result = auth.request_magic_link(connection, "a@example.com")
    auth.consume_magic_link(connection, result["dev_magic_token"])
    with pytest.raises(HTTPException):
        auth.consume_magic_link(connection, result["dev_magic_token"])


def test_consume_expired_link_fails(conn):
    from fastapi import HTTPException
    result = auth.request_magic_link(conn, "a@example.com")
    conn.execute(
        "UPDATE magic_link_tokens SET expires_at = ? WHERE token = ?",
        ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), result["dev_magic_token"]),
    )
    conn.commit()
    with pytest.raises(HTTPException):
        auth.consume_magic_link(conn, result["dev_magic_token"])


def test_current_user_id_resolves_valid_session(conn):
    result = auth.request_magic_link(conn, "a@example.com")
    session = auth.consume_magic_link(conn, result["dev_magic_token"])
    user_id = auth.current_user_id(conn, f"Bearer {session['session_token']}")
    row = conn.execute("SELECT id FROM users WHERE email = 'a@example.com'").fetchone()
    assert user_id == row["id"]


def test_current_user_id_rejects_missing_or_bad_auth(conn):
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        auth.current_user_id(conn, None)
    with pytest.raises(HTTPException):
        auth.current_user_id(conn, "Bearer not-a-real-token")


def test_profile_save_and_load_roundtrip(conn):
    conn.execute("INSERT INTO users (email) VALUES ('a@example.com')")
    conn.commit()
    user_id = conn.execute("SELECT id FROM users").fetchone()["id"]

    saved = profile_service.save_profile_for_user(
        conn, user_id, "Jordan", date(1990, 3, 21), time(14, 15, 0), 40.7128, -74.0060, "America/New_York",
    )
    assert saved.name == "Jordan"

    loaded = profile_service.get_profile_for_user(conn, user_id)
    assert loaded is not None
    assert loaded.name == "Jordan"
    assert loaded.birth_date == date(1990, 3, 21)


def test_profile_missing_returns_none(conn):
    conn.execute("INSERT INTO users (email) VALUES ('a@example.com')")
    conn.commit()
    user_id = conn.execute("SELECT id FROM users").fetchone()["id"]
    assert profile_service.get_profile_for_user(conn, user_id) is None


def test_checkin_upsert_validates_mood(conn):
    conn.execute("INSERT INTO users (email) VALUES ('a@example.com')")
    conn.commit()
    user_id = conn.execute("SELECT id FROM users").fetchone()["id"]
    with pytest.raises(ValueError):
        checkin_service.upsert_checkin(conn, user_id, "Ecstatic", None, None)


def test_checkin_upsert_validates_life_area(conn):
    conn.execute("INSERT INTO users (email) VALUES ('a@example.com')")
    conn.commit()
    user_id = conn.execute("SELECT id FROM users").fetchone()["id"]
    with pytest.raises(ValueError):
        checkin_service.upsert_checkin(conn, user_id, "Calm", "Not a real area", None)


def test_checkin_upsert_is_one_per_day_overwritable(conn):
    conn.execute("INSERT INTO users (email) VALUES ('a@example.com')")
    conn.commit()
    user_id = conn.execute("SELECT id FROM users").fetchone()["id"]

    checkin_service.upsert_checkin(conn, user_id, "Calm", "Work", "first note")
    checkin_service.upsert_checkin(conn, user_id, "Anxious", "Money", "updated note")

    count = conn.execute("SELECT COUNT(*) AS c FROM check_ins WHERE user_id = ?", (user_id,)).fetchone()["c"]
    assert count == 1
    latest = checkin_service.get_checkin(conn, user_id)
    assert latest["mood"] == "Anxious"
    assert latest["note"] == "updated note"


def test_checkin_history_orders_most_recent_first(conn):
    conn.execute("INSERT INTO users (email) VALUES ('a@example.com')")
    conn.commit()
    user_id = conn.execute("SELECT id FROM users").fetchone()["id"]

    checkin_service.upsert_checkin(conn, user_id, "Calm", None, None, checkin_date=date(2026, 8, 17))
    checkin_service.upsert_checkin(conn, user_id, "Happy", None, None, checkin_date=date(2026, 8, 19))
    checkin_service.upsert_checkin(conn, user_id, "Flat", None, None, checkin_date=date(2026, 8, 18))

    history = checkin_service.list_checkins(conn, user_id)
    assert [c["checkin_date"] for c in history] == ["2026-08-19", "2026-08-18", "2026-08-17"]
