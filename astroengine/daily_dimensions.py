"""Today's Understand layer: the same evidence engine LIFE_CATEGORIES reads
for the six-month Season, cut instead into seven daily emotional/behavioral
dimensions. See PRODUCT_ARCHITECTURE.md section 5.

No new astrology gets computed here -- this is a new SIGNIFICATOR MAPPING
(which points matter for which dimension) over hits astroengine.timing_
engine already produces, following the exact same generic, chart-agnostic,
reviewable pattern as theme_definitions.py's LIFE_CATEGORIES. Two kinds of
significator feed each dimension:

  - house-derived (via theme_definitions.significators_for_houses): the
    same actual-ruler / natural-ruler / posited-planet / angle derivation
    already used for Season, applied to whichever house most directly
    concerns this dimension.
  - fixed planet significators: a planet's classical, chart-agnostic
    association with a dimension (the Moon for emotional tone, Mercury for
    decision-making, ...) that doesn't depend on chart-specific rulership
    at all -- these are real, established astrological conventions, not
    invented, but still just symbolic framing (see astroengine.theme's own
    "not causation" stance; the product layer is responsible for phrasing
    them that way to the user).

Beyond relevance/specificity (which theme.py already scores), a daily
dimension also needs a rough CHARACTER: does today's activity for this
dimension read as more contractive/tense or more expansive/flowing. That's
derived here from the hard/soft split of a dimension's top evidence --
documented, adjustable, not a claim of psychological fact.
"""

from __future__ import annotations

from dataclasses import dataclass

from astroengine.constants import HARD_ASPECTS, SOFT_ASPECTS
from astroengine.models import TimingHit
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings
from astroengine.theme import ThemeAssessment, ThemeDefinition, ThemeSignificator, assess_theme_relevance
from astroengine.theme_definitions import significators_for_houses

_SPECIFICITY_RANK = {"high": 2, "moderate": 1, "low": 0}

MAX_HITS_PER_DIMENSION = 6

# dimension key -> label, one-line editorial framing (for the LLM prompt,
# kept beside the mapping so they can't drift apart), the house(s) this
# dimension draws structural significators from, and its fixed,
# chart-agnostic planet significators: (point, role, specificity).
DAILY_DIMENSIONS: dict[str, dict] = {
    "emotional_climate": {
        "label": "Emotional climate",
        "framing": "how emotionally settled or stirred up things feel",
        "houses": [4],
        "fixed": [("moon", "the natural significator of emotional tone and mood", "high")],
    },
    "energy": {
        "label": "Energy",
        "framing": "overall vitality, drive, and physical get-up-and-go",
        "houses": [1],
        "fixed": [
            ("sun", "the natural significator of vitality and drive", "high"),
            ("mars", "the natural significator of active energy and initiative", "high"),
        ],
    },
    "social_energy": {
        "label": "Social energy",
        "framing": "appetite for connection, groups, and being seen",
        "houses": [11],
        "fixed": [
            ("mercury", "the natural significator of communication and exchange", "moderate"),
            ("venus", "the natural significator of connection and likability", "moderate"),
        ],
    },
    "creativity": {
        "label": "Creativity",
        "framing": "creative and expressive impulse",
        "houses": [5],
        "fixed": [
            ("venus", "the natural significator of creative and aesthetic expression", "moderate"),
            ("neptune", "the natural significator of imagination and inspiration", "moderate"),
        ],
    },
    "decision_making": {
        "label": "Decision-making",
        "framing": "mental clarity and ease of choosing",
        "houses": [3],
        "fixed": [("mercury", "the natural significator of thinking and choosing", "high")],
    },
    "relationships": {
        "label": "Relationships",
        "framing": "the tone of your closest one-to-one connections",
        "houses": [7],
        "fixed": [("venus", "the natural significator of closeness and affection", "high")],
    },
    "rest_vs_action": {
        "label": "Rest vs. action",
        "framing": "whether this is a stretch to push through or to recover in",
        "houses": [1, 6],
        "fixed": [
            ("saturn", "the natural significator of structure, limits, and pacing", "moderate"),
            ("mars", "the natural significator of active push and initiative", "moderate"),
        ],
    },
}


