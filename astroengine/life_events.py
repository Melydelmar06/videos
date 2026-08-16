"""CRUD for the life-event log (My Life screen)."""

from __future__ import annotations

import sqlite3
from datetime import date

from astroengine.models import LifeEvent


def add_life_event(conn: sqlite3.Connection, event: LifeEvent) -> int:
    cur = conn.execute(
        """INSERT INTO life_events
           (birth_profile_id, start_date, end_date, category, title, description, importance)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            event.birth_profile_id,
            event.start_date.isoformat(),
            event.end_date.isoformat() if event.end_date else None,
            event.category,
            event.title,
            event.description,
            event.importance,
        ),
    )
    conn.commit()
    event.id = cur.lastrowid
    return cur.lastrowid


def _row_to_event(row: sqlite3.Row) -> LifeEvent:
    return LifeEvent(
        id=row["id"],
        birth_profile_id=row["birth_profile_id"],
        start_date=date.fromisoformat(row["start_date"]),
        end_date=date.fromisoformat(row["end_date"]) if row["end_date"] else None,
        category=row["category"],
        title=row["title"],
        description=row["description"],
        importance=row["importance"],
    )


def get_life_event(conn: sqlite3.Connection, event_id: int) -> LifeEvent:
    row = conn.execute("SELECT * FROM life_events WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        raise KeyError(f"no life_event with id={event_id}")
    return _row_to_event(row)


def list_life_events(
    conn: sqlite3.Connection,
    birth_profile_id: int,
    start: date | None = None,
    end: date | None = None,
) -> list[LifeEvent]:
    """List events for a profile, optionally overlapping [start, end]."""
    query = "SELECT * FROM life_events WHERE birth_profile_id = ?"
    params: list = [birth_profile_id]

    if start is not None:
        # an event overlaps the window if it has no end_date and starts on/before
        # the window's end, or its [start_date, end_date] range overlaps [start, end]
        query += " AND (COALESCE(end_date, start_date) >= ?)"
        params.append(start.isoformat())
    if end is not None:
        query += " AND start_date <= ?"
        params.append(end.isoformat())

    query += " ORDER BY start_date"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_event(row) for row in rows]


def update_life_event(conn: sqlite3.Connection, event: LifeEvent) -> None:
    if event.id is None:
        raise ValueError("event.id is required for update")
    conn.execute(
        """UPDATE life_events
           SET start_date = ?, end_date = ?, category = ?, title = ?,
               description = ?, importance = ?
           WHERE id = ?""",
        (
            event.start_date.isoformat(),
            event.end_date.isoformat() if event.end_date else None,
            event.category,
            event.title,
            event.description,
            event.importance,
            event.id,
        ),
    )
    conn.commit()


def delete_life_event(conn: sqlite3.Connection, event_id: int) -> None:
    conn.execute("DELETE FROM life_events WHERE id = ?", (event_id,))
    conn.commit()
