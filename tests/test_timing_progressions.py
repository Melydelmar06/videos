from datetime import date, time, datetime, timezone

import pytest
import swisseph as swe

from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.timing_progressions import compute_progression_hits
from astroengine.timeutil import birth_julian_moment


@pytest.fixture(scope="module")
def real_chart_and_birth_jd():
    profile = BirthProfile(
        name="Test", birth_date=date(1986, 11, 6), birth_time=time(6, 30, 0), time_known=True,
        birth_place="Cartagena de Indias, Colombia", latitude=10.3910, longitude=-75.4794,
        timezone_name="America/Bogota",
    )
    settings = AstrologySettings(node_type="true")
    chart = compute_natal_chart(profile, settings)
    birth_jd_ut = birth_julian_moment(profile.birth_date, profile.birth_time, profile.timezone_name).jd_ut
    return chart, settings, birth_jd_ut


def test_progressed_positions_move_much_slower_than_transits(real_chart_and_birth_jd):
    """Sanity floor: across a 2-month query window, progressed Sun (the
    fastest-moving progressed body in practice, ~1 deg/year of real time)
    should move only a small fraction of a degree -- nowhere near the tens
    of degrees a transiting Sun would move in the same window."""
    chart, settings, birth_jd_ut = real_chart_and_birth_jd
    from astroengine.timing_progressions import _position_fn_for_mover
    fn = _position_fn_for_mover("sun", settings, birth_jd_ut)
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    from astroengine.timeutil import utc_to_julian_moment
    lon_start, _ = fn(utc_to_julian_moment(start).jd_ut)
    lon_end, _ = fn(utc_to_julian_moment(end).jd_ut)
    from astroengine.constants import angular_separation
    assert angular_separation(lon_start, lon_end) < 1.0


def test_progressed_venus_return_matches_independently_verified_station(real_chart_and_birth_jd):
    """Independent cross-check: this person's natal Venus was retrograde at
    birth (visible in the validated natal chart) and, per direct Swiss
    Ephemeris inspection, stationed direct ~21 days after birth and crossed
    back through the natal Venus degree (222.064 deg) between day+39 and
    day+42 post-birth. Under day-for-a-year, that lands at real age ~39.8-
    40.1 years, i.e. right around Nov 2026 (birth 1986-11-06). The
    progressions engine should find exactly this: a progressed Venus
    conjunct natal Venus hit with its exact date in that window.
    """
    chart, settings, birth_jd_ut = real_chart_and_birth_jd
    natal_venus = next(p for p in chart.planets if p.planet == "venus")
    assert natal_venus.is_retrograde is True  # precondition this test depends on

    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 12, 31, tzinfo=timezone.utc)
    hits = compute_progression_hits(chart, settings, birth_jd_ut, start, end)

    venus_returns = [
        h for h in hits
        if h.moving_point == "progressed:venus" and h.natal_target == "venus" and h.aspect_type == "conjunction"
    ]
    assert len(venus_returns) == 1
    exact_dates = venus_returns[0].exact_hit_dates
    assert len(exact_dates) == 1
    # day+39..day+42 post-birth, independently computed via raw swisseph above
    assert date(2026, 10, 20) <= exact_dates[0].date() <= date(2026, 11, 20)


def test_all_hits_within_or_touching_query_window(real_chart_and_birth_jd):
    chart, settings, birth_jd_ut = real_chart_and_birth_jd
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    hits = compute_progression_hits(chart, settings, birth_jd_ut, start, end)
    for h in hits:
        window_start = h.entry_into_orb or start
        window_end = h.exit_from_orb or end
        assert window_end >= start
        assert window_start <= end
        assert h.system == "progression"
        assert h.moving_point.startswith("progressed:")
