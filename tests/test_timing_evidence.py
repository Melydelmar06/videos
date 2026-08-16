from datetime import datetime, timezone

from astroengine.evidence import (
    annotate_timing_hit_evidence_eligibility, assign_evidence_strength, classify_hit_strength,
)
from astroengine.models import DataConfidence, TimingHit


def _dt(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _hit(system, moving_point, natal_target, aspect_type, entry, exit_, exact_dates=None, orb=0.5):
    return TimingHit(
        system=system,
        moving_point=moving_point,
        natal_target=natal_target,
        aspect_type=aspect_type,
        exact_angle=90.0,
        degree_at_reference=0.0,
        orb_at_reference=orb,
        is_applying=True,
        entry_into_orb=entry,
        exact_hit_dates=exact_dates or [],
        exit_from_orb=exit_,
        confidence=DataConfidence(basis="exact_time"),
    )


def test_same_mover_overlapping_window_linked_pair_is_deduped():
    hits = [
        _hit("transit", "transit:saturn", "Ascendant", "square", _dt(2026, 9, 1), _dt(2026, 9, 20)),
        _hit("transit", "transit:saturn", "Descendant", "square", _dt(2026, 9, 1), _dt(2026, 9, 20)),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assert sum(h.evidence_eligible for h in hits) == 1
    assert hits[0].evidence_eligible is True
    assert hits[1].evidence_eligible is False
    assert "mirror duplicate" in hits[1].evidence_note


def test_same_mover_non_overlapping_windows_not_merged():
    # transiting Moon squares natal Ascendant twice in the window, weeks
    # apart -- two real events, both must stay eligible.
    hits = [
        _hit("transit", "transit:moon", "Ascendant", "square", _dt(2026, 9, 3), _dt(2026, 9, 4)),
        _hit("transit", "transit:moon", "Ascendant", "square", _dt(2026, 10, 1), _dt(2026, 10, 2)),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assert all(h.evidence_eligible for h in hits)


def test_different_movers_not_merged():
    hits = [
        _hit("transit", "transit:mars", "Ascendant", "square", _dt(2026, 9, 1), _dt(2026, 9, 10)),
        _hit("transit", "transit:venus", "Descendant", "square", _dt(2026, 9, 1), _dt(2026, 9, 10)),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assert all(h.evidence_eligible for h in hits)


def test_different_systems_same_mover_name_not_accidentally_merged():
    # "transit:sun" vs "progressed:sun" are different moving_point strings,
    # and different systems -- must never merge even with identical targets.
    hits = [
        _hit("transit", "transit:sun", "Ascendant", "conjunction", _dt(2026, 9, 1), _dt(2026, 9, 5)),
        _hit("progression", "progressed:sun", "Descendant", "opposition", _dt(2026, 9, 1), _dt(2026, 9, 5)),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assert all(h.evidence_eligible for h in hits)


def test_strong_requires_exact_hard_angle_slow_mover_and_corroboration():
    window_start, window_end = _dt(2026, 9, 1), _dt(2026, 10, 31)
    hits = [
        _hit("transit", "transit:saturn", "Ascendant", "square", _dt(2026, 9, 1), _dt(2026, 9, 30),
             exact_dates=[_dt(2026, 9, 14)], orb=0.0),
        _hit("solar_arc", "solar_arc:mars", "Ascendant", "square", _dt(2026, 9, 1), _dt(2026, 9, 30),
             exact_dates=[_dt(2026, 9, 15)], orb=0.0),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, window_start, window_end)
    assert hits[0].evidence_strength == "strong"
    assert hits[1].evidence_strength == "strong"


def test_exact_but_uncorroborated_is_moderate_not_strong():
    window_start, window_end = _dt(2026, 9, 1), _dt(2026, 10, 31)
    hit = _hit("transit", "transit:saturn", "Ascendant", "square", _dt(2026, 9, 1), _dt(2026, 9, 30),
               exact_dates=[_dt(2026, 9, 14)], orb=0.0)
    annotate_timing_hit_evidence_eligibility([hit])
    assign_evidence_strength([hit], window_start, window_end)
    assert hit.evidence_strength == "moderate"


def test_fast_mover_exact_hit_capped_below_strong_even_if_corroborated():
    # Moon doesn't qualify as "slow/outer" -- even exact + hard + angle +
    # corroborated, it can't reach Strong per ARCHITECTURE.md's mover gate.
    window_start, window_end = _dt(2026, 9, 1), _dt(2026, 10, 31)
    hits = [
        _hit("transit", "transit:moon", "Ascendant", "conjunction", _dt(2026, 9, 3), _dt(2026, 9, 4),
             exact_dates=[_dt(2026, 9, 3, 12)], orb=0.0),
        _hit("solar_arc", "solar_arc:sun", "Ascendant", "conjunction", _dt(2026, 9, 1), _dt(2026, 9, 30),
             exact_dates=[_dt(2026, 9, 14)], orb=0.0),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, window_start, window_end)
    assert hits[0].evidence_strength == "moderate"
    assert hits[1].evidence_strength == "strong"


def test_plain_lunation_cannot_reach_strong_but_real_eclipse_can():
    """Regression: system="lunation" (an ordinary New/Full Moon) must not
    get the same 'rare, pay attention' mover credit as system="eclipse" --
    otherwise every routine monthly lunation that happens to aspect the
    chart exactly would inflate to Strong just like an actual eclipse."""
    window_start, window_end = _dt(2026, 9, 1), _dt(2026, 10, 31)

    lunation_hit = _hit("lunation", "lunation:new_moon:2026-10-10", "moon", "square",
                         _dt(2026, 10, 7), _dt(2026, 10, 13), exact_dates=[_dt(2026, 10, 10)], orb=0.0)
    corroborator = _hit("solar_arc", "solar_arc:mars", "moon", "square",
                         _dt(2026, 9, 1), _dt(2026, 10, 31), exact_dates=[_dt(2026, 10, 10)], orb=0.0)
    hits = [lunation_hit, corroborator]
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, window_start, window_end)
    assert lunation_hit.evidence_strength == "moderate"  # not strong

    eclipse_hit = _hit("eclipse", "eclipse:solar_total:2026-08-12", "moon", "square",
                        _dt(2026, 8, 9), _dt(2026, 8, 15), exact_dates=[_dt(2026, 8, 12)], orb=0.0)
    eclipse_corroborator = _hit("solar_arc", "solar_arc:mars", "moon", "square",
                                 _dt(2026, 8, 1), _dt(2026, 8, 31), exact_dates=[_dt(2026, 8, 12)], orb=0.0)
    eclipse_hits = [eclipse_hit, eclipse_corroborator]
    annotate_timing_hit_evidence_eligibility(eclipse_hits)
    assign_evidence_strength(eclipse_hits, _dt(2026, 8, 1), _dt(2026, 8, 31))
    assert eclipse_hit.evidence_strength == "strong"


def test_unknown_location_confidence_caps_below_strong():
    """A hit whose confidence.basis is 'unknown_location' (a location-
    dependent value computed without a real known location, e.g. a future
    solar-return house/angle hit with no solar_return_location supplied)
    must never reach Strong, even if every other Strong criterion is met."""
    window_start, window_end = _dt(2026, 9, 1), _dt(2026, 10, 31)
    hits = [
        _hit("solar_return", "solar_return:sun", "Ascendant", "conjunction",
             _dt(2025, 11, 5), _dt(2026, 11, 6), exact_dates=[], orb=0.0),
        _hit("transit", "transit:jupiter", "Ascendant", "conjunction",
             _dt(2026, 9, 1), _dt(2026, 10, 31), exact_dates=[_dt(2026, 9, 15)], orb=0.0),
    ]
    hits[0].confidence = DataConfidence(basis="unknown_location")
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, window_start, window_end)
    assert hits[0].evidence_strength != "strong"
    assert hits[0].evidence_strength == "moderate"  # still counts, just capped


def test_wide_orb_uncorroborated_is_weak():
    window_start, window_end = _dt(2026, 9, 1), _dt(2026, 10, 31)
    hit = _hit("transit", "transit:jupiter", "sun", "trine", _dt(2026, 9, 1), _dt(2026, 9, 30), orb=5.0)
    assign_evidence_strength([hit], window_start, window_end)
    assert hit.evidence_strength == "weak"


def test_wide_orb_corroborated_within_three_degrees_is_moderate():
    window_start, window_end = _dt(2026, 9, 1), _dt(2026, 10, 31)
    hits = [
        _hit("transit", "transit:jupiter", "sun", "trine", _dt(2026, 9, 1), _dt(2026, 9, 30), orb=2.0),
        _hit("progression", "progressed:venus", "sun", "trine", _dt(2026, 9, 1), _dt(2026, 9, 30), orb=2.0),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, window_start, window_end)
    assert hits[0].evidence_strength == "moderate"
    assert hits[1].evidence_strength == "moderate"


def test_pre_flagged_ineligible_hit_is_not_overwritten_by_clustering():
    """Regression: a caller-set evidence_eligible=False (e.g. a solar-return
    system flagging its own 'return Sun conjunct natal Sun' tautology) must
    survive annotate_timing_hit_evidence_eligibility, even though the hit
    shares a mover+window with other hits that get clustered/reassigned."""
    tautology = _hit("solar_return", "solar_return:sun", "sun", "conjunction",
                      _dt(2025, 11, 5), _dt(2026, 11, 6), orb=0.0)
    tautology.evidence_eligible = False
    tautology.evidence_note = "structural: return's own defining condition"

    other = _hit("solar_return", "solar_return:sun", "jupiter", "trine",
                  _dt(2025, 11, 5), _dt(2026, 11, 6), orb=0.8)

    hits = [tautology, other]
    annotate_timing_hit_evidence_eligibility(hits)

    assert hits[0].evidence_eligible is False
    assert "return's own defining condition" in hits[0].evidence_note
    assert hits[1].evidence_eligible is True


def test_mover_side_linked_pair_is_deduped_solar_arc_directed_angles():
    """Regression: solar arc directs angles/nodes too, so the MOVER itself
    can be a linked-pair member (directed Ascendant vs directed Descendant
    are always 180 deg apart, just like the natal points they're built
    from). moving_point strings differ ('solar_arc:Ascendant' vs
    'solar_arc:Descendant'), so this can only be caught by canonicalizing
    the mover, not by exact-string mover matching."""
    hits = [
        _hit("solar_arc", "solar_arc:north_node", "saturn", "opposition",
             _dt(2026, 8, 18), None, orb=7.96),
        _hit("solar_arc", "solar_arc:south_node", "saturn", "conjunction",
             _dt(2026, 8, 18), None, orb=7.96),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assert sum(h.evidence_eligible for h in hits) == 1


def test_open_ended_windows_with_no_exit_or_exact_date_still_detected_as_overlapping():
    """Regression: a very slow mover (e.g. a solar-arc-directed node) can
    have an entry date but no exit AND no exact_hit_dates yet (both still
    beyond the scan horizon). Two such hits sharing that same open entry
    must still be recognized as the same underlying window, not silently
    treated as 'unknown, so no overlap' (which would let both stay
    eligible)."""
    hits = [
        _hit("solar_arc", "solar_arc:north_node", "mercury", "opposition",
             _dt(2026, 8, 18), None, exact_dates=[], orb=3.14),
        _hit("solar_arc", "solar_arc:south_node", "mercury", "conjunction",
             _dt(2026, 8, 18), None, exact_dates=[], orb=3.14),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assert sum(h.evidence_eligible for h in hits) == 1


def test_ineligible_hits_never_get_a_strength_tier():
    hits = [
        _hit("transit", "transit:saturn", "Ascendant", "square", _dt(2026, 9, 1), _dt(2026, 9, 20),
             exact_dates=[_dt(2026, 9, 10)], orb=0.0),
        _hit("transit", "transit:saturn", "Descendant", "square", _dt(2026, 9, 1), _dt(2026, 9, 20),
             exact_dates=[_dt(2026, 9, 10)], orb=0.0),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, _dt(2026, 9, 1), _dt(2026, 10, 31))
    assert hits[1].evidence_eligible is False
    assert hits[1].evidence_strength is None
