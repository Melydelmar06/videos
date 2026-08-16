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


def sign_for_longitude(longitude: float) -> str:
    """Zodiac sign name for an ecliptic longitude in [0, 360)."""
    index = int(longitude % 360.0 // 30.0)
    return SIGNS[index]


def degree_in_sign(longitude: float) -> float:
    """Degrees into the current sign, in [0, 30)."""
    return longitude % 30.0
