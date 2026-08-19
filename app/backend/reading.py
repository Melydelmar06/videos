"""Orchestrates one end-to-end reading: birth data -> natal chart -> forward
forecast packet -> per-category evidence slice -> LLM writing pass. All
calculation goes through astroengine unchanged; this module only shapes
inputs/outputs for the web app.

Two things are deliberately kept OUT of the LLM's hands, computed here
instead, so they can never drift from what the engine actually found:
  - the "why is this showing up" transparency panel per category (tier,
    independent-system count, main window, which other categories share
    the same underlying evidence)
  - the ranking that decides which 1-2 categories are "the real story" for
    the bigger-picture synthesis, and which date buckets the timeline gets
The LLM's only job is turning already-computed, already-ranked facts into
plain-language prose -- never deciding what's significant on its own.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from astroengine.forecast import build_forecast_packet
from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.theme import assess_theme_relevance
from astroengine.theme_definitions import LIFE_CATEGORIES, build_category_significators

import llm

READING_WINDOW_DAYS = 180
MAX_EVIDENCE_PER_CATEGORY = 6

# timeline bucket cutoffs, in days from "now" (query_start)
NOW_CUTOFF_DAYS = 21
NEXT_CUTOFF_DAYS = 90

_SPECIFICITY_RANK = {"high": 2, "moderate": 1, "low": 0}


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


def _parse_dates(iso_dates: list[str]) -> list[datetime]:
    return [datetime.fromisoformat(d) for d in iso_dates]


def _format_date_list(iso_dates: list[str]) -> str:
    if not iso_dates:
        return "no exact date in this window"
    return ", ".join(d.strftime("%b %-d, %Y") for d in _parse_dates(iso_dates))


def _describe_hit(view: _HitView, significator_point: str, role: str, specificity: str) -> str:
    """Technical description for the MODEL's internal understanding only --
    never to be echoed into the reading. See the system prompt's jargon ban."""
    corroboration = (
        "independently confirmed by another system around the same date"
        if view.temporal_corroborators else
        "active during this window, but not independently confirmed close to a specific date"
    )
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


def _category_tier(top: list[tuple]) -> str:
    """Computed, not LLM-chosen -- so the visible badge and the 'why' panel
    can never contradict each other. Strong-tier hits under the redesigned
    engine are already temporally corroborated by construction (see
    astroengine.evidence), so a single strong hit alone justifies 'strong
    signal' here."""
    if not top:
        return "quiet"
    if any(hit.evidence_strength == "strong" for hit, _a in top):
        return "strong signal"
    if any(a.theme_specificity in ("high", "moderate") for _hit, a in top):
        return "notable"
    return "minor undertone"


def _main_window(top: list[tuple], query_start: datetime, query_end: datetime) -> str | None:
    """Human-readable month(s) for the single best hit's exact date, if it
    has one in this window. None for background-only evidence."""
    for hit, _a in top:
        for d in _parse_dates(hit.exact_hit_dates):
            if query_start <= d <= query_end:
                return d.strftime("%B %Y")
    return None


def build_category_data(chart, settings: AstrologySettings, forecast_packet: dict) -> dict[str, dict]:
    """Per category: top evidence (hit, assessment, original index) plus
    everything needed downstream (LLM prompt text, the computed 'why'
    panel, and cross-category overlap for the bigger-picture ranking)."""
    eligible_hits = [
        _HitView(h)
        for tier in ("strong", "moderate")
        for h in forecast_packet["timing_evidence"][tier]
    ]

    category_data: dict[str, dict] = {}
    for key in LIFE_CATEGORIES:
        significators = build_category_significators(chart, settings, key)
        roles_to_point = {s.role: s.point for s in significators}
        relevant = []
        for idx, hit in enumerate(eligible_hits):
            assessment = assess_theme_relevance(hit, significators)
            if assessment.theme_relevant:
                relevant.append((idx, hit, assessment))

        relevant.sort(
            key=lambda triple: (
                triple[1].evidence_strength == "strong",
                bool(triple[1].temporal_corroborators),
                _SPECIFICITY_RANK.get(triple[2].theme_specificity, 0),
            ),
            reverse=True,
        )

        top = relevant[:MAX_EVIDENCE_PER_CATEGORY]
        top_hit_pairs = [(hit, a) for _idx, hit, a in top]
        category_data[key] = {
            "top_indices": {idx for idx, _hit, _a in top},
            "top": top_hit_pairs,
            "evidence_text": [
                _describe_hit(hit, roles_to_point[a.natal_role], a.natal_role, a.theme_specificity)
                for hit, a in top_hit_pairs
            ],
        }

    return category_data


