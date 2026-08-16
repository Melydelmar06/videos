"""AstrologySettings: every calculation choice that must be explicit and
stored rather than hardcoded, per ARCHITECTURE.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional

from astroengine.constants import DEFAULT_ORBS, LUMINARY_ORB_BONUS, MAJOR_ASPECTS


def default_aspect_set() -> dict:
    return {name: True for name in MAJOR_ASPECTS} | {
        "semisextile": False,
        "semisquare": False,
        "sesquiquadrate": False,
        "quincunx": False,
    }


def default_orb_rules() -> dict:
    return {
        "base_orbs": dict(DEFAULT_ORBS),
        "luminary_bonus": LUMINARY_ORB_BONUS,
    }


def default_timezone_policy() -> dict:
    return {
        # "exact" | "approximate" | "unknown"
        "precision": "exact",
        "unknown_time_fallback": "suppress_houses_and_angles",
    }


@dataclass
class AstrologySettings:
    birth_profile_id: Optional[int] = None
    zodiac_type: str = "tropical"                 # "tropical" | "sidereal"
    ayanamsha: Optional[str] = None                # e.g. "lahiri"; only used if sidereal
    house_system: str = "placidus"
    node_type: str = "mean"                        # "mean" | "true"
    rulership_scheme: str = "modern"                # "modern" | "traditional"
    aspect_set: dict = field(default_factory=default_aspect_set)
    orb_rules: dict = field(default_factory=default_orb_rules)
    timezone_policy: dict = field(default_factory=default_timezone_policy)
    id: Optional[int] = None

    def __post_init__(self):
        if self.zodiac_type not in ("tropical", "sidereal"):
            raise ValueError(f"unknown zodiac_type: {self.zodiac_type!r}")
        if self.zodiac_type == "sidereal" and not self.ayanamsha:
            raise ValueError("ayanamsha is required when zodiac_type='sidereal'")
        if self.node_type not in ("mean", "true"):
            raise ValueError(f"unknown node_type: {self.node_type!r}")
        if self.rulership_scheme not in ("modern", "traditional"):
            raise ValueError(f"unknown rulership_scheme: {self.rulership_scheme!r}")

    def enabled_aspects(self) -> list[str]:
        return [name for name, enabled in self.aspect_set.items() if enabled]

    def orb_for(self, aspect_name: str, involves_luminary: bool) -> float:
        base = self.orb_rules["base_orbs"][aspect_name]
        if involves_luminary:
            base += self.orb_rules.get("luminary_bonus", 0.0)
        return base

    def to_row(self) -> dict:
        """Flat dict matching the astrology_settings table columns."""
        return {
            "id": self.id,
            "birth_profile_id": self.birth_profile_id,
            "zodiac_type": self.zodiac_type,
            "ayanamsha": self.ayanamsha,
            "house_system": self.house_system,
            "node_type": self.node_type,
            "rulership_scheme": self.rulership_scheme,
            "aspect_set_json": json.dumps(self.aspect_set),
            "orb_rules_json": json.dumps(self.orb_rules),
            "timezone_policy_json": json.dumps(self.timezone_policy),
        }

    @classmethod
    def from_row(cls, row: dict) -> "AstrologySettings":
        return cls(
            id=row["id"],
            birth_profile_id=row["birth_profile_id"],
            zodiac_type=row["zodiac_type"],
            ayanamsha=row["ayanamsha"],
            house_system=row["house_system"],
            node_type=row["node_type"],
            rulership_scheme=row["rulership_scheme"],
            aspect_set=json.loads(row["aspect_set_json"]),
            orb_rules=json.loads(row["orb_rules_json"]),
            timezone_policy=json.loads(row["timezone_policy_json"]),
        )
