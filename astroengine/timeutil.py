"""Birth-local-time -> UTC -> Julian Day conversion.

This is the highest-risk correctness area in the whole engine: a timezone
or coordinate-sign mistake here silently produces a wrong Ascendant/MC/house
chart while every downstream number still looks plausible. Two things are
deliberately explicit rather than convenient:

1. Timezone is resolved from an IANA zone name (e.g. "Europe/Rome") via the
   standard library's zoneinfo, never from a manually-entered UTC offset --
   that's what makes historical DST rules resolve correctly.
2. Longitude is always treated as east-positive / west-negative, matching
   what pyswisseph's house functions expect (see swe.houses_ex2 docs).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

import swisseph as swe


@dataclass(frozen=True)
class JulianMoment:
    utc: datetime
    jd_et: float     # Julian day, Ephemeris/Terrestrial Time -- for planetary calc
    jd_ut: float      # Julian day, UT1 -- for houses/sidereal time


def local_time_to_utc(local_date: date, local_time: time, timezone_name: str) -> datetime:
    """Resolve a civil birth date/time in `timezone_name` to an aware UTC datetime.

    Uses zoneinfo so historical DST transitions for that specific date are
    honored (a fixed UTC-offset input would silently get this wrong for any
    birth date on the other side of a DST boundary from today).
    """
    tz = ZoneInfo(timezone_name)
    local_dt = datetime.combine(local_date, local_time, tzinfo=tz)
    return local_dt.astimezone(dt_timezone.utc)


def utc_to_julian_moment(utc_dt: datetime) -> JulianMoment:
    """Convert an aware UTC datetime to Julian Day numbers via Swiss Ephemeris.

    Returns both the ET/TT Julian day (used for planetary position calc) and
    the UT1 Julian day (used for houses / sidereal time), matching what
    swe.utc_to_jd hands back.
    """
    if utc_dt.tzinfo is None:
        raise ValueError("utc_dt must be timezone-aware")
    utc_dt = utc_dt.astimezone(dt_timezone.utc)
    seconds = utc_dt.second + utc_dt.microsecond / 1_000_000.0
    jd_et, jd_ut = swe.utc_to_jd(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour, utc_dt.minute, seconds,
        swe.GREG_CAL,
    )
    return JulianMoment(utc=utc_dt, jd_et=jd_et, jd_ut=jd_ut)


def birth_julian_moment(local_date: date, local_time: time, timezone_name: str) -> JulianMoment:
    """One-shot: birth-local date/time/timezone -> JulianMoment."""
    utc_dt = local_time_to_utc(local_date, local_time, timezone_name)
    return utc_to_julian_moment(utc_dt)
