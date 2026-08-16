"""Orchestrates a full natal chart calculation: planets, nodes, houses,
angles, and aspects, from a BirthProfile + AstrologySettings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from astroengine import ephemeris
from astroengine.aspects import AspectPoint, find_aspects
from astroengine.constants import degree_in_sign, sign_for_longitude
from astroengine.houses import compute_houses_and_angles, house_index_for_longitude
from astroengine.models import (
    BirthProfile, DataConfidence, HouseCusp, NatalAngle, NatalAspect,
    NatalPlanet, confidence_for_degree_in_sign,
)
from astroengine.settings import AstrologySettings
from astroengine.timeutil import birth_julian_moment

# used when time_known is False: planets are still calculated (their
# positions are only mildly time-of-day sensitive, except the Moon), but
# houses/angles are meaningless without a real birth time and are suppressed.
UNKNOWN_TIME_FALLBACK = time(12, 0, 0)


@dataclass
class NatalChart:
    planets: list[NatalPlanet]
    houses: list[HouseCusp]          # empty if birth time unknown
    angles: list[NatalAngle]          # empty if birth time unknown
    aspects: list[NatalAspect]


def compute_natal_chart(profile: BirthProfile, settings: AstrologySettings) -> NatalChart:
    time_known = profile.time_known
    local_time = profile.birth_time if time_known else UNKNOWN_TIME_FALLBACK
    confidence_basis = "exact_time" if time_known else "unknown_time"

    moment = birth_julian_moment(profile.birth_date, local_time, profile.timezone_name)

    planets: list[NatalPlanet] = []
    aspect_points: list[AspectPoint] = []

    for planet_name in ("sun", "moon", "mercury", "venus", "mars", "jupiter",
                         "saturn", "uranus", "neptune", "pluto"):
        raw = ephemeris.planet_position(moment.jd_ut, planet_name, settings.zodiac_type, settings.ayanamsha)
        sign = sign_for_longitude(raw.longitude)
        deg = degree_in_sign(raw.longitude)
        confidence = confidence_for_degree_in_sign(confidence_basis, deg)
        planets.append(NatalPlanet(
            planet=planet_name,
            longitude=raw.longitude,
            sign=sign,
            degree_in_sign=deg,
            house=None,  # filled in below once houses are known
            is_retrograde=raw.speed_longitude < 0,
            speed_longitude=raw.speed_longitude,
            confidence=confidence,
        ))
        aspect_points.append(AspectPoint(
            name=planet_name, longitude=raw.longitude,
            speed_longitude=raw.speed_longitude, confidence=confidence,
        ))

    north_node = ephemeris.node_position(moment.jd_ut, settings.node_type, settings.zodiac_type, settings.ayanamsha)
    for node_name, node_longitude in (
        ("north_node", north_node.longitude),
        ("south_node", (north_node.longitude + 180.0) % 360.0),
    ):
        sign = sign_for_longitude(node_longitude)
        deg = degree_in_sign(node_longitude)
        confidence = confidence_for_degree_in_sign(confidence_basis, deg)
        # nodes are always retrograde except during rare stations; report
        # their true instantaneous speed rather than hardcoding that.
        planets.append(NatalPlanet(
            planet=node_name,
            longitude=node_longitude,
            sign=sign,
            degree_in_sign=deg,
            house=None,
            is_retrograde=north_node.speed_longitude < 0,
            speed_longitude=north_node.speed_longitude,
            confidence=confidence,
        ))
        aspect_points.append(AspectPoint(
            name=node_name, longitude=node_longitude,
            speed_longitude=north_node.speed_longitude, confidence=confidence,
        ))

    houses: list[HouseCusp] = []
    angles: list[NatalAngle] = []

    if time_known:
        houses, angles = compute_houses_and_angles(
            moment.jd_ut, profile.latitude, profile.longitude, settings, confidence_basis,
        )
        cusp_longitudes = tuple(h.longitude for h in houses)
        for p in planets:
            p.house = house_index_for_longitude(p.longitude, cusp_longitudes)

        for angle in angles:
            aspect_points.append(AspectPoint(
                name=angle.name, longitude=angle.longitude,
                speed_longitude=0.0, confidence=angle.confidence,
            ))

    aspects = find_aspects(aspect_points, settings)

    return NatalChart(planets=planets, houses=houses, angles=angles, aspects=aspects)
