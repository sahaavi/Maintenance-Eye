"""
Maintenance-Eye Backend
FastAPI application entry point.
Initializes the ADK Runner for bidi-streaming Live API sessions.
"""

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from config import settings
from api.routes import router as api_router
from api.websocket import router as ws_router
from agent.maintenance_agent import maintenance_agent
from services.auth_service import require_auth_http

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("maintenance-eye")

# ============================================================================
# ADK Application Initialization (once at startup)
# ============================================================================

APP_NAME = "maintenance-eye"

# Session service — stores conversation history across streaming sessions
session_service = InMemorySessionService()

# Runner — orchestrates agent + session + Live API connection
runner = Runner(
    app_name=APP_NAME,
    agent=maintenance_agent,
    session_service=session_service,
)

logger.info(f"Initialized ADK Runner: app={APP_NAME}, agent={maintenance_agent.name}")

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Maintenance-Eye",
    description="AI Co-Pilot for Physical Infrastructure Maintenance Operations",
    version="1.0.0",
)

# CORS
cors_origins = settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS origins configured: {cors_origins or 'none'}")

import os
from pathlib import Path

# API routes
api_dependencies = [Depends(require_auth_http)] if settings.auth_enabled else []
app.include_router(api_router, prefix="/api", dependencies=api_dependencies)
app.include_router(ws_router)


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {
        "status": "healthy",
        "service": "maintenance-eye",
        "version": "1.0.0",
        "agent": maintenance_agent.name,
        "model": settings.GEMINI_LIVE_MODEL,
    }


# Serve frontend static files (must be AFTER all other routes)
# In Docker: /app/frontend/  |  Local dev: ../frontend/
_frontend_dir = Path(__file__).parent / "frontend"
if not _frontend_dir.exists():
    _frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
    logger.info(f"Serving frontend from: {_frontend_dir}")
else:
    logger.warning(f"Frontend directory not found, static files not served")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=settings.APP_ENV == "development",
    )
