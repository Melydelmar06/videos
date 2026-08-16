"""Static reference data: signs, planets, rulerships, default aspect/orb tables.

These are the values an AstrologySettings row can override; nothing here is
meant to be the only allowed choice.
"""

import swisseph as swe

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# The ten classical + modern planets. The lunar nodes are handled separately
# (astroengine.natal) since which node body to query depends on
# AstrologySettings.node_type.
PLANET_SWE_IDS = {
    "sun": swe.SUN,
    "moon": swe.MOON,
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
    "uranus": swe.URANUS,
    "neptune": swe.NEPTUNE,
    "pluto": swe.PLUTO,
}

NODE_SWE_IDS = {
    "mean": swe.MEAN_NODE,
    "true": swe.TRUE_NODE,
}

HOUSE_SYSTEM_CODES = {
    "placidus": b"P",
    "koch": b"K",
    "whole_sign": b"W",
    "equal": b"E",
    "campanus": b"C",
    "regiomontanus": b"R",
    "porphyry": b"O",
}

SIDEREAL_MODES = {
    "lahiri": swe.SIDM_LAHIRI,
    "fagan_bradley": swe.SIDM_FAGAN_BRADLEY,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
}

# planet -> sign it rules, under each rulership scheme.
RULERSHIP = {
    "modern": {
        "Aries": "mars", "Taurus": "venus", "Gemini": "mercury", "Cancer": "moon",
        "Leo": "sun", "Virgo": "mercury", "Libra": "venus", "Scorpio": "pluto",
        "Sagittarius": "jupiter", "Capricorn": "saturn", "Aquarius": "uranus", "Pisces": "neptune",
    },
    "traditional": {
        "Aries": "mars", "Taurus": "venus", "Gemini": "mercury", "Cancer": "moon",
        "Leo": "sun", "Virgo": "mercury", "Libra": "venus", "Scorpio": "mars",
        "Sagittarius": "jupiter", "Capricorn": "saturn", "Aquarius": "saturn", "Pisces": "jupiter",
    },
}

# aspect name -> exact angle in degrees
ASPECT_ANGLES = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
    "semisextile": 30.0,
    "semisquare": 45.0,
    "sesquiquadrate": 135.0,
    "quincunx": 150.0,
}

MAJOR_ASPECTS = ["conjunction", "sextile", "square", "trine", "opposition"]
MINOR_ASPECTS = ["semisextile", "semisquare", "sesquiquadrate", "quincunx"]

HARD_ASPECTS = {"conjunction", "square", "opposition"}
SOFT_ASPECTS = {"trine", "sextile"}

# an aspect to a point automatically implies the complementary aspect to
# that point's exact-opposite (P+180): conjunction<->opposition, square is
# self-complementary, trine<->sextile, and likewise for the minors. Used to
# recognize when two aspect records describe the same underlying alignment
# reached via a structurally-linked point (see astroengine.evidence).
COMPLEMENT_ASPECT = {
    "conjunction": "opposition",
    "opposition": "conjunction",
    "square": "square",
    "trine": "sextile",
    "sextile": "trine",
    "semisextile": "quincunx",
    "quincunx": "semisextile",
    "semisquare": "sesquiquadrate",
    "sesquiquadrate": "semisquare",
}

# point name -> the "primary" point it is always exactly 180 degrees from,
# by definition rather than by chart-specific placement. Primary points
# (Ascendant, Midheaven, north_node) are not keys here; looking a name up
# and getting nothing back means it isn't part of a definitionally-linked
# pair.
LINKED_POINT_PAIRS = {
    "Descendant": "Ascendant",
    "IC": "Midheaven",
    "south_node": "north_node",
}

# rough real-time degrees/day used only to size how far a timing scan needs
# to look before/after a query window to find genuine entry/exit dates --
# not used for any position calculation.
TRANSIT_TYPICAL_DAILY_SPEED = {
    "sun": 0.9856, "moon": 13.18, "mercury": 1.38, "venus": 1.2, "mars": 0.52,
    "jupiter": 0.083, "saturn": 0.034, "uranus": 0.012, "neptune": 0.006, "pluto": 0.004,
    "north_node": 0.053, "south_node": 0.053,
}
# secondary-progressed / solar-arc-directed points move at their natal daily
# speed compressed by day-for-a-year, i.e. roughly 1/365.25 of the transit rate.
PROGRESSED_TYPICAL_DAILY_SPEED = {
    name: speed / 365.25 for name, speed in TRANSIT_TYPICAL_DAILY_SPEED.items()
}

# default orb (degrees) per aspect, used unless AstrologySettings overrides it
DEFAULT_ORBS = {
    "conjunction": 8.0,
    "opposition": 8.0,
    "square": 7.0,
    "trine": 7.0,
    "sextile": 4.0,
    "semisextile": 2.0,
    "semisquare": 2.0,
    "sesquiquadrate": 2.0,
    "quincunx": 3.0,
}

# extra orb (degrees) added when the Sun or Moon is one of the two points,
# reflecting the common convention that luminary contacts read as tighter/
# stronger at a given nominal orb.
LUMINARY_ORB_BONUS = 1.0


def angular_separation(longitude_a: float, longitude_b: float) -> float:
    """Shortest angular distance between two ecliptic longitudes, in [0, 180]."""
    diff = abs(longitude_a - longitude_b) % 360.0
    return min(diff, 360.0 - diff)


def is_applying_to_fixed_target(
    lon_moving: float, speed_moving: float, lon_fixed: float, exact_angle: float,
    current_orb: float, dt_days: float = 0.01,
) -> bool:
    """Whether a moving point (given its longitude and speed) is approaching
    or separating from an exact aspect to a FIXED (non-moving) target degree
    -- the situation for every timing-engine hit, where the natal target
    doesn't move in real time. See aspects._is_applying for the natal-chart
    case where both points have their own speed."""
    future_lon = (lon_moving + speed_moving * dt_days) % 360.0
    future_orb = abs(angular_separation(future_lon, lon_fixed) - exact_angle)
    return future_orb < current_orb


def sign_for_longitude(longitude: float) -> str:
    """Zodiac sign name for an ecliptic longitude in [0, 360)."""
    index = int(longitude % 360.0 // 30.0)
    return SIGNS[index]


def degree_in_sign(longitude: float) -> float:
    """Degrees into the current sign, in [0, 30)."""
    return longitude % 30.0
