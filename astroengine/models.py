"""Core dataclasses for birth data and natal chart results.

DataConfidence is deliberately separate from anything about "evidence
strength" -- it only describes how trustworthy a *computed placement* is
given the precision of its inputs (birth time known/approximate/unknown,
proximity to a sign/house boundary). Evidence strength belongs to the
not-yet-built timing/theme engine and operates on a different axis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional


BOUNDARY_THRESHOLD_DEGREES = 1.0  # within this many degrees of a 30-degree
                                   # sign line (or a house cusp) is "near_boundary"


@dataclass(frozen=True)
class DataConfidence:
    basis: str                      # "exact_time" | "approximate_time" | "unknown_time"
    near_boundary: bool = False
    boundary_detail: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps({
            "basis": self.basis,
            "near_boundary": self.near_boundary,
            "boundary_detail": self.boundary_detail,
        })

    @classmethod
    def from_json(cls, raw: str) -> "DataConfidence":
        data = json.loads(raw)
        return cls(**data)


def confidence_for_degree_in_sign(basis: str, degree_in_sign: float) -> DataConfidence:
    """near_boundary is true if the placement sits within
    BOUNDARY_THRESHOLD_DEGREES of either edge of its current sign."""
    dist_to_edge = min(degree_in_sign, 30.0 - degree_in_sign)
    near = dist_to_edge < BOUNDARY_THRESHOLD_DEGREES
    detail = f"{dist_to_edge:.3f} deg from sign boundary" if near else None
    return DataConfidence(basis=basis, near_boundary=near, boundary_detail=detail)


@dataclass
class BirthProfile:
    name: str
    birth_date: date
    birth_time: Optional[time]      # None if time_known is False
    time_known: bool
    birth_place: str
    latitude: float                 # north positive
    longitude: float                # east positive
    timezone_name: str              # IANA name, e.g. "Europe/Rome"
    id: Optional[int] = None

    def __post_init__(self):
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError(f"latitude out of range: {self.latitude}")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError(f"longitude out of range: {self.longitude}")
        if self.time_known and self.birth_time is None:
            raise ValueError("time_known=True requires birth_time")
        if not self.time_known and self.birth_time is not None:
            raise ValueError("birth_time must be None when time_known=False")


@dataclass
class NatalPlanet:
    planet: str
    longitude: float                # absolute ecliptic longitude, 0-360
    sign: str
    degree_in_sign: float
    house: Optional[int]            # None if houses are suppressed (unknown birth time)
    is_retrograde: bool
    speed_longitude: float          # degrees/day; negative == retrograde
    confidence: DataConfidence
    birth_profile_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class HouseCusp:
    house_number: int               # 1-12
    longitude: float
    sign: str
    degree_in_sign: float
    ruling_planet: str
    confidence: DataConfidence
    birth_profile_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class NatalAngle:
    name: str                       # "Ascendant" | "Midheaven" | "Descendant" | "IC"
    longitude: float
    sign: str
    degree_in_sign: float
    confidence: DataConfidence
    birth_profile_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class NatalAspect:
    point_a: str                    # planet name or angle name
    point_b: str
    aspect_type: str
    exact_angle: float              # the aspect's defining angle, e.g. 90.0 for square
    orb: float                      # absolute orb, degrees, always >= 0
    is_applying: bool
    confidence: DataConfidence
    birth_profile_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class LifeEvent:
    start_date: date
    category: str                   # relationship | career | move | fertility | financial | decision | other
    title: str
    description: str = ""
    end_date: Optional[date] = None
    importance: int = 3             # 1-5
    birth_profile_id: Optional[int] = None
    id: Optional[int] = None

    VALID_CATEGORIES = frozenset({
        "relationship", "career", "move", "fertility", "financial", "decision", "other",
    })

    def __post_init__(self):
        if self.category not in self.VALID_CATEGORIES:
            raise ValueError(f"unknown category: {self.category!r}")
        if not (1 <= self.importance <= 5):
            raise ValueError(f"importance must be 1-5, got {self.importance}")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
