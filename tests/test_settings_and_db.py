import pytest

from astroengine import repository
from astroengine.settings import AstrologySettings


def test_sidereal_requires_ayanamsha():
    with pytest.raises(ValueError):
        AstrologySettings(zodiac_type="sidereal", ayanamsha=None)


def test_default_settings_are_tropical_placidus_mean_node_modern():
    s = AstrologySettings()
    assert s.zodiac_type == "tropical"
    assert s.house_system == "placidus"
    assert s.node_type == "mean"
    assert s.rulership_scheme == "modern"
    assert set(s.enabled_aspects()) == {"conjunction", "sextile", "square", "trine", "opposition"}


def test_settings_round_trip_through_sqlite(conn, sample_profile):
    profile_id = repository.save_birth_profile(conn, sample_profile)
    settings = AstrologySettings(
        birth_profile_id=profile_id,
        zodiac_type="sidereal",
        ayanamsha="lahiri",
        house_system="whole_sign",
        node_type="true",
        rulership_scheme="traditional",
    )
    repository.save_astrology_settings(conn, settings)

    reloaded = repository.load_astrology_settings(conn, profile_id)
    assert reloaded.zodiac_type == "sidereal"
    assert reloaded.ayanamsha == "lahiri"
    assert reloaded.house_system == "whole_sign"
    assert reloaded.node_type == "true"
    assert reloaded.rulership_scheme == "traditional"


def test_settings_upsert_on_conflict(conn, sample_profile, default_settings):
    profile_id = repository.save_birth_profile(conn, sample_profile)
    default_settings.birth_profile_id = profile_id
    repository.save_astrology_settings(conn, default_settings)

    default_settings.house_system = "koch"
    repository.save_astrology_settings(conn, default_settings)

    reloaded = repository.load_astrology_settings(conn, profile_id)
    assert reloaded.house_system == "koch"

    count = conn.execute(
        "SELECT COUNT(*) AS c FROM astrology_settings WHERE birth_profile_id = ?", (profile_id,)
    ).fetchone()["c"]
    assert count == 1


def test_migrations_are_idempotent(conn):
    from astroengine.db import run_migrations
    run_migrations(conn)  # already applied via conftest fixture; must not raise
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"birth_profiles", "astrology_settings", "natal_planets", "natal_houses",
            "natal_angles", "natal_aspects", "life_events"} <= tables


def test_v1_5_product_tables_exist(conn):
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "magic_link_tokens", "check_ins", "daily_dimension_snapshots",
            "season_snapshots", "practice_interactions"} <= tables


def test_check_in_is_one_per_user_per_day(conn):
    conn.execute("INSERT INTO users (email) VALUES ('a@example.com')")
    user_id = conn.execute("SELECT id FROM users WHERE email = 'a@example.com'").fetchone()["id"]
    conn.execute(
        "INSERT INTO check_ins (user_id, checkin_date, mood) VALUES (?, '2026-08-19', 'calm')", (user_id,)
    )
    conn.commit()
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO check_ins (user_id, checkin_date, mood) VALUES (?, '2026-08-19', 'anxious')", (user_id,)
        )


def test_check_ins_and_daily_snapshots_are_separate_tables(conn):
    """Structural guard for PRODUCT_ARCHITECTURE.md section 2 -- CHART data
    (daily_dimension_snapshots) and HUMAN data (check_ins) must never live
    in the same table, so a self-report can never be mistaken for, or
    silently merged with, a chart-derived read."""
    checkin_cols = {r[1] for r in conn.execute("PRAGMA table_info(check_ins)")}
    snapshot_cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_dimension_snapshots)")}
    assert "mood" in checkin_cols and "mood" not in snapshot_cols
    assert "dimensions_json" in snapshot_cols and "dimensions_json" not in checkin_cols
