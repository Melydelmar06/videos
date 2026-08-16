"""Thin wrapper around pyswisseph calls used by the natal calculation layer.

Uses the Moshier analytical ephemeris (SEFLG_MOSEPH), which needs no external
data files and is accurate to about 1 arcsecond over several millennia --
plenty for natal-chart purposes. If higher precision is ever needed, point
swe.set_ephe_path() at a JPL/Swiss data file directory and switch the flag
to SEFLG_SWIEPH; nothing else in this module would need to change.
"""

from __future__ import annotations

from dataclasses import dataclass

import swisseph as swe

from astroengine.constants import (
    HOUSE_SYSTEM_CODES, NODE_SWE_IDS, PLANET_SWE_IDS, SIDEREAL_MODES,
)

_CALC_FLAG = swe.FLG_MOSEPH | swe.FLG_SPEED


@dataclass(frozen=True)
class RawPosition:
    longitude: float
    latitude: float
    distance: float
    speed_longitude: float


def _calc_flag(zodiac_type: str) -> int:
    flag = _CALC_FLAG
    if zodiac_type == "sidereal":
        flag |= swe.FLG_SIDEREAL
    return flag


def _apply_sidereal_mode(zodiac_type: str, ayanamsha: str | None) -> None:
    if zodiac_type == "sidereal":
        if not ayanamsha:
            raise ValueError("ayanamsha required for sidereal zodiac_type")
        swe.set_sid_mode(SIDEREAL_MODES[ayanamsha])


def planet_position(jd_ut: float, planet_name: str, zodiac_type: str, ayanamsha: str | None) -> RawPosition:
    """jd_ut must be the UT1 Julian day (JulianMoment.jd_ut), not the ET/TT
    one -- swe.calc_ut takes UT and applies Delta-T internally."""
    _apply_sidereal_mode(zodiac_type, ayanamsha)
    planet_id = PLANET_SWE_IDS[planet_name]
    xx, _retflags = swe.calc_ut(jd_ut, planet_id, _calc_flag(zodiac_type))
    return RawPosition(longitude=xx[0] % 360.0, latitude=xx[1], distance=xx[2], speed_longitude=xx[3])


def node_position(jd_ut: float, node_type: str, zodiac_type: str, ayanamsha: str | None) -> RawPosition:
    """jd_ut must be the UT1 Julian day, see planet_position()."""
    _apply_sidereal_mode(zodiac_type, ayanamsha)
    node_id = NODE_SWE_IDS[node_type]
    xx, _retflags = swe.calc_ut(jd_ut, node_id, _calc_flag(zodiac_type))
    return RawPosition(longitude=xx[0] % 360.0, latitude=xx[1], distance=xx[2], speed_longitude=xx[3])


@dataclass(frozen=True)
class RawHouses:
    cusps: tuple          # 12 floats, index 0 == house 1 cusp
    ascendant: float
    midheaven: float
    descendant: float
    imum_coeli: float


def houses(jd_ut: float, latitude: float, longitude: float, house_system: str,
           zodiac_type: str = "tropical", ayanamsha: str | None = None) -> RawHouses:
    """Compute house cusps and angles.

    latitude: north positive. longitude: EAST positive -- this matches what
    swe.houses_ex2 expects; callers must not silently flip this convention.
    """
    _apply_sidereal_mode(zodiac_type, ayanamsha)
    hsys_code = HOUSE_SYSTEM_CODES[house_system]
    flags = swe.FLG_SIDEREAL if zodiac_type == "sidereal" else 0
    cusps, ascmc, _cusp_speeds, _ascmc_speeds = swe.houses_ex2(jd_ut, latitude, longitude, hsys_code, flags)
    ascendant = ascmc[0] % 360.0
    midheaven = ascmc[1] % 360.0
    return RawHouses(
        cusps=tuple(c % 360.0 for c in cusps),
        ascendant=ascendant,
        midheaven=midheaven,
        descendant=(ascendant + 180.0) % 360.0,
        imum_coeli=(midheaven + 180.0) % 360.0,
    )