def _cross_category_overlap(category_data: dict[str, dict]) -> dict[str, list[str]]:
    """key -> labels of OTHER categories whose top evidence shares at least
    one underlying hit (the same TimingHit, not just the same theme) --
    i.e. genuinely moving together, not just coincidentally both relevant."""
    overlap: dict[str, list[str]] = {key: [] for key in LIFE_CATEGORIES}
    keys = list(LIFE_CATEGORIES.keys())
    for i, key_a in enumerate(keys):
        for key_b in keys[i + 1:]:
            if category_data[key_a]["top_indices"] & category_data[key_b]["top_indices"]:
                overlap[key_a].append(LIFE_CATEGORIES[key_b]["label"])
                overlap[key_b].append(LIFE_CATEGORIES[key_a]["label"])
    return overlap


def _category_score(top: list[tuple]) -> int:
    score = 0
    for hit, a in top:
        if hit.evidence_strength == "strong":
            score += 5
        elif hit.evidence_strength == "moderate" and a.theme_specificity in ("high", "moderate"):
            score += 2
        elif hit.evidence_strength == "moderate":
            score += 1
    return score


def build_why_panels(category_data: dict[str, dict], query_start: datetime, query_end: datetime) -> dict[str, dict]:
    overlap = _cross_category_overlap(category_data)
    panels = {}
    for key, data in category_data.items():
        top = data["top"]
        panels[key] = {
            "tier": _category_tier(top),
            "independent_systems": len({hit.system for hit, _a in top}),
            "main_window": _main_window(top, query_start, query_end),
            "themes_involved": overlap[key],
        }
    return panels


def build_ranking(category_data: dict[str, dict], why_panels: dict[str, dict]) -> list[dict]:
    """Descending by computed score -- this, not the LLM, decides which
    categories are 'the real story' of the season."""
    ranked = [
        {
            "key": key,
            "label": LIFE_CATEGORIES[key]["label"],
            "score": _category_score(data["top"]),
            "tier": why_panels[key]["tier"],
            "main_window": why_panels[key]["main_window"],
            "themes_involved": why_panels[key]["themes_involved"],
        }
        for key, data in category_data.items()
    ]
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked


def _bucket_strong_hits(
    category_data: dict[str, dict], query_start: datetime, query_end: datetime,
) -> dict[str, list[dict]]:
    """Buckets ONLY strong-tier (i.e. genuinely convergent) hits by when
    they land, so 'only include timing where the evidence actually
    supports it' is enforced structurally, not just by prompt instruction.
    Dedupes by (system, mover, target, aspect, date) so one hit shared
    across categories doesn't get listed twice within a bucket."""
    buckets: dict[str, dict] = {"now": {}, "next": {}, "later": {}}

    for key, data in category_data.items():
        label = LIFE_CATEGORIES[key]["label"]
        for hit, _a in data["top"]:
            if hit.evidence_strength != "strong":
                continue
            rep_date = None
            for d in _parse_dates(hit.exact_hit_dates):
                if query_start <= d <= query_end:
                    rep_date = d
                    break
            if rep_date is None:
                continue
            days_out = (rep_date - query_start).days
            bucket = "now" if days_out <= NOW_CUTOFF_DAYS else "next" if days_out <= NEXT_CUTOFF_DAYS else "later"
            hit_key = (hit.system, hit.moving_point, hit.natal_target, hit.aspect_type, rep_date.isoformat())
            entry = buckets[bucket].setdefault(hit_key, {"date": rep_date, "categories": set()})
            entry["categories"].add(label)

    result: dict[str, list[dict]] = {}
    for bucket_name, entries in buckets.items():
        result[bucket_name] = [
            {"date": e["date"].strftime("%B %-d, %Y"), "categories": sorted(e["categories"])}
            for e in sorted(entries.values(), key=lambda e: e["date"])
        ]
    return result


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

    category_data = build_category_data(chart, settings, forecast_packet)
    why_panels = build_why_panels(category_data, query_start, query_end)
    ranking = build_ranking(category_data, why_panels)
    timeline_evidence = _bucket_strong_hits(category_data, query_start, query_end)
    natal_summary = _natal_summary(chart, profile)

    category_evidence_text = {key: data["evidence_text"] for key, data in category_data.items()}
    llm_output = llm.generate_reading(natal_summary, category_evidence_text, ranking, timeline_evidence)

    return {
        "natal_summary": natal_summary,
        "window": {"start": query_start.date().isoformat(), "end": query_end.date().isoformat()},
        "categories": {
            key: {
                "label": LIFE_CATEGORIES[key]["label"],
                "headline": llm_output["categories"][key]["headline"],
                "body": llm_output["categories"][key]["body"],
                "confidence": why_panels[key]["tier"],
                "why": why_panels[key],
            }
            for key in LIFE_CATEGORIES
        },
        "bigger_picture": llm_output["bigger_picture"],
        "timeline": llm_output["timeline"],
    }
