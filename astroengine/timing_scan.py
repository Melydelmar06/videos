"""Generic day-sampling scanner: finds when a moving point's longitude comes
within orb of a fixed target longitude over a date range, and refines entry/
exact/exit to sub-day precision. Shared by transits, secondary progressions,
and solar arc directions -- the three systems that are "a longitude
approaches, touches, and separates from a fixed degree over time," just with
different position functions (real ephemeris position, day-for-a-year
progressed position, and directed position, respectively).

This module has no astrological knowledge -- it just does root-finding on
a scalar function of Julian day. That keeps the (correctness-critical, easy
to get subtly wrong) crossing/refinement math in one place instead of
duplicated three times.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from astroengine.constants import angular_separation


@dataclass
class ScanWindow:
    entry_jd: float | None    # None if already in orb at the scan's start (true entry not observed)
    exit_jd: float | None      # None if still in orb at the scan's end (true exit not observed)
    exact_jds: list            # list[float]; can be empty if the run never quite reaches minimum orb tightness


PositionFn = Callable[[float], tuple[float, float]]  # jd_ut -> (longitude_deg, speed_deg_per_day)


def choose_step_days(typical_daily_speed_deg: float, allowed_orb_deg: float) -> float:
    """Aim for roughly 8 samples while the mover crosses the orb window in
    either direction, bounded to a sane range so very slow or very fast
    movers don't produce absurdly coarse or absurdly expensive scans."""
    if typical_daily_speed_deg <= 0:
        return 10.0
    raw = allowed_orb_deg / typical_daily_speed_deg / 8.0
    return min(max(raw, 0.25), 10.0)


def _quadratic_vertex(x0: float, y0: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Vertex (minimum) of the parabola through 3 equally-spaced points, in
    x-units. Falls back to x1 if the points aren't (near) equally spaced or
    don't describe a genuine local minimum."""
    h1, h2 = x1 - x0, x2 - x1
    if abs(h1 - h2) > 1e-6 * max(abs(h1), abs(h2), 1.0):
        return x1
    denom = y0 - 2 * y1 + y2
    if denom == 0:
        return x1
    offset = 0.5 * (y0 - y2) / denom * h1
    vertex = x1 + offset
    if vertex < x0 or vertex > x2:
        return x1
    return vertex


def _refine_crossing(jd0: float, orb0: float, jd1: float, orb1: float, threshold: float) -> float:
    """Linear-interpolated Julian day where orb crosses `threshold` between
    two consecutive samples (one on each side of the threshold)."""
    if orb1 == orb0:
        return jd1
    t = (threshold - orb0) / (orb1 - orb0)
    t = min(max(t, 0.0), 1.0)
    return jd0 + t * (jd1 - jd0)


def _find_local_minima_jds(jds: list[float], orbs: list[float], start_idx: int, end_idx: int) -> list[float]:
    exact: list[float] = []
    for i in range(start_idx, end_idx + 1):
        if i - 1 < 0 or i + 1 >= len(orbs):
            continue
        if orbs[i] < orbs[i - 1] and orbs[i] <= orbs[i + 1]:
            exact.append(_quadratic_vertex(jds[i - 1], orbs[i - 1], jds[i], orbs[i], jds[i + 1], orbs[i + 1]))
    return exact


def sample_longitudes(position_fn: PositionFn, scan_start_jd: float, scan_end_jd: float, step_days: float) -> tuple[list[float], list[float]]:
    """Samples position_fn's longitude over [scan_start_jd, scan_end_jd] at
    step_days resolution. Split out from scan_aspect_windows so a caller
    checking one mover against many (target, aspect) combinations -- e.g.
    the transit engine, ~16 targets x 5 aspects per mover -- can sample the
    mover's ephemeris position ONCE and reuse it, instead of re-querying the
    ephemeris from scratch for every combination.
    """
    if scan_end_jd <= scan_start_jd:
        return [], []
    n_steps = max(1, int((scan_end_jd - scan_start_jd) / step_days))
    jds = [scan_start_jd + i * step_days for i in range(n_steps + 1)]
    if jds[-1] < scan_end_jd:
        jds.append(scan_end_jd)
    longitudes = [position_fn(jd)[0] for jd in jds]
    return jds, longitudes


def find_orb_windows(
    jds: list[float], longitudes: list[float], target_longitude: float, exact_angle: float, allowed_orb: float,
) -> list[ScanWindow]:
    """Given pre-sampled (jds, longitudes) -- see sample_longitudes -- finds
    the orb-crossing windows against one fixed target/aspect. This is the
    part of scan_aspect_windows that's cheap to repeat per (target, aspect)
    once the mover's positions are already sampled.
    """
    if not jds:
        return []

    orbs = [abs(angular_separation(lon, target_longitude) - exact_angle) for lon in longitudes]

    windows: list[ScanWindow] = []
    in_run = False
    run_start_idx = 0

    for i, orb in enumerate(orbs):
        if orb <= allowed_orb and not in_run:
            in_run = True
            run_start_idx = i
        elif orb > allowed_orb and in_run:
            in_run = False
            windows.append(_build_window(jds, orbs, run_start_idx, i - 1, allowed_orb))

    if in_run:
        windows.append(_build_window(jds, orbs, run_start_idx, len(orbs) - 1, allowed_orb))

    return windows


def _build_window(jds: list[float], orbs: list[float], start_idx: int, end_idx: int, allowed_orb: float) -> ScanWindow:
    entry_jd = None
    if start_idx > 0:
        entry_jd = _refine_crossing(
            jds[start_idx - 1], orbs[start_idx - 1], jds[start_idx], orbs[start_idx], allowed_orb,
        )
    exit_jd = None
    if end_idx < len(jds) - 1:
        exit_jd = _refine_crossing(
            jds[end_idx], orbs[end_idx], jds[end_idx + 1], orbs[end_idx + 1], allowed_orb,
        )
    exact_jds = _find_local_minima_jds(jds, orbs, start_idx, end_idx)
    return ScanWindow(entry_jd=entry_jd, exit_jd=exit_jd, exact_jds=exact_jds)


def scan_aspect_windows(
    position_fn: PositionFn,
    target_longitude: float,
    exact_angle: float,
    allowed_orb: float,
    scan_start_jd: float,
    scan_end_jd: float,
    step_days: float,
) -> list[ScanWindow]:
    """Convenience wrapper: sample_longitudes() + find_orb_windows() in one
    call, for callers checking a single (target, aspect) pair. Callers
    should pad [scan_start_jd, scan_end_jd] well beyond their actual query
    range so entry/exit aren't clipped to None just because the run started
    before or ended after the padded scan itself.
    """
    jds, longitudes = sample_longitudes(position_fn, scan_start_jd, scan_end_jd, step_days)
    return find_orb_windows(jds, longitudes, target_longitude, exact_angle, allowed_orb)
