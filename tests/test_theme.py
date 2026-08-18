from datetime import datetime, timezone

from astroengine.models import DataConfidence, TimingHit
from astroengine.theme import ThemeSignificator, assess_theme_relevance, theme_specificity_for_window


def _dt(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _hit(natal_target, moving_point="transit:saturn", aspect_type="square"):
    return TimingHit(
        system="transit", moving_point=moving_point, natal_target=natal_target,
        aspect_type=aspect_type, exact_angle=90.0, degree_at_reference=0.0,
        orb_at_reference=0.0, is_applying=True, entry_into_orb=_dt(2027, 2, 1),
        exact_hit_dates=[_dt(2027, 2, 19)], exit_from_orb=_dt(2027, 3, 1),
        confidence=DataConfidence(basis="exact_time"),
    )


IMMIGRATION_THEME = [
    ThemeSignificator("moon", "actual chart ruler of the 9th house cusp", "low"),
    ThemeSignificator("jupiter", "posited in the 9th house", "high"),
    ThemeSignificator("saturn", "natural/generic significator of restriction and bureaucracy", "low"),
]


def test_hit_to_undefined_point_is_not_theme_relevant():
    hit = _hit("venus")
    assessment = assess_theme_relevance(hit, IMMIGRATION_THEME)
    assert assessment.theme_relevant is False
    assert assessment.theme_specificity is None


def test_saturn_square_moon_is_relevant_but_low_specificity():
    """The exact audit worked example: Moon rules the 9th house, so a hit
    to it is legitimately relevant to immigration -- but that's a low
    (not moderate/high) specificity tie, since Moon's dominant meanings lie
    mostly outside the immigration theme."""
    moon_hit = _hit("moon")
    assessment = assess_theme_relevance(moon_hit, IMMIGRATION_THEME)
    assert assessment.theme_relevant is True
    assert assessment.theme_specificity == "low"
    assert "9th house" in assessment.natal_role


def test_window_specificity_high_requires_two_distinct_non_low_points():
    hits = [_hit("jupiter"), _hit("moon", moving_point="solar_arc:mars", aspect_type="trine")]
    # only one non-low point (jupiter) in this window -- moderate, not high
    assert theme_specificity_for_window(hits, IMMIGRATION_THEME) == "moderate"


def test_window_specificity_low_when_every_relevant_point_is_low():
    hits = [_hit("moon"), _hit("saturn", moving_point="progressed:mars")]
    assert theme_specificity_for_window(hits, IMMIGRATION_THEME) == "low"


def test_window_specificity_empty_when_nothing_relevant():
    hits = [_hit("venus"), _hit("mars", moving_point="solar_arc:sun")]
    assert theme_specificity_for_window(hits, IMMIGRATION_THEME) == ""


def test_window_specificity_high_with_two_non_low_significators():
    theme = [
        ThemeSignificator("jupiter", "posited in the 9th house", "high"),
        ThemeSignificator("mercury", "chart ruler of the 9th house cusp", "moderate"),
    ]
    hits = [_hit("jupiter"), _hit("mercury", moving_point="solar_arc:venus")]
    assert theme_specificity_for_window(hits, theme) == "high"
