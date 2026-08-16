"""Orchestrates the five timing systems for a date range and returns a flat,
evidence-annotated hit list. Calculation only -- no interpretation, no
narrative. See astroengine.forecast for turning this into the structured
packet handed to the AI reading layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from astroengine.evidence import annotate_timing_hit_evidence_eligibility, assign_evidence_strength
from astroengine.models import BirthProfile, TimingHit
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings
from astroengine.timeutil import birth_julian_moment
from astroengine.timing_eclipses import LunationEvent, compute_eclipse_hits
from astroengine.timing_progressions import compute_progression_hits
from astroengine.timing_solar_arc import compute_solar_arc_hits
from astroengine.timing_solar_returns import ReturnChart, compute_solar_return_hits
from astroengine.timing_transits import compute_transit_hits


@dataclass
class TimingResult:
    hits: list[TimingHit]
    solar_return_charts: list[ReturnChart]
    lunation_events: list[LunationEvent]


def compute_timing_result(
    chart: NatalChart, settings: AstrologySettings, profile: BirthProfile,
    query_start: datetime, query_end: datetime,
) -> TimingResult:
    if not profile.time_known:
        raise ValueError(
            "the timing engine requires a known birth time (progressions, solar arc, and "
            "solar returns are all anchored to the exact birth moment); this profile has "
            "time_known=False"
        )

    birth_jd_ut = birth_julian_moment(profile.birth_date, profile.birth_time, profile.timezone_name).jd_ut
    natal_sun_longitude = next(p for p in chart.planets if p.planet == "sun").longitude

    hits: list[TimingHit] = []

    hits += compute_transit_hits(chart, settings, query_start, query_end)
    hits += compute_progression_hits(chart, settings, birth_jd_ut, query_start, query_end)
    hits += compute_solar_arc_hits(chart, settings, birth_jd_ut, natal_sun_longitude, query_start, query_end)

    solar_return_hits, return_charts = compute_solar_return_hits(
        chart, settings, natal_sun_longitude, profile.birth_date.month, profile.birth_date.day,
        profile.latitude, profile.longitude, query_start, query_end,
    )
    hits += solar_return_hits

    eclipse_hits, lunation_events = compute_eclipse_hits(chart, settings, query_start, query_end)
    hits += eclipse_hits

    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, query_start, query_end)

    return TimingResult(hits=hits, solar_return_charts=return_charts, lunation_events=lunation_events)
