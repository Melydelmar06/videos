"""Ties a BirthProfile to a signed-in user. One profile per user in
V1.5 -- reusing astroengine.repository's existing save/load, just adding
the user_id association the original single-user schema didn't need.
"""

from __future__ import annotations

import sqlite3
from datetime import date, time

from astroengine import repository
from astroengine.models import BirthProfile


def save_profile_for_user(
    conn: sqlite3.Connection, user_id: int, name: str, birth_date: date, birth_time: time,
    latitude: float, longitude: float, timezone_name: str,
) -> BirthProfile:
    profile = BirthProfile(
        name=name, birth_date=birth_date, birth_time=birth_time, time_known=True,
        birth_place="", latitude=latitude, longitude=longitude, timezone_name=timezone_name,
    )
    profile_id = repository.save_birth_profile(conn, profile)
    conn.execute("UPDATE birth_profiles SET user_id = ? WHERE id = ?", (user_id, profile_id))
    conn.commit()
    return profile


def get_profile_for_user(conn: sqlite3.Connection, user_id: int) -> BirthProfile | None:
    row = conn.execute(
        "SELECT id FROM birth_profiles WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)
    ).fetchone()
    if row is None:
        return None
    return repository.load_birth_profile(conn, row["id"])
