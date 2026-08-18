from datetime import datetime, timezone

from astroengine.evidence import (
    annotate_timing_hit_evidence_eligibility, assign_evidence_strength, classify_hit_strength,
    compute_natal_clusters, independent_corroborator_count,
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
    # Moon doesn't qualify as "slow/outer" -- even exact + hard + angle, it
    # can't reach Strong per ARCHITECTURE.md's mover gate. It also can never
    # act as a corroborator FOR another hit (req #6: fast transiting movers
    # are excluded from the corroborator pool entirely, background or
    # temporal) -- so a real corroborator (transiting Saturn, slow/outer,
    # exact one day later) is what pushes hits[1] to strong, not the Moon.
    window_start, window_end = _dt(2026, 9, 1), _dt(2026, 10, 31)
    hits = [
        _hit("transit", "transit:moon", "Ascendant", "conjunction", _dt(2026, 9, 3), _dt(2026, 9, 4),
             exact_dates=[_dt(2026, 9, 3, 12)], orb=0.0),
        _hit("solar_arc", "solar_arc:sun", "Ascendant", "conjunction", _dt(2026, 9, 1), _dt(2026, 9, 30),
             exact_dates=[_dt(2026, 9, 14)], orb=0.0),
        _hit("transit", "transit:saturn", "Ascendant", "square", _dt(2026, 9, 1), _dt(2026, 9, 30),
             exact_dates=[_dt(2026, 9, 15)], orb=0.0),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, window_start, window_end)
    assert hits[0].evidence_strength == "moderate"
    assert hits[1].evidence_strength == "strong"
    # the Moon must not appear as any kind of corroborator for hits[1]
    assert not any("moon" in c for c in hits[1].background_corroborators)
    assert not any("moon" in c for c in hits[1].temporal_corroborators)
    assert any("saturn" in c for c in hits[1].temporal_corroborators)


def test_fast_transit_mover_alone_cannot_create_a_strong_window():
    """Regression for the audit finding itself: two hits whose active
    windows merely overlap (both spanning the same months) but whose exact
    dates land far apart must NOT corroborate each other into Strong --
    only background. This is the exact shape of the Saturn/Moon Feb 2027
    bug: a slow hit's wide orb window overlaps a bunch of other systems'
    wide orb windows, none of which peak anywhere near its exact date."""
    window_start, window_end = _dt(2027, 1, 1), _dt(2027, 3, 31)
    hits = [
        _hit("transit", "transit:saturn", "moon", "square", _dt(2026, 12, 1), _dt(2027, 4, 30),
             exact_dates=[_dt(2027, 2, 19)], orb=0.0),
        # active the whole quarter, but its OWN exact date is nowhere near
        # Feb 19 -- this must be background only, not temporal.
        _hit("progression", "progressed:venus", "moon", "trine", _dt(2026, 10, 1), _dt(2027, 6, 1),
             exact_dates=[_dt(2027, 5, 30)], orb=0.0),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, window_start, window_end)
    assert hits[0].evidence_strength != "strong"
    assert hits[0].background_corroborators  # still active-at-the-same-time
    assert not hits[0].temporal_corroborators  # but never peaks nearby


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


def test_temporal_corroboration_is_anchored_to_the_pass_in_this_window_not_an_earlier_one():
    """Regression: a hit with multiple exact_hit_dates (e.g. a retrograde
    station producing three separate passes months apart, all on ONE
    TimingHit -- exactly the shape of the real Saturn-square-Moon hit) must
    only accept temporal corroboration near the pass that actually falls
    inside the window being scored, not near an earlier, unrelated pass."""
    window_start, window_end = _dt(2027, 1, 1), _dt(2027, 3, 31)
    hits = [
        # three passes: May 2026, Sep 2026, Feb 2027 -- only Feb 2027 is
        # the one being evaluated in this window.
        _hit("transit", "transit:saturn", "moon", "square", _dt(2026, 5, 1), _dt(2027, 3, 1),
             exact_dates=[_dt(2026, 5, 29), _dt(2026, 9, 24), _dt(2027, 2, 19)], orb=0.0),
        # this progression turns exact Oct 15, 2026 -- only 21 days from
        # the SEPTEMBER pass, but ~127 days from the FEBRUARY pass being
        # scored here. Must NOT count as temporal for this window.
        _hit("progression", "progressed:venus", "moon", "sextile", _dt(2026, 6, 1), _dt(2027, 6, 1),
             exact_dates=[_dt(2026, 10, 15)], orb=0.0),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, window_start, window_end)
    assert hits[0].evidence_strength != "strong"
    assert hits[0].background_corroborators
    assert not hits[0].temporal_corroborators


def test_narrow_window_with_no_in_window_exact_date_anchors_to_nearest_pass():
    """Regression: a narrow query window that contains none of a multi-pass
    hit's exact dates (but starts/ends close enough to one of them that
    orb_at_reference is still < 1 deg, e.g. a window opening a week after a
    retrograde station's exact hit) must anchor temporal comparisons to the
    NEAREST pass to window_start, not fall back to comparing against every
    pass -- including a distant, unrelated one -- which could accept a
    coincidentally-close corroborator that has nothing to do with the
    period actually being queried."""
    window_start, window_end = _dt(2026, 10, 1), _dt(2026, 10, 31)
    hits = [
        # exact Sep 24, 2026 (7 days before window) and Feb 19, 2027 (far
        # future) -- window contains neither, but orb at Oct 1 is tight.
        _hit("transit", "transit:saturn", "moon", "square", _dt(2026, 3, 1), _dt(2027, 4, 1),
             exact_dates=[_dt(2026, 9, 24), _dt(2027, 2, 19)], orb=0.45),
        # 21 days from the Sep 24 pass -- legitimately close to the pass
        # nearest this window, so this SHOULD count as temporal.
        _hit("progression", "progressed:venus", "moon", "sextile", _dt(2026, 6, 1), _dt(2027, 6, 1),
             exact_dates=[_dt(2026, 10, 15)], orb=0.0),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, window_start, window_end)
    assert hits[0].evidence_strength == "strong"
    assert hits[0].temporal_corroborators


def test_solar_return_never_supplies_temporal_corroboration():
    """req #4: Solar Return is a background annual theme only. Even when a
    solar-return hit's own window overlaps another hit's exact date very
    closely, it must show up as background, never temporal, for that
    other hit."""
    window_start, window_end = _dt(2026, 9, 1), _dt(2026, 10, 31)
    hits = [
        _hit("transit", "transit:jupiter", "sun", "conjunction", _dt(2026, 9, 1), _dt(2026, 9, 30),
             exact_dates=[_dt(2026, 9, 15)], orb=0.0),
        _hit("solar_return", "solar_return:venus", "sun", "trine",
             _dt(2025, 11, 5), _dt(2026, 11, 6), exact_dates=[_dt(2026, 9, 15)], orb=0.0),
    ]
    annotate_timing_hit_evidence_eligibility(hits)
    assign_evidence_strength(hits, window_start, window_end)
    assert hits[0].background_corroborators
    assert not hits[0].temporal_corroborators
    assert hits[0].evidence_strength != "strong"


def test_solar_arc_becomes_temporal_only_when_exact_close_to_the_event():
    """req #1/#4: a solar arc/progression hit is background by default; it
    only earns TEMPORAL weight if it turns exact within the documented
    proximity window (45 days) of the primary hit's own exact date."""
    window_start, window_end = _dt(2026, 9, 1), _dt(2027, 3, 31)

    close_hits = [
        _hit("transit", "transit:saturn", "sun", "square", _dt(2026, 9, 1), _dt(2026, 9, 30),
             exact_dates=[_dt(2026, 9, 15)], orb=0.0),
        _hit("solar_arc", "solar_arc:mars", "sun", "square", _dt(2026, 6, 1), _dt(2026, 12, 1),
             exact_dates=[_dt(2026, 9, 20)], orb=0.0),  # 5 days away
    ]
    annotate_timing_hit_evidence_eligibility(close_hits)
    assign_evidence_strength(close_hits, window_start, window_end)
    assert close_hits[0].evidence_strength == "strong"
    assert close_hits[0].temporal_corroborators

    far_hits = [
        _hit("transit", "transit:saturn", "sun", "square", _dt(2026, 9, 1), _dt(2026, 9, 30),
             exact_dates=[_dt(2026, 9, 15)], orb=0.0),
        _hit("solar_arc", "solar_arc:mars", "sun", "square", _dt(2026, 6, 1), _dt(2027, 3, 1),
             exact_dates=[_dt(2027, 2, 1)], orb=0.0),  # ~140 days away
    ]
    annotate_timing_hit_evidence_eligibility(far_hits)
    assign_evidence_strength(far_hits, window_start, window_end)
    assert far_hits[0].evidence_strength != "strong"
    assert far_hits[0].background_corroborators
    assert not far_hits[0].temporal_corroborators


def test_eclipse_can_be_strong_standalone_without_corroboration():
    """req #3's explicit exception: a real eclipse, exact, hard-or-conjunct
    on an angle/luminary, is 'exceptionally important enough by itself' and
    does not need another system to confirm the date."""
    window_start, window_end = _dt(2026, 8, 1), _dt(2026, 8, 31)
    hit = _hit("eclipse", "eclipse:solar_total:2026-08-12", "moon", "conjunction",
               _dt(2026, 8, 9), _dt(2026, 8, 15), exact_dates=[_dt(2026, 8, 12)], orb=0.0)
    assign_evidence_strength([hit], window_start, window_end)
    assert hit.evidence_strength == "strong"
    assert not hit.background_corroborators
    assert not hit.temporal_corroborators


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


def test_natal_clusters_group_tight_conjunctions_and_oppositions():
    # Midheaven and Uranus 3 deg apart natally -- one transit through that
    # degree area will tend to contact both within days of each other.
    aspects = [
        ("Midheaven", "uranus", "conjunction", 3.0),
        ("sun", "mars", "square", 1.0),  # square never clusters, even tight
        ("jupiter", "venus", "conjunction", 8.0),  # too wide to cluster
    ]
    clusters = compute_natal_clusters(aspects)
    assert clusters["Midheaven"] == clusters["uranus"]
    assert "sun" not in clusters and "mars" not in clusters
    assert "jupiter" not in clusters and "venus" not in clusters


def test_independent_corroborator_count_collapses_one_pass_through_a_cluster():
    aspects = [("Midheaven", "uranus", "conjunction", 3.0)]
    clusters = compute_natal_clusters(aspects)
    hits = [
        _hit("transit", "transit:jupiter", "Midheaven", "conjunction", _dt(2026, 9, 1), _dt(2026, 9, 10),
             exact_dates=[_dt(2026, 9, 5)]),
        _hit("transit", "transit:jupiter", "uranus", "square", _dt(2026, 9, 8), _dt(2026, 9, 18),
             exact_dates=[_dt(2026, 9, 13)]),
        _hit("solar_arc", "solar_arc:venus", "Midheaven", "trine", _dt(2026, 9, 1), _dt(2026, 9, 30),
             exact_dates=[_dt(2026, 9, 10)]),
    ]
    # naive count would say 3 independent hits; the Jupiter pair is really
    # one underlying transit pass through a tight natal cluster.
    assert independent_corroborator_count(hits, [0, 1, 2], clusters) == 2
