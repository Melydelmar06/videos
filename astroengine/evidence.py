"""Evidence eligibility: keeps calculation (every aspect/hit that exists)
separate from evidence (which of those facts are allowed to count toward
corroboration, strength scoring, and convergence).

Two things get filtered out here, per the reasoning that structural
relationships that hold by definition carry zero information:

1. "Structural" aspects: the two ends of a definitionally-linked pair
   aspecting EACH OTHER (north_node opposite south_node, Ascendant opposite
   Descendant, MC opposite IC). These are always exactly 0 orb and always
   true, in every chart, regardless of birth data -- they say nothing about
   this particular person.

2. "Mirror duplicates": a third point (a planet, or a moving point in the
   timing engine) aspecting BOTH ends of a linked pair is not two facts, it's
   one fact expressed twice -- hitting Ascendant necessarily means hitting
   Descendant with the complementary aspect at the identical orb, since
   Descendant IS Ascendant+180 by definition. This generalizes to axis-vs-
   axis alignments (e.g. the node axis near the MC/IC axis), which can
   otherwise show up as four near-identical aspect rows for one underlying
   alignment.

Both raw aspects/hits stay in the data (nothing is deleted) -- they're only
flagged ineligible for the evidence-facing layers (theme corroboration,
evidence-strength scoring, predictive convergence counts).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from astroengine.constants import COMPLEMENT_ASPECT, HARD_ASPECTS, LINKED_POINT_PAIRS
from astroengine.models import TimingHit


@dataclass(frozen=True)
class EvidenceEligibility:
    eligible: bool
    note: str | None = None


def canonicalize_point(name: str) -> tuple[str, bool]:
    """(canonical_name, was_mirrored). was_mirrored is True if `name` is the
    non-primary end of a linked pair (Descendant, IC, south_node).

    Prefix-aware: a timing-engine mover name like "solar_arc:Descendant" is
    canonicalized by its body (the part after the colon), preserving the
    prefix -- solar arc directs angles and nodes too, so the MOVER side can
    itself be a linked-pair member (directed Ascendant and directed
    Descendant are always exactly 180 deg apart, same as the natal points
    they're built from), not just the natal-target side.
    """
    if ":" in name:
        prefix, body = name.split(":", 1)
        canonical_body, mirrored = _canonicalize_bare_point(body)
        return f"{prefix}:{canonical_body}", mirrored
    return _canonicalize_bare_point(name)


def _canonicalize_bare_point(name: str) -> tuple[str, bool]:
    if name in LINKED_POINT_PAIRS:
        return LINKED_POINT_PAIRS[name], True
    return name, False


def _mirror_flip_count(point_a: str, point_b: str) -> int:
    _, mirrored_a = canonicalize_point(point_a)
    _, mirrored_b = canonicalize_point(point_b)
    return int(mirrored_a) + int(mirrored_b)


def canonical_key(point_a: str, point_b: str, aspect_type: str) -> tuple[frozenset, str]:
    """Two aspect records that describe the same underlying alignment always
    share this key, regardless of which end of any linked pair(s) they were
    expressed through."""
    ca, mirrored_a = canonicalize_point(point_a)
    cb, mirrored_b = canonicalize_point(point_b)
    flips = int(mirrored_a) + int(mirrored_b)
    canonical_type = aspect_type if flips % 2 == 0 else COMPLEMENT_ASPECT[aspect_type]
    return frozenset((ca, cb)), canonical_type


def evaluate_evidence_eligibility(entries: list[tuple[str, str, str]]) -> list[EvidenceEligibility]:
    """entries: list of (point_a, point_b, aspect_type), in any order.
    Returns one EvidenceEligibility per entry, same order/length as input.
    """
    n = len(entries)
    results: list[EvidenceEligibility | None] = [None] * n

    # pass 1: structural (both ends of one linked pair, aspecting each other)
    for i, (a, b, _aspect_type) in enumerate(entries):
        ca, mirrored_a = canonicalize_point(a)
        cb, mirrored_b = canonicalize_point(b)
        if ca == cb and mirrored_a != mirrored_b:
            results[i] = EvidenceEligibility(
                False,
                f"structural: {a} and {b} are always exactly opposite by definition, "
                f"not evidence about this specific chart",
            )

    # pass 2: mirror duplicates -- group everything left by canonical key,
    # keep the least-mirrored (most "primary") entry as eligible.
    groups: dict[tuple, list[int]] = {}
    for i, (a, b, aspect_type) in enumerate(entries):
        if results[i] is not None:
            continue
        groups.setdefault(canonical_key(a, b, aspect_type), []).append(i)

    for idxs in groups.values():
        if len(idxs) == 1:
            results[idxs[0]] = EvidenceEligibility(True)
            continue
        best = min(idxs, key=lambda i: (_mirror_flip_count(entries[i][0], entries[i][1]), i))
        ba, bb, b_type = entries[best]
        for i in idxs:
            if i == best:
                results[i] = EvidenceEligibility(True)
            else:
                results[i] = EvidenceEligibility(
                    False,
                    f"mirror duplicate of '{ba} {b_type} {bb}' -- same underlying alignment, "
                    f"reached through a structurally-linked point",
                )

    return results


_DISTANT_PAST = datetime(1, 1, 1, tzinfo=timezone.utc)
_DISTANT_FUTURE = datetime(9999, 12, 31, tzinfo=timezone.utc)


def _interval_bounds(hit: TimingHit) -> tuple[datetime, datetime]:
    """A missing entry/exit means the window was already open at the start
    of the scan, or is still open at its end -- an unknown OPEN boundary,
    not an unknown-therefore-nonexistent one. Treating it as a sentinel far
    past/future (rather than bailing out to "no overlap") matters for very
    slow movers (e.g. a solar-arc-directed node): both ends of a linked
    pair can share an entry date with no exit or exact date yet observed,
    and that must still register as the same, fully-overlapping window."""
    start = hit.entry_into_orb or (hit.exact_hit_dates[0] if hit.exact_hit_dates else _DISTANT_PAST)
    end = hit.exit_from_orb or (hit.exact_hit_dates[-1] if hit.exact_hit_dates else _DISTANT_FUTURE)
    return start, end


def _intervals_overlap(a: TimingHit, b: TimingHit) -> bool:
    a_start, a_end = _interval_bounds(a)
    b_start, b_end = _interval_bounds(b)
    return a_start <= b_end and b_start <= a_end


def _cluster_by_mover_and_overlap(hits: list[TimingHit]) -> list[list[int]]:
    """Groups hit indices that share a system, a CANONICAL moving_point, a
    CANONICAL natal target, and an overlapping active window -- i.e. hits
    that could plausibly be mirror-images of the same underlying pass.

    Both sides are canonicalized (not just the natal target) because solar
    arc directs angles and nodes too: "solar_arc:Ascendant" and
    "solar_arc:Descendant" are different moving_point strings but always
    exactly 180 deg apart, same as any other linked pair, so an exact-string
    match on moving_point alone would silently miss that mirror.

    The canonical-target condition (independent of the mover match) matters
    for a different reason: without it, a fast mover like transiting Moon
    squaring several DIFFERENT nearby natal points in succession (e.g. a
    cluster of planets a few degrees apart) can produce a chain of
    pairwise-overlapping windows across unrelated targets, which would
    transitively union-find its way into merging temporally-separate passes
    at the SAME target months apart -- exactly the "unrelated later time"
    case this function must keep separate. Restricting edges to pairs that
    share both a canonical mover and a canonical target means only genuine
    potential mirrors can ever be unioned.
    """
    n = len(hits)
    parent = list(range(n))
    canonical_movers = [canonicalize_point(h.moving_point)[0] for h in hits]
    canonical_targets = [canonicalize_point(h.natal_target)[0] for h in hits]

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if hits[i].system != hits[j].system:
                continue
            if canonical_movers[i] != canonical_movers[j]:
                continue
            if canonical_targets[i] != canonical_targets[j]:
                continue
            if _intervals_overlap(hits[i], hits[j]):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def annotate_timing_hit_evidence_eligibility(hits: list[TimingHit]) -> None:
    """Flags mirror-duplicate timing hits: the SAME mover, in the SAME
    overlapping window, contacting both ends of a natal linked pair (e.g.
    transiting Saturn squaring both natal Ascendant and natal Descendant at
    once -- one event, not two). Movers are never themselves linked-pair
    members in this engine (there is no transiting-angle tracking in V1), so
    unlike the natal-aspect case there is no "structural self-opposition" to
    flag here, only mirrors.

    Hits a caller has already marked evidence_eligible=False (e.g. a solar
    return system flagging its own "return Sun conjunct natal Sun" as a
    structural tautology before calling this) are left untouched and
    excluded from clustering -- this function only ever narrows eligibility
    further, never restores it. Mutates hits in place.
    """
    already_ineligible = {i for i, h in enumerate(hits) if not h.evidence_eligible}
    eligible_hits = [h for i, h in enumerate(hits) if i not in already_ineligible]

    for cluster in _cluster_by_mover_and_overlap(eligible_hits):
        entries = [(eligible_hits[i].moving_point, eligible_hits[i].natal_target, eligible_hits[i].aspect_type) for i in cluster]
        for idx, eligibility in zip(cluster, evaluate_evidence_eligibility(entries)):
            eligible_hits[idx].evidence_eligible = eligibility.eligible
            eligible_hits[idx].evidence_note = eligibility.note


# ---------------------------------------------------------------------------
# Evidence-strength scoring (Strong / Moderate / Weak), per ARCHITECTURE.md.
# This only runs on evidence_eligible hits -- structural/mirror-duplicate
# hits never get a strength tier (they aren't evidence at all).
# ---------------------------------------------------------------------------

ANGLE_TARGETS = {"Ascendant", "Midheaven", "Descendant", "IC"}
LUMINARY_TARGETS = {"sun", "moon"}

# "slow/outer" transiting bodies, per ARCHITECTURE.md's Strong-tier wording.
# Mercury/Venus/Mars are deliberately excluded (Mercury/Moon are the doc's
# own worked "fast" example; Mars is grouped with the personal/fast planets
# here rather than the social/outer ones -- a judgment call, documented so
# it's easy to revisit).
SLOW_OR_OUTER_TRANSIT_BODIES = {"jupiter", "saturn", "uranus", "neptune", "pluto"}
FAST_TRANSIT_BODIES = {"moon", "mercury"}
DIRECTED_SYSTEMS = {"progression", "solar_arc", "solar_return"}

EXACT_ORB_THRESHOLD_DEG = 1.0
MODERATE_ORB_THRESHOLD_DEG = 3.0


def _mover_body_name(moving_point: str) -> str:
    return moving_point.split(":")[-1].lower()


def _mover_qualifies_for_strong(system: str, moving_point: str) -> bool:
    """The Strong tier requires the mover to be 'slow/outer, or a directed/
    progressed point'. Directed/progressed systems always qualify (they are
    slow in real-time by construction). Actual eclipses (system == "eclipse",
    never plain New/Full Moon "lunation" hits -- see timing_eclipses.py) are
    treated as qualifying too -- they're rare, non-repeating alignments,
    which is the same "this doesn't happen often, so pay attention" property
    the slow-outer-planet rule is protecting; also a judgment call,
    documented here rather than left implicit. Ordinary monthly lunations
    get no such boost -- they aspect the chart every month regardless of
    whether that month is astrologically significant, so their mover alone
    can never justify Strong.
    """
    if system in DIRECTED_SYSTEMS or system == "eclipse":
        return True
    if system == "transit":
        return _mover_body_name(moving_point) in SLOW_OR_OUTER_TRANSIT_BODIES
    return False


def effective_orb_for_window(hit: TimingHit, window_start: datetime, window_end: datetime) -> float:
    """How exact this hit is FOR THIS QUERY WINDOW specifically: 0 if it
    turns exact at some point inside the window, otherwise its orb as of the
    window's reference moment (orb_at_reference, evaluated at window_start
    by convention -- see TimingHit)."""
    if any(window_start <= d <= window_end for d in hit.exact_hit_dates):
        return 0.0
    return hit.orb_at_reference


def compute_corroboration(hits: list[TimingHit]) -> list[list[int]]:
    """For each hit, the indices of OTHER hits that corroborate it: a
    different system, contacting the same natal point (canonicalized, so a
    hit to Descendant corroborates one to Ascendant), with an overlapping
    active window. Only evidence_eligible hits can corroborate or be
    corroborated -- a mirror duplicate contacting the same point at the same
    moment is not a second, independent system confirming anything.
    """
    n = len(hits)
    canonical_targets = [canonicalize_point(h.natal_target)[0] for h in hits]
    corroborators: list[list[int]] = [[] for _ in range(n)]

    for i in range(n):
        if not hits[i].evidence_eligible:
            continue
        for j in range(n):
            if i == j or not hits[j].evidence_eligible:
                continue
            if hits[i].system == hits[j].system:
                continue
            if canonical_targets[i] != canonical_targets[j]:
                continue
            if _intervals_overlap(hits[i], hits[j]):
                corroborators[i].append(j)

    return corroborators


def classify_hit_strength(hit: TimingHit, effective_orb: float, corroborated: bool) -> str:
    is_hard = hit.aspect_type in HARD_ASPECTS
    touches_angle_or_luminary = (
        hit.natal_target in ANGLE_TARGETS or hit.natal_target.lower() in LUMINARY_TARGETS
    )
    is_exact = effective_orb < EXACT_ORB_THRESHOLD_DEG
    mover_ok = _mover_qualifies_for_strong(hit.system, hit.moving_point)

    # a hit whose confidence is location-dependent and location wasn't
    # actually known (e.g. a solar-return house/angle computed against a
    # birth-location fallback because no return location was supplied) can
    # never be Strong -- the underlying geometry itself is uncertain, no
    # amount of corroboration or exactness should be read as confident.
    location_ok = hit.confidence.basis != "unknown_location"

    if is_exact and is_hard and touches_angle_or_luminary and mover_ok and corroborated and location_ok:
        return "strong"

    # "single-system exact hit" -> moderate, even without corroboration.
    if is_exact:
        return "moderate"

    # "multiple systems with wider orbs (1-3 deg)" -> moderate; without
    # corroboration a 1-3 deg orb is not, on its own, in any doc-defined
    # tier, so it falls to weak (see ARCHITECTURE.md discussion).
    if effective_orb <= MODERATE_ORB_THRESHOLD_DEG and corroborated:
        return "moderate"

    return "weak"


def assign_evidence_strength(hits: list[TimingHit], window_start: datetime, window_end: datetime) -> None:
    """Mutates hits in place, setting evidence_strength for every
    evidence_eligible hit (None for ineligible ones)."""
    corroborators = compute_corroboration(hits)
    for i, hit in enumerate(hits):
        if not hit.evidence_eligible:
            hit.evidence_strength = None
            continue
        effective_orb = effective_orb_for_window(hit, window_start, window_end)
        hit.evidence_strength = classify_hit_strength(hit, effective_orb, corroborated=bool(corroborators[i]))
