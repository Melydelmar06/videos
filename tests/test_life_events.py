from datetime import date

import pytest

from astroengine import life_events, repository
from astroengine.models import LifeEvent


@pytest.fixture
def profile_id(conn, sample_profile):
    return repository.save_birth_profile(conn, sample_profile)


def test_add_and_get_life_event(conn, profile_id):
    event = LifeEvent(
        birth_profile_id=profile_id,
        start_date=date(2026, 6, 1),
        category="career",
        title="Started visa sponsorship process",
        description="Employer filed paperwork",
        importance=4,
    )
    event_id = life_events.add_life_event(conn, event)
    reloaded = life_events.get_life_event(conn, event_id)

    assert reloaded.title == "Started visa sponsorship process"
    assert reloaded.category == "career"
    assert reloaded.importance == 4
    assert reloaded.end_date is None


def test_invalid_category_rejected():
    with pytest.raises(ValueError):
        LifeEvent(birth_profile_id=1, start_date=date(2026, 1, 1), category="not_a_category", title="x")


def test_invalid_importance_rejected():
    with pytest.raises(ValueError):
        LifeEvent(birth_profile_id=1, start_date=date(2026, 1, 1), category="career", title="x", importance=6)


def test_end_date_before_start_date_rejected():
    with pytest.raises(ValueError):
        LifeEvent(
            birth_profile_id=1, start_date=date(2026, 6, 1), end_date=date(2026, 5, 1),
            category="career", title="x",
        )


def test_list_life_events_filters_by_date_range(conn, profile_id):
    events = [
        LifeEvent(birth_profile_id=profile_id, start_date=date(2025, 1, 1), category="career", title="old"),
        LifeEvent(birth_profile_id=profile_id, start_date=date(2026, 9, 15), category="relationship", title="in range"),
        LifeEvent(
            birth_profile_id=profile_id, start_date=date(2026, 8, 1), end_date=date(2026, 10, 1),
            category="move", title="spans range",
        ),
        LifeEvent(birth_profile_id=profile_id, start_date=date(2027, 1, 1), category="financial", title="future"),
    ]
    for e in events:
        life_events.add_life_event(conn, e)

    results = life_events.list_life_events(conn, profile_id, start=date(2026, 9, 1), end=date(2026, 10, 31))
    titles = {e.title for e in results}
    assert titles == {"in range", "spans range"}


def test_update_and_delete_life_event(conn, profile_id):
    event = LifeEvent(birth_profile_id=profile_id, start_date=date(2026, 1, 1), category="decision", title="original")
    event_id = life_events.add_life_event(conn, event)

    event.title = "updated"
    event.importance = 5
    life_events.update_life_event(conn, event)
    reloaded = life_events.get_life_event(conn, event_id)
    assert reloaded.title == "updated"
    assert reloaded.importance == 5

    life_events.delete_life_event(conn, event_id)
    with pytest.raises(KeyError):
        life_events.get_life_event(conn, event_id)
