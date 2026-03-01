"""
REST API Routes
Provides endpoints for inspection history, reports, and asset lookup.
Falls back to data/seed_data.json when Firestore is unavailable.
"""

import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import Optional

from config import settings
from models.schemas import WorkOrderStatus
from services.firestore_eam import get_eam_service

router = APIRouter()
logger = logging.getLogger("maintenance-eye.routes")


def _firestore_available() -> bool:
    """Check if Firestore is likely configured (emulator or real GCP credentials)."""
    return bool(settings.FIRESTORE_EMULATOR_HOST) or settings.APP_ENV == "production"

# ---- JSON fallback --------------------------------------------------------

_json_cache: dict = {}
_seed_json_path: Optional[Path] = None


def _resolve_seed_json_path() -> Optional[Path]:
    """Resolve seed_data.json across local and container layouts."""
    global _seed_json_path
    if _seed_json_path is not None:
        return _seed_json_path

    routes_file = Path(__file__).resolve()
    candidates = [
        # Local dev: <repo>/backend/api/routes.py -> <repo>/data/seed_data.json
        routes_file.parent.parent.parent / "data" / "seed_data.json",
        # Container: /app/api/routes.py -> /app/data/seed_data.json
        routes_file.parent.parent / "data" / "seed_data.json",
        # Explicit Cloud Run container layout
        Path("/app/data/seed_data.json"),
        # Fallback to current working directory
        Path.cwd() / "data" / "seed_data.json",
    ]

    for candidate in candidates:
        if candidate.exists():
            _seed_json_path = candidate
            return _seed_json_path

    return None

def _load_json() -> dict:
    """Load seed_data.json once and cache it."""
    if _json_cache:
        return _json_cache

    json_path = _resolve_seed_json_path()
    if json_path:
        with open(json_path, "r", encoding="utf-8") as f:
            _json_cache.update(json.load(f))
        logger.info(f"Loaded fallback JSON from {json_path}")
    else:
        logger.warning("seed_data.json not found in known locations for fallback")
    return _json_cache


@router.get("/assets/{asset_id}")
async def get_asset(asset_id: str):
    """Get a specific asset by ID."""
    if _firestore_available():
        try:
            eam = get_eam_service()
            asset = await eam.get_asset(asset_id)
            if not asset:
                raise HTTPException(status_code=404, detail="Asset not found")
            return asset
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Firestore unavailable, using JSON fallback: {e}")

    data = _load_json()
    for a in data.get("assets", []):
        if a.get("asset_id") == asset_id:
            return a
    raise HTTPException(status_code=404, detail="Asset not found")


@router.get("/assets")
async def search_assets(
    q: str = "",
    department: str = "",
    station: str = "",
    asset_type: str = "",
):
    """Search assets by query, department, station, or type."""
    if _firestore_available():
        try:
            eam = get_eam_service()
            return await eam.search_assets(
                query=q, department=department, station=station, asset_type=asset_type
            )
        except Exception as e:
            logger.debug(f"Using JSON fallback for assets: {e}")

    data = _load_json()
    assets = data.get("assets", [])
    if q:
        ql = q.lower()
        assets = [a for a in assets if
                  ql in a.get("name", "").lower() or
                  ql in a.get("asset_id", "").lower() or
                  ql in str(a.get("location", {}).get("station", "")).lower()]
    if department:
        assets = [a for a in assets if a.get("department") == department]
    if asset_type:
        assets = [a for a in assets if a.get("type") == asset_type]
    return assets


@router.get("/work-orders")
async def get_work_orders(
    asset_id: str = "",
    status: Optional[str] = None,
    q: str = "",
    priority: str = "",
    department: str = "",
    location: str = "",
):
    """Get work orders with optional full-text search and filters."""
    wo_status = None
    if status:
        try:
            wo_status = WorkOrderStatus(status.lower())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc

    # Use search_work_orders when advanced filters are provided
    has_advanced = q or priority or department or location
    try:
        eam = get_eam_service()
        if has_advanced:
            return await eam.search_work_orders(
                q=q, priority=priority, department=department,
                status=wo_status, location=location,
            )
        return await eam.get_work_orders(asset_id=asset_id, status=wo_status)
    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"Using JSON fallback for work-orders: {e}")

    # JSON fallback for basic filtering
    data = _load_json()
    orders = data.get("work_orders", [])
    if asset_id:
        orders = [o for o in orders if o.get("asset_id") == asset_id]
    if status:
        status_value = status.lower()
        orders = [o for o in orders if str(o.get("status", "")).lower() == status_value]
    return orders


@router.get("/locations")
async def get_locations():
    """Get unique stations derived from assets."""
    try:
        eam = get_eam_service()
        return await eam.get_locations()
    except Exception as e:
        logger.debug(f"Using JSON fallback for locations: {e}")

    # JSON fallback
    data = _load_json()
    stations: dict[str, dict] = {}
    for a in data.get("assets", []):
        loc = a.get("location", {})
        station = loc.get("station", "")
        if not station:
            continue
        if station not in stations:
            stations[station] = {
                "station": station,
                "station_code": loc.get("station_code", ""),
                "zone": loc.get("zone", ""),
                "asset_count": 0,
            }
        stations[station]["asset_count"] += 1
    return sorted(stations.values(), key=lambda s: s["station"])


