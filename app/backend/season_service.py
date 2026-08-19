"""Caches the six-month Season reading per user, regenerated every ~2-4
weeks (default 21 days) or on explicit refresh -- the underlying evidence
doesn't meaningfully change day to day, so recomputing (and re-calling the
LLM) on every visit is wasted cost. See PRODUCT_ARCHITECTURE.md section 3.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import reading as reading_module

REGENERATE_AFTER_DAYS = 21


def _parse_db_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_season_reading(conn: sqlite3.Connection, user_id: int, profile, force_refresh: bool = False) -> dict:
    if not force_refresh:
        row = conn.execute(
            "SELECT reading_json, generated_at FROM season_snapshots WHERE user_id = ? "
            "ORDER BY generated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row is not None:
            age = datetime.now(timezone.utc) - _parse_db_datetime(row["generated_at"])
            if age < timedelta(days=REGENERATE_AFTER_DAYS):
                cached = json.loads(row["reading_json"])
                cached["_cached"] = True
                return cached

    reading = reading_module.generate_reading(
        name=profile.name, birth_date=profile.birth_date, birth_time=profile.birth_time,
        latitude=profile.latitude, longitude=profile.longitude, timezone_name=profile.timezone_name,
    )
    conn.execute(
        "INSERT INTO season_snapshots (user_id, window_start, window_end, reading_json) VALUES (?, ?, ?, ?)",
        (user_id, reading["window"]["start"], reading["window"]["end"], json.dumps(reading)),
    )
    conn.commit()
    reading["_cached"] = False
    return reading
