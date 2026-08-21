"""
main.py
-------
FastAPI application entry point for the WeatherNow web application.

Run locally with:

    uvicorn backend.main:app --reload

Deploy (e.g. on Render) with:

    uvicorn backend.main:app --host 0.0.0.0 --port $PORT

The frontend (static HTML/CSS/JS) is served directly by FastAPI via
StaticFiles, so the whole app — API + UI — runs as a single service
from one URL.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import health, weather
from backend.config import ALLOWED_ORIGINS, APP_NAME, APP_VERSION, FRONTEND_DIR

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "Backend API for WeatherNow — a current weather, forecast, and "
        "search-history service backed by OpenWeatherMap."
    ),
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API routers (must be registered before the catch-all static mount below)
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api")
app.include_router(weather.router)

# ---------------------------------------------------------------------------
# Frontend static files — serves frontend/index.html at "/" and everything
# else under frontend/ (css/, js/) at matching paths, so the whole app is
# reachable from a single URL/port.
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
