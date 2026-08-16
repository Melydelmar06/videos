from datetime import date, time, datetime, timezone

import pytest

from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.timing_eclipses import compute_eclipse_hits
from astroengine.timeutil import jd_ut_to_datetime


@pytest.fixture(scope="module")
def eclipse_fixture():
    profile = BirthProfile(
        name="Test", birth_date=date(1986, 11, 6), birth_time=time(6, 30, 0), time_known=True,
        birth_place="Cartagena de Indias, Colombia", latitude=10.3910, longitude=-75.4794,
        timezone_name="America/Bogota",
    )
    settings = AstrologySettings(node_type="true")
    chart = compute_natal_chart(profile, settings)
    return chart, settings


def test_finds_two_new_moons_and_two_full_moons_in_a_typical_two_month_window(eclipse_fixture):
    chart, settings = eclipse_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    hits, events = compute_eclipse_hits(chart, settings, start, end)
    assert sum(e.kind == "new_moon" for e in events) == 2
    assert sum(e.kind == "full_moon" for e in events) == 2
    assert all(e.eclipse_label is None for e in events)  # verified independently: no eclipses in this window


def test_finds_the_known_august_2026_eclipses(eclipse_fixture):
    """Cross-check against real, independently-verifiable eclipse dates
    (matches the well-documented 2026-08-12 total solar eclipse and the
    2026-08-28 partial lunar eclipse)."""
    chart, settings = eclipse_fixture
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, tzinfo=timezone.utc)
    hits, events = compute_eclipse_hits(chart, settings, start, end)

    solar = [e for e in events if e.eclipse_label == "solar_total"]
    lunar = [e for e in events if e.eclipse_label == "lunar_partial"]
    assert len(solar) == 1
    assert len(lunar) == 1
    assert jd_ut_to_datetime(solar[0].jd_ut).date() == date(2026, 8, 12)
    assert jd_ut_to_datetime(lunar[0].jd_ut).date() == date(2026, 8, 28)


def test_hits_reference_a_single_moon_degree_not_both_ends(eclipse_fixture):
    """Only the Moon's degree is used as the lunation point (not a second
    hit from the Sun's opposite degree at Full Moon) -- generating both
    would double-count the same event."""
    chart, settings = eclipse_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    hits, events = compute_eclipse_hits(chart, settings, start, end)
    assert len(hits) > 0
    full_moon_events = [e for e in events if e.kind == "full_moon"]
    for event in full_moon_events:
        event_date = jd_ut_to_datetime(event.jd_ut).date().isoformat()
        related_hits = [h for h in hits if event_date in h.moving_point]
        # every hit for this event references the SAME degree_at_reference (the Moon's)
        degrees = {round(h.degree_at_reference, 6) for h in related_hits}
        assert len(degrees) <= 1


def test_exact_hit_dates_has_exactly_one_entry_and_window_is_symmetric(eclipse_fixture):
    chart, settings = eclipse_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    hits, events = compute_eclipse_hits(chart, settings, start, end)
    for h in hits:
        assert len(h.exact_hit_dates) == 1
        exact = h.exact_hit_dates[0]
        assert (exact - h.entry_into_orb).days == 3
        assert (h.exit_from_orb - exact).days == 3
        # no real eclipse falls in Sept-Oct 2026 (nearest is Aug 12/28 2026,
        # next is Feb 2027) -- every hit here must be tagged "lunation", not
        # "eclipse".
        assert h.system == "lunation"


def test_real_eclipses_are_tagged_eclipse_not_lunation(eclipse_fixture):
    """Regression: system must distinguish an actual eclipse from a plain
    New/Full Moon that merely aspects the chart -- a plain lunation must
    never be classified or weighted as an eclipse. Aug 2026 has two real
    eclipses (2026-08-12 solar total, 2026-08-28 lunar partial); the other
    New/Full Moons in the same window must still come through as
    "lunation"."""
    chart, settings = eclipse_fixture
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, tzinfo=timezone.utc)
    hits, events = compute_eclipse_hits(chart, settings, start, end)

    eclipse_movers = {h.moving_point for h in hits if h.system == "eclipse"}
    lunation_movers = {h.moving_point for h in hits if h.system == "lunation"}

    assert any("solar_total" in m for m in eclipse_movers)
    assert any("lunar_partial" in m for m in eclipse_movers)
    assert not any("solar_total" in m or "lunar_partial" in m for m in lunation_movers)
    for h in hits:
        assert h.system in ("eclipse", "lunation")
        if h.system == "eclipse":
            assert "eclipse:" in h.moving_point
        else:
            assert "lunation:" in h.moving_point
