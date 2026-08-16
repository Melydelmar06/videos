"""Cross-checks the Sun's calculated position against an independent
low-precision solar-position formula (Meeus ch. 25, ~0.01 deg accurate).
This catches Julian-day/UTC pipeline bugs and planet-index mixups -- the
things most likely to be silently wrong -- without trusting any single
memorized "known chart" value.
"""

from datetime import datetime, timezone

import pytest

from astroengine.ephemeris import planet_position
from astroengine.timeutil import utc_to_julian_moment
from tests.reference_formulas import low_precision_sun_longitude_deg

# Meeus's low-precision solar formula is accurate to ~0.01 deg; give it
# some headroom against the full-precision Moshier ephemeris.
SUN_TOLERANCE_DEG = 0.05


@pytest.mark.parametrize("iso_utc", [
    "2000-01-01T12:00:00",
    "1990-06-15T18:30:00",
    "1975-01-04T17:00:00",
    "2024-03-20T03:06:00",   # near the March 2024 equinox
    "2026-08-16T12:00:00",   # "today" per this project's context
])
def test_sun_longitude_matches_reference_formula(iso_utc):
    utc_dt = datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc)
    moment = utc_to_julian_moment(utc_dt)

    calculated = planet_position(moment.jd_ut, "sun", "tropical", None).longitude
    reference = low_precision_sun_longitude_deg(moment.jd_ut)

    diff = abs(calculated - reference) % 360.0
    diff = min(diff, 360.0 - diff)
    assert diff < SUN_TOLERANCE_DEG


def test_sun_at_reference_formula_equinox_is_near_zero_aries():
    """The tropical zodiac is defined by the equinox: at the moment the Sun's
    longitude is 0, that's 0 deg Aries by construction. Rather than trust a
    memorized real-world equinox timestamp, find the equinox moment using
    the independent reference formula itself (bisection on
    low_precision_sun_longitude_deg crossing 0 near a known March date), then
    confirm Swiss Ephemeris agrees that the Sun is at ~0 deg at that same
    moment. This checks agreement without relying on any external "known"
    value.
    """
    # bracket the March 2024 equinox loosely; low precision formula wraps
    # 350-360 before the crossing and 0-10 after, so track the signed
    # "distance to 0" instead of raw longitude to make bisection well-behaved.
    def signed_offset_from_zero(jd_ut: float) -> float:
        lon = low_precision_sun_longitude_deg(jd_ut)
        return lon - 360.0 if lon > 180.0 else lon

    lo = utc_to_julian_moment(datetime(2024, 3, 15, tzinfo=timezone.utc)).jd_ut
    hi = utc_to_julian_moment(datetime(2024, 3, 25, tzinfo=timezone.utc)).jd_ut
    assert signed_offset_from_zero(lo) < 0 < signed_offset_from_zero(hi)

    for _ in range(60):
        mid = (lo + hi) / 2.0
        if signed_offset_from_zero(mid) < 0:
            lo = mid
        else:
            hi = mid
    equinox_jd_ut = (lo + hi) / 2.0

    longitude = planet_position(equinox_jd_ut, "sun", "tropical", None).longitude
    diff = min(longitude, 360.0 - longitude)
    assert diff < 0.1
