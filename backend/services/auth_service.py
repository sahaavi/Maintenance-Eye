"""
Firebase Auth Service
Token verification helpers for HTTP and WebSocket endpoints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import firebase_admin
from config import settings
from fastapi import HTTPException, Request, WebSocket, status
from firebase_admin import auth, credentials

logger = logging.getLogger("maintenance-eye.auth")


@dataclass
class AuthContext:
    uid: str
    email: str = ""
    claims: dict | None = None


def _initialize_firebase() -> bool:
    """Initialize firebase-admin once, using ambient credentials."""
    if not settings.auth_enabled:
        return False
    if firebase_admin._apps:
        return True
    try:
        project_id = settings.FIREBASE_PROJECT_ID or settings.GCP_PROJECT_ID
        firebase_admin.initialize_app(
            credentials.ApplicationDefault(),
            {"projectId": project_id},
        )
        logger.info(f"Initialized Firebase Admin SDK (project={project_id})")
        return True
    except Exception as exc:
        logger.error(f"Firebase Admin initialization failed: {exc}")
        return False


def _extract_bearer_token(authorization_header: str) -> str | None:
    if not authorization_header:
        return None
    if not authorization_header.lower().startswith("bearer "):
        return None
    token = authorization_header[7:].strip()
    return token or None


def _verify_token(token: str) -> AuthContext:
    decoded = auth.verify_id_token(token)
    return AuthContext(
        uid=decoded.get("uid", ""),
        email=decoded.get("email", "") or "",
        claims=decoded,
    )


def _development_auth_context() -> AuthContext:
    return AuthContext(uid="dev-user", email="dev@example.com", claims={})


async def require_auth_http(request: Request) -> AuthContext:
    """FastAPI dependency for authenticated REST endpoints."""
    if not settings.auth_enabled:
        return _development_auth_context()
    if not _initialize_firebase():
        raise HTTPException(status_code=500, detail="Authentication service unavailable")

    token = _extract_bearer_token(request.headers.get("authorization", ""))
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    try:
        return _verify_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth token",
        )


async def require_auth_websocket(websocket: WebSocket) -> AuthContext | None:
    """
    Validate auth for WebSocket sessions.
    Token is accepted via Authorization header or ?token= query param.
    """
    if not settings.auth_enabled:
        return _development_auth_context()
    if not _initialize_firebase():
        await websocket.close(code=1011, reason="Authentication service unavailable")
        return None

    token = _extract_bearer_token(websocket.headers.get("authorization", ""))
    if not token:
        token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="Missing auth token")
        return None

    try:
        return _verify_token(token)
    except Exception:
        await websocket.close(code=4401, reason="Invalid auth token")
        return None
