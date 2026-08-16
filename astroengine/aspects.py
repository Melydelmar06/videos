"""Natal aspect detection between any set of chart points (planets, nodes,
angles), using the profile's configured aspect set and orb rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from astroengine.constants import ASPECT_ANGLES, angular_separation
from astroengine.evidence import evaluate_evidence_eligibility
from astroengine.models import DataConfidence, NatalAspect
from astroengine.settings import AstrologySettings

LUMINARIES = {"sun", "moon"}

# how far ahead (days) to look when deciding applying vs. separating, using
# each point's instantaneous speed. Angles get speed_longitude=0 (they are
# not treated as independently moving bodies for a natal-chart snapshot).
_APPLYING_CHECK_DT_DAYS = 0.01


@dataclass(frozen=True)
class AspectPoint:
    name: str
    longitude: float
    speed_longitude: float = 0.0
    confidence: DataConfidence | None = None

    @property
    def is_luminary(self) -> bool:
        return self.name.lower() in LUMINARIES


def _is_applying(a: AspectPoint, b: AspectPoint, exact_angle: float, current_orb: float) -> bool:
    future_a = (a.longitude + a.speed_longitude * _APPLYING_CHECK_DT_DAYS) % 360.0
    future_b = (b.longitude + b.speed_longitude * _APPLYING_CHECK_DT_DAYS) % 360.0
    future_sep = angular_separation(future_a, future_b)
    future_orb = abs(future_sep - exact_angle)
    return future_orb < current_orb


def find_aspects(points: list[AspectPoint], settings: AstrologySettings) -> list[NatalAspect]:
    enabled = settings.enabled_aspects()
    results: list[NatalAspect] = []

    for a, b in combinations(points, 2):
        separation = angular_separation(a.longitude, b.longitude)
        involves_luminary = a.is_luminary or b.is_luminary

        best_match: tuple[str, float, float] | None = None  # (aspect_name, exact_angle, orb)
        for aspect_name in enabled:
            exact_angle = ASPECT_ANGLES[aspect_name]
            orb = abs(separation - exact_angle)
            allowed_orb = settings.orb_for(aspect_name, involves_luminary)
            if orb <= allowed_orb:
                if best_match is None or orb < best_match[2]:
                    best_match = (aspect_name, exact_angle, orb)

        if best_match is None:
            continue

        aspect_name, exact_angle, orb = best_match
        applying = _is_applying(a, b, exact_angle, orb)

        confidence = _combine_confidence(a.confidence, b.confidence)
        results.append(NatalAspect(
            point_a=a.name,
            point_b=b.name,
            aspect_type=aspect_name,
            exact_angle=exact_angle,
            orb=orb,
            is_applying=applying,
            confidence=confidence,
        ))

    _annotate_evidence_eligibility(results)
    return results


def _annotate_evidence_eligibility(aspects: list[NatalAspect]) -> None:
    """Flags structural (Asc/Dsc, MC/IC, N/S Node opposing themselves) and
    mirror-duplicate aspects (a third point contacting both ends of one of
    those pairs) as not evidence-eligible. Mutates in place."""
    entries = [(a.point_a, a.point_b, a.aspect_type) for a in aspects]
    for aspect, eligibility in zip(aspects, evaluate_evidence_eligibility(entries)):
        aspect.evidence_eligible = eligibility.eligible
        aspect.evidence_note = eligibility.note


def _combine_confidence(a: DataConfidence | None, b: DataConfidence | None) -> DataConfidence:
    """An aspect's confidence can't be better than the weaker of its two
    endpoints -- e.g. a planet-to-Ascendant aspect is only as trustworthy as
    the Ascendant is, even if the planet's own position is exact."""
    candidates = [c for c in (a, b) if c is not None]
    if not candidates:
        return DataConfidence(basis="exact_time")
    rank = {"exact_time": 0, "approximate_time": 1, "unknown_time": 2}
    worst = max(candidates, key=lambda c: rank[c.basis])
    near_boundary = any(c.near_boundary for c in candidates)
    return DataConfidence(basis=worst.basis, near_boundary=near_boundary)
