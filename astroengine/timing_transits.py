"""Transiting planets vs. the natal chart.

Only "north_node" is scanned as a mover, not "south_node" -- since
south_node is always exactly north_node+180, scanning north_node against
every enabled aspect type already captures the whole node axis's
relationship to every natal point (a conjunction to south_node is the same
event as an opposition to north_node, which is already checked). Adding
south_node as a second mover would just reintroduce the mirror-duplication
problem one level up, in the mover itself rather than the natal target.
"""

from __future__ import annotations

from datetime import datetime

from astroengine.constants import ASPECT_ANGLES, TRANSIT_TYPICAL_DAILY_SPEED, angular_separation, is_applying_to_fixed_target
from astroengine.ephemeris import node_position, planet_position
from astroengine.models import TimingHit
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings
from astroengine.timing_common import natal_targets, orb_span_for_settings, scan_pad_days
from astroengine.timing_scan import choose_step_days, find_orb_windows, sample_longitudes
from astroengine.timeutil import JulianMoment, jd_ut_to_datetime, utc_to_julian_moment

TRANSIT_MOVERS = [
    "sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
    "uranus", "neptune", "pluto", "north_node",
]


def _position_fn_for_mover(mover: str, settings: AstrologySettings):
    if mover == "north_node":
        def fn(jd_ut: float) -> tuple[float, float]:
            raw = node_position(jd_ut, settings.node_type, settings.zodiac_type, settings.ayanamsha)
            return raw.longitude, raw.speed_longitude
        return fn

    def fn(jd_ut: float, mover=mover) -> tuple[float, float]:
        raw = planet_position(jd_ut, mover, settings.zodiac_type, settings.ayanamsha)
        return raw.longitude, raw.speed_longitude
    return fn


def compute_transit_hits(
    chart: NatalChart, settings: AstrologySettings, query_start: datetime, query_end: datetime,
) -> list[TimingHit]:
    query_start_jd = utc_to_julian_moment(query_start).jd_ut
    query_end_jd = utc_to_julian_moment(query_end).jd_ut

    targets = natal_targets(chart)
    enabled_aspects = settings.enabled_aspects()
    smallest_orb, largest_orb = orb_span_for_settings(settings)

    hits: list[TimingHit] = []

    for mover in TRANSIT_MOVERS:
        typical_speed = TRANSIT_TYPICAL_DAILY_SPEED[mover]
        step_days = choose_step_days(typical_speed, smallest_orb)
        pad_days = scan_pad_days(typical_speed, largest_orb)
        scan_start_jd = query_start_jd - pad_days
        scan_end_jd = query_end_jd + pad_days

        position_fn = _position_fn_for_mover(mover, settings)
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
                        continue  # never touches the requested window at all

                    ref_orb = abs(angular_separation(ref_longitude, target_longitude) - exact_angle)
                    hits.append(TimingHit(
                        system="transit",
                        moving_point=f"transit:{mover}",
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
