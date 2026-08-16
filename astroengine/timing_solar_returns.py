"""Solar returns: the exact annual moment the transiting Sun returns to its
natal degree, and that moment's chart compared against the natal chart.

Location: a solar return's houses/angles (Ascendant, Midheaven) depend on
WHERE the person physically is at the return moment -- unlike the return's
planetary positions, which are geocentric and location-independent. Callers
should pass solar_return_location (the person's actual location at that
moment) when known. If it isn't supplied, this module falls back to the
birth location purely so a chart can still be shown, and marks the result
location_known=False -- callers must not treat that fallback as if it were
the real answer.

Only return PLANETS (+ node) are used as "movers" for aspect-hit generation
(never return angles), matching the same reasoning as transits/progressions:
it keeps the linked-pair mirror-duplicate logic confined to the natal-target
side. Return Ascendant/Midheaven are still computed and reported as
descriptive context, just not aspected -- which also means NO current
solar_return TimingHit depends on location at all (movers are geocentric
planets, targets are the natal chart's own fixed points). The location_known
flag and the "unknown_location" confidence-basis handling in
astroengine.evidence exist to keep that true if return-house/angle-based
hits are ever added later, not because today's hits need it.

A solar return hit has no meaningful "approach" -- it's a snapshot chart,
valid for the ~year until the next return, at a fixed orb the whole time.
So exact_hit_dates is always left empty (there's no moment of exactness
sharper than "the return moment itself," and pretending otherwise would
overstate precision); entry_into_orb/exit_from_orb instead mark the return
chart's validity window (this return -> the next one).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import swisseph as swe

from astroengine.constants import ASPECT_ANGLES, angular_separation, is_applying_to_fixed_target
from astroengine.ephemeris import houses as compute_houses, node_position, planet_position
from astroengine.models import TimingHit
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings
from astroengine.timing_common import natal_targets
from astroengine.timeutil import jd_ut_to_datetime, utc_to_julian_moment

RETURN_MOVERS = [
    "sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
    "uranus", "neptune", "pluto", "north_node",
]


@dataclass
class ReturnChart:
    return_jd_ut: float
    return_utc: datetime
    planets: list[tuple]        # (name, longitude, speed)
    ascendant: float
    midheaven: float
    location_known: bool        # False if no solar_return_location was supplied
                                 # (ascendant/midheaven then fall back to birth location)


def find_solar_return_jd(natal_sun_longitude: float, return_year: int, birth_month: int, birth_day: int,
                          settings: AstrologySettings) -> float:
    """Exact UT1 Julian day the transiting Sun's longitude equals
    natal_sun_longitude, in the given calendar year. Bisects around the
    naive birthday guess -- the true return is always within a day or two
    of the same calendar date, since the Sun moves close to 1 deg/day."""
    guess_jd = swe.utc_to_jd(return_year, birth_month, birth_day, 12, 0, 0, swe.GREG_CAL)[1]

    def signed_offset(jd: float) -> float:
        lon = planet_position(jd, "sun", settings.zodiac_type, settings.ayanamsha).longitude
        diff = (lon - natal_sun_longitude) % 360.0
        return diff - 360.0 if diff > 180.0 else diff

    lo, hi = guess_jd - 3.0, guess_jd + 3.0
    if not (signed_offset(lo) < 0 < signed_offset(hi)):
        lo, hi = guess_jd - 10.0, guess_jd + 10.0

    for _ in range(50):
        mid = (lo + hi) / 2.0
        if signed_offset(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def compute_return_chart(
    return_jd_ut: float, latitude: float, longitude: float, settings: AstrologySettings, location_known: bool,
) -> ReturnChart:
    planets = []
    for name in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"):
        raw = planet_position(return_jd_ut, name, settings.zodiac_type, settings.ayanamsha)
        planets.append((name, raw.longitude, raw.speed_longitude))
    node_raw = node_position(return_jd_ut, settings.node_type, settings.zodiac_type, settings.ayanamsha)
    planets.append(("north_node", node_raw.longitude, node_raw.speed_longitude))

    raw_houses = compute_houses(return_jd_ut, latitude, longitude, settings.house_system,
                                 zodiac_type=settings.zodiac_type, ayanamsha=settings.ayanamsha)

    return ReturnChart(
        return_jd_ut=return_jd_ut,
        return_utc=jd_ut_to_datetime(return_jd_ut),
        planets=planets,
        ascendant=raw_houses.ascendant,
        midheaven=raw_houses.midheaven,
        location_known=location_known,
    )


def _relevant_return_years(query_start_year: int) -> list[int]:
    return [query_start_year - 1, query_start_year, query_start_year + 1]


def compute_solar_return_hits(
    chart: NatalChart, settings: AstrologySettings, natal_sun_longitude: float,
    birth_month: int, birth_day: int, birth_latitude: float, birth_longitude: float,
    query_start: datetime, query_end: datetime,
    solar_return_location: tuple[float, float] | None = None,
) -> tuple[list[TimingHit], list[ReturnChart]]:
    """Returns (hits, return_charts_used) -- the return charts are also
    handed back so the forecast packet can include them as descriptive
    context (ascendant/midheaven of the governing return year).

    solar_return_location: (latitude, longitude) the person actually was at
    the return moment. If omitted, the return chart's angles/houses fall
    back to the birth location and are marked location_known=False (see
    module docstring) -- the return PLANETS used for hit generation are
    geocentric and unaffected either way.
    """
    location_known = solar_return_location is not None
    return_latitude, return_longitude = solar_return_location if location_known else (birth_latitude, birth_longitude)

    query_start_jd = utc_to_julian_moment(query_start).jd_ut
    query_end_jd = utc_to_julian_moment(query_end).jd_ut

    candidate_jds = sorted(
        find_solar_return_jd(natal_sun_longitude, year, birth_month, birth_day, settings)
        for year in _relevant_return_years(query_start.year)
    )

    governing_returns: list[tuple[float, float]] = []  # (return_jd, validity_end_jd)
    for i, return_jd in enumerate(candidate_jds):
        validity_end_jd = candidate_jds[i + 1] if i + 1 < len(candidate_jds) else return_jd + 366.0
        if validity_end_jd < query_start_jd or return_jd > query_end_jd:
            continue
        governing_returns.append((return_jd, validity_end_jd))

    targets = natal_targets(chart)
    enabled_aspects = settings.enabled_aspects()

    hits: list[TimingHit] = []
    return_charts: list[ReturnChart] = []

    for return_jd, validity_end_jd in governing_returns:
        return_chart = compute_return_chart(return_jd, return_latitude, return_longitude, settings, location_known)
        return_charts.append(return_chart)
        entry_dt = jd_ut_to_datetime(return_jd)
        exit_dt = jd_ut_to_datetime(validity_end_jd)

        for mover_name, mover_longitude, mover_speed in return_chart.planets:
            for target_name, target_longitude, target_confidence in targets:
                involves_luminary = mover_name in ("sun", "moon") or target_name.lower() in ("sun", "moon")

                for aspect_name in enabled_aspects:
                    exact_angle = ASPECT_ANGLES[aspect_name]
                    allowed_orb = settings.orb_for(aspect_name, involves_luminary)
                    orb = abs(angular_separation(mover_longitude, target_longitude) - exact_angle)
                    if orb > allowed_orb:
                        continue

                    hit = TimingHit(
                        system="solar_return",
                        moving_point=f"solar_return:{mover_name}",
                        natal_target=target_name,
                        aspect_type=aspect_name,
                        exact_angle=exact_angle,
                        degree_at_reference=mover_longitude,
                        orb_at_reference=orb,
                        is_applying=is_applying_to_fixed_target(
                            mover_longitude, mover_speed, target_longitude, exact_angle, orb,
                        ),
                        entry_into_orb=entry_dt,
                        exact_hit_dates=[],
                        exit_from_orb=exit_dt,
                        confidence=target_confidence,
                    )
                    if mover_name == "sun" and target_name == "sun" and aspect_name == "conjunction":
                        # this is the return's OWN defining condition -- true
                        # of every solar return chart, every year, for
                        # everyone -- not evidence about this specific chart.
                        # Same principle as the linked-pair structural
                        # exclusions, via a different mechanism.
                        hit.evidence_eligible = False
                        hit.evidence_note = (
                            "structural: return Sun conjunct natal Sun (orb 0) is the return's own "
                            "defining condition, true for every solar return chart"
                        )
                    hits.append(hit)

    return hits, return_charts
