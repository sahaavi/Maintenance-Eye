"""
Maintenance-Eye Backend
FastAPI application entry point.
Initializes the ADK Runner for bidi-streaming Live API sessions.
"""

import json
import logging
import time

from agent.maintenance_agent import chat_agent, maintenance_agent
from api.routes import router as api_router
from api.websocket import router as ws_router
from config import settings
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from middleware.security import SecurityHeadersMiddleware
from services.auth_service import require_auth_http

# ============================================================================
# Logging — JSON in production, plaintext locally
# ============================================================================


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for Cloud Logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
            "logger": record.name,
            "module": record.module,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


_handler = logging.StreamHandler()
if settings.APP_ENV == "production":
    _handler.setFormatter(JSONFormatter())
else:
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    handlers=[_handler],
)
logger = logging.getLogger("maintenance-eye")

# Startup timestamp for uptime tracking
_startup_time = time.monotonic()

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

# Chat runner — uses text model (gemini-2.5-flash) for text chat sessions
CHAT_APP_NAME = "maintenance-eye-chat"
chat_session_service = InMemorySessionService()
chat_runner = Runner(
    app_name=CHAT_APP_NAME,
    agent=chat_agent,
    session_service=chat_session_service,
)

logger.info(f"Initialized ADK Runner: app={APP_NAME}, agent={maintenance_agent.name}")
logger.info(
    f"Initialized Chat Runner: app={CHAT_APP_NAME}, agent={chat_agent.name}, model={chat_agent.model}"
)

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Maintenance-Eye",
    description="AI Co-Pilot for Physical Infrastructure Maintenance Operations",
    version="1.0.0",
)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

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

from pathlib import Path

# API routes
api_dependencies = [Depends(require_auth_http)] if settings.auth_enabled else []
app.include_router(api_router, prefix="/api", dependencies=api_dependencies)
app.include_router(ws_router)


@app.on_event("startup")
async def startup_auto_seed():
    """Log active EAM backend and auto-seed Firestore if collections are empty."""
    from services.firestore_eam import FirestoreEAM, get_eam_service
    from services.seeder import auto_seed_firestore

    eam = get_eam_service()
    eam_type = type(eam).__name__
    logger.info(f"EAM backend active: {eam_type}")

    if not isinstance(eam, FirestoreEAM):
        logger.info("Using JsonEAM — seed data loaded from seed_data.json in-memory")
        return

    await auto_seed_firestore(eam)


@app.on_event("shutdown")
async def shutdown_notify_clients():
    """Notify active WebSocket clients before shutdown (Cloud Run SIGTERM)."""
    from api.websocket import active_connections

    for ws in list(active_connections):
        try:
            await ws.send_json(
                {
                    "type": "status",
                    "data": "Server is restarting. Please reconnect.",
                }
            )
            await ws.close(code=1012)  # 1012 = Service Restart
        except Exception:
            pass
    logger.info("Graceful shutdown: notified active WebSocket clients")


@app.get("/health")
async def health_check():
    """Liveness probe — returns uptime, version, active session count."""
    from api.websocket import active_connections

    uptime_seconds = round(time.monotonic() - _startup_time, 1)
    return {
        "status": "healthy",
        "service": "maintenance-eye",
        "version": "1.0.0",
        "agent": maintenance_agent.name,
        "model": settings.GEMINI_LIVE_MODEL,
        "uptime_seconds": uptime_seconds,
        "active_sessions": len(active_connections),
    }


@app.get("/readiness")
async def readiness_check():
    """Readiness probe — validates EAM backend connectivity."""
    from services.firestore_eam import get_eam_service

    eam = get_eam_service()
    eam_type = type(eam).__name__

    try:
        # Probe: fetch a single asset to verify connectivity
        assets = await eam.get_assets(limit=1)
        reachable = True
    except Exception as e:
        reachable = False
        logger.warning(f"Readiness probe failed: {e}")

    status_code = 200 if reachable else 503
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if reachable else "not_ready",
            "eam_backend": eam_type,
            "reachable": reachable,
        },
    )


# Serve frontend static files (must be AFTER all other routes)
# In Docker: /app/frontend/  |  Local dev: ../frontend/
_frontend_dir = Path(__file__).parent / "frontend"
if not _frontend_dir.exists():
    _frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
    logger.info(f"Serving frontend from: {_frontend_dir}")
else:
    logger.warning("Frontend directory not found, static files not served")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=settings.APP_ENV == "development",
    )
