"""
services/weather_service.py
----------------------------
Handles all communication with the OpenWeatherMap REST API.

This isolates every network concern (HTTP requests, error
translation, response parsing) away from the route handlers, the same
separation of concerns the original desktop app's `api.py` used
(`WeatherAPI` class). Ported to `httpx.AsyncClient` so it plays nicely
with FastAPI's async request handling, and extended with a forecast
lookup and coordinate-based (geolocation) lookup that the Tkinter app
did not need.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from backend.config import (
    CURRENT_WEATHER_URL,
    FORECAST_URL,
    ICON_URL_TEMPLATE,
    OPENWEATHER_API_KEY,
    REQUEST_TIMEOUT,
    UNIT_SYMBOLS,
    UNITS,
)


class WeatherAPIError(Exception):
    """Base exception for all weather API related errors."""


class InvalidAPIKeyError(WeatherAPIError):
    """Raised when the API key is invalid, unauthorized, or missing."""


class CityNotFoundError(WeatherAPIError):
    """Raised when the requested city cannot be found."""


class NetworkError(WeatherAPIError):
    """Raised when there is no internet connection or a network problem."""


def icon_url(icon_code: str) -> str:
    return ICON_URL_TEMPLATE.format(icon_code=icon_code or "01d")


def _format_time(unix_timestamp: Optional[int], tz_offset_seconds: int) -> Optional[str]:
    if not unix_timestamp:
        return None
    try:
        tz = timezone(timedelta(seconds=tz_offset_seconds))
        dt = datetime.fromtimestamp(unix_timestamp, tz=tz)
        return dt.strftime("%I:%M %p").lstrip("0")
    except (OverflowError, OSError, ValueError):
        return None


class WeatherService:
    """Async client wrapper around the OpenWeatherMap current-weather & forecast endpoints."""

    def __init__(self, api_key: str = OPENWEATHER_API_KEY, units: str = UNITS):
        self.api_key = api_key
        self.units = units

    def _ensure_api_key(self) -> None:
        if not self.api_key:
            raise InvalidAPIKeyError(
                "No OpenWeatherMap API key is configured on the server. "
                "Set OPENWEATHER_API_KEY in your .env file."
            )

    async def _request(self, url: str, params: dict) -> dict:
        self._ensure_api_key()
        params = {**params, "appid": self.api_key, "units": self.units}

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, params=params)
        except httpx.ConnectError as exc:
            raise NetworkError(
                "No internet connection. Please check your network and try again."
            ) from exc
        except httpx.TimeoutException as exc:
            raise NetworkError(
                "The request to the weather service timed out. Please try again."
            ) from exc
        except httpx.HTTPError as exc:
            raise NetworkError(f"A network error occurred: {exc}") from exc

        if response.status_code == 200:
            return response.json()

        if response.status_code in (401, 403):
            raise InvalidAPIKeyError(
                "The configured OpenWeatherMap API key was rejected. Note that "
                "newly created keys can take a few minutes to a couple of hours "
                "to activate."
            )

        if response.status_code == 404:
            raise CityNotFoundError("City not found. Please check the spelling and try again.")

        try:
            message = response.json().get("message", "Unknown error")
        except ValueError:
            message = "Unknown error"
        raise WeatherAPIError(f"Error {response.status_code}: {str(message).capitalize()}")

    # ------------------------------------------------------------------
    # Current weather
    # ------------------------------------------------------------------
    async def get_current_weather(self, city: str) -> dict:
        if not city or not city.strip():
            raise WeatherAPIError("Please enter a city name.")
        data = await self._request(CURRENT_WEATHER_URL, {"q": city.strip()})
        return self._parse_current(data)

    async def get_current_weather_by_coords(self, lat: float, lon: float) -> dict:
        data = await self._request(CURRENT_WEATHER_URL, {"lat": lat, "lon": lon})
        return self._parse_current(data)

    def _parse_current(self, data: dict) -> dict:
        try:
            weather = data["weather"][0]
            main = data["main"]
            wind = data.get("wind", {})
            sys_info = data.get("sys", {})
            tz_offset = data.get("timezone", 0)
            symbols = UNIT_SYMBOLS.get(self.units, UNIT_SYMBOLS["metric"])

            return {
                "city": data.get("name") or "N/A",
                "country": sys_info.get("country", "N/A"),
                "temperature": main.get("temp"),
                "feels_like": main.get("feels_like"),
                "temp_min": main.get("temp_min"),
                "temp_max": main.get("temp_max"),
                "humidity": main.get("humidity"),
                "pressure": main.get("pressure"),
                "wind_speed": wind.get("speed"),
                "wind_deg": wind.get("deg"),
                "visibility": data.get("visibility"),
                "description": weather.get("description", "").title(),
                "main_condition": weather.get("main", ""),
                "icon": weather.get("icon", "01d"),
                "icon_url": icon_url(weather.get("icon", "01d")),
                "sunrise": _format_time(sys_info.get("sunrise"), tz_offset),
                "sunset": _format_time(sys_info.get("sunset"), tz_offset),
                "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                "units": self.units,
                "temp_symbol": symbols["temp"],
                "speed_symbol": symbols["speed"],
            }
        except (KeyError, IndexError, TypeError) as exc:
            raise WeatherAPIError(
                "Unexpected response format received from the weather service."
            ) from exc

    # ------------------------------------------------------------------
    # Forecast (5 day / 3 hour endpoint, aggregated into daily + hourly)
    # ------------------------------------------------------------------
    async def get_forecast(self, city: str) -> dict:
        if not city or not city.strip():
            raise WeatherAPIError("Please enter a city name.")
        data = await self._request(FORECAST_URL, {"q": city.strip()})
        return self._parse_forecast(data)

    async def get_forecast_by_coords(self, lat: float, lon: float) -> dict:
        data = await self._request(FORECAST_URL, {"lat": lat, "lon": lon})
        return self._parse_forecast(data)

    def _parse_forecast(self, data: dict) -> dict:
        try:
            city_info = data.get("city", {})
            entries = data.get("list", [])
            symbols = UNIT_SYMBOLS.get(self.units, UNIT_SYMBOLS["metric"])

            # Hourly: the next ~24 hours (8 entries at 3-hour spacing).
            hourly = []
            for entry in entries[:8]:
                dt = datetime.strptime(entry["dt_txt"], "%Y-%m-%d %H:%M:%S")
                weather = (entry.get("weather") or [{}])[0]
                hourly.append(
                    {
                        "time": dt.strftime("%I %p").lstrip("0"),
                        "icon": weather.get("icon", "01d"),
                        "icon_url": icon_url(weather.get("icon", "01d")),
                        "temperature": entry.get("main", {}).get("temp"),
                        "pop": round((entry.get("pop") or 0) * 100),
                    }
                )

            # Daily: group the 3-hour entries by calendar date, take
            # min/max temp and pick the icon closest to midday.
            by_date = defaultdict(list)
            for entry in entries:
                dt = datetime.strptime(entry["dt_txt"], "%Y-%m-%d %H:%M:%S")
                by_date[dt.date()].append((dt, entry))

            today = datetime.now().date()
            daily = []
            for date, day_entries in list(by_date.items())[:6]:
                temps = [e["main"]["temp"] for _, e in day_entries if "main" in e]
                pops = [e.get("pop") or 0 for _, e in day_entries]
                # Prefer the entry nearest to noon for a representative icon/description.
                noon_entry = min(day_entries, key=lambda pair: abs(pair[0].hour - 12))[1]
                weather = (noon_entry.get("weather") or [{}])[0]

                if date == today:
                    label = "Today"
                else:
                    label = date.strftime("%a")

                daily.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "day_label": label,
                        "icon": weather.get("icon", "01d"),
                        "icon_url": icon_url(weather.get("icon", "01d")),
                        "description": weather.get("description", "").title(),
                        "temp_min": min(temps) if temps else None,
                        "temp_max": max(temps) if temps else None,
                        "pop": round(max(pops) * 100) if pops else None,
                    }
                )

            return {
                "city": city_info.get("name", "N/A"),
                "country": city_info.get("country", "N/A"),
                "units": self.units,
                "temp_symbol": symbols["temp"],
                "daily": daily,
                "hourly": hourly,
            }
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise WeatherAPIError(
                "Unexpected forecast response format received from the weather service."
            ) from exc


# A single shared instance used across the app (FastAPI dependency).
weather_service = WeatherService()
