from __future__ import annotations

from datetime import date, time

import pytest

from astroengine import db
from astroengine.models import BirthProfile
from astroengine.settings import AstrologySettings


@pytest.fixture
def conn(tmp_path):
    connection = db.connect_and_migrate(str(tmp_path / "test.db"))
    yield connection
    connection.close()


@pytest.fixture
def default_settings():
    return AstrologySettings()


@pytest.fixture
def sample_profile():
    # 1990-06-15, 14:30 local time, New York City, EDT in effect (America/New_York).
    return BirthProfile(
        name="Test Person",
        birth_date=date(1990, 6, 15),
        birth_time=time(14, 30, 0),
        time_known=True,
        birth_place="New York, NY, USA",
        latitude=40.7128,
        longitude=-74.0060,
        timezone_name="America/New_York",
    )
