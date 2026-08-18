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
# Evidence-strength scoring (Strong / Moderate / Weak), per ARCHITECTURE.md,
# as redesigned after the February 2027 audit (see CHANGE REPORT).
#
# THE PROBLEM THE REDESIGN FIXES: the original compute_corroboration()
# treated "another eligible hit to the same natal point whose active window
# happens to overlap mine" as corroboration, full stop. Active windows for
# slow systems (progressions, solar arc, solar returns) can span months to
# years, so almost anything active during a slow hit's window counted as
# "corroborating" it -- including things that never came anywhere near
# actually peaking on a nearby date. That is how Saturn square natal Moon
# (exact Feb 19, 2027) got tagged Strong from 17 "corroborators," of which
# zero peaked anywhere near Feb 19: they were all just independently active
# sometime during Saturn's own multi-month orb window. That is background
# noise, not convergence.
#
# THE FIX: split "corroboration" into two explicitly different things.
#
#   BACKGROUND CORROBORATION -- another eligible, different-system hit to
#   the same natal point whose active window overlaps mine. Weak timing
#   evidence: it says a theme is "live" during an overlapping stretch of
#   time, nothing about a specific date. This is what the old function
#   computed and called "corroboration."
#
#   TEMPORAL CORROBORATION -- a background corroborator that ALSO turns
#   exact within a system-appropriate number of days of MY exact date. This
#   is the actual "independent system confirms this date" evidence, and is
#   the only kind that can push a hit to Strong.
#
# Per-system temporal proximity windows (TEMPORAL_PROXIMITY_DAYS below) are
# deliberately different per technique, because "close in time" means
# different things to a transiting Moon and a solar arc direction. These are
# defensible defaults, not measured constants -- documented here so they are
# easy to find and adjust.
# ---------------------------------------------------------------------------

ANGLE_TARGETS = {"Ascendant", "Midheaven", "Descendant", "IC"}
LUMINARY_TARGETS = {"sun", "moon"}

# "slow/outer" transiting bodies, per ARCHITECTURE.md's Strong-tier wording.
# north_node is included: transiting nodes move about as slowly as an outer
# planet and are non-repeating on any human timescale, the same "this
# doesn't happen often" property the rest of this set is protecting.
# Mercury/Venus/Mars/Sun/Moon are the "fast, routine, low-information"
# personal planets -- see FAST_TRANSIT_MOVER_BODIES below.
SLOW_OR_OUTER_TRANSIT_BODIES = {"jupiter", "saturn", "uranus", "neptune", "pluto", "north_node"}

# Fast transiting bodies are excluded from the CORROBORATOR POOL entirely
# (req #6): a transiting Moon (or Mercury/Venus/Mars/Sun) squares *something*
# in the chart every few days by construction, so its presence says almost
# nothing about whether a given date is astrologically significant. They can
# still be scored and reported as hits in their own right (and, per
# _mover_qualifies_for_strong, can still refine timing within a window
# another technique already established), they just can never be listed as
# a background or temporal corroborator FOR another hit.
FAST_TRANSIT_MOVER_BODIES = {"sun", "moon", "mercury", "venus", "mars"}
DIRECTED_SYSTEMS = {"progression", "solar_arc", "solar_return"}

EXACT_ORB_THRESHOLD_DEG = 1.0
MODERATE_ORB_THRESHOLD_DEG = 3.0

# How close (in days) another hit's OWN exact date must fall to a hit's
# exact date to count as TEMPORAL (not just background) corroboration for
# that hit. None = this system can never provide temporal corroboration,
# background only, regardless of how close in time it happens to land.
#   eclipse            14 days -- eclipses have a real "activation window"
#                       around the moment itself; wider than a lunation
#                       because eclipse effects are conventionally read as
#                       unfolding over the following days, not just the day.
#   lunation             None -- an ordinary New/Full Moon is a routine
#                       monthly event (see req #6); it can still corroborate
#                       nothing needs an eclipse to be meaningful, but a
#                       plain lunation lands near *something* most months.
#   transit (slow/outer)  21 days -- Jupiter/Saturn/outer transits move
#                       slowly enough that "close in time" has to mean weeks,
#                       not days, or almost nothing would ever qualify; still
#                       tight enough to exclude a same-window pass that
#                       peaks months apart.
#   transit (fast)        None -- excluded from the corroborator pool
#                       entirely, see FAST_TRANSIT_MOVER_BODIES.
#   progression /
#   solar_arc             45 days -- these are slow-background by nature
#                       (req #1/#4); they only earn TEMPORAL weight when
#                       they themselves become exact close to the event, not
#                       merely "in orb" for the same multi-month stretch.
#   solar_return           None -- an annual theme, not a dated event; per
#                       req #4 it never supplies temporal corroboration on
#                       its own. A separate technique turning exact nearby
#                       is what "activates" a solar-return theme for a date.
def _temporal_proximity_days(hit: TimingHit) -> float | None:
    system = hit.system
    if system == "eclipse":
        return 14.0
    if system == "lunation":
        return None
    if system == "solar_return":
        return None
    if system == "transit":
        if _mover_body_name(hit.moving_point) in FAST_TRANSIT_MOVER_BODIES:
            return None
        return 21.0
    if system in ("progression", "solar_arc"):
        return 45.0
    return None


