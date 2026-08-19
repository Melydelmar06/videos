"""Proximity-triggered Prepare nudge. See PRODUCT_ARCHITECTURE.md section
8. Reuses the Season reading's "only strong-tier, dated evidence creates a
nudge" rule (astroengine.evidence's Strong tier is already temporally
corroborated by construction), computed fresh over a narrow near-term
window rather than derived from the Season cache, which can be weeks
stale by design (see season_service.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from astroengine.forecast import build_forecast_packet
from astroengine.natal import compute_natal_chart

import product_llm
from today_service import DEFAULT_SETTINGS

NUDGE_PROXIMITY_DAYS = 14


def get_prepare_nudge(profile) -> dict | None:
    settings = DEFAULT_SETTINGS
    chart = compute_natal_chart(profile, settings)

    query_start = datetime.now(timezone.utc)
    query_end = query_start + timedelta(days=NUDGE_PROXIMITY_DAYS)
    packet = build_forecast_packet(profile, settings, chart, query_start, query_end)

    best: tuple[dict, datetime] | None = None
    for hit in packet["timing_evidence"]["strong"]:
        for iso_date in hit["exact_hit_dates"]:
            d = datetime.fromisoformat(iso_date)
            if query_start <= d <= query_end and (best is None or d < best[1]):
                best = (hit, d)

    if best is None:
        return None

    hit, exact_date = best
    days_away = (exact_date - query_start).days
    evidence_text = f"{hit['system']} contacts {hit['natal_target']} via {hit['aspect_type']}"
    message = product_llm.generate_prepare_nudge(evidence_text, days_away, character=None)
    return {"days_away": days_away, "message": message}
