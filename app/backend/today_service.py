"""Computes (or returns the cached) Today reading for a user: today's
Understand dimensions, translated to plain language. Cached once per
calendar day per user in daily_dimension_snapshots (CHART data -- see
PRODUCT_ARCHITECTURE.md section 2 -- never touched by a check-in).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone

from astroengine.daily_dimensions import DAILY_DIMENSIONS, compute_all_dimension_reads
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.timing_engine import compute_timing_result

import product_llm

DEFAULT_SETTINGS = AstrologySettings(
    zodiac_type="tropical", house_system="placidus", node_type="true", rulership_scheme="modern",
)


def _natal_summary(chart) -> str:
    by_name = {p.planet: p for p in chart.planets}
    sun, moon = by_name["sun"], by_name["moon"]
    asc = next((a for a in chart.angles if a.name == "Ascendant"), None)
    parts = [f"Sun in {sun.sign}", f"Moon in {moon.sign}"]
    if asc is not None:
        parts.append(f"{asc.sign} rising")
    return ", ".join(parts) + "."


def _describe_hit(hit, significator_point: str, role: str, specificity: str) -> str:
    corroboration = (
        "independently confirmed by another system around the same date"
        if hit.temporal_corroborators else
        "active today, but not independently confirmed close to a specific date"
    )
    if significator_point != hit.natal_target:
        target_note = (
            f"{hit.natal_target} -- always exactly opposite {significator_point} by definition, "
            f"so this is equally a hit to {significator_point} ({role})"
        )
    else:
        target_note = f"{hit.natal_target} ({role})"
    return f"[{hit.evidence_strength} / {specificity} specificity] {hit.system} contacts {target_note} via {hit.aspect_type} -- {corroboration}."


def _build_active_dimensions(dimension_reads: dict, chart, settings) -> list[dict]:
    from astroengine.daily_dimensions import build_dimension_significators

    active = []
    for key, read in dimension_reads.items():
        if read.tier == "quiet":
            continue
        significators = build_dimension_significators(chart, settings, key)
        roles_to_point = {s.role: s.point for s in significators}
        evidence_text = [
            _describe_hit(hit, roles_to_point[a.natal_role], a.natal_role, a.theme_specificity)
            for hit, a in read.top
        ]
        active.append({
            "key": key, "label": DAILY_DIMENSIONS[key]["label"], "framing": DAILY_DIMENSIONS[key]["framing"],
            "tier": read.tier, "character": read.character, "evidence_text": evidence_text,
        })
    return active


def get_today_reading(conn: sqlite3.Connection, user_id: int, profile, target_date: date | None = None) -> dict:
    target_date = target_date or datetime.now(timezone.utc).date()

    cached = conn.execute(
        "SELECT dimensions_json FROM daily_dimension_snapshots WHERE user_id = ? AND snapshot_date = ?",
        (user_id, target_date.isoformat()),
    ).fetchone()
    if cached is not None:
        return json.loads(cached["dimensions_json"])

    settings = DEFAULT_SETTINGS
    chart = compute_natal_chart(profile, settings)

    window_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    window_end = window_start + timedelta(days=1) - timedelta(seconds=1)
    result = compute_timing_result(chart, settings, profile, window_start, window_end)

    dimension_reads = compute_all_dimension_reads(result.hits, chart, settings)
    active_dimensions = _build_active_dimensions(dimension_reads, chart, settings)
    natal_summary = _natal_summary(chart)

    llm_output = product_llm.generate_today_reading(natal_summary, active_dimensions)

    dimensions_out = {}
    for key, read in dimension_reads.items():
        text = llm_output["dimensions"].get(key)
        dimensions_out[key] = {
            "label": DAILY_DIMENSIONS[key]["label"], "tier": read.tier, "character": read.character, "text": text,
        }

    payload = {
        "date": target_date.isoformat(),
        "natal_summary": natal_summary,
        "overall_note": llm_output.get("overall_note"),
        "dimensions": dimensions_out,
        # internal-only field, used by regulate_service to derive chart_state
        # without recomputing the timing engine a second time this request.
        "_dimension_reads_tier_character": {
            key: {"tier": read.tier, "character": read.character} for key, read in dimension_reads.items()
        },
    }

    conn.execute(
        "INSERT INTO daily_dimension_snapshots (user_id, snapshot_date, dimensions_json) VALUES (?, ?, ?)",
        (user_id, target_date.isoformat(), json.dumps(payload)),
    )
    conn.commit()
    return payload
