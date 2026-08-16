"""Pythagorean numerology: core profile numbers plus Personal Year/Month/Day.

No external library needed -- this is digit-sum arithmetic on the birth
date and (optionally) a full name.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

MASTER_NUMBERS = (11, 22, 33)

# Pythagorean letter -> number mapping.
_LETTER_VALUES = {}
for _i, _letters in enumerate(["AJS", "BKT", "CLU", "DMV", "ENW", "FOX", "GPY", "HQZ", "IR"], start=1):
    for _ch in _letters:
        _LETTER_VALUES[_ch] = _i

VOWELS = set("AEIOU")


def _digit_sum(n: int) -> int:
    return sum(int(d) for d in str(abs(n)))


def reduce_number(n: int, keep_master: bool = True) -> int:
    """Repeatedly sum digits until a single digit (1-9), unless keep_master
    is set and the running total lands exactly on 11, 22, or 33."""
    while n > 9 and not (keep_master and n in MASTER_NUMBERS):
        n = _digit_sum(n)
    return n


def life_path_number(birth_date: date) -> int:
    """Reduces month, day, and year separately (each keeping its own master
    number if it lands on one), then sums and reduces the total. This is the
    standard Pythagorean convention; it can differ from the "sum every digit
    of the date at once" method on specific dates, which is why it's
    documented here rather than left implicit.
    """
    month = reduce_number(birth_date.month)
    day = reduce_number(birth_date.day)
    year = reduce_number(birth_date.year)
    return reduce_number(month + day + year)


def _name_value(full_name: str, letters: set[str] | None) -> int:
    total = 0
    for ch in full_name.upper():
        if not ch.isalpha():
            continue
        if letters is not None and ch not in letters:
            continue
        total += _LETTER_VALUES.get(ch, 0)
    return reduce_number(total)


def expression_number(full_name: str) -> int:
    """Also called the Destiny number: every letter of the full birth name."""
    return _name_value(full_name, letters=None)


def soul_urge_number(full_name: str) -> int:
    """Also called the Heart's Desire number: vowels only."""
    return _name_value(full_name, letters=VOWELS)


def personality_number(full_name: str) -> int:
    """Consonants only."""
    all_letters = {chr(c) for c in range(ord("A"), ord("Z") + 1)}
    return _name_value(full_name, letters=all_letters - VOWELS)


@dataclass(frozen=True)
class NumerologyProfile:
    life_path: int
    expression: int | None
    soul_urge: int | None
    personality: int | None


def numerology_profile(birth_date: date, full_name: str | None = None) -> NumerologyProfile:
    return NumerologyProfile(
        life_path=life_path_number(birth_date),
        expression=expression_number(full_name) if full_name else None,
        soul_urge=soul_urge_number(full_name) if full_name else None,
        personality=personality_number(full_name) if full_name else None,
    )


def personal_year_number(birth_date: date, target_year: int) -> int:
    """Personal Year/Month/Day conventionally reduce all the way to a single
    digit (1-9) -- master numbers are not retained at this level."""
    total = _digit_sum(birth_date.month) + _digit_sum(birth_date.day) + _digit_sum(target_year)
    return reduce_number(total, keep_master=False)


def personal_month_number(personal_year: int, target_month: int) -> int:
    return reduce_number(personal_year + target_month, keep_master=False)


def personal_day_number(personal_month: int, target_day: int) -> int:
    return reduce_number(personal_month + target_day, keep_master=False)


@dataclass(frozen=True)
class PersonalTiming:
    personal_year: int
    personal_month: int
    personal_day: int


def personal_timing(birth_date: date, target_date: date) -> PersonalTiming:
    py = personal_year_number(birth_date, target_date.year)
    pm = personal_month_number(py, target_date.month)
    pd = personal_day_number(pm, target_date.day)
    return PersonalTiming(personal_year=py, personal_month=pm, personal_day=pd)
