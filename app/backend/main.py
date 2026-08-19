from __future__ import annotations

import sys
from datetime import date, time as dtime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # repo root, for `astroengine`

import reading as reading_module  # noqa: E402

app = FastAPI(title="Astroengine Reading API")

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
