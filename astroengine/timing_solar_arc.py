"""Solar arc directions vs. the natal chart.

Arc convention: arc(t) = progressed-Sun longitude at t (day-for-a-year, see
timing_progressions.py) minus natal Sun longitude. This is the "true" solar
arc (uses the Sun's actual varying orbital speed) rather than the older
"mean" convention (a flat ~0.9856 deg/year) -- consistent with this engine
using the true node elsewhere rather than mean. The arc is added to EVERY
natal point to get that point's directed position, which is then checked
for aspects to the (unmoved) natal chart.

Because the real Sun's geocentric motion never goes retrograde, arc(t) is
monotonically increasing over a lifetime -- unlike transits or progressions
of the other bodies, a given directed-point-to-natal-target aspect can only
become exact once, never in a retrograde-station triple pass.
"""

from __future__ import annotations

from datetime import datetime

from astroengine.constants import ASPECT_ANGLES, PROGRESSED_TYPICAL_DAILY_SPEED, angular_separation, is_applying_to_fixed_target
from astroengine.ephemeris import planet_position
from astroengine.models import TimingHit
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings
from astroengine.timing_common import natal_targets, orb_span_for_settings, scan_pad_days
from astroengine.timing_progressions import DAYS_PER_YEAR, _progressed_jd
from astroengine.timing_scan import choose_step_days, find_orb_windows, sample_longitudes
from astroengine.timeutil import jd_ut_to_datetime, utc_to_julian_moment


def compute_solar_arc_hits(
    chart: NatalChart, settings: AstrologySettings, birth_jd_ut: float,
    natal_sun_longitude: float, query_start: datetime, query_end: datetime,
) -> list[TimingHit]:
    query_start_jd = utc_to_julian_moment(query_start).jd_ut
    query_end_jd = utc_to_julian_moment(query_end).jd_ut

    targets = natal_targets(chart)
    enabled_aspects = settings.enabled_aspects()
    smallest_orb, largest_orb = orb_span_for_settings(settings)

    # the arc itself: progressed Sun's longitude minus natal Sun, sampled
    # once and reused as an offset for every directed point (they all move
    # together, rigidly, by the same arc).
    typical_speed = PROGRESSED_TYPICAL_DAILY_SPEED["sun"]
    step_days = choose_step_days(typical_speed, smallest_orb)
    pad_days = scan_pad_days(typical_speed, largest_orb, min_pad_days=30.0)
    scan_start_jd = query_start_jd - pad_days
    scan_end_jd = query_end_jd + pad_days

    def sun_longitude_fn(real_jd_ut: float) -> tuple[float, float]:
        progressed_jd = _progressed_jd(real_jd_ut, birth_jd_ut)
        raw = planet_position(progressed_jd, "sun", settings.zodiac_type, settings.ayanamsha)
        return raw.longitude, raw.speed_longitude / DAYS_PER_YEAR

    jds, progressed_sun_longitudes = sample_longitudes(sun_longitude_fn, scan_start_jd, scan_end_jd, step_days)
    if not jds:
        return []

    # arc as an unwrapped (non-modular) quantity: how far the progressed Sun
    # has moved from ITS OWN starting longitude at the first sample, tracked
    # continuously so it can be added to any natal point without ambiguity.
    arcs = _unwrap_arc(progressed_sun_longitudes, natal_sun_longitude)

    ref_progressed_sun_lon, ref_sun_speed = sun_longitude_fn(query_start_jd)
    ref_arc = _shortest_signed_delta(natal_sun_longitude, ref_progressed_sun_lon)

    hits: list[TimingHit] = []

    for directed_point_name, directed_natal_longitude, directed_confidence in targets:
        directed_longitudes = [(directed_natal_longitude + a) % 360.0 for a in arcs]
        ref_directed_longitude = (directed_natal_longitude + ref_arc) % 360.0

        for target_name, target_longitude, target_confidence in targets:
            if target_name == directed_point_name:
                continue  # a point directed onto itself is always an exact conjunction, at arc=0 -- not informative
            involves_luminary = (
                directed_point_name.lower() in ("sun", "moon") or target_name.lower() in ("sun", "moon")
            )

            for aspect_name in enabled_aspects:
                exact_angle = ASPECT_ANGLES[aspect_name]
                allowed_orb = settings.orb_for(aspect_name, involves_luminary)

                for window in find_orb_windows(jds, directed_longitudes, target_longitude, exact_angle, allowed_orb):
                    window_start_jd = window.entry_jd if window.entry_jd is not None else scan_start_jd
                    window_end_jd = window.exit_jd if window.exit_jd is not None else scan_end_jd
                    if window_end_jd < query_start_jd or window_start_jd > query_end_jd:
                        continue

                    ref_orb = abs(angular_separation(ref_directed_longitude, target_longitude) - exact_angle)
                    hits.append(TimingHit(
                        system="solar_arc",
                        moving_point=f"solar_arc:{directed_point_name}",
                        natal_target=target_name,
                        aspect_type=aspect_name,
                        exact_angle=exact_angle,
                        degree_at_reference=ref_directed_longitude,
                        orb_at_reference=ref_orb,
                        is_applying=is_applying_to_fixed_target(
                            ref_directed_longitude, ref_sun_speed, target_longitude, exact_angle, ref_orb,
                        ),
                        entry_into_orb=jd_ut_to_datetime(window.entry_jd) if window.entry_jd is not None else None,
                        exact_hit_dates=[jd_ut_to_datetime(jd) for jd in window.exact_jds],
                        exit_from_orb=jd_ut_to_datetime(window.exit_jd) if window.exit_jd is not None else None,
                        confidence=target_confidence,
                    ))

    return hits


def _shortest_signed_delta(from_lon: float, to_lon: float) -> float:
    diff = (to_lon - from_lon) % 360.0
    if diff > 180.0:
        diff -= 360.0
    return diff


def _unwrap_arc(progressed_sun_longitudes: list[float], natal_sun_longitude: float) -> list[float]:
    """Turns the (mod-360, wrapping) progressed Sun longitude samples into a
    continuously-increasing arc-from-natal-Sun value, so it can be added to
    any natal point without a modular-wraparound ambiguity. Assumes samples
    are close enough together that the Sun never moves more than 180 deg
    between consecutive samples (true for any sane step_days)."""
    if not progressed_sun_longitudes:
        return []
    arcs = [_shortest_signed_delta(natal_sun_longitude, progressed_sun_longitudes[0])]
    for i in range(1, len(progressed_sun_longitudes)):
        prev_lon = progressed_sun_longitudes[i - 1]
        curr_lon = progressed_sun_longitudes[i]
        step = curr_lon - prev_lon
        if step > 180.0:
            step -= 360.0
        elif step < -180.0:
            step += 360.0
        arcs.append(arcs[-1] + step)
    return arcs
