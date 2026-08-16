"""Eclipses and plain lunations (New/Full Moon), cross-referenced against
the natal chart.

Real eclipse dates come from Swiss Ephemeris's own eclipse-finding
functions (swe_sol_eclipse_when_glob / swe_lun_eclipse_when) rather than a
hand-maintained almanac -- verified against well-known real eclipse dates
(e.g. the 2026-08-12 total solar eclipse) during development. Plain New/Full
Moons are found by root-finding on the Sun-Moon elongation crossing 0 or
180 degrees.

A hit's `system` is "eclipse" ONLY when the lunation is an actual eclipse
(event.eclipse_label is not None); an ordinary New/Full Moon that happens to
aspect the natal chart gets `system="lunation"` instead, never "eclipse" --
these must stay distinguishable downstream, since the evidence-strength
scorer (astroengine.evidence) treats real eclipses as inherently rare/
significant enough to help qualify a hit for the Strong tier, and a plain
monthly lunation must not get that same weight just because it aspects
something.

The "lunation point" checked against natal targets is the Moon's own
ecliptic longitude at the exact lunation moment (at New Moon this is the
same as the Sun's; at Full Moon the Sun is exactly opposite it, but only
one point is used here -- generating a second hit from the Sun's degree
too would just reintroduce the "same event counted twice" problem this
whole evidence system exists to avoid).

Each lunation is a single moment, not a gradually-forming aspect, so unlike
transits/progressions/solar arc there's no real entry/exact/exit lifecycle
to detect -- entry/exit instead mark a conventional +/-3 day "lunation
influence window" around the exact moment, a common astrological convention
for how long a lunation's effect is considered active.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import swisseph as swe

from astroengine.constants import ASPECT_ANGLES, angular_separation, is_applying_to_fixed_target
from astroengine.ephemeris import planet_position
from astroengine.models import TimingHit
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings
from astroengine.timing_common import natal_targets
from astroengine.timeutil import jd_ut_to_datetime, utc_to_julian_moment

LUNATION_SEARCH_PAD_DAYS = 45.0
LUNATION_INFLUENCE_WINDOW_DAYS = 3.0
LUNATION_SAMPLE_STEP_DAYS = 1.0


@dataclass(frozen=True)
class LunationEvent:
    jd_ut: float
    kind: str   # "new_moon" | "full_moon"
    eclipse_label: str | None   # e.g. "solar_total", "lunar_partial"; None if not an eclipse
    moon_longitude: float


def _signed_delta(target_deg: float, value_deg: float) -> float:
    diff = (value_deg - target_deg) % 360.0
    return diff - 360.0 if diff > 180.0 else diff


def _find_elongation_crossings(scan_start_jd: float, scan_end_jd: float, target_deg: float, settings: AstrologySettings) -> list[float]:
    def elongation(jd: float) -> float:
        sun = planet_position(jd, "sun", settings.zodiac_type, settings.ayanamsha).longitude
        moon = planet_position(jd, "moon", settings.zodiac_type, settings.ayanamsha).longitude
        return (moon - sun) % 360.0

    n_steps = max(1, int((scan_end_jd - scan_start_jd) / LUNATION_SAMPLE_STEP_DAYS))
    jds = [scan_start_jd + i * LUNATION_SAMPLE_STEP_DAYS for i in range(n_steps + 1)]
    offsets = [_signed_delta(target_deg, elongation(jd)) for jd in jds]

    crossings = []
    for i in range(len(offsets) - 1):
        if offsets[i] < 0 <= offsets[i + 1]:
            lo, hi = jds[i], jds[i + 1]
            for _ in range(40):
                mid = (lo + hi) / 2.0
                if _signed_delta(target_deg, elongation(mid)) < 0:
                    lo = mid
                else:
                    hi = mid
            crossings.append((lo + hi) / 2.0)
    return crossings


_SOL_ECLIPSE_LABELS = {swe.ECL_TOTAL: "total", swe.ECL_ANNULAR: "annular", swe.ECL_PARTIAL: "partial", swe.ECL_ANNULAR_TOTAL: "hybrid"}
_LUN_ECLIPSE_LABELS = {swe.ECL_TOTAL: "total", swe.ECL_PARTIAL: "partial", swe.ECL_PENUMBRAL: "penumbral"}


def _find_eclipse_moments(scan_start_jd: float, scan_end_jd: float) -> dict[float, str]:
    """jd -> label (e.g. 'solar_total'), for every eclipse (of either kind)
    with its maximum within [scan_start_jd, scan_end_jd]."""
    results: dict[float, str] = {}

    jd = scan_start_jd
    for _ in range(20):  # generous cap; eclipses are a few per year, this range is short
        retflag, tret = swe.sol_eclipse_when_glob(jd, swe.FLG_MOSEPH, 0, False)
        max_jd = tret[0]
        if max_jd > scan_end_jd:
            break
        for flag, label in _SOL_ECLIPSE_LABELS.items():
            if retflag & flag:
                results[max_jd] = f"solar_{label}"
                break
        else:
            results[max_jd] = "solar"
        jd = max_jd + 1.0

    jd = scan_start_jd
    for _ in range(20):
        retflag, tret = swe.lun_eclipse_when(jd, swe.FLG_MOSEPH, 0, False)
        max_jd = tret[0]
        if max_jd > scan_end_jd:
            break
        for flag, label in _LUN_ECLIPSE_LABELS.items():
            if retflag & flag:
                results[max_jd] = f"lunar_{label}"
                break
        else:
            results[max_jd] = "lunar"
        jd = max_jd + 1.0

    return results


def find_lunation_events(scan_start_jd: float, scan_end_jd: float, settings: AstrologySettings) -> list[LunationEvent]:
    new_moon_jds = _find_elongation_crossings(scan_start_jd, scan_end_jd, 0.0, settings)
    full_moon_jds = _find_elongation_crossings(scan_start_jd, scan_end_jd, 180.0, settings)
    eclipse_moments = _find_eclipse_moments(scan_start_jd, scan_end_jd)

    events = []
    for jd in new_moon_jds:
        label = _nearest_eclipse_label(jd, eclipse_moments)
        moon_lon = planet_position(jd, "moon", settings.zodiac_type, settings.ayanamsha).longitude
        events.append(LunationEvent(jd_ut=jd, kind="new_moon", eclipse_label=label, moon_longitude=moon_lon))
    for jd in full_moon_jds:
        label = _nearest_eclipse_label(jd, eclipse_moments)
        moon_lon = planet_position(jd, "moon", settings.zodiac_type, settings.ayanamsha).longitude
        events.append(LunationEvent(jd_ut=jd, kind="full_moon", eclipse_label=label, moon_longitude=moon_lon))

    return sorted(events, key=lambda e: e.jd_ut)


def _nearest_eclipse_label(jd: float, eclipse_moments: dict[float, str]) -> str | None:
    for eclipse_jd, label in eclipse_moments.items():
        if abs(eclipse_jd - jd) < 1.0:  # same lunation event
            return label
    return None


def compute_eclipse_hits(
    chart: NatalChart, settings: AstrologySettings, query_start: datetime, query_end: datetime,
) -> tuple[list[TimingHit], list[LunationEvent]]:
    query_start_jd = utc_to_julian_moment(query_start).jd_ut
    query_end_jd = utc_to_julian_moment(query_end).jd_ut
    scan_start_jd = query_start_jd - LUNATION_SEARCH_PAD_DAYS
    scan_end_jd = query_end_jd + LUNATION_SEARCH_PAD_DAYS

    events = find_lunation_events(scan_start_jd, scan_end_jd, settings)
    targets = natal_targets(chart)
    enabled_aspects = settings.enabled_aspects()

    hits: list[TimingHit] = []
    relevant_events: list[LunationEvent] = []

    for event in events:
        entry_jd = event.jd_ut - LUNATION_INFLUENCE_WINDOW_DAYS
        exit_jd = event.jd_ut + LUNATION_INFLUENCE_WINDOW_DAYS
        if exit_jd < query_start_jd or entry_jd > query_end_jd:
            continue  # influence window never touches the requested range
        relevant_events.append(event)

        is_real_eclipse = event.eclipse_label is not None
        system = "eclipse" if is_real_eclipse else "lunation"
        label = event.eclipse_label if is_real_eclipse else event.kind
        event_date_str = jd_ut_to_datetime(event.jd_ut).date().isoformat()
        mover_id = f"{system}:{label}:{event_date_str}"
        moon_speed = planet_position(event.jd_ut, "moon", settings.zodiac_type, settings.ayanamsha).speed_longitude

        for target_name, target_longitude, target_confidence in targets:
            involves_luminary = target_name.lower() in ("sun", "moon")  # the lunation point is always Sun/Moon-adjacent

            for aspect_name in enabled_aspects:
                exact_angle = ASPECT_ANGLES[aspect_name]
                allowed_orb = settings.orb_for(aspect_name, involves_luminary)
                orb = abs(angular_separation(event.moon_longitude, target_longitude) - exact_angle)
                if orb > allowed_orb:
                    continue

                hits.append(TimingHit(
                    system=system,
                    moving_point=mover_id,
                    natal_target=target_name,
                    aspect_type=aspect_name,
                    exact_angle=exact_angle,
                    degree_at_reference=event.moon_longitude,
                    orb_at_reference=orb,
                    is_applying=is_applying_to_fixed_target(
                        event.moon_longitude, moon_speed, target_longitude, exact_angle, orb,
                    ),
                    entry_into_orb=jd_ut_to_datetime(entry_jd),
                    exact_hit_dates=[jd_ut_to_datetime(event.jd_ut)],
                    exit_from_orb=jd_ut_to_datetime(exit_jd),
                    confidence=target_confidence,
                ))

    return hits, relevant_events
