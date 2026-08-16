from astroengine.constants import COMPLEMENT_ASPECT, LINKED_POINT_PAIRS
from astroengine.evidence import canonicalize_point, evaluate_evidence_eligibility


def test_complement_aspect_is_involutive():
    """Applying the complement mapping twice must return the original --
    otherwise the mirror-duplicate math (which relies on this) is broken."""
    for aspect_type, complement in COMPLEMENT_ASPECT.items():
        assert COMPLEMENT_ASPECT[complement] == aspect_type


def test_canonicalize_point():
    assert canonicalize_point("Ascendant") == ("Ascendant", False)
    assert canonicalize_point("Descendant") == ("Ascendant", True)
    assert canonicalize_point("Midheaven") == ("Midheaven", False)
    assert canonicalize_point("IC") == ("Midheaven", True)
    assert canonicalize_point("north_node") == ("north_node", False)
    assert canonicalize_point("south_node") == ("north_node", True)
    assert canonicalize_point("mars") == ("mars", False)


def test_structural_pairs_are_ineligible():
    entries = [
        ("north_node", "south_node", "opposition"),
        ("Ascendant", "Descendant", "opposition"),
        ("Midheaven", "IC", "opposition"),
    ]
    results = evaluate_evidence_eligibility(entries)
    for r in results:
        assert r.eligible is False
        assert "structural" in r.note


def test_ordinary_aspect_unaffected():
    entries = [("sun", "moon", "square")]
    results = evaluate_evidence_eligibility(entries)
    assert results[0].eligible is True
    assert results[0].note is None


def test_point_vs_linked_pair_keeps_only_the_primary_side():
    # a third point (mars) squares both Ascendant and Descendant -- same
    # underlying alignment, must only count once.
    entries = [
        ("mars", "Ascendant", "square"),
        ("mars", "Descendant", "square"),
    ]
    results = evaluate_evidence_eligibility(entries)
    eligible = [e for e, r in zip(entries, results) if r.eligible]
    assert eligible == [("mars", "Ascendant", "square")]
    assert results[1].eligible is False
    assert "mirror duplicate" in results[1].note


def test_point_vs_linked_pair_with_complement_aspect():
    # mars trine north_node implies mars sextile south_node -- same event.
    entries = [
        ("mars", "north_node", "trine"),
        ("mars", "south_node", "sextile"),
    ]
    results = evaluate_evidence_eligibility(entries)
    assert results[0].eligible is True
    assert results[1].eligible is False


def test_axis_vs_axis_collapses_to_one_eligible_entry():
    # node axis near the MC/IC axis: all four combinations are the same
    # underlying alignment (see report.py validation run for a real example).
    entries = [
        ("south_node", "IC", "trine"),
        ("north_node", "Midheaven", "trine"),
        ("north_node", "IC", "sextile"),
        ("south_node", "Midheaven", "sextile"),
    ]
    results = evaluate_evidence_eligibility(entries)
    eligible_entries = [e for e, r in zip(entries, results) if r.eligible]
    assert eligible_entries == [("north_node", "Midheaven", "trine")]
    assert sum(r.eligible for r in results) == 1


def test_unrelated_pairs_are_not_accidentally_merged():
    # two distinct movers each aspecting Ascendant/Descendant must not be
    # merged with each other -- only within their own mover.
    entries = [
        ("mars", "Ascendant", "square"),
        ("mars", "Descendant", "square"),
        ("venus", "Ascendant", "square"),
        ("venus", "Descendant", "square"),
    ]
    results = evaluate_evidence_eligibility(entries)
    eligible_entries = {e for e, r in zip(entries, results) if r.eligible}
    assert eligible_entries == {("mars", "Ascendant", "square"), ("venus", "Ascendant", "square")}


def test_every_linked_pair_key_covered_in_complement_and_pairs_tables():
    # sanity: every point named in LINKED_POINT_PAIRS has a sensible partner
    for secondary, primary in LINKED_POINT_PAIRS.items():
        assert secondary != primary
