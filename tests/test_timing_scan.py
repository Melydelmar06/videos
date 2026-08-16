import math

import pytest

from astroengine.timing_scan import choose_step_days, scan_aspect_windows


def test_linear_approach_gives_exact_entry_exact_exit():
    """A point moving at a constant 2 deg/day through an exact conjunction
    at jd=1000, with a 5 deg orb, should enter orb at jd=997.5, be exact at
    jd=1000, and exit at jd=1002.5 -- exactly, since the motion is linear
    and the scanner's refinement is exact for linear functions."""
    def position_fn(jd):
        return (2.0 * (jd - 1000.0)) % 360.0, 2.0

    windows = scan_aspect_windows(
        position_fn, target_longitude=0.0, exact_angle=0.0, allowed_orb=5.0,
        scan_start_jd=990.0, scan_end_jd=1010.0, step_days=0.5,
    )
    assert len(windows) == 1
    w = windows[0]
    assert w.entry_jd == 997.5
    assert w.exact_jds == [1000.0]
    assert w.exit_jd == 1002.5


def test_open_ended_run_reports_none_for_unobserved_boundary():
    """If the mover is already in orb at the scan's start (or still in orb
    at its end), the scanner must not fabricate an entry/exit date it never
    actually observed."""
    def position_fn(jd):
        return (2.0 * (jd - 1000.0)) % 360.0, 2.0

    # scan starts AFTER the true entry (997.5) -- entry must be None
    windows = scan_aspect_windows(
        position_fn, target_longitude=0.0, exact_angle=0.0, allowed_orb=5.0,
        scan_start_jd=999.0, scan_end_jd=1010.0, step_days=0.5,
    )
    assert windows[0].entry_jd is None
    assert windows[0].exit_jd == 1002.5


def test_no_crossing_returns_no_windows():
    def position_fn(jd):
        return 90.0, 0.0  # always 90 deg away, never near a conjunction

    windows = scan_aspect_windows(
        position_fn, target_longitude=0.0, exact_angle=0.0, allowed_orb=5.0,
        scan_start_jd=990.0, scan_end_jd=1010.0, step_days=0.5,
    )
    assert windows == []


def test_multiple_exact_hits_within_one_continuous_run():
    """Simulates a retrograde-station-style triple pass: the mover
    oscillates within orb the whole time (never leaves), touching exact
    twice. Both must be found within the single continuous window."""
    def position_fn(jd):
        lon = 3 + 2 * math.cos(2 * math.pi * (jd - 1000) / 10)
        return lon % 360.0, 0.0

    windows = scan_aspect_windows(
        position_fn, target_longitude=0.0, exact_angle=0.0, allowed_orb=5.0,
        scan_start_jd=988.0, scan_end_jd=1012.0, step_days=0.5,
    )
    assert len(windows) == 1
    exact = sorted(windows[0].exact_jds)
    assert len(exact) == 2
    assert exact[0] == pytest.approx(995.0, abs=1e-6)
    assert exact[1] == pytest.approx(1005.0, abs=1e-6)


def test_choose_step_days_is_bounded_and_scales_with_orb_over_speed():
    assert 0.25 <= choose_step_days(13.0, 5.0) <= 10.0
    # a much wider orb (slower crossing) should need a coarser-or-equal step
    assert choose_step_days(1.0, 8.0) >= choose_step_days(1.0, 2.0)
    # a stationary/near-zero-speed mover shouldn't cause a divide-by-zero
    assert choose_step_days(0.0, 5.0) == 10.0
