"""SQLite connection for the product layer, on top of astroengine.db's
migration runner -- same database file the natal-chart repository layer
uses, so a birth profile and its owning user live side by side.

FastAPI runs sync endpoints in a threadpool, and a single sqlite3.Connection
is not safe to share across threads even with check_same_thread=False (it
has no internal locking), so get_conn() opens a fresh, short-lived
connection per call rather than a shared singleton. Migrations are
idempotent (astroengine.db tracks applied versions), so re-checking them
on each connect is a cheap no-op after the first run.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from astroengine.db import connect_and_migrate

DB_PATH = os.environ.get("APHELION_DB_PATH", str(Path(__file__).resolve().parent / "aphelion.db"))


def get_conn() -> sqlite3.Connection:
    return connect_and_migrate(DB_PATH)
