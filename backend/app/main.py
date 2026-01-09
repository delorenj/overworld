"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Overworld API",
    description="AI-powered project mapping platform",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "overworld-backend"}


@app.get("/api/v1/status")
async def status():
    """API status endpoint."""
    return {
        "status": "running",
        "version": "0.1.0",
        "environment": "development",
    }
