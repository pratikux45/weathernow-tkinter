"""
models/weather.py
------------------
Pydantic models describing the shape of every request/response body
the API accepts or returns. Keeping these separate from the route
handlers gives FastAPI's automatic /docs and /redoc pages accurate,
self-documenting schemas for free.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class CurrentWeatherResponse(BaseModel):
    city: str
    country: str = "N/A"
    temperature: Optional[float] = None
    feels_like: Optional[float] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    humidity: Optional[int] = None
    pressure: Optional[int] = None
    wind_speed: Optional[float] = None
    wind_deg: Optional[int] = None
    visibility: Optional[int] = None
    description: str = ""
    main_condition: str = ""
    icon: str = "01d"
    icon_url: str = ""
    sunrise: Optional[str] = None
    sunset: Optional[str] = None
    last_updated: str
    units: str
    temp_symbol: str
    speed_symbol: str


class DailyForecastItem(BaseModel):
    date: str
    day_label: str
    icon: str
    icon_url: str
    description: str
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    pop: Optional[int] = Field(None, description="Chance of precipitation, percent")


class HourlyForecastItem(BaseModel):
    time: str
    icon: str
    icon_url: str
    temperature: Optional[float] = None
    pop: Optional[int] = Field(None, description="Chance of precipitation, percent")


class ForecastResponse(BaseModel):
    city: str
    country: str = "N/A"
    units: str
    temp_symbol: str
    daily: List[DailyForecastItem]
    hourly: List[HourlyForecastItem]


class HistoryEntry(BaseModel):
    id: int
    city: str
    country: Optional[str] = None
    temperature: Optional[float] = None
    description: Optional[str] = None
    searched_at: str


class HistoryCreate(BaseModel):
    city: str
    country: Optional[str] = None
    temperature: Optional[float] = None
    description: Optional[str] = None


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str
