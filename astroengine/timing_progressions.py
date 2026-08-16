"""Secondary progressions vs. the natal chart: the "day for a year" method
-- the progressed chart for age N years is the ephemeris at N days after
birth. A point's real-time speed is therefore its natal ephemeris speed
compressed by 1/365.25 (e.g. the progressed Moon moves ~13 deg/day in the
underlying ephemeris, i.e. ~13 deg per year of real time -- matching the
well-known "progressed Moon circles the zodiac in about 27-28 years" rule
of thumb, 360/13 ~ 27.7).

As with transits, only north_node is scanned as a mover; see
timing_transits.py's module docstring for why south_node would just move
the mirror-duplication problem into the mover instead of the target.
"""

from __future__ import annotations

from datetime import datetime

from astroengine.constants import ASPECT_ANGLES, PROGRESSED_TYPICAL_DAILY_SPEED, angular_separation, is_applying_to_fixed_target
from astroengine.ephemeris import node_position, planet_position
from astroengine.models import TimingHit
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings
from astroengine.timing_common import natal_targets, orb_span_for_settings, scan_pad_days
from astroengine.timing_scan import choose_step_days, find_orb_windows, sample_longitudes
from astroengine.timeutil import jd_ut_to_datetime, utc_to_julian_moment

DAYS_PER_YEAR = 365.25

PROGRESSION_MOVERS = [
    "sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
    "uranus", "neptune", "pluto", "north_node",
]


def _progressed_jd(real_jd_ut: float, birth_jd_ut: float) -> float:
    elapsed_days = real_jd_ut - birth_jd_ut
    return birth_jd_ut + elapsed_days / DAYS_PER_YEAR


def _position_fn_for_mover(mover: str, settings: AstrologySettings, birth_jd_ut: float):
    if mover == "north_node":
        def fn(real_jd_ut: float) -> tuple[float, float]:
            progressed_jd = _progressed_jd(real_jd_ut, birth_jd_ut)
            raw = node_position(progressed_jd, settings.node_type, settings.zodiac_type, settings.ayanamsha)
            return raw.longitude, raw.speed_longitude / DAYS_PER_YEAR
        return fn

    def fn(real_jd_ut: float, mover=mover) -> tuple[float, float]:
        progressed_jd = _progressed_jd(real_jd_ut, birth_jd_ut)
        raw = planet_position(progressed_jd, mover, settings.zodiac_type, settings.ayanamsha)
        return raw.longitude, raw.speed_longitude / DAYS_PER_YEAR
    return fn


def compute_progression_hits(
    chart: NatalChart, settings: AstrologySettings, birth_jd_ut: float,
    query_start: datetime, query_end: datetime,
) -> list[TimingHit]:
    query_start_jd = utc_to_julian_moment(query_start).jd_ut
    query_end_jd = utc_to_julian_moment(query_end).jd_ut

    targets = natal_targets(chart)
    enabled_aspects = settings.enabled_aspects()
    smallest_orb, largest_orb = orb_span_for_settings(settings)

    hits: list[TimingHit] = []

    for mover in PROGRESSION_MOVERS:
        typical_speed = PROGRESSED_TYPICAL_DAILY_SPEED[mover]
        step_days = choose_step_days(typical_speed, smallest_orb)
        pad_days = scan_pad_days(typical_speed, largest_orb, min_pad_days=30.0)
        scan_start_jd = query_start_jd - pad_days
        scan_end_jd = query_end_jd + pad_days

        position_fn = _position_fn_for_mover(mover, settings, birth_jd_ut)
        jds, longitudes = sample_longitudes(position_fn, scan_start_jd, scan_end_jd, step_days)
        if not jds:
            continue
        ref_longitude, ref_speed = position_fn(query_start_jd)

        for target_name, target_longitude, target_confidence in targets:
            involves_luminary = mover in ("sun", "moon") or target_name.lower() in ("sun", "moon")

            for aspect_name in enabled_aspects:
                exact_angle = ASPECT_ANGLES[aspect_name]
                allowed_orb = settings.orb_for(aspect_name, involves_luminary)

                for window in find_orb_windows(jds, longitudes, target_longitude, exact_angle, allowed_orb):
                    window_start_jd = window.entry_jd if window.entry_jd is not None else scan_start_jd
                    window_end_jd = window.exit_jd if window.exit_jd is not None else scan_end_jd
                    if window_end_jd < query_start_jd or window_start_jd > query_end_jd:
                        continue

                    ref_orb = abs(angular_separation(ref_longitude, target_longitude) - exact_angle)
                    hits.append(TimingHit(
                        system="progression",
                        moving_point=f"progressed:{mover}",
                        natal_target=target_name,
                        aspect_type=aspect_name,
                        exact_angle=exact_angle,
                        degree_at_reference=ref_longitude,
                        orb_at_reference=ref_orb,
                        is_applying=is_applying_to_fixed_target(
                            ref_longitude, ref_speed, target_longitude, exact_angle, ref_orb,
                        ),
                        entry_into_orb=jd_ut_to_datetime(window.entry_jd) if window.entry_jd is not None else None,
                        exact_hit_dates=[jd_ut_to_datetime(jd) for jd in window.exact_jds],
                        exit_from_orb=jd_ut_to_datetime(window.exit_jd) if window.exit_jd is not None else None,
                        confidence=target_confidence,
                    ))

    return hits
