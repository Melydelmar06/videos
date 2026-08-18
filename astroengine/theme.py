"""Theme relevance / natal role / theme specificity scoring (req #7/#8 of
the corroboration-system redesign).

Deliberately kept separate from evidence_strength (astroengine.evidence):
evidence_strength answers "how good is this hit's timing evidence,"
independent of what life theme (if any) it is being read for.
theme_relevance / natal_role / theme_specificity answer a different
question: "is this hit about the theme I'm asking about, and how
specifically?" A hit can be strong, well-corroborated evidence for a
well-timed event that has nothing to do with the theme in question, and
conversely a low-specificity hit can still be the best evidence a theme
has to offer for a given window. Conflating the two axes is exactly how
"Saturn square Moon" got read as immigration-heavy in the February 2027
audit: Moon genuinely IS relevant to the immigration theme (it rules the
9th house), but that relevance says nothing about how SPECIFICALLY the
hit points at immigration rather than at whatever else the Moon signifies.

This module holds no personal chart data. Callers (the analysis scripts
that actually build a theme for a specific person's chart) supply a
ThemeDefinition: a list of natal points relevant to a life theme, each
tagged with WHY (natal_role) and HOW SPECIFICALLY (specificity).
Deciding specificity is a judgment call about a real chart and is meant to
be made explicitly and documented per significator, not derived
automatically -- a house ruler that also happens to be a major luminary
with a large, unrelated symbolic footprint (the worked example: the Moon
ruling a 9th house) can legitimately be tagged "low" specificity for that
theme even though the rulership tie itself is real and chart-specific,
because a hit to it, taken alone, doesn't distinguish "this is about the
theme" from "this is about whatever else that point dominantly signifies."
"""

from __future__ import annotations

from dataclasses import dataclass

from astroengine.evidence import canonicalize_point
from astroengine.models import TimingHit


@dataclass(frozen=True)
class ThemeSignificator:
    """One reason a natal point is relevant to a life theme.

    point: natal point name (planet, angle, or node), as it appears in
        TimingHit.natal_target.
    role: human-readable description of WHY this point is tied to the
        theme, e.g. "actual chart ruler of the 9th house cusp", "posited
        in the 9th house", "natural/generic significator of travel and
        foreign countries".
    specificity: "high" | "moderate" | "low" -- how specifically a hit to
        this point, BY ITSELF, points at this particular theme rather than
        at whatever else the point also legitimately signifies:
          high     -- the point's dominant meaning IS this theme, with
                      little competing symbolic weight (e.g. a minor/
                      angular significator whose main job in this chart is
                      this house/theme, not several other major domains).
          moderate -- a real, chart-specific tie (rulership or placement),
                      but the point also carries a real secondary domain
                      of its own that a hit to it could just as plausibly
                      be about.
          low      -- either the tie is only through secondary/natural
                      rulership or broad symbolism (not chart-specific), OR
                      the point is a major significator (a luminary, an
                      angle) whose dominant, well-established meanings lie
                      mostly OUTSIDE this theme -- a hit to it, alone,
                      cannot be read as specifically about this theme even
                      though the underlying chart-specific tie is real.
    """
    point: str
    role: str
    specificity: str  # "high" | "moderate" | "low"


ThemeDefinition = list[ThemeSignificator]

_SPECIFICITY_RANK = {"low": 0, "moderate": 1, "high": 2}


@dataclass(frozen=True)
class ThemeAssessment:
    theme_relevant: bool
    natal_role: str | None            # the matched significator's role, if any
    theme_specificity: str | None     # this hit's own tag: "high"|"moderate"|"low"|None


def assess_theme_relevance(hit: TimingHit, theme: ThemeDefinition) -> ThemeAssessment:
    """theme_relevance and natal_role for a single hit, from its natal
    target alone. A hit is relevant to a theme if the point it contacts is
    one of the theme's defined significators. This says nothing yet about
    how specifically the WINDOW it belongs to points at the theme -- see
    theme_specificity_for_window for that (req #8's actual scoring rule).
    """
    target = canonicalize_point(hit.natal_target)[0]
    matches = [s for s in theme if canonicalize_point(s.point)[0] == target]
    if not matches:
        return ThemeAssessment(theme_relevant=False, natal_role=None, theme_specificity=None)
    best = max(matches, key=lambda s: _SPECIFICITY_RANK[s.specificity])
    return ThemeAssessment(theme_relevant=True, natal_role=best.role, theme_specificity=best.specificity)


def theme_specificity_for_window(hits: list[TimingHit], theme: ThemeDefinition) -> str:
    """theme_specificity for a CONVERGENCE WINDOW -- a group of hits
    believed to cluster around the same period -- per req #8's definitions:

      "high"     -- at least two DISTINCT significator points in the
                    window are independently relevant to the theme, and at
                    least two of those ties are themselves moderate-or-
                    better specificity (multiple independent indicators
                    specifically activate the same life area).
      "moderate" -- exactly one relevant significator point is activated
                    in the window, and its own tie is moderate-or-better
                    (a relevant significator is activated but has several
                    plausible natal meanings of its own).
      "low"      -- every relevant point in the window ties to the theme
                    only through a "low"-specificity significator
                    (secondary rulership, broad natural symbolism, or a
                    major point whose dominant meaning lies elsewhere --
                    the Saturn-square-Moon/immigration worked example).
      ""         -- no hit in the window is theme_relevant at all; callers
                    should treat this as "not applicable to this theme,"
                    not as "low."
    """
    relevant = [(h, assess_theme_relevance(h, theme)) for h in hits]
    relevant = [(h, a) for h, a in relevant if a.theme_relevant]
    if not relevant:
        return ""

    non_low_points = {
        canonicalize_point(h.natal_target)[0] for h, a in relevant if a.theme_specificity != "low"
    }
    if len(non_low_points) >= 2:
        return "high"
    if len(non_low_points) == 1:
        return "moderate"
    return "low"
