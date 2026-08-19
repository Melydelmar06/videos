"""Orchestrates one end-to-end reading: birth data -> natal chart -> forward
forecast packet -> per-category evidence slice -> LLM writing pass. All
calculation goes through astroengine unchanged; this module only shapes
inputs/outputs for the web app.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from astroengine.forecast import build_forecast_packet
from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.theme import assess_theme_relevance, theme_specificity_for_window
from astroengine.theme_definitions import LIFE_CATEGORIES, build_category_significators

import llm

READING_WINDOW_DAYS = 180
MAX_EVIDENCE_PER_CATEGORY = 6


class _HitView:
    """Adapter so a serialized forecast-packet dict can be scored by
    astroengine.theme (which expects TimingHit-like attribute access)."""

    def __init__(self, d: dict):
        self.natal_target = d["natal_target"]
        self.system = d["system"]
        self.moving_point = d["moving_point"]
        self.aspect_type = d["aspect_type"]
        self.evidence_strength = d["evidence_strength"]
        self.exact_hit_dates = d["exact_hit_dates"]
        self.temporal_corroborators = d["temporal_corroborators"]
        self._raw = d


def _format_date_list(iso_dates: list[str]) -> str:
    if not iso_dates:
        return "no exact date in this window"
    parsed = [datetime.fromisoformat(d) for d in iso_dates]
    return ", ".join(d.strftime("%b %-d, %Y") for d in parsed)


def _describe_hit(view: _HitView, significator_point: str, role: str, specificity: str) -> str:
    corroboration = (
        "independently confirmed by another system around the same date"
        if view.temporal_corroborators else
        "active during this window, but not independently confirmed close to a specific date"
    )
    # The evidence engine always keeps one side of a definitionally-linked
    # pair (Ascendant over Descendant, Midheaven over IC) and drops the
    # other as a mirror-duplicate, since they are always exactly opposite
    # by definition -- see astroengine.evidence. So a hit whose raw
    # natal_target is "Midheaven" can be the real, matching evidence for a
    # significator keyed on "IC" (4th house). Without this note, the copy
    # would read as if Midheaven IS the 4th house cusp, which is wrong.
    if significator_point != view.natal_target:
        target_note = (
            f"{view.natal_target} -- which is always exactly opposite {significator_point} by "
            f"definition, so this is equally a hit to {significator_point} ({role})"
        )
    else:
        target_note = f"{view.natal_target} ({role})"
    return (
        f"[{view.evidence_strength} / {specificity} specificity] {view.system} contacts "
        f"{target_note} via {view.aspect_type}, exact: {_format_date_list(view.exact_hit_dates)} "
        f"-- {corroboration}."
    )


def _natal_summary(chart, profile: BirthProfile) -> str:
    by_name = {p.planet: p for p in chart.planets}
    sun, moon = by_name["sun"], by_name["moon"]
    asc = next((a for a in chart.angles if a.name == "Ascendant"), None)
    parts = [f"Sun in {sun.sign}", f"Moon in {moon.sign}"]
    if asc is not None:
        parts.append(f"{asc.sign} rising")
    return ", ".join(parts) + "."


def build_category_evidence(chart, settings: AstrologySettings, forecast_packet: dict) -> dict[str, list[str]]:
    eligible_hits = [
        _HitView(h)
        for tier in ("strong", "moderate")
        for h in forecast_packet["timing_evidence"][tier]
    ]

    category_evidence: dict[str, list[str]] = {}
    for key in LIFE_CATEGORIES:
        significators = build_category_significators(chart, settings, key)
        roles_to_point = {s.role: s.point for s in significators}
        relevant = []
        for hit in eligible_hits:
            assessment = assess_theme_relevance(hit, significators)
            if assessment.theme_relevant:
                relevant.append((hit, assessment))

        # strongest, most specific, most temporally-corroborated first
        relevant.sort(
            key=lambda pair: (
                pair[0].evidence_strength == "strong",
                bool(pair[0].temporal_corroborators),
                {"high": 2, "moderate": 1, "low": 0}.get(pair[1].theme_specificity, 0),
            ),
            reverse=True,
        )

        top = relevant[:MAX_EVIDENCE_PER_CATEGORY]
        category_evidence[key] = [
            _describe_hit(hit, roles_to_point[a.natal_role], a.natal_role, a.theme_specificity)
            for hit, a in top
        ]

    return category_evidence


def generate_reading(
    name: str, birth_date: date, birth_time: time, latitude: float, longitude: float, timezone_name: str,
) -> dict:
    profile = BirthProfile(
        name=name, birth_date=birth_date, birth_time=birth_time, time_known=True,
        birth_place="", latitude=latitude, longitude=longitude, timezone_name=timezone_name,
    )
    settings = AstrologySettings(zodiac_type="tropical", house_system="placidus", node_type="true", rulership_scheme="modern")

    chart = compute_natal_chart(profile, settings)

    query_start = datetime.now(timezone.utc)
    query_end = query_start + timedelta(days=READING_WINDOW_DAYS)
    forecast_packet = build_forecast_packet(profile, settings, chart, query_start, query_end)

    category_evidence = build_category_evidence(chart, settings, forecast_packet)
    natal_summary = _natal_summary(chart, profile)

    reading = llm.generate_reading(natal_summary, category_evidence)

    return {
        "natal_summary": natal_summary,
        "window": {"start": query_start.date().isoformat(), "end": query_end.date().isoformat()},
        "categories": {
            key: {
                "label": LIFE_CATEGORIES[key]["label"],
                **reading[key],
            }
            for key in LIFE_CATEGORIES
        },
    }
