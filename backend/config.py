"""
config.py
---------
Central configuration for the WeatherNow FastAPI backend.

All secrets (API keys) are loaded from environment variables via
python-dotenv, never hardcoded. Copy `.env.example` to `.env` and fill
in your own OpenWeatherMap API key before running the app.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file in the project root, if present.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# OpenWeatherMap API configuration
# ---------------------------------------------------------------------------
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "").strip()

CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
ICON_URL_TEMPLATE = "https://openweathermap.org/img/wn/{icon_code}@2x.png"

UNITS = os.getenv("WEATHER_UNITS", "metric")  # "metric" -> °C, m/s | "imperial" -> °F, mph
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))

UNIT_SYMBOLS = {
    "metric": {"temp": "°C", "speed": "m/s"},
    "imperial": {"temp": "°F", "speed": "mph"},
}

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
DATABASE_NAME = os.getenv("DATABASE_NAME", str(BASE_DIR / "weather_history.db"))
MAX_HISTORY_RECORDS = int(os.getenv("MAX_HISTORY_RECORDS", "50"))

# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------
# Comma-separated list of allowed origins. Defaults to "*" for local
# development / single-service deployment. Tighten this in production by
# setting ALLOWED_ORIGINS in your environment (e.g. your Render URL).
_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",")] if _origins_env else ["*"]

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------
APP_NAME = "WeatherNow API"
APP_VERSION = "2.0.0"
FRONTEND_DIR = BASE_DIR / "frontend"