def _in_corroborator_pool(hit: TimingHit) -> bool:
    """Can this hit ever be listed as ANY corroborator (background or
    temporal) for another hit? Excludes fast transiting personal planets and
    plain lunations -- see FAST_TRANSIT_MOVER_BODIES / req #6."""
    if hit.system == "lunation":
        return False
    if hit.system == "transit" and _mover_body_name(hit.moving_point) in FAST_TRANSIT_MOVER_BODIES:
        return False
    return True


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


def _closest_date_gap_days(dates_a: list[datetime], dates_b: list[datetime]) -> float | None:
    """Smallest absolute gap, in days, between any date in dates_a and any
    date in dates_b. None if either list is empty (nothing to compare)."""
    if not dates_a or not dates_b:
        return None
    return min(abs((a - b).total_seconds()) for a in dates_a for b in dates_b) / 86400.0


def _anchor_dates_for_window(hit: TimingHit, window_start: datetime, window_end: datetime) -> list[datetime]:
    """Which of this hit's exact_hit_dates are 'the pass being evaluated'
    for this query window. A single TimingHit can carry several exact
    dates (e.g. a retrograde station producing three passes months apart --
    Saturn square Moon in the audit case: May 2026, Sep 2026, Feb 2027, all
    on ONE hit record). Without this filter, a corroborator landing near an
    EARLIER, unrelated pass could wrongly justify temporal corroboration
    for a LATER pass being scored in a different window -- the same class
    of "not actually close to the event in question" error the whole
    background/temporal split exists to fix. Restricting to in-window dates
    keeps the comparison anchored to the specific pass this window is
    about."""
    in_window = [d for d in hit.exact_hit_dates if window_start <= d <= window_end]
    return in_window if in_window else hit.exact_hit_dates


def compute_corroboration(
    hits: list[TimingHit], window_start: datetime, window_end: datetime,
) -> tuple[list[list[int]], list[list[int]]]:
    """For each hit, two lists of OTHER hit indices:

      background[i] -- different system, same canonical natal target,
      overlapping active window, drawn only from the corroborator pool
      (_in_corroborator_pool). "Active at the same time."

      temporal[i]   -- the subset of background[i] whose own exact date(s)
      fall within that corroborator's system-appropriate proximity window
      (_temporal_proximity_days) of one of hit i's own exact date(s) THAT
      FALLS WITHIN THIS QUERY WINDOW (_anchor_dates_for_window) --
      "independently peaks near the specific date being evaluated," not
      near some other pass of the same hit outside this window. A hit with
      no exact date of its own cannot receive temporal corroboration
      (there is no date to be close to) even if it has background
      corroborators.

    Only evidence_eligible hits can corroborate or be corroborated -- a
    mirror duplicate contacting the same point at the same moment is not a
    second, independent system confirming anything.
    """
    n = len(hits)
    canonical_targets = [canonicalize_point(h.natal_target)[0] for h in hits]
    anchor_dates = [_anchor_dates_for_window(h, window_start, window_end) for h in hits]
    background: list[list[int]] = [[] for _ in range(n)]
    temporal: list[list[int]] = [[] for _ in range(n)]

    for i in range(n):
        if not hits[i].evidence_eligible:
            continue
        for j in range(n):
            if i == j or not hits[j].evidence_eligible:
                continue
            if not _in_corroborator_pool(hits[j]):
                continue
            if hits[i].system == hits[j].system:
                continue
            if canonical_targets[i] != canonical_targets[j]:
                continue
            if not _intervals_overlap(hits[i], hits[j]):
                continue
            background[i].append(j)

            proximity = _temporal_proximity_days(hits[j])
            if proximity is None:
                continue
            gap = _closest_date_gap_days(anchor_dates[i], hits[j].exact_hit_dates)
            if gap is not None and gap <= proximity:
                temporal[i].append(j)

    return background, temporal


def classify_hit_strength(
    hit: TimingHit, effective_orb: float, background_corroborated: bool, temporal_corroborated: bool,
) -> str:
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

    core_strong_shape = is_exact and is_hard and touches_angle_or_luminary and mover_ok and location_ok

    # The normal Strong path (req #3): a meaningful primary hit AND at
    # least one genuinely independent, temporally concentrated corroborator.
    # Background-only corroboration (req #2/#3) is explicitly NOT enough --
    # this is the fix for the Saturn/Moon audit finding.
    if core_strong_shape and temporal_corroborated:
        return "strong"

    # The standalone exception (req #3): a real eclipse (never a plain
    # lunation) landing exactly, hard-or-conjunct, on an angle or luminary
    # is the methodology's one explicitly-defined "important enough by
    # itself" event -- eclipses are rare, non-repeating, and conventionally
    # read as significant on their own, so they don't need another system
    # to confirm the date.
    if core_strong_shape and hit.system == "eclipse":
        return "strong"

    # "single-system exact hit" -> moderate, even without corroboration.
    if is_exact:
        return "moderate"

    # "multiple systems with wider orbs (1-3 deg)" -> moderate. Background
    # corroboration is sufficient here -- Moderate only claims "this theme
    # is independently active," not "these dates converge," so it doesn't
    # need the stricter temporal test Strong requires.
    if effective_orb <= MODERATE_ORB_THRESHOLD_DEG and background_corroborated:
        return "moderate"

    return "weak"


