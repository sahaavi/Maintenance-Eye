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
from agent.maintenance_agent import maintenance_agent, chat_agent
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

# Chat runner — uses text model (gemini-2.5-flash) for text chat sessions
CHAT_APP_NAME = "maintenance-eye-chat"
chat_session_service = InMemorySessionService()
chat_runner = Runner(
    app_name=CHAT_APP_NAME,
    agent=chat_agent,
    session_service=chat_session_service,
)

logger.info(f"Initialized ADK Runner: app={APP_NAME}, agent={maintenance_agent.name}")
logger.info(f"Initialized Chat Runner: app={CHAT_APP_NAME}, agent={chat_agent.name}, model={chat_agent.model}")

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


@app.on_event("startup")
async def startup_auto_seed():
    """Log active EAM backend and auto-seed Firestore if collections are empty."""
    from services.firestore_eam import get_eam_service, FirestoreEAM

    eam = get_eam_service()
    eam_type = type(eam).__name__
    logger.info(f"EAM backend active: {eam_type}")

    if not isinstance(eam, FirestoreEAM):
        logger.info("Using JsonEAM — seed data loaded from seed_data.json in-memory")
        return

    # Check if Firestore has data; if empty, seed from seed_data.json
    try:
        existing_assets = await eam.search_assets()
        if len(existing_assets) > 0:
            logger.info(f"Firestore has {len(existing_assets)} assets — skipping seed")
            return

        logger.warning("Firestore collections are empty — auto-seeding from seed_data.json")
        import json

        seed_path = Path(__file__).parent / "data" / "seed_data.json"
        if not seed_path.exists():
            seed_path = Path(__file__).parent.parent / "data" / "seed_data.json"
        if not seed_path.exists():
            logger.error("seed_data.json not found — cannot auto-seed Firestore")
            return

        with open(seed_path, "r") as f:
            seed = json.load(f)

        batch = eam.db.batch()
        count = 0
        for collection_name, items in seed.items():
            if not isinstance(items, list):
                continue
            id_fields = {
                "assets": "asset_id", "work_orders": "wo_id",
                "eam_codes": "code", "inspections": "inspection_id",
                "knowledge_base": "doc_id",
            }
            id_field = id_fields.get(collection_name)
            for item in items:
                doc_id = item.get(id_field, str(count)) if id_field else str(count)
                ref = eam.db.collection(collection_name).document(doc_id)
                batch.set(ref, item)
                count += 1
                if count % 400 == 0:
                    await batch.commit()
                    batch = eam.db.batch()

        if count % 400 != 0:
            await batch.commit()
        logger.info(f"Auto-seeded Firestore with {count} documents across {len(seed)} collections")

    except Exception as e:
        logger.warning(f"Auto-seed check failed (non-fatal): {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    from services.firestore_eam import get_eam_service
    return {
        "status": "healthy",
        "service": "maintenance-eye",
        "version": "1.0.0",
        "agent": maintenance_agent.name,
        "model": settings.GEMINI_LIVE_MODEL,
        "eam_backend": type(get_eam_service()).__name__,
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
