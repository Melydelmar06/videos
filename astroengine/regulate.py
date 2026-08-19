"""Deterministic practice-type matching for the Regulate step. See
PRODUCT_ARCHITECTURE.md section 7.

This module decides WHICH KIND of practice fits today (grounding vs.
action-oriented vs. rest vs. ...) from two inputs: the person's own
reported mood (HUMAN data, from a check-in) and today's chart character
(CHART data, from astroengine.daily_dimensions). It deliberately does NOT
write any copy -- that stays an LLM's job, same division of labor as the
Season reading's why-panels/ranking vs. its prose. Keeping the match
itself in plain, testable code means the product can never produce a
practice recommendation nobody can explain or reproduce.

HUMAN DATA ALWAYS WINS: when a reported mood and today's chart character
point in different directions, the match follows the reported mood, and
`human_chart_mismatch` is set so the copy layer can name the disagreement
out loud (per PRODUCT_ARCHITECTURE.md section 2) instead of silently
picking a side.
"""

from __future__ import annotations

from dataclasses import dataclass

from astroengine.daily_dimensions import DimensionRead

# the full practice-type taxonomy (matches PRODUCT_ARCHITECTURE.md section
# 7 plus the two explicitly called-out "don't just calm an expansive
# person down" directions: planning_action, exploration).
PRACTICE_TYPES = {
    "guided_meditation", "breathing_exercise", "grounding_exercise", "journaling_prompt",
    "visualization", "manifestation_intention", "affirmation", "movement", "rest_recovery",
    "creative_exercise", "relationship_reflection", "gratitude", "nervous_system_regulation",
    "practical_behavioral_suggestion", "planning_action", "exploration",
}

# the check-in's 9 mood options, grouped by the DIRECTION they imply for
# regulation -- not by valence alone: "Energised"/"Happy" both point toward
# supporting momentum, not calming it, which is the whole point of the
# "don't automatically calm an expansive person down" instruction.
MOOD_BUCKET = {
    "Energised": "up", "Happy": "up",
    "Calm": "neutral",
    "Flat": "low", "Exhausted": "low",
    "Anxious": "distress", "Emotional": "distress", "Irritable": "distress", "Overwhelmed": "distress",
}

PRACTICE_BY_MOOD_BUCKET = {
    "distress": ["nervous_system_regulation", "grounding_exercise", "breathing_exercise", "rest_recovery"],
    "up": ["planning_action", "creative_exercise", "exploration", "manifestation_intention"],
    "low": ["rest_recovery", "journaling_prompt", "gratitude"],
}

# coarse chart-state read used only when there's no reported mood, or the
# reported mood is neutral ("Calm") and doesn't itself imply a direction.
CHART_STATES = ("high_energy_expansion", "emotionally_intense", "need_rest", "reflective", "steady_quiet")

PRACTICE_BY_CHART_STATE = {
    "high_energy_expansion": ["planning_action", "creative_exercise", "exploration", "manifestation_intention"],
    "emotionally_intense": ["grounding_exercise", "nervous_system_regulation", "journaling_prompt"],
    "need_rest": ["rest_recovery", "gratitude", "movement"],
    "reflective": ["journaling_prompt", "visualization", "gratitude"],
    "steady_quiet": ["manifestation_intention", "gratitude", "journaling_prompt"],
}

# a reported mood bucket conflicting with these chart states is exactly
# the "chart says X, human reports Y" case PRODUCT_ARCHITECTURE.md section
# 2 requires the product to name rather than silently resolve.
_MISMATCH_PAIRS = {
    ("up", "emotionally_intense"), ("up", "need_rest"),
    ("distress", "high_energy_expansion"), ("low", "high_energy_expansion"),
}


def chart_state_summary(dimension_reads: dict[str, DimensionRead]) -> str:
    """Reduces the 7 daily dimensions to one coarse chart-state read for
    matching purposes. energy/rest_vs_action decide the action-vs-rest
    axis first (most directly relevant to Regulate); emotional_climate
    decides intensity; anything else active but not fitting either falls
    to 'reflective'; nothing active anywhere is 'steady_quiet'."""
    energy = dimension_reads.get("energy")
    rest = dimension_reads.get("rest_vs_action")
    emotional = dimension_reads.get("emotional_climate")

    active = {"strong signal", "notable"}
    if energy and energy.tier in active and energy.character == "expansive":
        return "high_energy_expansion"
    if emotional and emotional.tier in active and emotional.character == "contractive":
        return "emotionally_intense"
    if rest and rest.tier in active and rest.character == "contractive":
        return "need_rest"
    if any(read.tier in active for read in dimension_reads.values()):
        return "reflective"
    return "steady_quiet"


@dataclass(frozen=True)
class PracticeSelection:
    practice_type: str
    alternates: list[str]
    chart_state: str
    mood: str | None
    human_chart_mismatch: bool
    # which side actually drove the match, for the "why" panel -- never
    # exposed as jargon, just "matched to how you said you feel today" vs
    # "matched to today's chart" in the UI copy.
    driven_by: str  # "human_reported" | "chart_only"


def select_practice(mood: str | None, dimension_reads: dict[str, DimensionRead]) -> PracticeSelection:
    chart_state = chart_state_summary(dimension_reads)

    if mood is None:
        candidates = PRACTICE_BY_CHART_STATE[chart_state]
        return PracticeSelection(candidates[0], candidates[1:], chart_state, None, False, "chart_only")

    if mood not in MOOD_BUCKET:
        raise ValueError(f"unknown mood: {mood!r}")
    bucket = MOOD_BUCKET[mood]

    if bucket == "neutral":
        candidates = PRACTICE_BY_CHART_STATE[chart_state]
        return PracticeSelection(candidates[0], candidates[1:], chart_state, mood, False, "chart_only")

    candidates = PRACTICE_BY_MOOD_BUCKET[bucket]
    mismatch = (bucket, chart_state) in _MISMATCH_PAIRS
    return PracticeSelection(candidates[0], candidates[1:], chart_state, mood, mismatch, "human_reported")
