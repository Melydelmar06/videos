import pytest

from astroengine.daily_dimensions import DimensionRead
from astroengine.regulate import (
    MOOD_BUCKET, PRACTICE_TYPES, chart_state_summary, select_practice,
)


def _read(key, tier="quiet", character=None):
    return DimensionRead(key=key, label=key, tier=tier, character=character, top=[])


def _reads(**overrides):
    keys = ["emotional_climate", "energy", "social_energy", "creativity",
            "decision_making", "relationships", "rest_vs_action"]
    base = {k: _read(k) for k in keys}
    base.update(overrides)
    return base


def test_every_mood_bucket_maps_to_real_practice_types():
    from astroengine.regulate import PRACTICE_BY_MOOD_BUCKET
    for bucket, practices in PRACTICE_BY_MOOD_BUCKET.items():
        for p in practices:
            assert p in PRACTICE_TYPES, (bucket, p)


def test_every_chart_state_maps_to_real_practice_types():
    from astroengine.regulate import PRACTICE_BY_CHART_STATE
    for state, practices in PRACTICE_BY_CHART_STATE.items():
        for p in practices:
            assert p in PRACTICE_TYPES, (state, p)


def test_all_nine_moods_are_bucketed():
    expected = {"Energised", "Calm", "Happy", "Flat", "Anxious", "Emotional", "Irritable", "Overwhelmed", "Exhausted"}
    assert set(MOOD_BUCKET.keys()) == expected


def test_chart_state_expansive_energy_reads_as_high_energy_expansion():
    reads = _reads(energy=_read("energy", "strong signal", "expansive"))
    assert chart_state_summary(reads) == "high_energy_expansion"


def test_chart_state_contractive_emotional_climate_reads_as_emotionally_intense():
    reads = _reads(emotional_climate=_read("emotional_climate", "strong signal", "contractive"))
    assert chart_state_summary(reads) == "emotionally_intense"


def test_chart_state_nothing_active_is_steady_quiet():
    assert chart_state_summary(_reads()) == "steady_quiet"


def test_distress_mood_gets_grounding_regardless_of_chart_state():
    """Emotional intensity in the chart AND distress mood point the same
    way -- no mismatch, straightforward match."""
    reads = _reads(emotional_climate=_read("emotional_climate", "strong signal", "contractive"))
    sel = select_practice("Overwhelmed", reads)
    assert sel.practice_type in ("nervous_system_regulation", "grounding_exercise", "breathing_exercise", "rest_recovery")
    assert sel.human_chart_mismatch is False


def test_energised_mood_gets_action_oriented_practice_not_calming():
    """The explicit worked example: an expansive chart state must NOT
    default to a calming practice just because that's the generic
    instinct -- energised mood should get planning/creative/exploration."""
    reads = _reads(energy=_read("energy", "strong signal", "expansive"))
    sel = select_practice("Energised", reads)
    assert sel.practice_type in ("planning_action", "creative_exercise", "exploration", "manifestation_intention")


def test_human_wins_on_mismatch_energised_during_contractive_chart():
    """Chart suggests a quieter/contractive stretch, but the person
    reports feeling energised: human data must win, and the mismatch must
    be flagged so the copy layer can name it."""
    reads = _reads(emotional_climate=_read("emotional_climate", "strong signal", "contractive"))
    sel = select_practice("Energised", reads)
    assert sel.practice_type in ("planning_action", "creative_exercise", "exploration", "manifestation_intention")
    assert sel.human_chart_mismatch is True
    assert sel.driven_by == "human_reported"


def test_no_checkin_falls_back_to_chart_only():
    reads = _reads(energy=_read("energy", "strong signal", "expansive"))
    sel = select_practice(None, reads)
    assert sel.driven_by == "chart_only"
    assert sel.mood is None
    assert sel.human_chart_mismatch is False


def test_calm_mood_is_neutral_and_defers_to_chart():
    reads = _reads(emotional_climate=_read("emotional_climate", "strong signal", "contractive"))
    sel = select_practice("Calm", reads)
    assert sel.driven_by == "chart_only"
    assert sel.practice_type in ("grounding_exercise", "nervous_system_regulation", "journaling_prompt")


def test_unknown_mood_raises():
    with pytest.raises(ValueError):
        select_practice("Ecstatic", _reads())
