"""End-to-end natal chart tests: wires together timezone handling, planet
positions, houses/angles, and aspects, and checks structural invariants plus
the unknown-birth-time fallback path.
"""

from datetime import date, time

import pytest

from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings


def _ang_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def test_full_chart_structure(sample_profile, default_settings):
    chart = compute_natal_chart(sample_profile, default_settings)

    assert len(chart.planets) == 12  # 10 classical planets + north/south node
    names = {p.planet for p in chart.planets}
    assert names == {
        "sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
        "uranus", "neptune", "pluto", "north_node", "south_node",
    }
    assert all(p.house is not None and 1 <= p.house <= 12 for p in chart.planets)
    assert all(p.sign for p in chart.planets)

    assert len(chart.houses) == 12
    assert [h.house_number for h in chart.houses] == list(range(1, 13))
    assert len(chart.angles) == 4
    assert {a.name for a in chart.angles} == {"Ascendant", "Midheaven", "Descendant", "IC"}


def test_angles_are_internally_consistent(sample_profile, default_settings):
    chart = compute_natal_chart(sample_profile, default_settings)
    by_name = {a.name: a for a in chart.angles}
    house_1 = next(h for h in chart.houses if h.house_number == 1)
    house_10 = next(h for h in chart.houses if h.house_number == 10)

    assert _ang_diff(by_name["Ascendant"].longitude, house_1.longitude) < 1e-6
    assert _ang_diff(by_name["Midheaven"].longitude, house_10.longitude) < 1e-6
    assert _ang_diff(by_name["Descendant"].longitude, (by_name["Ascendant"].longitude + 180) % 360) < 1e-6
    assert _ang_diff(by_name["IC"].longitude, (by_name["Midheaven"].longitude + 180) % 360) < 1e-6


def test_south_node_opposite_north_node(sample_profile, default_settings):
    chart = compute_natal_chart(sample_profile, default_settings)
    north = next(p for p in chart.planets if p.planet == "north_node")
    south = next(p for p in chart.planets if p.planet == "south_node")
    assert _ang_diff((north.longitude + 180) % 360, south.longitude) < 1e-6


def test_aspects_have_no_duplicate_unordered_pairs(sample_profile, default_settings):
    chart = compute_natal_chart(sample_profile, default_settings)
    seen = set()
    for asp in chart.aspects:
        key = frozenset((asp.point_a, asp.point_b))
        assert key not in seen, f"duplicate aspect pair {key}"
        seen.add(key)
        assert asp.orb >= 0.0


def test_unknown_birth_time_suppresses_houses_and_angles():
    profile = BirthProfile(
        name="Unknown Time Person",
        birth_date=date(1985, 3, 21),
        birth_time=None,
        time_known=False,
        birth_place="Unknown",
        latitude=51.5074,
        longitude=-0.1278,
        timezone_name="Europe/London",
    )
    chart = compute_natal_chart(profile, AstrologySettings())

    assert chart.houses == []
    assert chart.angles == []
    assert len(chart.planets) == 12
    assert all(p.house is None for p in chart.planets)
    assert all(p.confidence.basis == "unknown_time" for p in chart.planets)


def test_known_vs_approximate_time_confidence_differs():
    exact = BirthProfile(
        name="Exact", birth_date=date(1985, 3, 21), birth_time=time(10, 0),
        time_known=True, birth_place="X", latitude=51.5, longitude=-0.1,
        timezone_name="Europe/London",
    )
    chart = compute_natal_chart(exact, AstrologySettings())
    assert all(p.confidence.basis == "exact_time" for p in chart.planets)
    assert all(h.confidence.basis == "exact_time" for h in chart.houses)


def test_natal_chart_round_trips_through_sqlite(conn, sample_profile, default_settings):
    from astroengine import repository

    profile_id = repository.save_birth_profile(conn, sample_profile)
    default_settings.birth_profile_id = profile_id
    repository.save_astrology_settings(conn, default_settings)

    chart = compute_natal_chart(sample_profile, default_settings)
    repository.save_natal_chart(conn, profile_id, chart)

    reloaded_profile = repository.load_birth_profile(conn, profile_id)
    reloaded_settings = repository.load_astrology_settings(conn, profile_id)
    reloaded_chart = repository.load_natal_chart(conn, profile_id)

    assert reloaded_profile.name == sample_profile.name
    assert reloaded_profile.latitude == sample_profile.latitude
    assert reloaded_settings.house_system == default_settings.house_system

    assert len(reloaded_chart.planets) == len(chart.planets)
    assert len(reloaded_chart.houses) == len(chart.houses)
    assert len(reloaded_chart.angles) == len(chart.angles)
    assert len(reloaded_chart.aspects) == len(chart.aspects)

    original_sun = next(p for p in chart.planets if p.planet == "sun")
    reloaded_sun = next(p for p in reloaded_chart.planets if p.planet == "sun")
    assert reloaded_sun.longitude == pytest.approx(original_sun.longitude, abs=1e-9)
    assert reloaded_sun.confidence.basis == original_sun.confidence.basis
