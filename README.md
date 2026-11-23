# Weather App Backend

My technical assessment for the **AI Engineer Intern** role at **PM Accelerator**
(Product Manager Accelerator), Backend track (#2).

A user types a place name. The app finds the place, fetches its real current
weather from the free Open-Meteo API, and can save it as a record in a SQLite
database. Saved records can be listed, read, updated, deleted, and exported
as JSON or CSV.

## What it covers

- REST APIs with GET, POST, PUT and DELETE
- Full CRUD on saved weather records
- A SQLite database, so records survive after the app restarts
- Real external data, live from Open-Meteo, never typed in by hand
- Data export as JSON and CSV

## Stack

- **FastAPI** for the API (and free interactive docs at `/docs`)
- **SQLite** for storage, one file, no server to install
- **Open-Meteo** for geocoding and weather, free with no API key
- **httpx** to call the Open-Meteo APIs
- **Uvicorn** to run the app

## How to run it

Open PowerShell inside the project folder (the folder that contains `main.py`).

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m uvicorn main:app --reload
```

Then open in your browser:

- UI: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs
- Info: http://127.0.0.1:8000/api/info

To stop the app, press Ctrl+C in the PowerShell window. The database file
`weather.db` appears on its own the first time the app runs.

## Endpoints

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/` | The one-page UI |
| GET | `/api/info` | App info: my name, the project, PM Accelerator |
| GET | `/weather?location=Lahore` | Real current weather for a place, plus a Google Maps link. Does not save anything. |
| POST | `/records` | Save a record: location + start_date + end_date. Returns the saved record with its ID (201). |
| GET | `/records` | List all saved records, newest first. |
| GET | `/records/{id}` | Read one record by ID. 404 if it does not exist. |
| PUT | `/records/{id}` | Update location and/or dates. Weather is fetched fresh. |
| DELETE | `/records/{id}` | Delete one record. Returns a confirmation message. |
| GET | `/export?format=json` or `csv` | Download all records as JSON or CSV. Any other format returns 400. |

Save a record with this JSON body:

```json
{
  "location": "Lahore",
  "start_date": "2026-11-19",
  "end_date": "2026-11-20"
}
```

## How the code works

Everything in `main.py` follows three steps:

1. **Find the place.** `geocode()` turns a name like Lahore into latitude and
   longitude using the Open-Meteo geocoding API.
2. **Fetch the weather.** `fetch_weather()` gets the real current weather for
   those coordinates from the Open-Meteo forecast API.
3. **Save or return it.** `/weather` returns it straight away. `POST /records`
   stores it in SQLite first.

`check_dates()` runs before anything is saved: dates must be in YYYY-MM-DD
format, start_date must be before end_date, and end_date cannot be in the
future. An unknown place returns a clear "Location not found" error instead
of crashing.

## Project files

| File | What it holds |
| --- | --- |
| `main.py` | The whole backend: endpoints, database, validation and API calls. |
| `static/index.html` | The one-page UI. Plain HTML with inline CSS and JavaScript, no libraries. |
| `requirements.txt` | Three packages: fastapi, uvicorn, httpx. |
| `weather.db` | Created automatically by SQLite on first run. Not in the repo. |

## Author

Amina Abru
