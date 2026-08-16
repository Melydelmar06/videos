from datetime import date, time, datetime, timezone

import pytest

from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.timing_transits import compute_transit_hits


@pytest.fixture(scope="module")
def real_chart():
    profile = BirthProfile(
        name="Test", birth_date=date(1986, 11, 6), birth_time=time(6, 30, 0), time_known=True,
        birth_place="Cartagena de Indias, Colombia", latitude=10.3910, longitude=-75.4794,
        timezone_name="America/Bogota",
    )
    settings = AstrologySettings(node_type="true")
    return compute_natal_chart(profile, settings), settings


def test_hits_only_within_or_touching_query_window(real_chart):
    chart, settings = real_chart
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    hits = compute_transit_hits(chart, settings, start, end)
    assert len(hits) > 0
    for h in hits:
        window_start = h.entry_into_orb or start
        window_end = h.exit_from_orb or end
        assert window_end >= start
        assert window_start <= end


def test_entry_exact_exit_are_chronologically_ordered(real_chart):
    chart, settings = real_chart
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    hits = compute_transit_hits(chart, settings, start, end)
    for h in hits:
        if h.entry_into_orb and h.exit_from_orb:
            assert h.entry_into_orb <= h.exit_from_orb
        for exact in h.exact_hit_dates:
            if h.entry_into_orb:
                assert h.entry_into_orb <= exact
            if h.exit_from_orb:
                assert exact <= h.exit_from_orb


def test_all_natal_targets_and_aspect_types_are_valid(real_chart):
    chart, settings = real_chart
    valid_targets = {p.planet for p in chart.planets} | {a.name for a in chart.angles}
    enabled = set(settings.enabled_aspects())
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    hits = compute_transit_hits(chart, settings, start, end)
    for h in hits:
        assert h.natal_target in valid_targets
        assert h.aspect_type in enabled
        assert h.system == "transit"
        assert h.moving_point.startswith("transit:")


def test_transiting_sun_returns_to_natal_sun_near_birthday(real_chart):
    """An astronomically obvious, independently-checkable fact: the
    transiting Sun conjuncts the natal Sun once a year, right around the
    birthday (Nov 6). This is the actual mechanism a solar return is built
    on, so it's a meaningful correctness check on the transit scanner
    itself, not just a plausibility check."""
    chart, settings = real_chart
    start = datetime(2026, 10, 20, tzinfo=timezone.utc)
    end = datetime(2026, 11, 20, tzinfo=timezone.utc)
    hits = compute_transit_hits(chart, settings, start, end)
    sun_returns = [h for h in hits if h.moving_point == "transit:sun" and h.natal_target == "sun" and h.aspect_type == "conjunction"]
    assert len(sun_returns) == 1
    exact_dates = sun_returns[0].exact_hit_dates
    assert len(exact_dates) == 1
    # should land within a day or two of Nov 6
    assert exact_dates[0].date() in (date(2026, 11, 5), date(2026, 11, 6), date(2026, 11, 7))


def test_no_south_node_mover_present(real_chart):
    """south_node is deliberately not scanned as a mover -- north_node
    already covers the whole node axis via its full aspect set."""
    chart, settings = real_chart
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    hits = compute_transit_hits(chart, settings, start, end)
    assert not any(h.moving_point == "transit:south_node" for h in hits)
    assert any(h.moving_point == "transit:north_node" for h in hits)
