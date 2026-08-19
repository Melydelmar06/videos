"""Check-in persistence: HUMAN data, one canonical row per user per
calendar day (overwritable, not appended -- see PRODUCT_ARCHITECTURE.md
section 6). Never touches, and is never touched by, daily_dimension_
snapshots (CHART data) beyond the read-only chart_snapshot_id reference
captured for later pattern analysis.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

VALID_MOODS = {"Energised", "Calm", "Happy", "Flat", "Anxious", "Emotional", "Irritable", "Overwhelmed", "Exhausted"}
VALID_LIFE_AREAS = {"Relationship", "Work", "Money", "Family", "Health", "Myself", "Something else", "I don't know"}


def upsert_checkin(
    conn: sqlite3.Connection, user_id: int, mood: str, life_area: str | None, note: str | None,
    chart_snapshot_id: int | None = None, checkin_date: date | None = None,
) -> dict:
    if mood not in VALID_MOODS:
        raise ValueError(f"unknown mood: {mood!r}")
    if life_area is not None and life_area not in VALID_LIFE_AREAS:
        raise ValueError(f"unknown life_area: {life_area!r}")

    checkin_date = checkin_date or datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO check_ins (user_id, checkin_date, mood, life_area, note, chart_snapshot_id, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id, checkin_date) DO UPDATE SET
             mood = excluded.mood, life_area = excluded.life_area, note = excluded.note,
             chart_snapshot_id = COALESCE(excluded.chart_snapshot_id, check_ins.chart_snapshot_id),
             updated_at = excluded.updated_at""",
        (user_id, checkin_date.isoformat(), mood, life_area, note, chart_snapshot_id, now),
    )
    conn.commit()
    return get_checkin(conn, user_id, checkin_date)


def get_checkin(conn: sqlite3.Connection, user_id: int, checkin_date: date | None = None) -> dict | None:
    checkin_date = checkin_date or datetime.now(timezone.utc).date()
    row = conn.execute(
        "SELECT checkin_date, mood, life_area, note, created_at, updated_at FROM check_ins "
        "WHERE user_id = ? AND checkin_date = ?",
        (user_id, checkin_date.isoformat()),
    ).fetchone()
    return dict(row) if row else None


def list_checkins(conn: sqlite3.Connection, user_id: int, limit: int = 60) -> list[dict]:
    rows = conn.execute(
        "SELECT checkin_date, mood, life_area, note, created_at FROM check_ins "
        "WHERE user_id = ? ORDER BY checkin_date DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]