def build_dimension_significators(
    chart: NatalChart, settings: AstrologySettings, dimension_key: str,
) -> ThemeDefinition:
    if dimension_key not in DAILY_DIMENSIONS:
        raise ValueError(f"unknown dimension: {dimension_key!r}")
    spec = DAILY_DIMENSIONS[dimension_key]
    fixed = [ThemeSignificator(point, role, specificity) for point, role, specificity in spec["fixed"]]
    return significators_for_houses(chart, settings, spec["houses"], extra=fixed)


@dataclass(frozen=True)
class DimensionRead:
    key: str
    label: str
    tier: str                                        # "strong signal" | "notable" | "minor undertone" | "quiet"
    character: str | None                             # "expansive" | "contractive" | "mixed" | None
    top: list[tuple[TimingHit, ThemeAssessment]]


def _tier(top: list[tuple[TimingHit, ThemeAssessment]]) -> str:
    """Same ladder as the Season reading's why-panels (app/backend/
    reading.py's _category_tier) -- computed, not left to an LLM, so the
    badge shown to the user and any 'why' disclosure can never disagree.
    Strong-tier hits are already temporally corroborated by construction
    (see astroengine.evidence's redesigned Strong-tier rule)."""
    if not top:
        return "quiet"
    if any(hit.evidence_strength == "strong" for hit, _a in top):
        return "strong signal"
    if any(a.theme_specificity in ("high", "moderate") for _hit, a in top):
        return "notable"
    return "minor undertone"


def _character(top: list[tuple[TimingHit, ThemeAssessment]]) -> str | None:
    """Rough expansive/contractive read from the hard/soft split of this
    dimension's top evidence. A documented default, not a claim about how
    the person will actually feel -- see module docstring."""
    if not top:
        return None
    hard = sum(1 for hit, _a in top if hit.aspect_type in HARD_ASPECTS)
    soft = sum(1 for hit, _a in top if hit.aspect_type in SOFT_ASPECTS)
    if hard and not soft:
        return "contractive"
    if soft and not hard:
        return "expansive"
    return "mixed"


def compute_dimension_read(
    hits: list[TimingHit], chart: NatalChart, settings: AstrologySettings, dimension_key: str,
    max_hits: int = MAX_HITS_PER_DIMENSION,
) -> DimensionRead:
    """hits: evidence_eligible TimingHits, any strength tier -- weak-tier
    hits are filtered out here (same "only strong/moderate count as
    evidence" rule the Season reading uses)."""
    significators = build_dimension_significators(chart, settings, dimension_key)
    relevant: list[tuple[TimingHit, ThemeAssessment]] = []
    for hit in hits:
        if not hit.evidence_eligible or hit.evidence_strength not in ("strong", "moderate"):
            continue
        assessment = assess_theme_relevance(hit, significators)
        if assessment.theme_relevant:
            relevant.append((hit, assessment))

    relevant.sort(
        key=lambda pair: (
            pair[0].evidence_strength == "strong",
            bool(pair[0].temporal_corroborators),
            _SPECIFICITY_RANK.get(pair[1].theme_specificity, 0),
        ),
        reverse=True,
    )
    top = relevant[:max_hits]
    return DimensionRead(
        key=dimension_key, label=DAILY_DIMENSIONS[dimension_key]["label"],
        tier=_tier(top), character=_character(top), top=top,
    )


def compute_all_dimension_reads(
    hits: list[TimingHit], chart: NatalChart, settings: AstrologySettings,
) -> dict[str, DimensionRead]:
    return {key: compute_dimension_read(hits, chart, settings, key) for key in DAILY_DIMENSIONS}
