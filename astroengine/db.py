"""SQLite connection + a minimal migration runner.

Migrations are plain numbered .sql files in astroengine/migrations/, applied
in filename order, tracked in a schema_migrations table so re-running is a
no-op.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _applied_versions(conn: sqlite3.Connection) -> set[str]:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def run_migrations(conn: sqlite3.Connection) -> None:
    applied = _applied_versions(conn)
    for path in _migration_files():
        version = path.stem
        if version in applied:
            continue
        sql = path.read_text()
        with conn:
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))


def connect_and_migrate(db_path: str) -> sqlite3.Connection:
    conn = connect(db_path)
    run_migrations(conn)
    return conn
