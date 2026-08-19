from __future__ import annotations

import sys
from datetime import date, time as dtime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # repo root, for `astroengine`

import auth  # noqa: E402
import checkin_service  # noqa: E402
import profile as profile_service  # noqa: E402
import reading as reading_module  # noqa: E402
import regulate_service  # noqa: E402
import today_service  # noqa: E402
from db import get_conn  # noqa: E402

app = FastAPI(title="Aphelion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GeocodeResult(BaseModel):
    label: str
    latitude: float
    longitude: float
    timezone: str


@app.get("/api/geocode", response_model=list[GeocodeResult])
async def geocode(q: str):
    if len(q.strip()) < 2:
        return []
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": q, "count": 6, "language": "en", "format": "json"},
        )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    out = []
    for r in results:
        bits = [r["name"]]
        if r.get("admin1") and r["admin1"] != r["name"]:
            bits.append(r["admin1"])
        bits.append(r["country"])
        out.append(GeocodeResult(
            label=", ".join(bits), latitude=r["latitude"], longitude=r["longitude"], timezone=r["timezone"],
        ))
    return out


class ReadingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    birth_date: date
    birth_time: dtime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone_name: str


@app.post("/api/reading")
async def create_reading(req: ReadingRequest):
    try:
        return reading_module.generate_reading(
            name=req.name, birth_date=req.birth_date, birth_time=req.birth_time,
            latitude=req.latitude, longitude=req.longitude, timezone_name=req.timezone_name,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"could not generate reading: {e}")


@app.get("/api/health")
async def health():
    return {"ok": True}


# ---------------------------------------------------------------------------
# Auth (email + magic link, dev-mode -- see auth.py)
# ---------------------------------------------------------------------------

def current_user_id(authorization: Optional[str] = Header(default=None)) -> int:
    return auth.current_user_id(get_conn(), authorization)


class RequestLinkBody(BaseModel):
    email: EmailStr


@app.post("/api/auth/request-link")
async def request_link(body: RequestLinkBody):
    return auth.request_magic_link(get_conn(), body.email)


class ConsumeLinkBody(BaseModel):
    token: str


@app.post("/api/auth/consume")
async def consume_link(body: ConsumeLinkBody):
    return auth.consume_magic_link(get_conn(), body.token)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class ProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    birth_date: date
    birth_time: dtime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone_name: str


@app.post("/api/profile")
async def save_profile(body: ProfileRequest, user_id: int = Depends(current_user_id)):
    profile = profile_service.save_profile_for_user(
        get_conn(), user_id, body.name, body.birth_date, body.birth_time,
        body.latitude, body.longitude, body.timezone_name,
    )
    return {"has_profile": True, "name": profile.name}


@app.get("/api/profile")
async def get_profile(user_id: int = Depends(current_user_id)):
    profile = profile_service.get_profile_for_user(get_conn(), user_id)
    if profile is None:
        return {"has_profile": False}
    return {"has_profile": True, "name": profile.name}


def _require_profile(user_id: int):
    profile = profile_service.get_profile_for_user(get_conn(), user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No birth profile saved yet.")
    return profile


# ---------------------------------------------------------------------------
# Today (Understand)
# ---------------------------------------------------------------------------

@app.get("/api/today")
async def get_today(user_id: int = Depends(current_user_id)):
    profile = _require_profile(user_id)
    try:
        return today_service.get_today_reading(get_conn(), user_id, profile)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------------------------------------------------------------------------
# Check-ins (Reflect) -- HUMAN data
# ---------------------------------------------------------------------------

class CheckInRequest(BaseModel):
    mood: str
    life_area: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=2000)


@app.post("/api/checkin")
async def create_checkin(body: CheckInRequest, user_id: int = Depends(current_user_id)):
    conn = get_conn()
    today_snapshot = conn.execute(
        "SELECT id FROM daily_dimension_snapshots WHERE user_id = ? AND snapshot_date = date('now')",
        (user_id,),
    ).fetchone()
    try:
        return checkin_service.upsert_checkin(
            conn, user_id, body.mood, body.life_area, body.note,
            chart_snapshot_id=today_snapshot["id"] if today_snapshot else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/checkin")
async def get_checkin_today(user_id: int = Depends(current_user_id)):
    checkin = checkin_service.get_checkin(get_conn(), user_id)
    return checkin or {}


@app.get("/api/checkin/history")
async def get_checkin_history(user_id: int = Depends(current_user_id)):
    return {"check_ins": checkin_service.list_checkins(get_conn(), user_id)}


# ---------------------------------------------------------------------------
# Regulate
# ---------------------------------------------------------------------------

@app.get("/api/regulate")
async def get_regulate(user_id: int = Depends(current_user_id)):
    conn = get_conn()
    profile = _require_profile(user_id)
    checkin = checkin_service.get_checkin(conn, user_id)
    mood = checkin["mood"] if checkin else None
    try:
        return regulate_service.get_regulate_recommendation(conn, user_id, profile, mood)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
