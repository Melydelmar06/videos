from datetime import date, datetime, time, timedelta, timezone

import pytest

from astroengine.daily_dimensions import (
    DAILY_DIMENSIONS, build_dimension_significators, compute_all_dimension_reads, compute_dimension_read,
)
from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.timing_engine import compute_timing_result


@pytest.fixture(scope="module")
def chart_and_hits():
    profile = BirthProfile(
        name="Test", birth_date=date(1990, 3, 21), birth_time=time(14, 15, 0), time_known=True,
        birth_place="", latitude=40.7128, longitude=-74.0060, timezone_name="America/New_York",
    )
    settings = AstrologySettings(node_type="true")
    chart = compute_natal_chart(profile, settings)
    query_start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    query_end = query_start + timedelta(days=14)
    result = compute_timing_result(chart, settings, profile, query_start, query_end)
    return chart, settings, result.hits


def test_every_dimension_produces_a_significator_definition(chart_and_hits):
    chart, settings, _hits = chart_and_hits
    for key in DAILY_DIMENSIONS:
        sigs = build_dimension_significators(chart, settings, key)
        assert len(sigs) >= 1, key


def test_fixed_significator_present_even_without_house_activity(chart_and_hits):
    chart, settings, _hits = chart_and_hits
    sigs = build_dimension_significators(chart, settings, "emotional_climate")
    assert any(s.point == "moon" for s in sigs)


def test_unknown_dimension_raises(chart_and_hits):
    chart, settings, _hits = chart_and_hits
    with pytest.raises(ValueError):
        build_dimension_significators(chart, settings, "not_a_real_dimension")


def test_compute_dimension_read_returns_all_seven(chart_and_hits):
    chart, settings, hits = chart_and_hits
    reads = compute_all_dimension_reads(hits, chart, settings)
    assert set(reads.keys()) == set(DAILY_DIMENSIONS.keys())
    for key, read in reads.items():
        assert read.tier in ("strong signal", "notable", "minor undertone", "quiet")


def test_quiet_dimension_has_no_character():
    """A dimension with zero relevant strong/moderate hits must report
    tier='quiet' and character=None -- never invent a direction for
    evidence that doesn't exist."""
    from astroengine.daily_dimensions import _character, _tier
    assert _tier([]) == "quiet"
    assert _character([]) is None


def test_character_reflects_hard_vs_soft_aspect_mix():
    from datetime import datetime, timezone
    from astroengine.daily_dimensions import _character
    from astroengine.models import DataConfidence, TimingHit
    from astroengine.theme import ThemeAssessment

    def hit(aspect_type):
        return TimingHit(
            system="transit", moving_point="transit:mars", natal_target="sun",
            aspect_type=aspect_type, exact_angle=90.0, degree_at_reference=0.0,
            orb_at_reference=0.0, is_applying=True, entry_into_orb=datetime(2026, 9, 1, tzinfo=timezone.utc),
            exact_hit_dates=[], exit_from_orb=datetime(2026, 9, 5, tzinfo=timezone.utc),
            confidence=DataConfidence(basis="exact_time"), evidence_strength="moderate",
        )

    assessment = ThemeAssessment(theme_relevant=True, natal_role="x", theme_specificity="high")
    assert _character([(hit("square"), assessment)]) == "contractive"
    assert _character([(hit("trine"), assessment)]) == "expansive"
    assert _character([(hit("square"), assessment), (hit("trine"), assessment)]) == "mixed"


def test_hits_without_birth_time_would_fail_cleanly():
    """significators_for_houses (called under the hood) requires known
    houses; a caller passing a chart built without a known birth time
    should get the same clear error theme_definitions already raises."""
    profile = BirthProfile(
        name="Unknown time", birth_date=date(1990, 3, 21), birth_time=None, time_known=False,
        birth_place="", latitude=40.7128, longitude=-74.0060, timezone_name="America/New_York",
    )
    settings = AstrologySettings(node_type="true")
    chart = compute_natal_chart(profile, settings)
    with pytest.raises(ValueError):
        build_dimension_significators(chart, settings, "energy")
