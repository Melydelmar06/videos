"""Builds the structured JSON packet handed to the (not-yet-built)
interpretation layer: natal reference data + every timing hit for a date
range, tiered by evidence strength, with structural/mirror-duplicate hits
kept visible but clearly excluded. No interpretation happens here -- this
module only serializes what the calculation layer already computed.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from astroengine.evidence import effective_orb_for_window
from astroengine.models import BirthProfile, TimingHit
from astroengine.natal import NatalChart
from astroengine.settings import AstrologySettings
from astroengine.timing_engine import compute_timing_result
from astroengine.timeutil import jd_ut_to_datetime


def _serialize_hit(hit: TimingHit, window_start: datetime, window_end: datetime) -> dict:
    return {
        "system": hit.system,
        "moving_point": hit.moving_point,
        "natal_target": hit.natal_target,
        "aspect_type": hit.aspect_type,
        "exact_angle": hit.exact_angle,
        "degree_at_reference": round(hit.degree_at_reference, 4),
        "orb_at_reference": round(hit.orb_at_reference, 4),
        "orb_at_reference_note": (
            "orb as of the query window's start date -- can be wide even for a Strong hit "
            "if the hit only turns exact LATER in the window (see effective_orb_for_window)"
        ),
        "effective_orb_for_window": round(effective_orb_for_window(hit, window_start, window_end), 4),
        "is_applying": hit.is_applying,
        "entry_into_orb": hit.entry_into_orb.isoformat() if hit.entry_into_orb else None,
        "exact_hit_dates": [d.isoformat() for d in hit.exact_hit_dates],
        "exit_from_orb": hit.exit_from_orb.isoformat() if hit.exit_from_orb else None,
        "data_confidence": asdict(hit.confidence),
        "evidence_eligible": hit.evidence_eligible,
        "evidence_note": hit.evidence_note,
        "evidence_strength": hit.evidence_strength,
    }


def build_forecast_packet(
    profile: BirthProfile, settings: AstrologySettings, chart: NatalChart,
    query_start: datetime, query_end: datetime,
    solar_return_location: tuple[float, float] | None = None,
) -> dict:
    result = compute_timing_result(chart, settings, profile, query_start, query_end, solar_return_location)

    eligible = [h for h in result.hits if h.evidence_eligible]
    excluded = [h for h in result.hits if not h.evidence_eligible]

    tiers: dict[str, list[dict]] = {"strong": [], "moderate": [], "weak": []}
    for h in eligible:
        tiers[h.evidence_strength].append(_serialize_hit(h, query_start, query_end))
    for tier_hits in tiers.values():
        tier_hits.sort(key=lambda h: h["orb_at_reference"])

    return {
        "query": {
            "date_range": {"start": query_start.isoformat(), "end": query_end.isoformat()},
            "theme": None,
            "note": (
                "No theme/question specified for this run -- this is the full raw evidence "
                "set for the date range, for inspection before any interpretation is built."
            ),
        },
        "natal_chart_reference": {
            "name": profile.name,
            "birth_date": profile.birth_date.isoformat(),
            "birth_time_local": profile.birth_time.isoformat(),
            "timezone_name": profile.timezone_name,
            "birth_place": profile.birth_place,
        },
        "solar_return_charts_used": [
            {
                "return_utc": rc.return_utc.isoformat(),
                "ascendant": round(rc.ascendant, 4),
                "midheaven": round(rc.midheaven, 4),
                "location_known": rc.location_known,
                "note": (
                    "cast for the supplied solar_return_location"
                    if rc.location_known else
                    "NO solar_return_location was supplied -- these angles fall back to the "
                    "birth location and are NOT a reliable indication of the actual return "
                    "chart; descriptive only, never used as evidence (return-chart hits are "
                    "generated from geocentric planets, which don't depend on location)"
                ),
            }
            for rc in result.solar_return_charts
        ],
        "lunation_events": [
            {
                "kind": e.kind,
                "eclipse_label": e.eclipse_label,
                "moment_utc": jd_ut_to_datetime(e.jd_ut).isoformat(),
                "moon_longitude": round(e.moon_longitude, 4),
            }
            for e in result.lunation_events
        ],
        "timing_evidence": tiers,
        "excluded_from_evidence": {
            "count": len(excluded),
            "note": (
                "Structural relationships (e.g. Node opposite Node, Ascendant opposite "
                "Descendant, MC/IC, a solar return's own Sun-conjunct-Sun) and mirror-"
                "duplicate hits (the same underlying alignment reached via a linked point) "
                "-- kept here for transparency, never used for corroboration, strength, or "
                "convergence."
            ),
            "hits": [_serialize_hit(h, query_start, query_end) for h in excluded],
        },
        "counts": {
            "total_hits_calculated": len(result.hits),
            "evidence_eligible": len(eligible),
            "excluded": len(excluded),
            "strong": len(tiers["strong"]),
            "moderate": len(tiers["moderate"]),
            "weak": len(tiers["weak"]),
        },
        "interpretation_guardrails": [
            "This packet contains calculation and evidence-tiering only -- no interpretation, prediction, or narrative.",
            "Only Strong and Moderate evidence should drive any specific claims about this period.",
            "Weak evidence may be mentioned as minor color only, never as a standalone claim.",
            "Excluded hits (structural/mirror-duplicate) must never be counted toward corroboration or convergence, even though they are listed above for transparency.",
            "entry_into_orb / exit_from_orb of null means the hit was already in orb at the start of the scanned window, or is still in orb at its end -- not that it lacks a real boundary.",
            "Solar arc and slow progressed/transiting-outer-planet hits can have very wide entry/exit windows (months to years) -- that reflects how those techniques actually work, not an error.",
            "Solar return chart angles (ascendant/midheaven) are location-dependent; see solar_return_charts_used[].location_known -- when false, those angles are a birth-location fallback and must not be treated as accurate.",
        ],
    }
