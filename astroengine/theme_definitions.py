"""Generic, chart-agnostic life-category significator builder.

astroengine.theme (ThemeSignificator / theme_specificity_for_window) scores
relevance and specificity once given a ThemeDefinition, but building that
definition by hand (as earlier one-off analyses in this project did) means
someone has to sit down with a specific chart and decide "Uranus rules my
4th house, tag it moderate" for every user. That doesn't scale to a product
where any stranger can submit a birthday.

This module does that derivation mechanically, from the chart alone:
  - the ACTUAL (chart-specific) ruler of a house's cusp sign -> "moderate"
    (a real, chart-specific tie, but the ruling planet has its own other
    meanings too -- see astroengine.theme's docstring on why even a real
    rulership tie isn't automatically "high").
  - the NATURAL/traditional ruler of that house number (i.e. the
    traditional ruler of the sign that number naturally corresponds to --
    Aries/1st, Taurus/2nd, ...), when it differs from the actual ruler ->
    "low" (generic, not chart-specific).
  - any planet actually POSITED in the house -> "moderate" (a real,
    chart-specific placement, but the planet's other significations still
    compete).
  - the house's own angle, for the four angular houses (1st/4th/7th/10th ->
    Ascendant/IC/Descendant/Midheaven) -> "high" (an angle IS the house
    cusp; it carries none of a planet's competing symbolic baggage).

This is a defensible default derivation, not a claim that every rulership
tie is equally strong in every chart -- see astroengine.theme's own
docstring for the judgment-call caveat. It exists so the product has SOME
consistent, chart-agnostic starting point rather than no theme scoring at
all for users who aren't the one person we hand-built a ledger for.
"""

from __future__ import annotations

from astroengine.constants import RULERSHIP, SIGNS
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings
from astroengine.theme import ThemeDefinition, ThemeSignificator

# house number -> the sign that naturally/traditionally corresponds to it
# (1st house <-> Aries, 2nd <-> Taurus, ...), used only to look up that
# house's NATURAL ruler -- never the chart's actual cusp sign.
_NATURAL_SIGN_FOR_HOUSE = {i + 1: SIGNS[i] for i in range(12)}

_ANGLE_FOR_HOUSE = {1: "Ascendant", 4: "IC", 7: "Descendant", 10: "Midheaven"}

_ORDINAL_SUFFIX = {1: "st", 2: "nd", 3: "rd"}


def _ordinal(n: int) -> str:
    suffix = _ORDINAL_SUFFIX.get(n if n < 20 else n % 10, "th")
    return f"{n}{suffix}"


# life category -> (label, houses it draws from, one-line editorial framing
# for the LLM prompt -- kept here, next to the house mapping, so the prompt
# and the underlying astrological definition can't silently drift apart).
LIFE_CATEGORIES: dict[str, dict] = {
    "love_relationships": {
        "label": "Love & Relationships",
        "houses": [5, 7],
        "framing": "romance, attraction, and committed partnership",
    },
    "work_career": {
        "label": "Work & Career",
        "houses": [6, 10],
        "framing": "daily work, professional direction, and public standing",
    },
    "money_finance": {
        "label": "Money & Resources",
        "houses": [2, 8],
        "framing": "personal income/values and shared or entangled resources",
    },
    "home_family": {
        "label": "Home & Family",
        "houses": [4],
        "framing": "home, roots, and family",
    },
    "health_wellbeing": {
        "label": "Health & Vitality",
        "houses": [1, 6],
        "framing": "physical vitality and daily health/routine",
    },
    "personal_growth": {
        "label": "Growth & Beliefs",
        "houses": [9, 12],
        "framing": "learning, travel, belief, and inner life",
    },
}


def build_category_significators(
    chart: NatalChart, settings: AstrologySettings, category_key: str,
) -> ThemeDefinition:
    """ThemeDefinition for one LIFE_CATEGORIES entry, derived from this
    specific chart. Requires chart.houses/chart.angles to be populated
    (i.e. a known birth time -- see NatalChart)."""
    if category_key not in LIFE_CATEGORIES:
        raise ValueError(f"unknown life category: {category_key!r}")
    if not chart.houses:
        raise ValueError("build_category_significators requires a chart with known houses (birth time known)")

    houses_by_number = {h.house_number: h for h in chart.houses}
    significators: list[ThemeSignificator] = []
    seen: set[tuple[str, str]] = set()

    def add(point: str, role: str, specificity: str) -> None:
        key = (point, role)
        if key not in seen:
            seen.add(key)
            significators.append(ThemeSignificator(point, role, specificity))

    for house_num in LIFE_CATEGORIES[category_key]["houses"]:
        house = houses_by_number.get(house_num)
        if house is None:
            continue
        ordinal = _ordinal(house_num)

        actual_ruler = RULERSHIP[settings.rulership_scheme][house.sign]
        add(actual_ruler, f"actual chart ruler of the {ordinal} house cusp ({house.sign})", "moderate")

        natural_sign = _NATURAL_SIGN_FOR_HOUSE[house_num]
        natural_ruler = RULERSHIP["traditional"][natural_sign]
        if natural_ruler != actual_ruler:
            add(natural_ruler, f"natural/traditional ruler of the {ordinal} house (not the actual chart ruler)", "low")

        for planet in chart.planets:
            if planet.house == house_num:
                add(planet.planet, f"posited in the {ordinal} house", "moderate")

        angle = _ANGLE_FOR_HOUSE.get(house_num)
        if angle is not None:
            add(angle, f"{ordinal} house cusp (angle)", "high")

    return significators
