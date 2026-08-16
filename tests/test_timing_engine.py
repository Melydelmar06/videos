from datetime import date, time, datetime, timezone

import pytest

from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.timing_engine import compute_timing_result


@pytest.fixture(scope="module")
def engine_fixture():
    profile = BirthProfile(
        name="Test", birth_date=date(1986, 11, 6), birth_time=time(6, 30, 0), time_known=True,
        birth_place="Cartagena de Indias, Colombia", latitude=10.3910, longitude=-75.4794,
        timezone_name="America/Bogota",
    )
    settings = AstrologySettings(node_type="true")
    chart = compute_natal_chart(profile, settings)
    return chart, settings, profile


def test_raises_for_unknown_birth_time():
    profile = BirthProfile(
        name="Unknown", birth_date=date(1990, 1, 1), birth_time=None, time_known=False,
        birth_place="X", latitude=0.0, longitude=0.0, timezone_name="UTC",
    )
    settings = AstrologySettings()
    chart = compute_natal_chart(profile, settings)
    with pytest.raises(ValueError):
        compute_timing_result(chart, settings, profile,
                               datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 10, 31, tzinfo=timezone.utc))


def test_all_five_systems_represented(engine_fixture):
    chart, settings, profile = engine_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    result = compute_timing_result(chart, settings, profile, start, end)
    systems = {h.system for h in result.hits}
    assert systems == {"transit", "progression", "solar_arc", "solar_return", "eclipse"}


def test_every_eligible_hit_has_a_strength_tier_ineligible_have_none(engine_fixture):
    chart, settings, profile = engine_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    result = compute_timing_result(chart, settings, profile, start, end)
    for h in result.hits:
        if h.evidence_eligible:
            assert h.evidence_strength in ("strong", "moderate", "weak")
        else:
            assert h.evidence_strength is None


def test_linked_pair_dedup_holds_across_the_whole_combined_hit_list(engine_fixture):
    """Spot-check on the FULL combined list (all 5 systems mixed together):
    for any (system, moving_point) that hit both ends of a linked pair in
    an overlapping window, exactly one side is eligible."""
    chart, settings, profile = engine_fixture
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    result = compute_timing_result(chart, settings, profile, start, end)

    by_key: dict = {}
    for h in result.hits:
        by_key.setdefault((h.system, h.moving_point, h.aspect_type), []).append(h)

    checked_any = False
    for (system, mover, aspect_type), group in by_key.items():
        by_target = {h.natal_target: h for h in group}
        for pair in ({"Ascendant", "Descendant"}, {"Midheaven", "IC"}, {"north_node", "south_node"}):
            if pair <= by_target.keys():
                a, b = (by_target[t] for t in pair)
                # only meaningful if their windows actually overlap (same underlying pass)
                a_start = a.entry_into_orb or start
                a_end = a.exit_from_orb or end
                b_start = b.entry_into_orb or start
                b_end = b.exit_from_orb or end
                if a_start <= b_end and b_start <= a_end:
                    checked_any = True
                    assert sum(x.evidence_eligible for x in (a, b)) == 1

    assert checked_any, "expected at least one linked-pair case in this real chart's hit list to validate against"
