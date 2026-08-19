from datetime import date, time

import pytest

from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings
from astroengine.theme import assess_theme_relevance
from astroengine.theme_definitions import LIFE_CATEGORIES, build_category_significators


@pytest.fixture(scope="module")
def chart():
    profile = BirthProfile(
        name="Test", birth_date=date(1986, 11, 6), birth_time=time(6, 30, 0), time_known=True,
        birth_place="Cartagena de Indias, Colombia", latitude=10.3910, longitude=-75.4794,
        timezone_name="America/Bogota",
    )
    settings = AstrologySettings(node_type="true")
    return compute_natal_chart(profile, settings), settings


def test_every_life_category_produces_at_least_one_significator(chart):
    natal_chart, settings = chart
    for key in LIFE_CATEGORIES:
        sigs = build_category_significators(natal_chart, settings, key)
        assert len(sigs) >= 1, key


def test_angular_house_significator_is_tagged_high(chart):
    natal_chart, settings = chart
    sigs = build_category_significators(natal_chart, settings, "home_family")
    angle_sigs = [s for s in sigs if s.point == "IC"]
    assert angle_sigs
    assert angle_sigs[0].specificity == "high"


def test_natural_ruler_only_added_when_it_differs_from_actual(chart):
    natal_chart, settings = chart
    sigs = build_category_significators(natal_chart, settings, "money_finance")
    # 2nd house's natural ruler is Venus (Taurus); if the chart's actual
    # 2nd-cusp ruler happens to also be Venus, no separate "low" entry for
    # Venus should be added (no duplicate significator for the same point).
    venus_entries = [s for s in sigs if s.point == "venus"]
    assert len(venus_entries) <= 1


def test_no_duplicate_point_role_pairs(chart):
    natal_chart, settings = chart
    for key in LIFE_CATEGORIES:
        sigs = build_category_significators(natal_chart, settings, key)
        pairs = [(s.point, s.role) for s in sigs]
        assert len(pairs) == len(set(pairs))


def test_unknown_category_raises(chart):
    natal_chart, settings = chart
    with pytest.raises(ValueError):
        build_category_significators(natal_chart, settings, "not_a_real_category")


def test_significators_actually_usable_by_theme_relevance(chart):
    """End-to-end sanity: the built ThemeDefinition works with
    astroengine.theme's own relevance scoring, not just as inert data."""
    from datetime import datetime, timezone
    from astroengine.models import DataConfidence, TimingHit

    natal_chart, settings = chart
    sigs = build_category_significators(natal_chart, settings, "home_family")
    target_point = sigs[0].point
    hit = TimingHit(
        system="transit", moving_point="transit:saturn", natal_target=target_point,
        aspect_type="square", exact_angle=90.0, degree_at_reference=0.0, orb_at_reference=0.0,
        is_applying=True, entry_into_orb=datetime(2027, 1, 1, tzinfo=timezone.utc),
        exact_hit_dates=[], exit_from_orb=datetime(2027, 2, 1, tzinfo=timezone.utc),
        confidence=DataConfidence(basis="exact_time"),
    )
    assessment = assess_theme_relevance(hit, sigs)
    assert assessment.theme_relevant is True
