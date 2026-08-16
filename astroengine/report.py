"""Human-readable and JSON report generation for a computed natal chart.

This only formats data that natal.compute_natal_chart() already produced --
it performs no astrological interpretation and adds no new calculations
beyond the traditional-vs-modern ruler comparison (which is just constants.RULERSHIP
looked up a second time under the other scheme).
"""

from __future__ import annotations

from dataclasses import asdict
from zoneinfo import ZoneInfo

from astroengine.constants import RULERSHIP
from astroengine.models import BirthProfile
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings
from astroengine.timeutil import JulianMoment

ASPECT_SYMBOLS = {
    "conjunction": "☌", "sextile": "*", "square": "sq", "trine": "tri", "opposition": "opp",
}


def _format_offset(offset) -> str:
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    return f"UTC{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def ruler_pair(sign: str) -> tuple[str, str]:
    """(traditional_ruler, modern_ruler) for a sign -- identical for signs
    where the two schemes agree (everything except Scorpio/Aquarius/Pisces)."""
    return RULERSHIP["traditional"][sign], RULERSHIP["modern"][sign]


def _confidence_str(c) -> str:
    parts = [c.basis]
    if c.near_boundary:
        parts.append(f"near_boundary ({c.boundary_detail})")
    return ", ".join(parts)


def build_json_report(
    profile: BirthProfile,
    settings: AstrologySettings,
    chart: NatalChart,
    moment: JulianMoment,
) -> dict:
    houses_json = []
    for h in chart.houses:
        trad, modern = ruler_pair(h.sign)
        houses_json.append({
            "house_number": h.house_number,
            "longitude": round(h.longitude, 4),
            "sign": h.sign,
            "degree_in_sign": round(h.degree_in_sign, 4),
            "ruler_traditional": trad,
            "ruler_modern": modern,
            "rulers_agree": trad == modern,
            "data_confidence": asdict(h.confidence),
        })

    return {
        "birth_data": {
            "name": profile.name,
            "birth_date": profile.birth_date.isoformat(),
            "birth_time_local": profile.birth_time.isoformat() if profile.birth_time else None,
            "time_known": profile.time_known,
            "birth_place": profile.birth_place,
            "latitude": profile.latitude,
            "longitude": profile.longitude,
            "timezone_name": profile.timezone_name,
            "utc_datetime": moment.utc.isoformat(),
            "utc_offset_used": _format_offset(
                moment.utc.astimezone(ZoneInfo(profile.timezone_name)).utcoffset()
            ),
            "julian_day_ut": moment.jd_ut,
            "julian_day_et": moment.jd_et,
        },
        "settings_used": {
            "zodiac_type": settings.zodiac_type,
            "house_system": settings.house_system,
            "node_type": settings.node_type,
            "aspect_set": settings.enabled_aspects(),
            "orb_rules": settings.orb_rules,
            "rulership_note": "both traditional and modern rulers reported per house",
        },
        "planets": [
            {
                "planet": p.planet,
                "longitude": round(p.longitude, 4),
                "sign": p.sign,
                "degree_in_sign": round(p.degree_in_sign, 4),
                "house": p.house,
                "is_retrograde": p.is_retrograde,
                "speed_longitude": round(p.speed_longitude, 6),
                "data_confidence": asdict(p.confidence),
            }
            for p in chart.planets
        ],
        "angles": [
            {
                "name": a.name,
                "longitude": round(a.longitude, 4),
                "sign": a.sign,
                "degree_in_sign": round(a.degree_in_sign, 4),
                "data_confidence": asdict(a.confidence),
            }
            for a in chart.angles
        ],
        "houses": houses_json,
        "aspects": [
            {
                "point_a": asp.point_a,
                "point_b": asp.point_b,
                "aspect_type": asp.aspect_type,
                "exact_angle": asp.exact_angle,
                "orb": round(asp.orb, 4),
                "is_applying": asp.is_applying,
                "data_confidence": asdict(asp.confidence),
            }
            for asp in chart.aspects
        ],
    }


