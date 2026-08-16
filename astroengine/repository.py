"""Persistence layer: save/load BirthProfile, AstrologySettings, and
NatalChart results to/from SQLite.
"""

from __future__ import annotations

import sqlite3
from datetime import date, time

from astroengine.models import (
    BirthProfile, DataConfidence, HouseCusp, NatalAngle, NatalAspect, NatalPlanet,
)
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings


def save_birth_profile(conn: sqlite3.Connection, profile: BirthProfile) -> int:
    cur = conn.execute(
        """INSERT INTO birth_profiles
           (name, birth_date, birth_time, time_known, birth_place, latitude, longitude, timezone_name)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            profile.name,
            profile.birth_date.isoformat(),
            profile.birth_time.isoformat() if profile.birth_time else None,
            int(profile.time_known),
            profile.birth_place,
            profile.latitude,
            profile.longitude,
            profile.timezone_name,
        ),
    )
    conn.commit()
    profile.id = cur.lastrowid
    return cur.lastrowid


def load_birth_profile(conn: sqlite3.Connection, profile_id: int) -> BirthProfile:
    row = conn.execute("SELECT * FROM birth_profiles WHERE id = ?", (profile_id,)).fetchone()
    if row is None:
        raise KeyError(f"no birth_profile with id={profile_id}")
    return BirthProfile(
        id=row["id"],
        name=row["name"],
        birth_date=date.fromisoformat(row["birth_date"]),
        birth_time=time.fromisoformat(row["birth_time"]) if row["birth_time"] else None,
        time_known=bool(row["time_known"]),
        birth_place=row["birth_place"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        timezone_name=row["timezone_name"],
    )


def save_astrology_settings(conn: sqlite3.Connection, settings: AstrologySettings) -> int:
    row = settings.to_row()
    cur = conn.execute(
        """INSERT INTO astrology_settings
           (birth_profile_id, zodiac_type, ayanamsha, house_system, node_type,
            rulership_scheme, aspect_set_json, orb_rules_json, timezone_policy_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(birth_profile_id) DO UPDATE SET
             zodiac_type=excluded.zodiac_type, ayanamsha=excluded.ayanamsha,
             house_system=excluded.house_system, node_type=excluded.node_type,
             rulership_scheme=excluded.rulership_scheme,
             aspect_set_json=excluded.aspect_set_json, orb_rules_json=excluded.orb_rules_json,
             timezone_policy_json=excluded.timezone_policy_json,
             updated_at=datetime('now')""",
        (
            row["birth_profile_id"], row["zodiac_type"], row["ayanamsha"], row["house_system"],
            row["node_type"], row["rulership_scheme"], row["aspect_set_json"],
            row["orb_rules_json"], row["timezone_policy_json"],
        ),
    )
    conn.commit()
    settings.id = cur.lastrowid or _settings_id_for_profile(conn, settings.birth_profile_id)
    return settings.id


def _settings_id_for_profile(conn: sqlite3.Connection, birth_profile_id: int) -> int:
    row = conn.execute(
        "SELECT id FROM astrology_settings WHERE birth_profile_id = ?", (birth_profile_id,)
    ).fetchone()
    return row["id"]


def load_astrology_settings(conn: sqlite3.Connection, birth_profile_id: int) -> AstrologySettings:
    row = conn.execute(
        "SELECT * FROM astrology_settings WHERE birth_profile_id = ?", (birth_profile_id,)
    ).fetchone()
    if row is None:
        raise KeyError(f"no astrology_settings for birth_profile_id={birth_profile_id}")
    return AstrologySettings.from_row(dict(row))


def save_natal_chart(conn: sqlite3.Connection, birth_profile_id: int, chart: NatalChart) -> None:
    conn.execute("DELETE FROM natal_planets WHERE birth_profile_id = ?", (birth_profile_id,))
    conn.execute("DELETE FROM natal_houses WHERE birth_profile_id = ?", (birth_profile_id,))
    conn.execute("DELETE FROM natal_angles WHERE birth_profile_id = ?", (birth_profile_id,))
    conn.execute("DELETE FROM natal_aspects WHERE birth_profile_id = ?", (birth_profile_id,))

    for p in chart.planets:
        conn.execute(
            """INSERT INTO natal_planets
               (birth_profile_id, planet, longitude, sign, degree_in_sign, house,
                is_retrograde, speed_longitude, data_confidence_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (birth_profile_id, p.planet, p.longitude, p.sign, p.degree_in_sign, p.house,
             int(p.is_retrograde), p.speed_longitude, p.confidence.to_json()),
        )

    for h in chart.houses:
        conn.execute(
            """INSERT INTO natal_houses
               (birth_profile_id, house_number, longitude, sign, degree_in_sign,
                ruling_planet, data_confidence_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (birth_profile_id, h.house_number, h.longitude, h.sign, h.degree_in_sign,
             h.ruling_planet, h.confidence.to_json()),
        )

    for a in chart.angles:
        conn.execute(
            """INSERT INTO natal_angles
               (birth_profile_id, name, longitude, sign, degree_in_sign, data_confidence_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (birth_profile_id, a.name, a.longitude, a.sign, a.degree_in_sign, a.confidence.to_json()),
        )

    for asp in chart.aspects:
        conn.execute(
            """INSERT INTO natal_aspects
               (birth_profile_id, point_a, point_b, aspect_type, exact_angle, orb,
                is_applying, data_confidence_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (birth_profile_id, asp.point_a, asp.point_b, asp.aspect_type, asp.exact_angle,
             asp.orb, int(asp.is_applying), asp.confidence.to_json()),
        )

    conn.commit()


def load_natal_chart(conn: sqlite3.Connection, birth_profile_id: int) -> NatalChart:
    planets = [
        NatalPlanet(
            id=row["id"], birth_profile_id=birth_profile_id, planet=row["planet"],
            longitude=row["longitude"], sign=row["sign"], degree_in_sign=row["degree_in_sign"],
            house=row["house"], is_retrograde=bool(row["is_retrograde"]),
            speed_longitude=row["speed_longitude"],
            confidence=DataConfidence.from_json(row["data_confidence_json"]),
        )
        for row in conn.execute("SELECT * FROM natal_planets WHERE birth_profile_id = ?", (birth_profile_id,))
    ]
    houses = [
        HouseCusp(
            id=row["id"], birth_profile_id=birth_profile_id, house_number=row["house_number"],
            longitude=row["longitude"], sign=row["sign"], degree_in_sign=row["degree_in_sign"],
            ruling_planet=row["ruling_planet"],
            confidence=DataConfidence.from_json(row["data_confidence_json"]),
        )
        for row in conn.execute("SELECT * FROM natal_houses WHERE birth_profile_id = ? ORDER BY house_number", (birth_profile_id,))
    ]
    angles = [
        NatalAngle(
            id=row["id"], birth_profile_id=birth_profile_id, name=row["name"],
            longitude=row["longitude"], sign=row["sign"], degree_in_sign=row["degree_in_sign"],
            confidence=DataConfidence.from_json(row["data_confidence_json"]),
        )
        for row in conn.execute("SELECT * FROM natal_angles WHERE birth_profile_id = ?", (birth_profile_id,))
    ]
    aspects = [
        NatalAspect(
            id=row["id"], birth_profile_id=birth_profile_id, point_a=row["point_a"], point_b=row["point_b"],
            aspect_type=row["aspect_type"], exact_angle=row["exact_angle"], orb=row["orb"],
            is_applying=bool(row["is_applying"]),
            confidence=DataConfidence.from_json(row["data_confidence_json"]),
        )
        for row in conn.execute("SELECT * FROM natal_aspects WHERE birth_profile_id = ?", (birth_profile_id,))
    ]
    return NatalChart(planets=planets, houses=houses, angles=angles, aspects=aspects)
