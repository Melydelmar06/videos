"""Houses/angles tests: cross-check Ascendant/MC against the independent
reference formula, verify house-angle invariants, and specifically guard
against the exact kind of coordinate-sign bug that produces a "plausible
but wrong" chart (the failure mode called out when this layer was
commissioned: an Ascendant off by 10 degrees because of a timezone or
longitude-sign mistake).
"""

from datetime import date, time, datetime, timezone

import pytest

from astroengine import ephemeris
from astroengine.houses import compute_houses_and_angles, house_index_for_longitude, ruler_of_sign
from astroengine.settings import AstrologySettings
from astroengine.timeutil import birth_julian_moment, utc_to_julian_moment
from tests.reference_formulas import ascendant_midheaven_degrees

# accounts for mean-vs-apparent obliquity / truncated GMST in the reference
# formula (verified empirically to agree with swisseph to ~0.008 deg).
ASC_MC_TOLERANCE_DEG = 0.1


def _ang_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


@pytest.mark.parametrize("iso_utc,lat,lon", [
    ("1990-06-15T18:30:00", 40.7128, -74.0060),      # New York, western hemisphere
    ("1985-12-01T05:00:00", 51.5074, -0.1278),         # London, near-zero longitude
    ("2005-09-10T10:15:00", 35.6762, 139.6503),         # Tokyo, eastern hemisphere
    ("1978-02-20T22:45:00", -33.8688, 151.2093),         # Sydney, southern hemisphere
    ("2015-11-05T14:00:00", -1.2921, 36.8219),            # Nairobi, near-equator
])
def test_ascendant_and_mc_match_reference_formula(iso_utc, lat, lon):
    utc_dt = datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc)
    moment = utc_to_julian_moment(utc_dt)

    raw = ephemeris.houses(moment.jd_ut, lat, lon, "placidus")
    ref_asc, ref_mc = ascendant_midheaven_degrees(moment.jd_ut, lat, lon)

    assert _ang_diff(raw.ascendant, ref_asc) < ASC_MC_TOLERANCE_DEG
    assert _ang_diff(raw.midheaven, ref_mc) < ASC_MC_TOLERANCE_DEG


def test_house_one_cusp_equals_ascendant_and_house_ten_equals_mc():
    """Invariant for quadrant house systems (Placidus, Koch, etc.): cusp 1 is
    always the Ascendant and cusp 10 is always the Midheaven."""
    moment = birth_julian_moment(date(1990, 6, 15), time(14, 30), "America/New_York")
    raw = ephemeris.houses(moment.jd_ut, 40.7128, -74.0060, "placidus")
    assert raw.cusps[0] == pytest.approx(raw.ascendant, abs=1e-9)
    assert raw.cusps[9] == pytest.approx(raw.midheaven, abs=1e-9)


def test_longitude_sign_convention_matters():
    """Guards against the classic west/east longitude sign bug: New York is
    ~74 deg WEST, so passing +74 instead of -74 must produce a substantially
    different Ascendant (this doesn't prove which sign is right on its own --
    the reference-formula test above does that -- it just guards against a
    silent sign flip regression)."""
    moment = birth_julian_moment(date(1990, 6, 15), time(14, 30), "America/New_York")
    correct = ephemeris.houses(moment.jd_ut, 40.7128, -74.0060, "placidus")
    flipped = ephemeris.houses(moment.jd_ut, 40.7128, 74.0060, "placidus")
    assert _ang_diff(correct.ascendant, flipped.ascendant) > 5.0


def test_ascendant_advances_roughly_with_time_of_day():
    """A large timezone/UTC bug (e.g. off by several hours) would move the
    Ascendant by a large, easily-detectable amount: the Ascendant completes
    a full circuit of the zodiac in about 24h, i.e. roughly 1 degree every
    4 minutes at moderate latitudes. Two births 2 hours apart at the same
    place should show a substantial, non-trivial Ascendant shift -- if a
    UTC conversion bug silently added or dropped hours, this is the kind of
    check that would catch it even without an external reference value."""
    settings = AstrologySettings()
    moment_a = birth_julian_moment(date(1990, 6, 15), time(6, 0), "America/New_York")
    moment_b = birth_julian_moment(date(1990, 6, 15), time(8, 0), "America/New_York")

    houses_a, _ = compute_houses_and_angles(moment_a.jd_ut, 40.7128, -74.0060, settings, "exact_time")
    houses_b, _ = compute_houses_and_angles(moment_b.jd_ut, 40.7128, -74.0060, settings, "exact_time")

    asc_a = next(h for h in houses_a if h.house_number == 1).longitude
    asc_b = next(h for h in houses_b if h.house_number == 1).longitude
    shift = _ang_diff(asc_a, asc_b)
    # ~2 hours should move the Ascendant roughly 20-40 degrees depending on
    # latitude/season; assert it's in a sane ballpark rather than pinning an
    # exact value.
    assert 10.0 < shift < 50.0


def test_house_index_for_longitude_wraps_correctly():
    # evenly-spaced synthetic cusps for a simple, hand-checkable case
    cusps = tuple(float(i * 30) for i in range(12))
    assert house_index_for_longitude(5.0, cusps) == 1
    assert house_index_for_longitude(29.9, cusps) == 1
    assert house_index_for_longitude(30.0, cusps) == 2
    assert house_index_for_longitude(355.0, cusps) == 12
    assert house_index_for_longitude(0.0, cusps) == 1


@pytest.mark.parametrize("sign,scheme,expected", [
    ("Scorpio", "modern", "pluto"),
    ("Scorpio", "traditional", "mars"),
    ("Aquarius", "modern", "uranus"),
    ("Aquarius", "traditional", "saturn"),
    ("Leo", "modern", "sun"),
    ("Leo", "traditional", "sun"),
])
def test_ruler_of_sign(sign, scheme, expected):
    assert ruler_of_sign(sign, scheme) == expected