def assign_evidence_strength(hits: list[TimingHit], window_start: datetime, window_end: datetime) -> None:
    """Mutates hits in place, setting evidence_strength (and the
    background_corroborators / temporal_corroborators traceability lists)
    for every evidence_eligible hit (None/empty for ineligible ones)."""
    background, temporal = compute_corroboration(hits, window_start, window_end)
    for i, hit in enumerate(hits):
        if not hit.evidence_eligible:
            hit.evidence_strength = None
            hit.background_corroborators = []
            hit.temporal_corroborators = []
            continue
        hit.background_corroborators = [
            f"{hits[j].system}:{hits[j].moving_point} {hits[j].aspect_type} {hits[j].natal_target}"
            for j in background[i]
        ]
        hit.temporal_corroborators = [
            f"{hits[j].system}:{hits[j].moving_point} {hits[j].aspect_type} {hits[j].natal_target}"
            for j in temporal[i]
        ]
        effective_orb = effective_orb_for_window(hit, window_start, window_end)
        hit.evidence_strength = classify_hit_strength(
            hit, effective_orb,
            background_corroborated=bool(background[i]),
            temporal_corroborated=bool(temporal[i]),
        )


# ---------------------------------------------------------------------------
# Natal-cluster-aware independence counting (req #5, second half).
#
# compute_corroboration() above already prevents one kind of double-count:
# it only corroborates hits to the SAME canonical target. It does NOT catch
# a different pattern -- one moving planet crossing several DIFFERENT natal
# points that are themselves tightly aspected to each other (e.g. transiting
# Jupiter conjunct natal MC, then squaring natal Uranus three days later,
# because natal MC and natal Uranus are 3 deg apart). Those are two
# TimingHit rows with different natal_target, so they never corroborate each
# other under the same-target rule above -- but when a THEME REPORT counts
# "how many independent things converged in this window," treating both as
# separate confirmations double-counts one underlying transit pass.
#
# This is a report/convergence-window-level concern, not a per-hit
# evidence_strength concern (a single pass through a natal cluster is still
# perfectly good evidence for ITS OWN hits' strength; the issue is only
# inflating an independence COUNT across hits). compute_natal_clusters()
# exposes the grouping so a convergence-window count can collapse
# same-mover, same-window hits into tightly natally-linked targets into one
# unit before counting "how many independent systems/passes are here."
# Raw hits are never modified or hidden by this -- it is purely an
# aggregation-time input.
# ---------------------------------------------------------------------------

NATAL_CLUSTER_ORB_DEG = 3.0


def compute_natal_clusters(aspects: list[tuple[str, str, str, float]]) -> dict[str, str]:
    """aspects: list of (point_a, point_b, aspect_type, orb) from the natal
    chart. Returns {canonical_point_name: cluster_id} for every point that
    appears in a tight (<= NATAL_CLUSTER_ORB_DEG) conjunction or opposition
    to at least one other point -- i.e. points close enough on the same
    axis that one moving body crossing the degree area will tend to contact
    all of them within days of each other. Points not in any tight
    conjunction/opposition are simply absent from the returned mapping
    (each is its own singleton cluster, by construction).

    Only conjunction/opposition are used: those are the aspect types where
    "close in degree" directly implies "one transiting body's single pass
    contacts both around the same time." A tight square or trine between
    two natal points does NOT create that effect (the moving body reaches
    them at different, unrelated moments), so squares/trines are ignored
    here even though they're otherwise-real natal aspects.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    members: set[str] = set()
    for point_a, point_b, aspect_type, orb in aspects:
        if aspect_type not in ("conjunction", "opposition"):
            continue
        if orb > NATAL_CLUSTER_ORB_DEG:
            continue
        ca, _ = canonicalize_point(point_a)
        cb, _ = canonicalize_point(point_b)
        union(ca, cb)
        members.add(ca)
        members.add(cb)

    return {m: find(m) for m in members}


def independent_corroborator_count(hits: list[TimingHit], indices: list[int], natal_clusters: dict[str, str]) -> int:
    """Given a set of hit indices believed to converge in some window,
    counts how many genuinely INDEPENDENT things they represent for
    convergence purposes: hits collapse into one unit if they share both a
    system+mover AND their natal targets fall in the same natal cluster
    (per compute_natal_clusters) -- one transit pass through a tight natal
    degree area, counted once, however many cluster members it happens to
    touch on the way through."""
    units: set[tuple[str, str]] = set()
    for i in indices:
        hit = hits[i]
        target = canonicalize_point(hit.natal_target)[0]
        cluster_id = natal_clusters.get(target, target)
        units.add((f"{hit.system}:{_mover_body_name(hit.moving_point)}", cluster_id))
    return len(units)
