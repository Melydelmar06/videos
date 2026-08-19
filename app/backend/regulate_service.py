"""Orchestrates one Regulate recommendation: today's chart state (from the
already-computed Today snapshot) + today's check-in (if any) -> matched
practice type (astroengine.regulate, deterministic) -> LLM-written copy
for that type. Logs a practice_interactions row (HUMAN-adjacent
interaction log, never read by chart-scoring code) each time a fresh
recommendation is generated.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace

from astroengine.regulate import select_practice

import product_llm
import today_service


def _reads_from_cache(tier_character: dict) -> dict:
    return {key: SimpleNamespace(**vals) for key, vals in tier_character.items()}


def get_regulate_recommendation(
    conn: sqlite3.Connection, user_id: int, profile, mood: str | None, target_date: date | None = None,
) -> dict:
    target_date = target_date or datetime.now(timezone.utc).date()
    today_reading = today_service.get_today_reading(conn, user_id, profile, target_date)
    reads = _reads_from_cache(today_reading["_dimension_reads_tier_character"])

    selection = select_practice(mood, reads)
    copy = product_llm.generate_practice_copy(
        selection.practice_type, selection.mood, selection.chart_state,
        selection.human_chart_mismatch, selection.driven_by,
    )

    conn.execute(
        "INSERT INTO practice_interactions (user_id, interaction_date, practice_type) VALUES (?, ?, ?)",
        (user_id, target_date.isoformat(), selection.practice_type),
    )
    conn.commit()

    return {
        "practice_type": selection.practice_type,
        "alternates": selection.alternates,
        "human_chart_mismatch": selection.human_chart_mismatch,
        "driven_by": selection.driven_by,
        "intro": copy["intro"],
        "practice_title": copy["practice_title"],
        "practice_body": copy["practice_body"],
    }
