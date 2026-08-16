import json
from datetime import date, time, datetime, timezone

import pytest

from astroengine.forecast import build_forecast_packet
from astroengine.models import BirthProfile
from astroengine.natal import compute_natal_chart
from astroengine.settings import AstrologySettings


@pytest.fixture(scope="module")
def packet():
    profile = BirthProfile(
        name="Test", birth_date=date(1986, 11, 6), birth_time=time(6, 30, 0), time_known=True,
        birth_place="Cartagena de Indias, Colombia", latitude=10.3910, longitude=-75.4794,
        timezone_name="America/Bogota",
    )
    settings = AstrologySettings(node_type="true")
    chart = compute_natal_chart(profile, settings)
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    return build_forecast_packet(profile, settings, chart, start, end)


def test_packet_is_json_serializable(packet):
    serialized = json.dumps(packet)
    assert len(serialized) > 0


def test_counts_are_internally_consistent(packet):
    counts = packet["counts"]
    assert counts["evidence_eligible"] + counts["excluded"] == counts["total_hits_calculated"]
    assert counts["strong"] + counts["moderate"] + counts["weak"] == counts["evidence_eligible"]
    assert counts["strong"] == len(packet["timing_evidence"]["strong"])
    assert counts["moderate"] == len(packet["timing_evidence"]["moderate"])
    assert counts["weak"] == len(packet["timing_evidence"]["weak"])
    assert counts["excluded"] == len(packet["excluded_from_evidence"]["hits"])


def test_tiered_hits_have_matching_strength_field(packet):
    for tier_name in ("strong", "moderate", "weak"):
        for h in packet["timing_evidence"][tier_name]:
            assert h["evidence_strength"] == tier_name
            assert h["evidence_eligible"] is True


def test_excluded_hits_are_all_ineligible(packet):
    for h in packet["excluded_from_evidence"]["hits"]:
        assert h["evidence_eligible"] is False
        assert h["evidence_note"] is not None
        assert h["evidence_strength"] is None


def test_no_interpretation_language_leaks_into_the_packet(packet):
    """This packet is calculation + evidence tiering only. Guard against
    accidentally embedding narrative/predictive text anywhere."""
    serialized = json.dumps(packet).lower()
    banned_phrases = ["you will", "you should", "this means you"]
    for phrase in banned_phrases:
        assert phrase not in serialized


def test_query_and_reference_metadata_present(packet):
    assert packet["query"]["date_range"]["start"].startswith("2026-09-01")
    assert packet["query"]["theme"] is None
    assert packet["natal_chart_reference"]["birth_date"] == "1986-11-06"
    assert len(packet["interpretation_guardrails"]) > 0
