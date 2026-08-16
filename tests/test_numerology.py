"""Numerology is pure digit arithmetic -- these are hand-verified by working
the Pythagorean reduction by hand (see comments), not by trusting the
implementation to check itself.
"""

from datetime import date

from astroengine.numerology import (
    expression_number, life_path_number, personal_day_number,
    personal_month_number, personal_timing, personal_year_number,
    personality_number, reduce_number, soul_urge_number,
)


def test_reduce_number_basic():
    assert reduce_number(29) == 11         # 2+9=11, a master number, so reduction stops
    assert reduce_number(38) == 11          # 3+8=11 too, same master-number stop
    assert reduce_number(38, keep_master=False) == 2  # ...unless master numbers are disabled: 1+1=2
    assert reduce_number(11, keep_master=False) == 2
    assert reduce_number(7) == 7


def test_life_path_hand_verified():
    # 1990-06-15: month 6 -> 6; day 15 -> 1+5=6; year 1990 -> 1+9+9+0=19 -> 1+9=10 -> 1+0=1
    # sum = 6+6+1 = 13 -> 1+3 = 4
    assert life_path_number(date(1990, 6, 15)) == 4


def test_life_path_retains_master_number():
    # 2002-09-09: month 9; day 9; year 2002 -> 2+0+0+2=4
    # sum = 9+9+4 = 22 -> master number, not reduced further
    assert life_path_number(date(2002, 9, 9)) == 22


def test_personal_year_month_day_hand_verified():
    # birth 1990-06-15, target 2026-08-16
    # personal_year = digitsum(6) + digitsum(15=1+5=6) + digitsum(2026=2+0+2+6=10) = 6+6+10=22 -> 2+2=4
    # personal_month = digitsum-reduce(4+8=12) = 1+2=3
    # personal_day = digitsum-reduce(3+16=19) = 1+9=10 -> 1+0=1
    assert personal_year_number(date(1990, 6, 15), 2026) == 4
    assert personal_month_number(4, 8) == 3
    assert personal_day_number(3, 16) == 1

    timing = personal_timing(date(1990, 6, 15), date(2026, 8, 16))
    assert (timing.personal_year, timing.personal_month, timing.personal_day) == (4, 3, 1)


def test_personal_year_never_returns_a_master_number():
    for year in range(2020, 2035):
        assert personal_year_number(date(1990, 6, 15), year) not in (11, 22, 33)


def test_name_numbers_hand_verified():
    # "Anna Lee": A=1 N=5 N=5 A=1 L=3 E=5 E=5
    # expression (all letters): 1+5+5+1+3+5+5 = 25 -> 7
    # soul urge (vowels A,A,E,E): 1+1+5+5 = 12 -> 3
    # personality (consonants N,N,L): 5+5+3 = 13 -> 4
    assert expression_number("Anna Lee") == 7
    assert soul_urge_number("Anna Lee") == 3
    assert personality_number("Anna Lee") == 4
