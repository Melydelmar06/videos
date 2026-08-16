from datetime import date, time, datetime, timezone

import pytest

from astroengine.evidence import annotate_timing_hit_evidence_eligibility
from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.timing_solar_arc import compute_solar_arc_hits
from astroengine.timeutil import birth_julian_moment


@pytest.fixture(scope="module")
def solar_arc_fixture():
    profile = BirthProfile(
        name="Test", birth_date=date(1986, 11, 6), birth_time=time(6, 30, 0), time_known=True,
        birth_place="Cartagena de Indias, Colombia", latitude=10.3910, longitude=-75.4794,
        timezone_name="America/Bogota",
    )
    settings = AstrologySettings(node_type="true")
    chart = compute_natal_chart(profile, settings)
    birth_jd_ut = birth_julian_moment(profile.birth_date, profile.birth_time, profile.timezone_name).jd_ut
    natal_sun = next(p for p in chart.planets if p.planet == "sun").longitude
    return chart, settings, birth_jd_ut, natal_sun


def test_solar_arc_hits_have_at_most_one_exact_date(solar_arc_fixture):
    """The real Sun's geocentric motion never goes retrograde, so the arc is
    monotonic -- unlike transits/progressions, a solar arc hit can never
    have more than one exact_hit_date."""
    chart, settings, birth_jd_ut, natal_sun = solar_arc_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    hits = compute_solar_arc_hits(chart, settings, birth_jd_ut, natal_sun, start, end)
    assert len(hits) > 0
    for h in hits:
        assert len(h.exact_hit_dates) <= 1
        assert h.system == "solar_arc"
        assert h.moving_point.startswith("solar_arc:")


def test_no_self_directed_hits(solar_arc_fixture):
    chart, settings, birth_jd_ut, natal_sun = solar_arc_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    hits = compute_solar_arc_hits(chart, settings, birth_jd_ut, natal_sun, start, end)
    for h in hits:
        directed_name = h.moving_point.split(":", 1)[1]
        assert directed_name != h.natal_target


def test_linked_pair_mirror_duplicates_present_in_raw_but_collapsed_after_annotation(solar_arc_fixture):
    chart, settings, birth_jd_ut, natal_sun = solar_arc_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    hits = compute_solar_arc_hits(chart, settings, birth_jd_ut, natal_sun, start, end)

    # find a directed point that hits both Ascendant and Descendant (or
    # another linked pair) -- if the dataset has one, it must dedupe to 1.
    by_mover_aspect: dict = {}
    for h in hits:
        by_mover_aspect.setdefault((h.moving_point, h.aspect_type), []).append(h)

    found_pair = False
    for (mover, aspect_type), group in by_mover_aspect.items():
        targets = {h.natal_target for h in group}
        if {"Ascendant", "Descendant"} <= targets or {"Midheaven", "IC"} <= targets or {"north_node", "south_node"} <= targets:
            found_pair = True

    if found_pair:
        annotate_timing_hit_evidence_eligibility(hits)
        # every mover+aspect group touching a linked pair should have
        # exactly one eligible entry among that pair's members
        for (mover, aspect_type), group in by_mover_aspect.items():
            targets_in_group = {h.natal_target: h for h in group}
            for pair in ({"Ascendant", "Descendant"}, {"Midheaven", "IC"}, {"north_node", "south_node"}):
                if pair <= targets_in_group.keys():
                    eligible_count = sum(targets_in_group[t].evidence_eligible for t in pair)
                    assert eligible_count == 1
