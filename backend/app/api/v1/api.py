"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.routers import auth, documents, export, generation, jobs, stripe, tokens, users, websocket

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(auth.router)  # Authentication endpoints
api_router.include_router(users.router)  # User management endpoints
api_router.include_router(documents.router)
api_router.include_router(generation.router)  # Legacy generation endpoints
api_router.include_router(jobs.router)  # New ARQ-based job queue endpoints
api_router.include_router(stripe.router)  # Stripe payment integration
api_router.include_router(tokens.router)  # Token balance and transaction endpoints
api_router.include_router(websocket.router)  # WebSocket for real-time progress
api_router.include_router(export.router)  # Map export endpoints
