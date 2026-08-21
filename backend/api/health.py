"""
api/health.py
-------------
Simple liveness endpoint, useful for Render (and any other host's)
deployment health checks.
"""
from fastapi import APIRouter

from backend.models.weather import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy")
