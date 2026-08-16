from datetime import date, time, datetime, timezone

import pytest

from astroengine.evidence import annotate_timing_hit_evidence_eligibility
from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.timing_solar_returns import compute_solar_return_hits, find_solar_return_jd
from astroengine.timeutil import jd_ut_to_datetime


@pytest.fixture(scope="module")
def solar_return_fixture():
    profile = BirthProfile(
        name="Test", birth_date=date(1986, 11, 6), birth_time=time(6, 30, 0), time_known=True,
        birth_place="Cartagena de Indias, Colombia", latitude=10.3910, longitude=-75.4794,
        timezone_name="America/Bogota",
    )
    settings = AstrologySettings(node_type="true")
    chart = compute_natal_chart(profile, settings)
    natal_sun = next(p for p in chart.planets if p.planet == "sun").longitude
    return chart, settings, natal_sun, profile


def test_solar_return_lands_within_a_day_of_the_birthday(solar_return_fixture):
    chart, settings, natal_sun, profile = solar_return_fixture
    for year in (2020, 2025, 2026, 2030):
        jd = find_solar_return_jd(natal_sun, year, 11, 6, settings)
        return_dt = jd_ut_to_datetime(jd)
        assert return_dt.date() in (date(year, 11, 5), date(year, 11, 6), date(year, 11, 7))


def test_return_sun_conjunct_natal_sun_is_flagged_structural_tautology(solar_return_fixture):
    chart, settings, natal_sun, profile = solar_return_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    hits, _returns = compute_solar_return_hits(
        chart, settings, natal_sun, 11, 6, profile.latitude, profile.longitude, start, end,
    )
    tautology = [h for h in hits if h.moving_point == "solar_return:sun" and h.natal_target == "sun"]
    assert len(tautology) == 1
    assert tautology[0].orb_at_reference == pytest.approx(0.0, abs=1e-6)
    assert tautology[0].evidence_eligible is False
    assert "structural" in tautology[0].evidence_note

    # and it must SURVIVE the general dedup pass, not get overwritten
    annotate_timing_hit_evidence_eligibility(hits)
    tautology_after = [h for h in hits if h.moving_point == "solar_return:sun" and h.natal_target == "sun"][0]
    assert tautology_after.evidence_eligible is False


def test_correct_return_year_governs_a_pre_birthday_window(solar_return_fixture):
    """Sept-Oct 2026 is before the Nov 6 2026 birthday, so the governing
    return must be the 2025 one (valid Nov 2025 -> Nov 2026), not 2026's."""
    chart, settings, natal_sun, profile = solar_return_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    hits, returns = compute_solar_return_hits(
        chart, settings, natal_sun, 11, 6, profile.latitude, profile.longitude, start, end,
    )
    assert len(returns) == 1
    assert returns[0].return_utc.year == 2025
    for h in hits:
        assert h.entry_into_orb.year == 2025
        assert h.exit_from_orb.year == 2026


def test_no_solar_return_hit_lacks_a_validity_window(solar_return_fixture):
    chart, settings, natal_sun, profile = solar_return_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    hits, _returns = compute_solar_return_hits(
        chart, settings, natal_sun, 11, 6, profile.latitude, profile.longitude, start, end,
    )
    assert len(hits) > 0
    for h in hits:
        assert h.entry_into_orb is not None
        assert h.exit_from_orb is not None
        assert h.entry_into_orb < h.exit_from_orb
        assert h.exact_hit_dates == []