@router.get("/inspections/{asset_id}")
async def get_inspection_history(asset_id: str, limit: int = 10):
    """Get inspection history for an asset."""
    if _firestore_available():
        try:
            eam = get_eam_service()
            return await eam.get_inspection_history(asset_id=asset_id, limit=limit)
        except Exception as e:
            logger.debug(f"Using JSON fallback for inspections: {e}")

    data = _load_json()
    inspections = data.get("inspections", [])
    return [i for i in inspections if i.get("asset_id") == asset_id][:limit]


@router.get("/knowledge")
async def search_knowledge(q: str = "", asset_type: str = "", department: str = ""):
    """Search the maintenance knowledge base."""
    if _firestore_available():
        try:
            eam = get_eam_service()
            return await eam.search_knowledge_base(
                query=q or "maintenance", asset_type=asset_type, department=department
            )
        except Exception as e:
            logger.debug(f"Using JSON fallback for knowledge: {e}")

    data = _load_json()
    kb = data.get("knowledge_base", [])
    if q:
        ql = q.lower()
        kb = [k for k in kb if
              ql in k.get("title", "").lower() or
              ql in k.get("content", "").lower() or
              any(ql in t.lower() for t in k.get("tags", []))]
    if department:
        kb = [k for k in kb if k.get("department") == department]
    if asset_type:
        kb = [k for k in kb if asset_type in k.get("asset_types", [])]
    return kb


@router.get("/eam-codes")
async def get_eam_codes(code_type: str = "", department: str = "", asset_type: str = ""):
    """Get EAM classification codes."""
    if _firestore_available():
        try:
            eam = get_eam_service()
            return await eam.get_eam_codes(
                code_type=code_type, department=department, asset_type=asset_type
            )
        except Exception as e:
            logger.debug(f"Using JSON fallback for eam-codes: {e}")

    data = _load_json()
    codes = data.get("eam_codes", [])
    if code_type:
        codes = [c for c in codes if c.get("code_type") == code_type]
    if department:
        codes = [c for c in codes if c.get("department") == department]
    if asset_type:
        codes = [c for c in codes if asset_type in c.get("asset_types", [])]
    return codes


# ---------------------------------------------------------------------------
# Confirmation endpoints (human-in-the-loop)
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/pending")
async def get_pending_actions(session_id: str):
    """Get pending actions for a session that need technician confirmation."""
    from services.confirmation_manager import get_confirmation_manager
    mgr = get_confirmation_manager(session_id)
    pending = mgr.get_pending()
    return {
        "session_id": session_id,
        "pending_count": len(pending),
        "actions": [a.model_dump() for a in pending],
    }


@router.post("/sessions/{session_id}/confirm/{action_id}")
async def confirm_action(session_id: str, action_id: str, notes: str = ""):
    """Technician confirms a proposed action."""
    from services.confirmation_manager import get_confirmation_manager
    mgr = get_confirmation_manager(session_id)
    action = mgr.confirm(action_id, notes)
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    return {"status": "confirmed", "action": action.model_dump()}


@router.post("/sessions/{session_id}/reject/{action_id}")
async def reject_action(session_id: str, action_id: str, notes: str = ""):
    """Technician rejects a proposed action."""
    from services.confirmation_manager import get_confirmation_manager
    mgr = get_confirmation_manager(session_id)
    action = mgr.reject(action_id, notes)
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    return {"status": "rejected", "action": action.model_dump()}


@router.post("/sessions/{session_id}/correct/{action_id}")
async def correct_action(session_id: str, action_id: str, corrections: dict = {}, notes: str = ""):
    """Technician corrects a proposed action with updated values."""
    from services.confirmation_manager import get_confirmation_manager
    mgr = get_confirmation_manager(session_id)
    action = mgr.correct(action_id, corrections, notes)
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    return {"status": "corrected", "action": action.model_dump()}


@router.get("/sessions/{session_id}/stats")
async def get_session_stats(session_id: str):
    """Get confirmation workflow stats for a session."""
    from services.confirmation_manager import get_confirmation_manager
    mgr = get_confirmation_manager(session_id)
    return {"session_id": session_id, **mgr.get_stats()}


# ---------------------------------------------------------------------------
# Report generation endpoints
# ---------------------------------------------------------------------------

@router.post("/reports/generate")
async def generate_report_html(
    asset_id: str,
    inspector_name: str = "Field Technician",
    findings_summary: str = "",
    overall_condition: str = "requires_attention",
):
    """Generate an inspection report and return HTML."""
    from agent.tools.report_generator import generate_report
    from services.report_renderer import render_report_html
    from fastapi.responses import HTMLResponse

    result = await generate_report(
        asset_id=asset_id,
        inspector_name=inspector_name,
        findings_summary=findings_summary,
        overall_condition=overall_condition,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Report generation failed"))

    html = render_report_html(result["report"])
    return HTMLResponse(content=html)


@router.post("/reports/generate/pdf")
async def generate_report_pdf(
    asset_id: str,
    inspector_name: str = "Field Technician",
    findings_summary: str = "",
    overall_condition: str = "requires_attention",
):
    """Generate an inspection report and return downloadable PDF."""
    from agent.tools.report_generator import generate_report
    from services.report_renderer import render_report_pdf
    from fastapi.responses import Response

    result = await generate_report(
        asset_id=asset_id,
        inspector_name=inspector_name,
        findings_summary=findings_summary,
        overall_condition=overall_condition,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Report generation failed"))

    pdf_bytes = render_report_pdf(result["report"])
    report_id = result.get("report_id", "report")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{report_id}.pdf"',
        },
    )

