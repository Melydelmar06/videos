"""Shared helpers for the timing engines (transits, progressions, solar arc):
extracting a natal chart's aspectable points, and picking scan resolution/
padding for a given mover so slow and fast bodies each get a sane scan.
"""

from __future__ import annotations

from astroengine.models import DataConfidence
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings

MAX_SCAN_PAD_DAYS = 1825.0  # 5-year safety cap on how far a scan looks beyond the query window


def natal_targets(chart: NatalChart) -> list[tuple[str, float, DataConfidence]]:
    """Every point in a natal chart worth checking timing hits against:
    planets, both nodes, and (if the birth time was known) the four angles.
    """
    targets = [(p.planet, p.longitude, p.confidence) for p in chart.planets]
    targets += [(a.name, a.longitude, a.confidence) for a in chart.angles]
    return targets


def orb_span_for_settings(settings: AstrologySettings) -> tuple[float, float]:
    """(smallest, largest) orb across the enabled aspect set, luminary bonus
    included in the largest -- used to size scan step/padding conservatively
    (fine enough for the tightest aspect, wide enough for the loosest)."""
    enabled = settings.enabled_aspects()
    smallest = min(settings.orb_for(a, involves_luminary=False) for a in enabled)
    largest = max(settings.orb_for(a, involves_luminary=True) for a in enabled)
    return smallest, largest


def scan_pad_days(typical_daily_speed_deg: float, largest_orb_deg: float, min_pad_days: float = 5.0) -> float:
    """How far beyond the query window to scan so genuine entry/exit dates
    aren't clipped, capped at MAX_SCAN_PAD_DAYS."""
    if typical_daily_speed_deg <= 0:
        return MAX_SCAN_PAD_DAYS
    pad = largest_orb_deg / typical_daily_speed_deg * 4.0
    return min(max(pad, min_pad_days), MAX_SCAN_PAD_DAYS)
