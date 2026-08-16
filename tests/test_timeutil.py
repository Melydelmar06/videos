"""Timezone -> UTC conversion is the single highest-risk piece of this
engine (a wrong offset here produces a wrong-but-plausible-looking chart).
These tests check it against well-documented civil timekeeping facts, not
against astronomical calculations.
"""

from datetime import date, time

import pytest

from astroengine.timeutil import local_time_to_utc


@pytest.mark.parametrize(
    "local_date,local_time,tz_name,expected_utc_hour,expected_utc_minute,note",
    [
        # US DST is in effect (EDT, UTC-4) in mid-June.
        (date(1990, 6, 15), time(14, 30), "America/New_York", 18, 30, "summer EDT"),
        # Standard time (EST, UTC-5) in mid-January.
        (date(1990, 1, 15), time(14, 30), "America/New_York", 19, 30, "winter EST"),
        # Pre-2007 US DST rules (changed in 2007; and 1968 predates the brief
        # 1974-75 "emergency" year-round DST period too, so there's no rule
        # ambiguity): under the 1966 Uniform Time Act, DST ran last Sunday of
        # April to last Sunday of October, so these summer/winter dates are
        # unambiguously EDT/EST.
        (date(1968, 7, 4), time(12, 0), "America/New_York", 16, 0, "historical EDT"),
        (date(1968, 1, 4), time(12, 0), "America/New_York", 17, 0, "historical EST"),
        # Southern hemisphere: Sydney DST (AEDT, UTC+11) is in effect in January
        # (southern summer) and not in July (AEST, UTC+10).
        (date(2000, 1, 15), time(9, 0), "Australia/Sydney", 22, 0, "AEDT (previous UTC day)"),
        (date(2000, 7, 15), time(9, 0), "Australia/Sydney", 23, 0, "AEST (previous UTC day)"),
        # A zone with a non-hour UTC offset, to check we're not silently
        # rounding to whole hours anywhere in the pipeline.
        (date(2000, 6, 15), time(12, 0), "Asia/Kolkata", 6, 30, "UTC+5:30"),
    ],
)
def test_known_utc_offsets(local_date, local_time, tz_name, expected_utc_hour, expected_utc_minute, note):
    utc_dt = local_time_to_utc(local_date, local_time, tz_name)
    assert utc_dt.hour == expected_utc_hour, note
    assert utc_dt.minute == expected_utc_minute, note


def test_utc_conversion_changes_with_timezone():
    """Same civil date/time, different zones, must produce different UTC
    instants -- guards against the timezone argument being silently ignored."""
    ny = local_time_to_utc(date(2020, 3, 1), time(12, 0), "America/New_York")
    london = local_time_to_utc(date(2020, 3, 1), time(12, 0), "Europe/London")
    assert ny != london
    assert abs((ny - london).total_seconds()) == pytest.approx(5 * 3600, abs=1)
