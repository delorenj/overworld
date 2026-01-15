"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.routers import documents, generation

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(documents.router)
api_router.include_router(generation.router)