def format_degree(degree_in_sign: float) -> str:
    d = int(degree_in_sign)
    m_full = (degree_in_sign - d) * 60
    m = int(m_full)
    s = round((m_full - m) * 60)
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{d}°{m:02d}'{s:02d}\""


def build_human_report(
    profile: BirthProfile,
    settings: AstrologySettings,
    chart: NatalChart,
    moment: JulianMoment,
) -> str:
    lines: list[str] = []
    add = lines.append

    add("=" * 70)
    add("NATAL CHART -- CALCULATION VALIDATION REPORT (no interpretation)")
    add("=" * 70)
    add("")
    add("Birth data")
    add("-" * 70)
    add(f"  Name:            {profile.name}")
    add(f"  Local birth time: {profile.birth_date.isoformat()} {profile.birth_time.isoformat()}")
    add(f"  Place:            {profile.birth_place}  (lat {profile.latitude}, lon {profile.longitude})")
    tz_offset = moment.utc.astimezone(ZoneInfo(profile.timezone_name)).utcoffset()
    add(f"  Timezone used:    {profile.timezone_name}  (historical offset at this date: {_format_offset(tz_offset)})")
    add(f"  Converted to UTC: {moment.utc.isoformat()}")
    add(f"  Julian Day (UT1): {moment.jd_ut:.6f}")
    add(f"  Julian Day (TT):  {moment.jd_et:.6f}")
    add("")
    add("Settings used")
    add("-" * 70)
    add(f"  Zodiac: {settings.zodiac_type}   House system: {settings.house_system}   Node: {settings.node_type}")
    add(f"  Aspects enabled: {', '.join(settings.enabled_aspects())}")
    add("  Rulerships: traditional and modern both reported per house below")
    add("")

    add("Planets")
    add("-" * 70)
    add(f"  {'Planet':<12}{'Sign':<12}{'Degree':<12}{'House':<7}{'Retrograde':<11}{'Speed(deg/day)':<15}{'Confidence'}")
    order = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
              "uranus", "neptune", "pluto", "north_node", "south_node"]
    by_name = {p.planet: p for p in chart.planets}
    for name in order:
        p = by_name[name]
        add(
            f"  {name.replace('_', ' ').title():<12}{p.sign:<12}{format_degree(p.degree_in_sign):<12}"
            f"{p.house or '-':<7}{'R' if p.is_retrograde else '-':<11}{p.speed_longitude:<15.6f}"
            f"{_confidence_str(p.confidence)}"
        )
    add("")

    add("Angles")
    add("-" * 70)
    for a in chart.angles:
        add(f"  {a.name:<12}{a.sign:<12}{format_degree(a.degree_in_sign):<12}{_confidence_str(a.confidence)}")
    add("")

    add("House cusps (Placidus) with traditional / modern rulers")
    add("-" * 70)
    add(f"  {'House':<7}{'Sign':<12}{'Degree':<12}{'Ruler (trad.)':<15}{'Ruler (modern)':<15}")
    for h in chart.houses:
        trad, modern = ruler_pair(h.sign)
        marker = "" if trad == modern else "  <- differ"
        add(f"  {h.house_number:<7}{h.sign:<12}{format_degree(h.degree_in_sign):<12}{trad:<15}{modern:<15}{marker}")
    add("")

    add(f"Major aspects ({len(chart.aspects)} total)")
    add("-" * 70)
    add(f"  {'Point A':<12}{'Aspect':<12}{'Point B':<14}{'Orb':<10}{'Motion':<12}{'Confidence'}")
    for asp in sorted(chart.aspects, key=lambda a: a.orb):
        add(
            f"  {asp.point_a:<12}{asp.aspect_type:<12}{asp.point_b:<14}{format_degree(asp.orb):<10}"
            f"{'applying' if asp.is_applying else 'separating':<12}{_confidence_str(asp.confidence)}"
        )

    return "\n".join(lines)
