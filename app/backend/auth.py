"""Email + magic-link auth. No password, no third-party identity provider.

DEV MODE: this environment has no outbound email sending configured, so
request_magic_link returns the link directly in the API response instead
of emailing it -- clearly marked `dev_mode: true` in the response so a
real integration can swap in an actual mail send later without touching
the token/session logic below.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException

MAGIC_LINK_TTL_MINUTES = 15
SESSION_TTL_DAYS = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_magic_link(conn: sqlite3.Connection, email: str) -> dict:
    email = email.strip().lower()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        cur = conn.execute("INSERT INTO users (email) VALUES (?)", (email,))
        user_id = cur.lastrowid
    else:
        user_id = row["id"]

    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_TTL_MINUTES)).isoformat()
    conn.execute(
        "INSERT INTO magic_link_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at),
    )
    conn.commit()

    dev_mode = not os.environ.get("MAIL_SENDER_CONFIGURED")
    return {"dev_mode": dev_mode, "dev_magic_token": token if dev_mode else None}


def consume_magic_link(conn: sqlite3.Connection, token: str) -> dict:
    row = conn.execute(
        "SELECT id, user_id, expires_at, used_at FROM magic_link_tokens WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=400, detail="This link isn't valid.")
    if row["used_at"] is not None:
        raise HTTPException(status_code=400, detail="This link has already been used.")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This link has expired -- request a new one.")

    conn.execute("UPDATE magic_link_tokens SET used_at = ? WHERE id = ?", (_now_iso(), row["id"]))

    session_token = secrets.token_urlsafe(32)
    session_expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).isoformat()
    conn.execute(
        "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
        (row["user_id"], session_token, session_expires_at),
    )
    conn.commit()
    return {"session_token": session_token}


def current_user_id(conn: sqlite3.Connection, authorization: str | None = Header(default=None)) -> int:
    """FastAPI dependency: resolves the bearer session token to a user_id,
    or 401s. Kept as a plain function (not a class) so it's easy to unit
    test without spinning up FastAPI's DI."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in required.")
    token = authorization.removeprefix("Bearer ").strip()
    row = conn.execute("SELECT user_id, expires_at FROM sessions WHERE token = ?", (token,)).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Session not found -- please sign in again.")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired -- please sign in again.")
    return row["user_id"]
