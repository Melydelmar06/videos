"""House cusps, angles (Asc/MC/Dsc/IC), and house rulers."""

from __future__ import annotations

from astroengine import ephemeris
from astroengine.constants import RULERSHIP, degree_in_sign, sign_for_longitude
from astroengine.models import (
    DataConfidence, HouseCusp, NatalAngle, confidence_for_degree_in_sign,
)
from astroengine.settings import AstrologySettings


def house_index_for_longitude(longitude: float, cusps: tuple[float, ...]) -> int:
    """Which house (1-12) a given ecliptic longitude falls in, given 12 cusp
    longitudes (cusps[0] == house 1 cusp, ...). Cusps need not be evenly
    spaced (Placidus etc.); this walks the ring looking for the cusp interval
    that contains `longitude`, wrapping past 360.
    """
    longitude = longitude % 360.0
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        span = (end - start) % 360.0
        offset = (longitude - start) % 360.0
        if offset < span or span == 0.0:
            return i + 1
    raise AssertionError("longitude did not fall into any house interval")


def ruler_of_sign(sign: str, rulership_scheme: str) -> str:
    return RULERSHIP[rulership_scheme][sign]


def compute_houses_and_angles(
    jd_ut: float,
    latitude: float,
    longitude: float,
    settings: AstrologySettings,
    confidence_basis: str,
) -> tuple[list[HouseCusp], list[NatalAngle]]:
    """confidence_basis should be "exact_time" or "approximate_time" -- callers
    with an unknown birth time should not call this at all (houses/angles are
    meaningless without a real birth time), per timezone_policy.unknown_time_fallback.
    """
    raw = ephemeris.houses(
        jd_ut, latitude, longitude, settings.house_system,
        zodiac_type=settings.zodiac_type, ayanamsha=settings.ayanamsha,
    )

    house_cusps: list[HouseCusp] = []
    for house_number, cusp_longitude in enumerate(raw.cusps, start=1):
        sign = sign_for_longitude(cusp_longitude)
        deg = degree_in_sign(cusp_longitude)
        house_cusps.append(HouseCusp(
            house_number=house_number,
            longitude=cusp_longitude,
            sign=sign,
            degree_in_sign=deg,
            ruling_planet=ruler_of_sign(sign, settings.rulership_scheme),
            confidence=confidence_for_degree_in_sign(confidence_basis, deg),
        ))

    angles: list[NatalAngle] = []
    for name, angle_longitude in (
        ("Ascendant", raw.ascendant),
        ("Midheaven", raw.midheaven),
        ("Descendant", raw.descendant),
        ("IC", raw.imum_coeli),
    ):
        sign = sign_for_longitude(angle_longitude)
        deg = degree_in_sign(angle_longitude)
        angles.append(NatalAngle(
            name=name,
            longitude=angle_longitude,
            sign=sign,
            degree_in_sign=deg,
            confidence=confidence_for_degree_in_sign(confidence_basis, deg),
        ))

    return house_cusps, angles
