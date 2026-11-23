"""Weather App Backend - PM Accelerator technical assessment.

Amina Abru | AI Engineer Intern | Backend track (#2)

A user types a place name. The app finds the place, fetches its real
current weather from Open-Meteo, and can save it as a record in SQLite.
Saved records can be listed, read, updated, deleted, and exported
as JSON or CSV.

Run it:  uvicorn main:app --reload
Docs:    http://127.0.0.1:8000/docs
"""

import csv
import io
import json
import sqlite3
from datetime import date, datetime

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Weather App Backend")

DB_PATH = "weather.db"

# Open-Meteo is free and needs no API key, so there is nothing secret
# to configure. One API turns a place name into coordinates, the other
# returns the weather for those coordinates.
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo weather codes (WMO). Only the common ones are listed here,
# anything else falls back to "Unknown conditions".
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class RecordCreate(BaseModel):
    location: str
    start_date: str
    end_date: str


class RecordUpdate(BaseModel):
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the records table if it does not exist yet."""
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            temperature_c REAL,
            humidity_percent REAL,
            wind_speed_kmh REAL,
            weather_code INTEGER,
            saved_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
def on_startup():
    init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def maps_link(lat, lon):
    return f"https://www.google.com/maps?q={lat},{lon}"


def record_to_dict(row):
    """Turn a database row into the JSON shape the API returns."""
    record = dict(row)
    code = record.get("weather_code")
    record["condition"] = WEATHER_CODES.get(code, "Unknown conditions")
    record["maps_link"] = maps_link(record["latitude"], record["longitude"])
    return record


def check_dates(start_date, end_date):
    """Check a date range before anything is saved.

    Returns (start, end) as date objects, or raises a 400 error with
    a plain message the user can act on.
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Dates must be in YYYY-MM-DD format, for example 2026-11-19.",
        )
    if start >= end:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before end_date.",
        )
    if end > date.today():
        raise HTTPException(
            status_code=400,
            detail="end_date cannot be in the future.",
        )
    return start, end


def geocode(location):
    """Turn a place name into coordinates. Returns None if the place
    does not exist, so the endpoint can answer with a clear error."""
    response = httpx.get(
        GEOCODING_URL,
        params={"name": location, "count": 1, "language": "en", "format": "json"},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("results")
    if not results:
        return None
    place = results[0]
    return place["latitude"], place["longitude"], place["name"]


def fetch_weather(lat, lon):
    """Fetch the real current weather for a pair of coordinates."""
    response = httpx.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "wind_speed_unit": "kmh",
        },
        timeout=10,
    )
    response.raise_for_status()
    current = response.json()["current"]
    return {
        "temperature_c": current["temperature_2m"],
        "humidity_percent": current["relative_humidity_2m"],
        "wind_speed_kmh": current["wind_speed_10m"],
        "weather_code": current["weather_code"],
    }


def get_place_and_weather(location):
    """Geocode a place and fetch its weather in one go. Shared by the
    live lookup, the save endpoint and the update endpoint."""
    found = geocode(location)
    if not found:
        raise HTTPException(
            status_code=400,
            detail="Location not found. Please check the spelling.",
        )
    lat, lon, name = found
    weather = fetch_weather(lat, lon)
    return lat, lon, name, weather


def get_record_or_404(record_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM records WHERE id = ?", (record_id,)
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No record found with id {record_id}.",
        )
    return row


# ---------------------------------------------------------------------------
# Pages and info
# ---------------------------------------------------------------------------

@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/api/info")
def info():
    return {
        "name": "Amina Abru",
        "project": "Weather App Backend",
        "programme": "PM Accelerator",
        "role": "AI Engineer Intern",
        "track": "Backend (#2)",
        "stack": "FastAPI + SQLite + Open-Meteo",
    }


# ---------------------------------------------------------------------------
# Live weather (no saving)
# ---------------------------------------------------------------------------

@app.get("/weather")
def weather(location: str = Query(..., description="Place name, for example Lahore")):
    lat, lon, name, current = get_place_and_weather(location)
    code = current["weather_code"]
    return {
        "location": name,
        "latitude": lat,
        "longitude": lon,
        "temperature_c": current["temperature_c"],
        "humidity_percent": current["humidity_percent"],
        "wind_speed_kmh": current["wind_speed_kmh"],
        "weather_code": code,
        "condition": WEATHER_CODES.get(code, "Unknown conditions"),
        "maps_link": maps_link(lat, lon),
    }


# ---------------------------------------------------------------------------
# Records: full CRUD
# ---------------------------------------------------------------------------

@app.post("/records", status_code=201)
def create_record(record: RecordCreate):
    check_dates(record.start_date, record.end_date)
    lat, lon, name, current = get_place_and_weather(record.location)

    conn = get_db()
    cursor = conn.execute(
        """
        INSERT INTO records
            (location, latitude, longitude, start_date, end_date,
             temperature_c, humidity_percent, wind_speed_kmh,
             weather_code, saved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            lat,
            lon,
            record.start_date,
            record.end_date,
            current["temperature_c"],
            current["humidity_percent"],
            current["wind_speed_kmh"],
            current["weather_code"],
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM records WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    conn.close()
    return record_to_dict(row)


@app.get("/records")
def list_records():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM records ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [record_to_dict(row) for row in rows]


@app.get("/records/{record_id}")
def read_record(record_id: int):
    return record_to_dict(get_record_or_404(record_id))


@app.put("/records/{record_id}")
def update_record(record_id: int, update: RecordUpdate):
    old = get_record_or_404(record_id)

    # Partial update: anything left out keeps its old value.
    location = update.location or old["location"]
    start_date = update.start_date or old["start_date"]
    end_date = update.end_date or old["end_date"]

    check_dates(start_date, end_date)
    lat, lon, name, current = get_place_and_weather(location)

    conn = get_db()
    conn.execute(
        """
        UPDATE records SET
            location = ?, latitude = ?, longitude = ?,
            start_date = ?, end_date = ?,
            temperature_c = ?, humidity_percent = ?,
            wind_speed_kmh = ?, weather_code = ?
        WHERE id = ?
        """,
        (
            name,
            lat,
            lon,
            start_date,
            end_date,
            current["temperature_c"],
            current["humidity_percent"],
            current["wind_speed_kmh"],
            current["weather_code"],
            record_id,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM records WHERE id = ?", (record_id,)
    ).fetchone()
    conn.close()
    return record_to_dict(row)


@app.delete("/records/{record_id}")
def delete_record(record_id: int):
    get_record_or_404(record_id)
    conn = get_db()
    conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return {"message": f"Record {record_id} deleted."}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@app.get("/export")
def export_records(format: str = Query("json", description="json or csv")):
    fmt = format.lower()
    if fmt not in ("json", "csv"):
        raise HTTPException(
            status_code=400,
            detail="format must be json or csv.",
        )

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM records ORDER BY id DESC"
    ).fetchall()
    conn.close()
    records = [record_to_dict(row) for row in rows]

    if fmt == "json":
        return StreamingResponse(
            io.StringIO(json.dumps(records, indent=2)),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=weather-records.json"},
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id", "location", "latitude", "longitude",
            "start_date", "end_date", "temperature_c",
            "humidity_percent", "wind_speed_kmh",
            "weather_code", "condition", "saved_at", "maps_link",
        ],
    )
    writer.writeheader()
    writer.writerows(records)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=weather-records.csv"},
    )
