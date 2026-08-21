"""
api/weather.py
---------------
Route handlers for current weather, forecast, and search-history
endpoints. Business logic lives in `services/weather_service.py` and
`database/database.py` — this module only translates HTTP requests
into calls on those layers and turns their exceptions into proper
HTTP status codes.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database.database import WeatherDatabase, db
from backend.models.weather import (
    CurrentWeatherResponse,
    ForecastResponse,
    HistoryCreate,
    HistoryEntry,
)
from backend.services.weather_service import (
    CityNotFoundError,
    InvalidAPIKeyError,
    NetworkError,
    WeatherAPIError,
    WeatherService,
    weather_service,
)

router = APIRouter(prefix="/api", tags=["Weather"])


def get_weather_service() -> WeatherService:
    return weather_service


def get_database() -> WeatherDatabase:
    return db


def _handle_weather_error(exc: Exception) -> None:
    """Translate service-layer exceptions into HTTPException with the right status code."""
    if isinstance(exc, CityNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, InvalidAPIKeyError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if isinstance(exc, NetworkError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, WeatherAPIError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail="An unexpected server error occurred.") from exc


def _save_to_history(database: WeatherDatabase, weather: dict) -> None:
    try:
        database.add_search(
            city=weather.get("city", "N/A"),
            country=weather.get("country"),
            temperature=weather.get("temperature"),
            description=weather.get("description"),
        )
    except Exception:
        # History logging is best-effort and must never break a weather lookup.
        pass


@router.get(
    "/weather",
    response_model=CurrentWeatherResponse,
    summary="Get current weather by city name or coordinates",
)
async def get_weather(
    city: Optional[str] = Query(None, description="City name, e.g. 'Nagpur'"),
    lat: Optional[float] = Query(None, description="Latitude, for geolocation lookups"),
    lon: Optional[float] = Query(None, description="Longitude, for geolocation lookups"),
    service: WeatherService = Depends(get_weather_service),
    database: WeatherDatabase = Depends(get_database),
) -> CurrentWeatherResponse:
    if lat is not None and lon is not None:
        try:
            weather = await service.get_current_weather_by_coords(lat, lon)
        except Exception as exc:
            _handle_weather_error(exc)
            raise
    elif city:
        try:
            weather = await service.get_current_weather(city)
        except Exception as exc:
            _handle_weather_error(exc)
            raise
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a 'city' name or both 'lat' and 'lon' query parameters.",
        )

    _save_to_history(database, weather)
    return CurrentWeatherResponse(**weather)


@router.get(
    "/weather/{city}",
    response_model=CurrentWeatherResponse,
    summary="Get current weather for a named city",
)
async def get_weather_by_city(
    city: str,
    service: WeatherService = Depends(get_weather_service),
    database: WeatherDatabase = Depends(get_database),
) -> CurrentWeatherResponse:
    try:
        weather = await service.get_current_weather(city)
    except Exception as exc:
        _handle_weather_error(exc)
        raise

    _save_to_history(database, weather)
    return CurrentWeatherResponse(**weather)


@router.get(
    "/forecast/{city}",
    response_model=ForecastResponse,
    summary="Get 5-day / hourly forecast for a named city",
)
async def get_forecast(
    city: str,
    service: WeatherService = Depends(get_weather_service),
) -> ForecastResponse:
    try:
        forecast = await service.get_forecast(city)
    except Exception as exc:
        _handle_weather_error(exc)
        raise
    return ForecastResponse(**forecast)


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Get 5-day / hourly forecast by coordinates",
)
async def get_forecast_by_coords(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    service: WeatherService = Depends(get_weather_service),
) -> ForecastResponse:
    try:
        forecast = await service.get_forecast_by_coords(lat, lon)
    except Exception as exc:
        _handle_weather_error(exc)
        raise
    return ForecastResponse(**forecast)


# ---------------------------------------------------------------------------
# Search history — preserves the SQLite history feature from the desktop app
# ---------------------------------------------------------------------------
@router.get("/history", response_model=List[HistoryEntry], summary="List recent searches")
async def get_history(
    limit: int = Query(50, ge=1, le=200),
    database: WeatherDatabase = Depends(get_database),
) -> List[HistoryEntry]:
    try:
        rows = database.get_history(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read search history: {exc}") from exc
    return [HistoryEntry(**row) for row in rows]


@router.post("/history", response_model=HistoryEntry, status_code=201, summary="Add a search-history record")
async def add_history(
    entry: HistoryCreate,
    database: WeatherDatabase = Depends(get_database),
) -> HistoryEntry:
    try:
        new_id = database.add_search(
            city=entry.city,
            country=entry.country,
            temperature=entry.temperature,
            description=entry.description,
        )
        rows = database.get_history(limit=1)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not save search history: {exc}") from exc
    if not rows or rows[0]["id"] != new_id:
        # Fallback in case the newest row was pruned (shouldn't normally happen).
        return HistoryEntry(id=new_id, **entry.model_dump())
    return HistoryEntry(**rows[0])


@router.delete("/history/{record_id}", status_code=204, summary="Delete a single search-history record")
async def delete_history_entry(
    record_id: int,
    database: WeatherDatabase = Depends(get_database),
) -> None:
    try:
        deleted = database.delete_entry(record_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not delete history record: {exc}") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"History record {record_id} not found.")


@router.delete("/history", status_code=204, summary="Clear all search history")
async def clear_history(
    database: WeatherDatabase = Depends(get_database),
) -> None:
    try:
        database.clear_history()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not clear search history: {exc}") from exc
