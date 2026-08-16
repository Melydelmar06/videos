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
